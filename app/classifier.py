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

# Ren pris/tilbudsforespørsel → OFFER_ONLY (forward_to_human, ingen auto-utkast).
# Må ikke matche ren innbyttehenvendelse; sjekkes sammen med TRADE_IN_KEYWORDS.
EXPLICIT_PRICE_OR_OFFER_PHRASES = [
    "tilbud",
    "pristilbud",
    "pris på",
    "pris for",
    "prisen på",
    "hva koster",
    "hvor mye koster",
    "hva er prisen",
    "kan jeg få pris",
    "kan jeg få et tilbud",
    "kan dere gi pris",
    "ønsker pris",
    "vil ha pris",
    "trenger pris",
    "lurer på pris",
    "lurer på prisen",
    "spør om pris",
    "sende pris",
    "gi pris",
    "vite prisen",
    "få vite pris",
    "hva må jeg betale",
    "hva må jeg gi",
]


def classify_text(text: str) -> ClassificationResult:
    lowered = text.lower()

    mentions_trade_in = any(kw in lowered for kw in TRADE_IN_KEYWORDS)
    wants_price_or_offer_only = any(
        phrase in lowered for phrase in EXPLICIT_PRICE_OR_OFFER_PHRASES
    )
    # Ikke generer utkast for ren pris/tilbudsforespørsel uten innbytte (menneskehåndtering).
    if wants_price_or_offer_only and not mentions_trade_in:
        return ClassificationResult(category=Category.OFFER_ONLY, confidence=0.88)

    # Maks ett poeng per kategori: unngå at flere pris-fraser slår én innbytte-treff.
    trade_score = 1 if any(kw in lowered for kw in TRADE_IN_KEYWORDS) else 0
    service_score = 1 if any(kw in lowered for kw in SERVICE_KEYWORDS) else 0
    offer_score = (
        1 if any(p in lowered for p in EXPLICIT_PRICE_OR_OFFER_PHRASES) else 0
    )

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

