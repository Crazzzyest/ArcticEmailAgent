from app.business_rules import check_service_requirements, check_trade_in_requirements
from app.models import Attachment


def test_trade_in_complete_when_all_fields_present():
    text = (
        "Hei, her er info om maskinen.\n"
        "Registreringsnummer: AB12345\n"
        "Km-stand: 12345 km\n"
        "Servicehistorikk: fullført på merkeverksted.\n"
        "Generell tilstand er god, ingen nevneverdige skader, dekk er bra.\n"
    )
    attachments = [Attachment(name="bilde.jpg", content_type="image/jpeg")]

    result = check_trade_in_requirements(text, attachments)
    assert result.complete is True
    assert result.missing == []


def test_service_requires_basic_fields():
    text = (
        "Jeg ønsker å bestille service på traktoren.\n"
        "Registreringsnummer: AB12345\n"
        "Km-stand: 54321 km\n"
    )
    attachments: list[Attachment] = []

    result = check_service_requirements(text, attachments)
    assert result.complete is True
    assert result.missing == []

