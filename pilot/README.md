# Pilot-session build

A cleaned-up version of `prototype/` for running an actual Session 2 pilot,
mirroring the real protocol: a warm-up round (W0, no explanations), then
three content-set rounds (C1, C2, C3) in strict forward order, each shown in
whichever variant the participant is actually assigned (see
`config/order.yaml`), each followed by its own NASA-TLX + transparency
questionnaire. "Start course" is hidden and a round only advances once the
participant clicks Save or Not for me. No participant switcher, no variant
override, no debug toggle, no way to jump back or sideways -- a single
"Next"/"Continue" button at the bottom of each screen.

Rendering is shared with `prototype/` via `prototype/render.js`, so this can't
drift from what's already been exercised there -- only the flow around it
(start screen, forward-only sequence, survey pages, completion screen) is
pilot-specific.

## Running it

For logging to work (Save/Not-for-me decisions and survey answers land in a
Google Sheet), run the Express server from the repo root instead of a plain
static server:

```
npm install
npm start
```

Then open <http://localhost:3000/index.html?participant=P4> (any of
P1-P9/D0). Set `GOOGLE_SERVICE_ACCOUNT_KEY_FILE`/`GOOGLE_SERVICE_ACCOUNT_KEY`
and `SPREADSHEET_ID` first -- see `.env.example` and the repo root
`render.yaml` for deployment on Render.

Without the server (e.g. `python3 -m http.server` from the repo root), the
frontend still works identically -- the Save/Not-for-me and survey POSTs just
fail silently (`.catch`), so this is fine for a quick local run without
logging.

## Flow

1. `index.html?participant=P4` -- short intro, confirms the target role, "Begin pilot session".
2. `app.html?step=warmup&participant=P4` -- spreadsheet-basics browsing, no
   badge/explanation/report (spec §9).
3. `app.html?step=task-1&participant=P4` -- the round's recommended list,
   gated: "Continue to questionnaire" stays disabled until Save or Not for me
   is clicked.
4. `app.html?step=survey-1&participant=P4` -- NASA-TLX (6 sliders) +
   transparency (6 Likert items) for the round just finished; gated until all
   12 are answered.
5. Repeats for rounds 2 and 3 (`task-2`/`survey-2`, `task-3`/`survey-3`).
6. `app.html?step=done&participant=P4` -- completion screen, with a button to
   download that participant's survey responses as JSON (a local backup;
   the Sheet is the real record).

"Restart pilot" (top bar) goes back to the start screen, in case a session
needs to be redone from scratch.

## Files

- `index.html`, `app.html` -- pilot-specific pages.
- `app.js` -- pilot-specific state/flow (warm-up + task/survey sequencing,
  progress indicator, Sheets logging POSTs). Depends on `../prototype/render.js`
  (shared rendering) and `../prototype/data.js` (fetch + normalization
  helpers), both loaded via `<script>` in `app.html`.
- `pilot.css` -- supplements `../prototype/styles.css` with the progress bar,
  survey-page sliders/Likert rows, and start/end screens.
- `../server/` -- the Express server + Google Sheets logging (not pilot-specific
  code, but what makes this build loggable when deployed).
