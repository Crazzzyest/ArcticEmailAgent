from typing import List

from .models import Attachment, RequirementsResult


def _has_any_picture(attachments: List[Attachment]) -> bool:
    for a in attachments:
        if a.content_type and a.content_type.startswith("image/"):
            return True
    return False


def check_trade_in_requirements(text: str, attachments: List[Attachment]) -> RequirementsResult:
    """
    Sjekker minimumskrav for å kunne regne et innbytte.

    Påkrevd:
      - Registreringsnummer
      - Servicehistorikk
      - Noen bilder av maskinen
      - Km‑stand

    Ønskelig:
      - Generell tilstandsbeskrivelse, skader, dekk
    """
    lowered = text.lower()
    missing: List[str] = []
    desired_missing: List[str] = []

    if "regnr" not in lowered and "registreringsnummer" not in lowered and "skilt" not in lowered:
        missing.append("registreringsnummer")

    if "km" not in lowered and "kilometer" not in lowered:
        missing.append("km-stand")

    if "service" not in lowered:
        missing.append("servicehistorikk")

    if not _has_any_picture(attachments):
        missing.append("minst ett bilde av maskinen")

    if "tilstand" not in lowered and "generell stand" not in lowered:
        desired_missing.append("beskrivelse av generell tilstand")

    if "skade" not in lowered:
        desired_missing.append("informasjon om eventuelle skader")

    if "dekk" not in lowered:
        desired_missing.append("informasjon om dekktilstand")

    complete = len(missing) == 0
    return RequirementsResult(complete=complete, missing=missing, desired_missing=desired_missing)


def check_service_requirements(text: str, attachments: List[Attachment]) -> RequirementsResult:
    """
    Sjekker minimumskrav for å kunne gi tilbud/booke service/reparasjon.

    Påkrevd:
      - Hva skal gjøres (service, reparasjon eller annet)
      - Km‑stand
      - Registreringsnummer

    Ved skadebesiktigelse:
      - Skadenummer
      - Forsikringsselskap

    Ønskelig:
      - Når den sist hadde service
    """
    lowered = text.lower()
    missing: List[str] = []
    desired_missing: List[str] = []

    if not any(keyword in lowered for keyword in ["service", "reparasjon", "verksted", "skade", "besiktigelse", "kontroll"]):
        missing.append("hva som skal gjøres (service, reparasjon eller annet)")

    if "km" not in lowered and "kilometer" not in lowered:
        missing.append("km-stand")

    if "regnr" not in lowered and "registreringsnummer" not in lowered and "skilt" not in lowered:
        missing.append("registreringsnummer")

    if "skade" in lowered or "skadebesiktigelse" in lowered:
        if "skadenr" not in lowered and "skadenummer" not in lowered:
            missing.append("skadenummer")
        if "forsikring" not in lowered and "forsikringsselskap" not in lowered:
            missing.append("forsikringsselskap")

    if "sist service" not in lowered and "forrige service" not in lowered:
        desired_missing.append("når den sist hadde service")

    complete = len(missing) == 0
    return RequirementsResult(complete=complete, missing=missing, desired_missing=desired_missing)

