// Pilot-session wiring. Mirrors the actual session protocol in "Session 2
// Comparative Study.docx": a warm-up round (W0, no explanations), then three
// content-set rounds in strict forward sequence, each shown in the
// participant's actually-assigned variant (content_set.variant -- same
// fetchContentSets() data path as the test prototype, so it already resolves
// the right order for any of P1-P9/D0) and each followed by its own
// NASA-TLX + transparency questionnaire (replacing the docx's Qualtrics step
// -- captured in-app instead, then logged to a Google Sheet via server/).
// No free task/variant switching like prototype/app.js has. Per the docx,
// "Start course" is hidden and the task only ends once Save or Not for me is
// clicked; the verbal decision question and comprehension check are the
// facilitator's job, not this app's. Rendering itself is shared with the
// test prototype via render.js.

const PARTICIPANT_ID = new URLSearchParams(location.search).get("participant") || "D0";

const STEP_SEQUENCE = ["warmup", "task-1", "survey-1", "task-2", "survey-2", "task-3", "survey-3", "done"];

function stepRoundNum(step) {
  const m = /-(\d)$/.exec(step);
  return m ? Number(m[1]) : null;
}

function stepPhase(step) {
  if (step === "warmup" || step === "done") return step;
  return step.startsWith("task-") ? "task" : "survey";
}

// NASA_TLX_ITEMS/TRANSPARENCY_ITEMS/renderSurveyPage/wireSurveyEvents/
// surveyComplete all live in render.js (shared with prototype/app.js's
// "preview as participant" mode), so neither app can drift from the other.

const state = {
  w0: null,
  contentSets: [], // 3 items
  stepIndex: 0,
  viewingCourseId: null,
  expanded: false,
  report: null, // null | "open" | "sent"
  notForMe: false,
  saved: false,
  surveyAnswers: {}, // the CURRENT survey step's in-progress answers, id -> number
  surveyResponses: {}, // committed answers, "C1"/"C2"/"C3" -> {id: number}
};

function currentStep() {
  return STEP_SEQUENCE[state.stepIndex];
}

function currentContentSet() {
  const round = stepRoundNum(currentStep());
  return round ? state.contentSets[round - 1] : null;
}

function totalRounds() {
  return state.contentSets.length; // 3, not counting the warm-up
}

async function boot() {
  state.w0 = await fetchWarmup();
  state.contentSets = await fetchContentSets(PARTICIPANT_ID);

  const params = new URLSearchParams(location.search);
  const requested = params.get("step") || "warmup";
  const idx = STEP_SEQUENCE.indexOf(requested);
  state.stepIndex = idx === -1 ? 0 : idx;
  resetStepState();
  render();
}

function resetStepState() {
  const phase = stepPhase(currentStep());
  if (phase === "warmup") {
    state.viewingCourseId = state.w0.courses[0].id;
  } else if (phase === "task") {
    state.viewingCourseId = currentContentSet().selectedCourseId;
  } else if (phase === "survey") {
    state.surveyAnswers = {};
  }
  state.expanded = false;
  state.report = null;
  state.notForMe = false;
  state.saved = false;
}

function goToStep(stepName) {
  history.pushState(null, "", `app.html?step=${stepName}&participant=${encodeURIComponent(PARTICIPANT_ID)}`);
  state.stepIndex = STEP_SEQUENCE.indexOf(stepName);
  resetStepState();
  render();
}

function advanceToNextStep() {
  const step = currentStep();
  if (stepPhase(step) === "survey") {
    const round = stepRoundNum(step);
    const cs = state.contentSets[round - 1];
    state.surveyResponses[cs.contentSet] = { ...state.surveyAnswers };
    persistResponses();
    logSurvey(cs, round, state.surveyAnswers);
  }
  goToStep(STEP_SEQUENCE[state.stepIndex + 1]);
}

function persistResponses() {
  try {
    localStorage.setItem(`pilot-survey-${PARTICIPANT_ID}`, JSON.stringify(state.surveyResponses));
  } catch (e) {
    // private browsing / storage disabled -- the JSON download at the end still works
  }
}

// Best-effort logging to the Sheets-backed server (server/index.js). Never
// blocks the UI -- if the server isn't running (e.g. plain `python -m
// http.server` during frontend-only dev) this just fails silently.
function postJson(url, body) {
  fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }).catch((err) =>
    console.error(`Could not reach ${url}:`, err)
  );
}

function logDecision(action) {
  const step = currentStep();
  const phase = stepPhase(step);
  const round = stepRoundNum(step);
  const cs = phase === "task" ? currentContentSet() : null;
  postJson("/api/decision", {
    participant_id: PARTICIPANT_ID,
    phase,
    content_set: cs ? cs.contentSet : "warmup",
    variant: cs ? cs.variant : "",
    round: round || "",
    course_id: state.viewingCourseId,
    action,
  });
}

function logSurvey(cs, round, answers) {
  postJson("/api/survey", {
    participant_id: PARTICIPANT_ID,
    content_set: cs.contentSet,
    variant: cs.variant,
    round,
    answers,
  });
}

function downloadResponses() {
  const payload = { participant_id: PARTICIPANT_ID, generated_at: new Date().toISOString(), survey_responses: state.surveyResponses };
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${PARTICIPANT_ID}-pilot-survey-responses.json`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function updateSurveyNav() {
  const btn = document.getElementById("next-step-btn");
  const hint = document.getElementById("nav-hint");
  const complete = surveyComplete(state.surveyAnswers);
  if (btn) btn.disabled = !complete;
  if (hint) hint.textContent = complete ? "" : "Answer all 12 items to continue.";
}

// ---------------------------------------------------------------------------
// Render
// ---------------------------------------------------------------------------

function render() {
  const step = currentStep();
  const phase = stepPhase(step);
  const round = stepRoundNum(step);

  document.getElementById("progress-label").textContent =
    phase === "warmup"
      ? "Warm-up"
      : phase === "done"
        ? "Pilot complete"
        : phase === "task"
          ? `Round ${round} of ${totalRounds()} — Task`
          : `Round ${round} of ${totalRounds()} — Questionnaire`;

  const dotCount = totalRounds() + 1; // warm-up + 3 rounds
  const currentDotIndex = phase === "warmup" ? 0 : phase === "done" ? dotCount : round;
  document.getElementById("progress-dots").innerHTML = Array.from({ length: dotCount }, (_, i) => {
    const cls = phase === "done" || i < currentDotIndex ? "done" : i === currentDotIndex ? "current" : "";
    return `<span class="progress-dot ${cls}"></span>`;
  }).join("");

  const content = document.getElementById("content");
  const nav = document.getElementById("pilot-nav");

  if (phase === "done") {
    document.getElementById("role-title").textContent = "Pilot complete";
    document.getElementById("role-bar-msg").textContent = "";
    content.className = "";
    content.innerHTML = `
      <section class="end-card">
        <h2 style="margin:0">That's the end of this pilot session</h2>
        <p class="simple-note" style="font-style:normal">The warm-up, all three rounds, and their questionnaires have been completed.</p>
        <div style="display:flex;gap:10px;flex-wrap:wrap">
          <button type="button" class="btn-primary" id="download-btn">Download questionnaire responses (JSON)</button>
          <a href="index.html" class="btn-secondary" style="display:inline-flex;align-items:center;text-decoration:none">Restart pilot</a>
        </div>
      </section>`;
    nav.innerHTML = "";
    document.getElementById("download-btn").addEventListener("click", downloadResponses);
    return;
  }

  if (phase === "survey") {
    document.getElementById("role-title").textContent = `Questionnaire — Round ${round}`;
    document.getElementById("role-bar-msg").textContent = "A couple of quick scales about the round you just finished.";
    content.className = "";
    const cs = state.contentSets[round - 1];
    content.innerHTML = renderSurveyPage(cs.variant, state.surveyAnswers);
    wireSurveyEvents(content, state.surveyAnswers, updateSurveyNav);
    const isLast = round === totalRounds();
    const complete = surveyComplete(state.surveyAnswers);
    nav.innerHTML = `
      <div style="display:flex;flex-direction:column;align-items:flex-end;gap:6px">
        <span id="nav-hint" class="simple-note" style="font-style:normal">${complete ? "" : "Answer all 12 items to continue."}</span>
        <button type="button" class="btn-primary" id="next-step-btn" ${complete ? "" : "disabled"}>${isLast ? "Finish Round 3, continue →" : `Continue to Round ${round + 1} →`}</button>
      </div>`;
    document.getElementById("next-step-btn").addEventListener("click", () => advanceToNextStep());
    updateSurveyNav();
    return;
  }

  if (phase === "warmup") {
    document.getElementById("role-title").textContent = "Warm-up (no role)";
    document.getElementById("role-bar-msg").textContent = "Spreadsheet basics -- no explanations shown for this round.";
    content.className = "columns";
    const ui = { viewingCourseId: state.viewingCourseId, notForMe: state.notForMe, saved: state.saved, hideStartCourse: true };
    content.innerHTML = renderW0ListColumn(state.w0, ui) + renderW0DetailColumn(state.w0, ui);
    wireContentEvents(content, handleSelectCourse, handleAction);
    nav.innerHTML = `<div style="display:flex;justify-content:flex-end"><button type="button" class="btn-primary" id="next-step-btn">Finish warm-up, start Round 1 →</button></div>`;
    document.getElementById("next-step-btn").addEventListener("click", () => advanceToNextStep());
    return;
  }

  // phase === "task"
  const cs = currentContentSet();
  document.getElementById("role-title").textContent = cs.role.title;
  document.getElementById("role-bar-msg").textContent = cs.ui.role_bar;
  content.className = "columns";
  const ui = {
    variant: cs.variant,
    viewingCourseId: state.viewingCourseId,
    expanded: state.expanded,
    report: state.report,
    notForMe: state.notForMe,
    saved: state.saved,
    showDebug: false,
    hideStartCourse: true,
  };
  content.innerHTML = renderListColumn(cs, ui) + renderDetailColumn(cs, ui);
  wireContentEvents(content, handleSelectCourse, handleAction);

  // Per the docx: "The task ends when the participant clicks Save or Not for
  // me" -- so the questionnaire can't be reached until one of those happened.
  const decided = state.saved || state.notForMe;
  nav.innerHTML = `
    <div style="display:flex;flex-direction:column;align-items:flex-end;gap:6px">
      <span class="simple-note" style="font-style:normal">${decided ? "" : "Save or mark Not for me to continue."}</span>
      <button type="button" class="btn-primary" id="next-step-btn" ${decided ? "" : "disabled"}>Continue to questionnaire →</button>
    </div>`;
  document.getElementById("next-step-btn").addEventListener("click", () => advanceToNextStep());
}

function handleSelectCourse(courseId) {
  state.viewingCourseId = courseId;
  state.expanded = false;
  state.report = null;
  state.notForMe = false;
  state.saved = false;
  render();
}

function handleAction(action) {
  if (action === "save") state.saved = true;
  if (action === "not-for-me") state.notForMe = true;
  if (action === "save" || action === "not-for-me") logDecision(action);
  if (action === "toggle-expanded") state.expanded = !state.expanded;
  if (action === "open-report") state.report = "open";
  if (action === "send-report") state.report = "sent";
  if (action === "close-report") state.report = null;
  render();
}

boot();
