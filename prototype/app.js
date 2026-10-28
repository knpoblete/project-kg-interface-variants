// Test-harness wiring for app.html. Rendering itself lives in render.js
// (shared with pilot/app.js) -- this file owns the test-only state (free
// participant / content-set / variant switching, debug toggle) and the DOM
// plumbing around it.

const state = {
  participantId: null,
  mode: "normal", // "normal" | "warmup" (W0 has no explanations at all -- spec §9)
  contentSets: [], // 3 items for "normal" mode
  currentIndex: 0,
  w0: null, // for "warmup" mode
  variant: "A",
  viewingCourseId: null,
  expanded: false,
  report: null, // null | "open" | "sent"
  notForMe: false,
  saved: false,
  showDebug: false,
  // "Preview as participant would see it": hides Start course (matching
  // pilot) and reveals a button to preview the survey page for the current
  // content set. Pure admin preview -- never gated, never logged anywhere.
  previewAsParticipant: false,
  previewingSurvey: false,
  surveyAnswers: {},
};

function uiState() {
  return {
    variant: state.variant,
    viewingCourseId: state.viewingCourseId,
    expanded: state.expanded,
    report: state.report,
    notForMe: state.notForMe,
    saved: state.saved,
    showDebug: state.showDebug,
    hideStartCourse: state.previewAsParticipant,
  };
}

async function boot() {
  const params = new URLSearchParams(location.search);
  state.participantId = params.get("participant") || "D0";
  await loadParticipant(state.participantId);
  wireStaticControls();
  render();
}

async function loadParticipant(pid) {
  state.participantId = pid;
  state.report = null;
  state.notForMe = false;
  state.saved = false;
  state.expanded = false;
  state.previewingSurvey = false;
  state.surveyAnswers = {};

  if (pid === "W0") {
    state.mode = "warmup";
    state.w0 = await fetchWarmup();
    state.viewingCourseId = state.w0.courses[0].id;
    return;
  }

  state.mode = "normal";
  state.contentSets = await fetchContentSets(pid);
  state.currentIndex = 0;
  applyCurrentContentSet();
}

function applyCurrentContentSet() {
  const cs = state.contentSets[state.currentIndex];
  state.variant = cs.variant;
  state.viewingCourseId = cs.selectedCourseId;
  state.expanded = false;
  state.report = null;
  state.notForMe = false;
  state.saved = false;
  state.previewingSurvey = false;
  state.surveyAnswers = {};
}

function wireStaticControls() {
  const participantSelect = document.getElementById("ctl-participant");
  participantSelect.innerHTML = [...PARTICIPANT_IDS, "W0"]
    .map((id) => `<option value="${id}" ${id === state.participantId ? "selected" : ""}>${id}</option>`)
    .join("");
  participantSelect.addEventListener("change", async (e) => {
    const next = e.target.value;
    history.replaceState(null, "", `app.html?participant=${encodeURIComponent(next)}`);
    await loadParticipant(next);
    render();
  });

  document.getElementById("ctl-variant").addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-variant]");
    if (!btn) return;
    state.variant = btn.dataset.variant;
    render();
  });

  document.getElementById("ctl-debug").addEventListener("change", (e) => {
    state.showDebug = e.target.checked;
    render();
  });

  document.getElementById("ctl-preview").addEventListener("change", (e) => {
    state.previewAsParticipant = e.target.checked;
    if (!state.previewAsParticipant) state.previewingSurvey = false;
    render();
  });

  document.getElementById("ctl-preview-survey").addEventListener("click", () => {
    state.previewingSurvey = !state.previewingSurvey;
    render();
  });
}

function handleAction(action) {
  if (action === "save") state.saved = true;
  if (action === "not-for-me") state.notForMe = true;
  if (action === "toggle-expanded") state.expanded = !state.expanded;
  if (action === "open-report") state.report = "open";
  if (action === "send-report") state.report = "sent";
  if (action === "close-report") state.report = null;
  render();
}

function handleSelectCourse(courseId) {
  state.viewingCourseId = courseId;
  state.expanded = false;
  state.report = null;
  state.notForMe = false;
  state.saved = false;
  render();
}

function render() {
  const content = document.getElementById("content");
  const variantWrap = document.getElementById("ctl-variant-wrap");
  const csWrap = document.getElementById("ctl-cs-wrap");
  const csCtl = document.getElementById("ctl-cs");
  const previewSurveyBtn = document.getElementById("ctl-preview-survey");

  if (state.mode === "warmup") {
    document.getElementById("role-title").textContent = "Warm-up (no role)";
    document.getElementById("role-bar-msg").textContent = "Spreadsheet basics -- no explanations shown for this round.";
    variantWrap.hidden = true;
    csWrap.hidden = true;
    previewSurveyBtn.hidden = true;
    content.innerHTML = renderW0ListColumn(state.w0, uiState()) + renderW0DetailColumn(state.w0, uiState());
    wireContentEvents(content, handleSelectCourse, handleAction);
    return;
  }

  variantWrap.hidden = false;
  csWrap.hidden = false;
  const cs = state.contentSets[state.currentIndex];
  document.getElementById("role-title").textContent = cs.role.title;
  document.getElementById("role-bar-msg").textContent = cs.ui.role_bar;

  document.querySelectorAll("#ctl-variant button").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.variant === state.variant);
  });

  csCtl.innerHTML = state.contentSets
    .map((s, i) => `<button type="button" class="seg" data-cs="${i}">${s.contentSet} (${escapeHtml(s.variant)})</button>`)
    .join("");
  csCtl.querySelectorAll("button").forEach((btn) => {
    btn.classList.toggle("active", Number(btn.dataset.cs) === state.currentIndex);
    btn.addEventListener("click", () => {
      state.currentIndex = Number(btn.dataset.cs);
      applyCurrentContentSet();
      render();
    });
  });

  previewSurveyBtn.hidden = !state.previewAsParticipant;
  previewSurveyBtn.textContent = state.previewingSurvey ? "Back to course view" : "Preview questionnaire";

  if (state.previewingSurvey) {
    content.className = "";
    content.innerHTML = renderSurveyPage(cs.variant, state.surveyAnswers);
    wireSurveyEvents(content, state.surveyAnswers, () => {});
    return;
  }

  content.className = "columns";
  content.innerHTML = renderListColumn(cs, uiState()) + renderDetailColumn(cs, uiState());
  wireContentEvents(content, handleSelectCourse, handleAction);
}

boot();
