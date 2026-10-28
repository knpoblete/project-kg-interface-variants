// Deploy entry point (Render: `npm start`). Serves the existing static
// pilot/prototype frontend unchanged and adds two logging routes that the
// frontend posts to -- decisions (Save/Not-for-me) and completed surveys
// (NASA-TLX + transparency). Both land in Google Sheets (see sheets.js) so
// the data survives Render's ephemeral filesystem.
//
// Deliberately does NOT statically serve the repo root or mockups/ -- the
// Google service-account key lives there locally and must never be
// reachable over HTTP.

require("dotenv").config();
const path = require("path");
const express = require("express");
const { logDecision, logSurvey } = require("./sheets");

const ROOT = path.join(__dirname, "..");
const app = express();

app.use(express.json());

app.use("/", express.static(path.join(ROOT, "pilot")));
app.use("/prototype", express.static(path.join(ROOT, "prototype")));
app.use("/data/synthetic", express.static(path.join(ROOT, "data", "synthetic")));

app.post("/api/decision", async (req, res) => {
  try {
    await logDecision(req.body);
    res.json({ ok: true });
  } catch (err) {
    console.error("logDecision failed:", err.message);
    res.status(500).json({ ok: false, error: err.message });
  }
});

app.post("/api/survey", async (req, res) => {
  try {
    await logSurvey(req.body);
    res.json({ ok: true });
  } catch (err) {
    console.error("logSurvey failed:", err.message);
    res.status(500).json({ ok: false, error: err.message });
  }
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`JobEd pilot server listening on http://localhost:${PORT}`);
});
