from .models import Category, ClassificationResult


TRADE_IN_KEYWORDS = [
    "innbytte",
    "bytte inn",
    "ta igjen",
    "ta i innbytte",
    "hva får jeg for",
]

SERVICE_KEYWORDS = [
    "service",
    "reparasjon",
    "verksted",
    "time",
    "booking",
    "oljeskift",
    "kontroll",
]

OFFER_ONLY_KEYWORDS = [
    "tilbud",
    "pris på",
    "kan jeg få et tilbud",
    "kan dere gi pris",
]


def classify_text(text: str) -> ClassificationResult:
    lowered = text.lower()

    trade_score = sum(1 for kw in TRADE_IN_KEYWORDS if kw in lowered)
    service_score = sum(1 for kw in SERVICE_KEYWORDS if kw in lowered)
    offer_score = sum(1 for kw in OFFER_ONLY_KEYWORDS if kw in lowered)

    if trade_score == 0 and service_score == 0 and offer_score == 0:
        return ClassificationResult(category=Category.OTHER, confidence=0.3)

    if trade_score >= service_score and trade_score >= offer_score:
        total = max(trade_score + service_score + offer_score, 1)
        return ClassificationResult(
            category=Category.TRADE_IN, confidence=trade_score / total
        )

    if service_score >= trade_score and service_score >= offer_score:
        total = max(trade_score + service_score + offer_score, 1)
        return ClassificationResult(
            category=Category.SERVICE, confidence=service_score / total
        )

    total = max(trade_score + service_score + offer_score, 1)
    return ClassificationResult(
        category=Category.OFFER_ONLY, confidence=offer_score / total
    )

