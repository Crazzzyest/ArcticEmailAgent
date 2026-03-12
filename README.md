# Automatisk e‑postklassifisering og svar (innbytte / service)

Dette prosjektet er en liten Python/FastAPI‑tjeneste som:

- Leser inn e‑posttråder (enten via Microsoft Graph eller manuelt test‑endepunkt).
- Klassifiserer henvendelsen i kategorier:
  - Innbytte (trade‑in)
  - Service / reparasjon / annet
  - Tilbud/prisspørsmål som skal håndteres manuelt
- Sjekker om nødvendig informasjon er på plass ut fra faste regler.
- Bruker Claude API til å lage et norsk svarutkast når det er hensiktsmessig.

## Kom i gang (lokalt)

1. Opprett et virtuelt miljø og installer avhengigheter:

```bash
pip install -r requirements.txt
```

2. Sett nødvendige miljøvariabler (for eksempel via `.env`):

- `CLAUDE_API_KEY` – API‑nøkkel til Claude.
- `GRAPH_TENANT_ID`, `GRAPH_CLIENT_ID`, `GRAPH_CLIENT_SECRET` – for Microsoft Graph.

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
  arctic-email-assistant
```

Da er API‑et tilgjengelig på `http://localhost:8000`, og en eventuell plattform som Sliplane kan eksponere dette over HTTPS med en offentlig URL, f.eks. `https://<ditt-sliplane-domene>/graph/webhook`, som dere bruker som webhook‑URL i Microsoft Graph.

