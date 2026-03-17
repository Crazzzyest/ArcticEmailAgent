import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List, Optional

from pypdf import PdfReader

from app.models import Attachment
from app.service import process_email_thread_from_raw


@dataclass
class EmailExampleResult:
    index: int
    subject: str
    raw_text: str
    category: str
    confidence: float
    complete: Optional[bool]
    missing: List[str]
    desired_missing: List[str]
    action: str
    reply_draft: Optional[str]


def extract_emails_from_pdf(path: Path) -> List[str]:
    """
    Leser all tekst fra PDF og splitter på '---' som separator mellom eksempler.
    Du kan justere separatoren etter hvordan eposter.pdf faktisk er strukturert.
    """
    reader = PdfReader(str(path))
    full_text_parts: List[str] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        full_text_parts.append(text)
    full_text = "\n".join(full_text_parts)

    # Anta at '---' på egen linje skiller eksempler
    examples: List[str] = []
    current: List[str] = []
    for line in full_text.splitlines():
        if line.strip() == "---":
            if current:
                examples.append("\n".join(current).strip())
                current = []
        else:
            current.append(line)
    if current:
        examples.append("\n".join(current).strip())

    # Filtrer ut tomme
    return [e for e in examples if e]


async def run_pdf_test(
    pdf_path: Path,
    limit: Optional[int] = None,
    output_path: Optional[Path] = None,
) -> None:
    emails = extract_emails_from_pdf(pdf_path)
    if limit is not None:
        emails = emails[:limit]

    print(f"Fant {len(emails)} epost-eksempler i {pdf_path}")

    results: List[EmailExampleResult] = []

    for idx, raw in enumerate(emails, start=1):
        lines = [l for l in raw.splitlines() if l.strip()]
        subject = lines[0][:120] if lines else f"Test-epost #{idx}"
        body = "\n".join(lines[1:]) if len(lines) > 1 else raw

        print(f"\n=== Eksempel #{idx} ===")
        print(f"Subject: {subject}")

        # Ingen faktiske vedlegg i PDF-scenariet
        attachments: List[Attachment] = []

        try:
            response = await process_email_thread_from_raw(
                subject=subject,
                body=body,
                attachments=attachments,
            )
        except Exception as exc:  # pragma: no cover - ren beskyttelse av testrun
            print(f"FEIL under prosessering: {exc}")
            continue

        requirements = response.requirements
        complete = requirements.complete if requirements is not None else None
        missing = requirements.missing if requirements is not None else []
        desired_missing = (
            requirements.desired_missing if requirements is not None else []
        )

        print(f"Kategori: {response.category} (confidence={response.confidence:.2f})")
        print(f"Complete: {complete}  Missing: {missing}  Desired: {desired_missing}")
        if response.reply_draft:
            preview = "\n".join(response.reply_draft.splitlines()[:6])
            print("Svarutkast (utdrag):")
            print(preview)
        else:
            print("Ingen svarutkast (action=", response.action, ")")

        results.append(
            EmailExampleResult(
                index=idx,
                subject=subject,
                raw_text=raw,
                category=response.category.value,
                confidence=response.confidence,
                complete=complete,
                missing=missing,
                desired_missing=desired_missing,
                action=response.action,
                reply_draft=response.reply_draft,
            )
        )

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as f:
            json.dump([asdict(r) for r in results], f, ensure_ascii=False, indent=2)
        print(f"\nSkrev resultater til {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Kjør epost-testpipeline mot en PDF med eksempler."
    )
    parser.add_argument(
        "pdf",
        type=str,
        help="Sti til PDF med test-eposter (f.eks. eposter.pdf)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maks antall eksempler å kjøre (default: alle).",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="tests/output/pdf_results.json",
        help="Sti til JSON-fil for resultater.",
    )

    args = parser.parse_args()
    pdf_path = Path(args.pdf)
    output_path = Path(args.output) if args.output else None

    import anyio

    anyio.run(
        run_pdf_test,
        pdf_path,
        args.limit,
        output_path,
    )


if __name__ == "__main__":
    main()

