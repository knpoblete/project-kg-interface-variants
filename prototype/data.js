// Shared data access for the test prototype and the pilot build. Reads the
// generated JSON in data/synthetic/ directly -- nothing here is hardcoded
// content, it's all produced by scripts/generate.py. Must be served over
// http:// (not file://) so fetch() can load local JSON; see README.md.
//
// Every participant's three content sets (P1-P9 and D0 alike) are each a
// separate, independent file (sets/<ID>-C<n>.json) -- no course repeats
// across a participant's three rounds (spec §5.4). D0 used to be exempt and
// kept one combined file with a single shared 4-course list reused across
// all three rounds; that was removed since a real pilot session can't reuse
// the same courses round to round without confounding the comparison.

const PARTICIPANT_IDS = ["P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8", "P9", "D0"];

async function fetchJson(path) {
  // no-store: the underlying JSON changes frequently as the generator is
  // re-run during development; python -m http.server sends no Cache-Control
  // header, so without this the browser can silently serve a stale copy.
  const res = await fetch(path, { cache: "no-store" });
  if (!res.ok) throw new Error(`Could not load ${path} (HTTP ${res.status})`);
  return res.json();
}

async function fetchContentSets(participantId) {
  const raws = await Promise.all([1, 2, 3].map((n) => fetchJson(`../data/synthetic/sets/${participantId}-C${n}.json`)));
  return raws.map((s) => ({
    participantId: s.participant_id,
    contentSet: s.content_set,
    position: s.position,
    variant: s.variant,
    role: s.role,
    ui: s.ui,
    courses: s.courses,
    selectedCourseId: s.selected_course_id,
    alternates: s.alternates,
    paths: s.paths,
    explanation: s.explanation,
  }));
}

async function fetchWarmup() {
  return fetchJson(`../data/synthetic/sets/W0.json`);
}

async function fetchRoleSummaries() {
  const results = [];
  for (const pid of PARTICIPANT_IDS) {
    const sets = await fetchContentSets(pid);
    const topSkills = sets.map((s) => s.paths.find((p) => p.which === "main").skill_name);
    results.push({ participantId: pid, roleTitle: sets[0].role.title, topSkills });
  }
  results.push({ participantId: "W0", roleTitle: "Warm-up", topSkills: [] });
  return results;
}
