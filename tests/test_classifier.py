from app.classifier import classify_text
from app.models import Category


def test_classify_trade_in():
    text = "Hei, jeg vil gjerne høre hva jeg kan få i innbytte for traktoren min."
    result = classify_text(text)
    assert result.category == Category.TRADE_IN


def test_classify_service():
    text = "Hei, jeg ønsker å bestille time for service på maskinen min."
    result = classify_text(text)
    assert result.category == Category.SERVICE


def test_classify_offer_only():
    text = "Hei, kan jeg få et tilbud på en ny maskin?"
    result = classify_text(text)
    assert result.category == Category.OFFER_ONLY


def test_classify_price_question_without_trade_in_is_offer_only():
    text = "Hei, hva koster Polaris 570 6x6 hos dere?"
    result = classify_text(text)
    assert result.category == Category.OFFER_ONLY


def test_classify_price_with_trade_in_stays_trade_in():
    text = (
        "Hei, jeg vurderer innbytte av min gamle scooter og lurer på pris på en ny Polaris."
    )
    result = classify_text(text)
    assert result.category == Category.TRADE_IN

