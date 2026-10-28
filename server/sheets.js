// Appends pilot-session events to a Google Sheet, which is the durable
// record -- Render's filesystem is ephemeral across restarts/redeploys, so
// nothing here depends on local disk. Locally, point
// GOOGLE_SERVICE_ACCOUNT_KEY_FILE at the downloaded service-account JSON; on
// Render, paste that same JSON's contents into the GOOGLE_SERVICE_ACCOUNT_KEY
// env var instead (the key file itself is gitignored and never deployed).

const fs = require("fs");
const { google } = require("googleapis");

const DECISIONS_TAB = "Decisions";
const DECISIONS_HEADER = ["timestamp_iso", "participant_id", "phase", "content_set", "variant", "round", "course_id", "action"];

const SURVEY_TAB = "Survey";
const SURVEY_HEADER = [
  "timestamp_iso",
  "participant_id",
  "content_set",
  "variant",
  "round",
  "mental_demand",
  "physical_demand",
  "temporal_demand",
  "performance",
  "effort",
  "frustration",
  "understanding",
  "trust_judgement",
  "trust",
  "provenance",
  "contestability",
  "overall_transparency",
];

function loadCredentials() {
  if (process.env.GOOGLE_SERVICE_ACCOUNT_KEY) {
    return JSON.parse(process.env.GOOGLE_SERVICE_ACCOUNT_KEY);
  }
  const keyPath = process.env.GOOGLE_SERVICE_ACCOUNT_KEY_FILE;
  if (!keyPath) {
    throw new Error("Set GOOGLE_SERVICE_ACCOUNT_KEY (JSON contents) or GOOGLE_SERVICE_ACCOUNT_KEY_FILE (path) to use Google Sheets logging.");
  }
  return JSON.parse(fs.readFileSync(keyPath, "utf8"));
}

let sheetsClientPromise = null;
function getSheets() {
  if (!sheetsClientPromise) {
    sheetsClientPromise = (async () => {
      const auth = new google.auth.GoogleAuth({
        credentials: loadCredentials(),
        scopes: ["https://www.googleapis.com/auth/spreadsheets"],
      });
      return google.sheets({ version: "v4", auth });
    })();
  }
  return sheetsClientPromise;
}

function spreadsheetId() {
  const id = process.env.SPREADSHEET_ID;
  if (!id) throw new Error("Set the SPREADSHEET_ID env var to the target Google Sheet's ID (from its URL).");
  return id;
}

const ensuredTabs = new Set();

// Creates the tab with a header row if it doesn't exist yet -- so you only
// have to create the Sheet itself, not pre-build its tabs by hand.
async function ensureTab(sheets, tabName, header) {
  if (ensuredTabs.has(tabName)) return;
  const meta = await sheets.spreadsheets.get({ spreadsheetId: spreadsheetId() });
  const exists = meta.data.sheets.some((s) => s.properties.title === tabName);
  if (!exists) {
    await sheets.spreadsheets.batchUpdate({
      spreadsheetId: spreadsheetId(),
      requestBody: { requests: [{ addSheet: { properties: { title: tabName } } }] },
    });
    await sheets.spreadsheets.values.append({
      spreadsheetId: spreadsheetId(),
      range: `${tabName}!A1`,
      valueInputOption: "RAW",
      insertDataOption: "INSERT_ROWS",
      requestBody: { values: [header] },
    });
  }
  ensuredTabs.add(tabName);
}

async function appendRow(tabName, header, row) {
  const sheets = await getSheets();
  await ensureTab(sheets, tabName, header);
  await sheets.spreadsheets.values.append({
    spreadsheetId: spreadsheetId(),
    range: `${tabName}!A1`,
    valueInputOption: "RAW",
    insertDataOption: "INSERT_ROWS",
    requestBody: { values: [row] },
  });
}

async function logDecision({ participant_id, phase, content_set, variant, round, course_id, action }) {
  await appendRow(DECISIONS_TAB, DECISIONS_HEADER, [
    new Date().toISOString(),
    participant_id,
    phase,
    content_set,
    variant,
    round,
    course_id,
    action,
  ]);
}

async function logSurvey({ participant_id, content_set, variant, round, answers }) {
  await appendRow(SURVEY_TAB, SURVEY_HEADER, [
    new Date().toISOString(),
    participant_id,
    content_set,
    variant,
    round,
    answers.mental_demand,
    answers.physical_demand,
    answers.temporal_demand,
    answers.performance,
    answers.effort,
    answers.frustration,
    answers.understanding,
    answers.trust_judgement,
    answers.trust,
    answers.provenance,
    answers.contestability,
    answers.overall_transparency,
  ]);
}

module.exports = { logDecision, logSurvey };
