# Course-recommendation explanation study

A small Express app serving a synthetic course-recommendation prototype used
for an HCI MSc dissertation study comparing three explanation formats
(natural language, graph, rule-based). Includes a test/preview harness for
any participant and a forward-only pilot-session build that logs Save/Not
-for-me decisions and NASA-TLX/transparency survey answers to a Google Sheet.

## Running locally

```
npm install
cp .env.example .env   # fill in GOOGLE_SERVICE_ACCOUNT_KEY_FILE/SPREADSHEET_ID
npm start
```

- Test/preview harness: <http://localhost:3000/prototype/index.html>
- Pilot session: <http://localhost:3000/index.html?participant=P1> (any of P1-P9/D0)

Without a `.env`, the app still runs -- Save/Not-for-me and survey logging
just fail silently (no Google Sheets credentials configured).

## Deploying on Render

`render.yaml` is a Render Blueprint (Node web service, `npm install` / `npm
start`). After connecting this repo, set these in the service's Environment
tab:

- `SPREADSHEET_ID` -- the target Google Sheet's ID (from its URL)
- `GOOGLE_SERVICE_ACCOUNT_KEY` -- the full contents of a Google service-account
  JSON key, shared as Editor on that Sheet

## Layout

- `server/` -- Express server: serves `prototype/`/`pilot/` statically, logs
  decisions/survey answers to Google Sheets (`server/sheets.js`).
- `prototype/` -- free-switching test/preview harness (any participant,
  variant, content set; a "preview as participant" toggle shows exactly what
  the pilot build shows).
- `pilot/` -- the real forward-only session build: warm-up, then 3
  content-set rounds each followed by a survey page.
- `scripts/` -- the Python data generator (`generate.py`) and validator
  (`validate.py`) that produce `data/synthetic/sets/*.json`, the only data
  the app reads at runtime. Regenerate with:
  ```
  python scripts/generate.py --seed 2026 --out data/synthetic
  python scripts/validate.py --dir data/synthetic
  ```
- `config/` -- per-participant role assignments and variant order used by
  the generator.
- `data/synthetic/sets/` -- the generated JSON the app serves.
