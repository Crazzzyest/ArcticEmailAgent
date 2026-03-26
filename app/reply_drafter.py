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


def _has_image_attachments(attachments: list[Attachment]) -> bool:
    return any(
        a.content_bytes and a.content_type and a.content_type.startswith("image/")
        for a in attachments
    )


def _build_system_context() -> str:
    return (
        "Du er kundebehandler hos Arctic Motor (norsk maskinforhandler). "
        "Skriv korte, profesjonelle svar på norsk bokmål.\n"
        "Stil: høflig og konkret, som en erfaren medarbeider – ikke overivrig, ikke "
        "kjærlig-språk og ikke typiske KI-formuleringer.\n"
        "Unngå blant annet: «spennende handel», overdreven entusiasm, tomme superlativer, "
        "«kjære kunde» (med mindre kunden selv har brukt det i tråden).\n"
        "Begynn gjerne med takk for henvendelsen og vis at du har forstått forespørselen – "
        "gjerne med konkret referanse til produkt eller tema når det fremgår av e-posten, "
        "f.eks. «Takk for din henvendelse, og for at du vurderer å kjøpe en Polaris 570 6x6 hos oss!» "
        "(tilpass modell/navn til det kunden faktisk skriver).\n"
        "Ikke avslutt med «Med vennlig hilsen», navn, telefon eller firmaadresse; signaturen "
        "legges til automatisk etterpå. Avslutt med siste faglige setning, neste steg eller et "
        "kort spørsmål til kunden.\n\n"
    )


_IMAGE_ANALYSIS_INSTRUCTIONS = (
    "Kunden har lagt ved bilder. Analyser bildene nøye og ta med dine observasjoner i svaret:\n"
    "- Beskriv kort hva du ser (tilstand, synlige skader, riper, bulker, rust, slitasje osv.).\n"
    "- Hvis bildene viser skader/riper/slitasje, bekreft at du har sett og notert dette.\n"
    "- Ikke be om bilder kunden allerede har sendt.\n"
    "- Vær ærlig men saklig i vurderingen – ikke overdriv verken positivt eller negativt.\n\n"
)


def _build_prompt_for_trade_in(
    text: str, requirements: RequirementsResult, has_images: bool
) -> str:
    image_block = _IMAGE_ANALYSIS_INSTRUCTIONS if has_images else ""

    if requirements.complete:
        return (
            _build_system_context()
            + image_block
            + "Kunden har sendt en henvendelse om innbytte.\n\n"
            "Epostinnhold:\n"
            f"{text}\n\n"
            "Lag et kort, profesjonelt svar på norsk der du:\n"
            "- Bekrefter at vi har fått nødvendig informasjon for å regne på innbytte.\n"
            "- Forteller kort om veien videre, f.eks. at vi kommer tilbake med et konkret tilbud.\n"
            "- Ikke finn på tall eller konkrete priser.\n"
        )
    else:
        missing = ", ".join(requirements.missing)
        desired = ", ".join(requirements.desired_missing)
        return (
            _build_system_context()
            + image_block
            + "Kunden ønsker innbytte, men informasjonen er ikke komplett.\n\n"
            "Epostinnhold:\n"
            f"{text}\n\n"
            "Lag et kort, profesjonelt svar på norsk der du:\n"
            f"- Forklarer at vi trenger mer informasjon før vi kan regne innbytte.\n"
            f"- Ber spesifikt om følgende manglende punkter: {missing or 'ingen'}.\n"
            f"- Dersom det passer naturlig kan du også spørre etter ønsket ekstra info: {desired or 'ingen'}.\n"
            "- Ikke finn på tall eller konkrete priser.\n"
        )


def _build_prompt_for_service(
    text: str, requirements: RequirementsResult, has_images: bool
) -> str:
    image_block = _IMAGE_ANALYSIS_INSTRUCTIONS if has_images else ""

    if requirements.complete:
        return (
            _build_system_context()
            + image_block
            + "Kunden ønsker service/reparasjon/annet verkstedbesøk.\n\n"
            "Epostinnhold:\n"
            f"{text}\n\n"
            "Lag et kort, profesjonelt svar på norsk der du:\n"
            "- Bekrefter hva kunden ønsker å gjøre.\n"
            "- Bekrefter at vi har tilstrekkelig informasjon til å gi tilbud eller foreslå time.\n"
            "- Forklarer kort hva som skjer videre (for eksempel at vi kontakter kunden med tidspunkt/bekreftelse).\n"
        )
    else:
        missing = ", ".join(requirements.missing)
        desired = ", ".join(requirements.desired_missing)
        return (
            _build_system_context()
            + image_block
            + "Kunden ønsker service/reparasjon/annet, men informasjonen er ikke komplett.\n\n"
            "Epostinnhold:\n"
            f"{text}\n\n"
            "Lag et kort, profesjonelt svar på norsk der du:\n"
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

    has_images = _has_image_attachments(attachments)

    if category == Category.TRADE_IN:
        requirements = check_trade_in_requirements(text, attachments)
        prompt = _build_prompt_for_trade_in(text, requirements, has_images)
        reply = await generate_reply(prompt, attachments=attachments)
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
        prompt = _build_prompt_for_service(text, requirements, has_images)
        reply = await generate_reply(prompt, attachments=attachments)
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
