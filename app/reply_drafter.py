from .business_rules import check_service_requirements, check_trade_in_requirements
from .llm_client import generate_reply
from .models import (
    Attachment,
    Category,
    ProcessThreadResponse,
    TradeInInfo,
    ServiceInfo,
    RequirementsResult,
)


def _build_system_context() -> str:
    return (
        "Du er en kundebehandler hos en norsk maskinforhandler. "
        "Du skriver korte, høflige svar på norsk til kunder.\n\n"
    )


def _build_prompt_for_trade_in(
    text: str, requirements: RequirementsResult
) -> str:
    if requirements.complete:
        return (
            _build_system_context()
            + "Kunden har sendt en henvendelse om innbytte.\n\n"
            "Epostinnhold:\n"
            f"{text}\n\n"
            "Lag et kort og hyggelig svar på norsk der du:\n"
            "- Bekrefter at vi har fått nødvendig informasjon for å regne på innbytte.\n"
            "- Forteller kort om veien videre, f.eks. at vi kommer tilbake med et konkret tilbud.\n"
            "- Ikke finn på tall eller konkrete priser.\n"
        )
    else:
        missing = ", ".join(requirements.missing)
        desired = ", ".join(requirements.desired_missing)
        return (
            _build_system_context()
            + "Kunden ønsker innbytte, men informasjonen er ikke komplett.\n\n"
            "Epostinnhold:\n"
            f"{text}\n\n"
            "Lag et kort, høflig svar på norsk der du:\n"
            f"- Forklarer at vi trenger mer informasjon før vi kan regne innbytte.\n"
            f"- Ber spesifikt om følgende manglende punkter: {missing or 'ingen'}.\n"
            f"- Dersom det passer naturlig kan du også spørre etter ønsket ekstra info: {desired or 'ingen'}.\n"
            "- Ikke finn på tall eller konkrete priser.\n"
        )


def _build_prompt_for_service(
    text: str, requirements: RequirementsResult
) -> str:
    if requirements.complete:
        return (
            _build_system_context()
            + "Kunden ønsker service/reparasjon/annet verkstedbesøk.\n\n"
            "Epostinnhold:\n"
            f"{text}\n\n"
            "Lag et kort og hyggelig svar på norsk der du:\n"
            "- Bekrefter hva kunden ønsker å gjøre.\n"
            "- Bekrefter at vi har tilstrekkelig informasjon til å gi tilbud eller foreslå time.\n"
            "- Forklarer kort hva som skjer videre (for eksempel at vi kontakter kunden med tidspunkt/bekreftelse).\n"
        )
    else:
        missing = ", ".join(requirements.missing)
        desired = ", ".join(requirements.desired_missing)
        return (
            _build_system_context()
            + "Kunden ønsker service/reparasjon/annet, men informasjonen er ikke komplett.\n\n"
            "Epostinnhold:\n"
            f"{text}\n\n"
            "Lag et kort, høflig svar på norsk der du:\n"
            f"- Forklarer at vi trenger mer informasjon før vi kan gi et godt tilbud eller booke time.\n"
            f"- Ber spesifikt om følgende manglende punkter: {missing or 'ingen'}.\n"
            f"- Dersom det passer naturlig kan du også spørre etter ønsket ekstra info: {desired or 'ingen'}.\n"
        )


async def draft_reply_for_category(
    category: Category,
    text: str,
    attachments: list[Attachment],
) -> ProcessThreadResponse:
    """
    Hovedinngang for å lage svarutkast.
    """
    if category == Category.OFFER_ONLY:
        return ProcessThreadResponse(
            category=category,
            confidence=0.9,
            trade_in_info=None,
            service_info=None,
            requirements=None,
            reply_draft=None,
            action="forward_to_human",
        )

    if category == Category.TRADE_IN:
        requirements = check_trade_in_requirements(text, attachments)
        prompt = _build_prompt_for_trade_in(text, requirements)
        reply = await generate_reply(prompt)
        trade_info = TradeInInfo(
            has_pictures=any(a.content_type and a.content_type.startswith("image/") for a in attachments),
        )
        return ProcessThreadResponse(
            category=category,
            confidence=0.9,
            trade_in_info=trade_info,
            service_info=None,
            requirements=requirements,
            reply_draft=reply,
            action="create_draft_reply",
        )

    if category == Category.SERVICE:
        requirements = check_service_requirements(text, attachments)
        prompt = _build_prompt_for_service(text, requirements)
        reply = await generate_reply(prompt)
        service_info = ServiceInfo()
        return ProcessThreadResponse(
            category=category,
            confidence=0.9,
            trade_in_info=None,
            service_info=service_info,
            requirements=requirements,
            reply_draft=reply,
            action="create_draft_reply",
        )

    return ProcessThreadResponse(
        category=category,
        confidence=0.5,
        trade_in_info=None,
        service_info=None,
        requirements=None,
        reply_draft=None,
        action="forward_to_human",
    )

