# Automatisk e‑postklassifisering og svar (innbytte / service)

Dette prosjektet er en liten Python/FastAPI‑tjeneste som:

- Leser inn e‑posttråder (enten via Microsoft Graph eller manuelt test‑endepunkt).
- Klassifiserer henvendelsen i kategorier:
  - Innbytte (trade‑in)
  - Service / reparasjon / annet
  - Tilbud/prisspørsmål som skal håndteres manuelt
- Sjekker om nødvendig informasjon er på plass ut fra faste regler.
- Bruker Claude API til å lage et norsk svarutkast når det er hensiktsmessig.

### Tone og signatur

- Promptene er tilpasset **profesjonell** tone (unngår «KI-hyggelig» språk som *spennende handel*). Modellen instrueres blant annet til takk for henvendelsen og **konkret** referanse til det kunden skriver (produkt/tema).
- **Outlook-signatur kan ikke «skrus på» via Graph** når vi setter hele `body` med PATCH: innholdet vi sender **er** kladden. Firmasignaturen derfor **lagt inn som fast HTML** i `app/email_signature.py`. Juster tekst/HTML der ved behov (f.eks. annen signatur for `service@` senere).

## Kom i gang (lokalt)

1. Opprett et virtuelt miljø og installer avhengigheter:

```bash
pip install -r requirements.txt
```

2. Sett nødvendige miljøvariabler (for eksempel via `.env`):

- `CLAUDE_API_KEY` – API‑nøkkel til Claude.
- `GRAPH_TENANT_ID`, `GRAPH_CLIENT_ID`, `GRAPH_CLIENT_SECRET` – for Microsoft Graph.
- `GRAPH_DEFAULT_MAILBOX` – valgfri fallback (f.eks. `Salg@arcticmotor.no`) hvis webhook-notification ikke inneholder parsebar postboks i `resource`/`@odata.id`. For delte postbokser brukes `users/{mailbox}/messages/...` i stedet for `/me/...`.
- `GRAPH_WEBHOOK_URL` – full offentlig webhook‑URL (f.eks. `https://arcticemailagent.sliplane.app/graph/webhook`). Brukes til automatisk **fornyelse** av Graph‑subscriptions som matcher denne URL‑en (PATCH med ny `expirationDateTime`).
- Valgfritt: `GRAPH_SUBSCRIPTION_RENEW_ENABLED` (default `true`), `GRAPH_SUBSCRIPTION_RENEW_INTERVAL_SECONDS` (default `21600` = 6 timer), `GRAPH_SUBSCRIPTION_EXTEND_MINUTES` (default `4180`, litt under maks for postboks).
- `GRAPH_WEBHOOK_ONLY_CREATED` (default `true`) – ignorer Graph-notifications med kun `updated` (reduserer duplikater og Claude-bruk).
- `GRAPH_WEBHOOK_MESSAGE_DEDUPE_TTL_SECONDS` (default `86400`) – ikke kjør pipeline på nytt for samme `message_id` innenfor dette tidsvinduet (in-memory; ved flere instanser trengs ev. delt lagring). Samme `message_id` kan heller ikke behandles **samtidig** (to webhook-POST med mikrosekunders mellomrom, f.eks. doble subscriptions) – da hoppes den ene over som `duplicate_concurrent_or_recent`.

3. Start API‑et lokalt:

```bash
uvicorn app.main:app --reload
```

4. Test lokalt uten Graph ved å kalle:

- `POST /test/process-thread`

med emne, tekst og eventuelle vedlegg/metadata.

Microsoft‑partneren kan senere sette opp en Graph‑subscription mot `POST /graph/webhook` for å koble dette mot en faktisk mailbox.

## Kjøre som Docker‑container

Bygg image:

```bash
docker build -t arctic-email-assistant .
```

Kjør container (lokalt):

```bash
docker run -p 8000:8000 \
  -e CLAUDE_API_KEY=din_nokkel \
  -e GRAPH_TENANT_ID=... \
  -e GRAPH_CLIENT_ID=... \
  -e GRAPH_CLIENT_SECRET=... \
  -e GRAPH_WEBHOOK_URL=https://<ditt-domene>/graph/webhook \
  arctic-email-assistant
```

Da er API‑et tilgjengelig på `http://localhost:8000`, og en eventuell plattform som Sliplane kan eksponere dette over HTTPS med en offentlig URL, f.eks. `https://<ditt-sliplane-domene>/graph/webhook`, som dere bruker som webhook‑URL i Microsoft Graph.

