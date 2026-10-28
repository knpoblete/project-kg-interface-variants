// Shared rendering logic for the test prototype (prototype/app.js) and the
// pilot-demo build (pilot/app.js). Pure functions: nothing here reads a global
// `state` -- every function that needs UI state takes an explicit `ui` object,
// so the two apps can each own their own state shape without this file
// drifting between them. Load this script before either app's own app.js.
//
// Matches mockups/SYNTHETIC_DATA_SPEC.md v2: the primary data object is a
// "content set" (data.js's fetchContentSets() normalizes P1-P9's three
// independent per-set files and D0's one shared-list file into the same
// shape: {participantId, contentSet, position, variant, role, ui, courses,
// selectedCourseId, alternates, paths, explanation}). W0 (warm-up) has its
// own much simpler renderW0* functions -- no badge/explanation/report/toggle
// at all, per spec §9.

const REPORT_ACTION = "Report a mistake";
// Fixed vocabulary from wording.py's band-phrase functions -- bolded wherever
// it appears in generator-produced prose (panel_prose, rule condition
// source_text), matching the mockups' visual treatment. Longest-first so
// "covers some of it" isn't partially shadowed by a shorter alternative.
const BAND_PHRASES = ["covers some of it", "covered in part", "main topic", "sometimes", "often"];

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = String(str);
  return div.innerHTML;
}

function capitalize(s) {
  return s.length ? s[0].toUpperCase() + s.slice(1) : s;
}

function boldKnownPhrases(text) {
  const escaped = escapeHtml(text);
  const pattern = BAND_PHRASES.map((p) => p.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|");
  const re = new RegExp(`\\b(${pattern})\\b`, "g");
  return escaped.replace(re, "<b>$1</b>");
}

function primaryTaughtSkill(course) {
  // course.taught_skills is pre-sorted desc by teaches_confidence by generate.py
  return course.taught_skills.length ? course.taught_skills[0] : null;
}

function findCourse(courses, courseId) {
  return courses.find((c) => c.id === courseId);
}

function debugTag(reportId, ui) {
  return ui.showDebug ? `<span class="debug-tag">${escapeHtml(reportId)}</span>` : "";
}

function reportButton() {
  return `<button type="button" class="report-link" data-action="open-report">${REPORT_ACTION}</button>`;
}

function wrapLines(text, singleLineThreshold = 14) {
  const words = text.split(" ");
  if (words.length === 1 || text.length <= singleLineThreshold) return [text];
  let bestSplit = 1;
  let bestDiff = Infinity;
  for (let i = 1; i < words.length; i++) {
    const line1 = words.slice(0, i).join(" ");
    const line2 = words.slice(i).join(" ");
    const diff = Math.abs(line1.length - line2.length);
    if (diff < bestDiff) {
      bestDiff = diff;
      bestSplit = i;
    }
  }
  return [words.slice(0, bestSplit).join(" "), words.slice(bestSplit).join(" ")];
}

function tspans(lines, x, centerY, lineGap) {
  if (lines.length === 1) {
    return `<tspan x="${x}" y="${centerY + lineGap * 0.32}">${escapeHtml(lines[0])}</tspan>`;
  }
  const half = lineGap * 0.5;
  return (
    `<tspan x="${x}" y="${centerY - half}">${escapeHtml(lines[0])}</tspan>` +
    `<tspan x="${x}" y="${centerY + half}">${escapeHtml(lines[1])}</tspan>`
  );
}

function highlightEvidence(description, terms) {
  const escaped = escapeHtml(description);
  const cleanTerms = terms.filter(Boolean);
  if (!cleanTerms.length) return escaped;
  const pattern = cleanTerms
    .slice()
    .sort((a, b) => b.length - a.length)
    .map((t) => escapeHtml(t).replace(/[.*+?^${}()|[\]\\]/g, "\\$&"))
    .join("|");
  const re = new RegExp(`(${pattern})`, "gi");
  return escaped.replace(re, '<mark class="evidence-mark">$1</mark>');
}

// "These are the only two decision options" (spec protocol): Save and Not for
// me are mutually exclusive and final -- once one is chosen, its button
// becomes a confirmation and the other disappears, rather than allowing a
// participant to flip back and forth.
function renderDecisionButtons(ui) {
  if (ui.saved) {
    return `<span class="status-text">Saved.</span>`;
  }
  if (ui.notForMe) {
    return `<span class="status-text">Got it. We'll show fewer courses like this.</span>`;
  }
  return `
    <button type="button" class="btn-secondary" data-action="save">Save</button>
    <button type="button" class="btn-secondary" data-action="not-for-me">Not for me</button>`;
}

function certIcon() {
  return '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="9" r="6"></circle><path d="M8.5 14 7 22l5-3 5 3-1.5-8"></path></svg>';
}

// ---------------------------------------------------------------------------
// Course list (left column)
// ---------------------------------------------------------------------------

function renderCourseCard(role, course, ui) {
  const selected = course.id === ui.viewingCourseId;
  const badgeClass = course.badge === "Great fit" ? "strong-fit" : "good-fit";
  const skill = primaryTaughtSkill(course);

  let variantLine = "";
  if (skill) {
    if (ui.variant === "A") {
      variantLine = `<span class="course-reason">${escapeHtml(course.explanation.A.card_reason)}</span>`;
    } else if (ui.variant === "B") {
      variantLine = `
        <span class="chips-flow">
          <span class="chip-role">${escapeHtml(role.title)}</span>
          <span class="flow-arrow">&rarr;</span>
          <span class="chip-skill">${escapeHtml(capitalize(skill.skill_name))}</span>
          <span class="flow-arrow">&rarr;</span>
          <span class="chip-course">This course</span>
        </span>`;
    } else {
      variantLine = `
        <span class="match-row">
          <span class="match-label">Rules matched:</span>
          <span class="match-chip">${escapeHtml(course.rules_matched)}</span>
        </span>`;
    }
  }

  return `
    <a href="#" class="course-card ${selected ? "selected" : ""}" data-select-course="${course.id}">
      <span class="course-title">${escapeHtml(course.title)}</span>
      <span class="course-meta"><span class="dur-chip">${escapeHtml(course.dur)}</span>${escapeHtml(course.meta_no_duration)}</span>
      <span class="course-row">
        <span class="badge ${badgeClass}">${escapeHtml(course.badge)}</span>
        <span class="muted">${escapeHtml(course.covers_line)}</span>
      </span>
      ${variantLine}
    </a>`;
}

function renderListColumn(contentSet, ui) {
  return `
    <section class="list-col">
      <div class="list-head">
        <h1>Recommended for ${escapeHtml(contentSet.role.title)}</h1>
        <p>${escapeHtml(contentSet.ui.sort_line)}</p>
      </div>
      ${contentSet.courses.map((c) => renderCourseCard(contentSet.role, c, ui)).join("")}
    </section>`;
}

// ---------------------------------------------------------------------------
// Selected-course detail column (right column)
// ---------------------------------------------------------------------------

function renderDetailColumn(contentSet, ui) {
  const course = findCourse(contentSet.courses, ui.viewingCourseId);
  const isExplained = course.id === contentSet.selectedCourseId;

  const head = `
    <div class="detail-head">
      <div class="detail-head-main">
        <div aria-hidden="true" class="course-image-placeholder">Course image</div>
        <div class="detail-titles">
          <h2>${escapeHtml(course.title)}</h2>
          <span class="detail-sub">${escapeHtml(course.meta_line)}</span>
          <span class="instructor-line">By <b>[Instructor name]</b> &middot; [Learning platform]<span class="cert-pill">${certIcon()}Certificate of completion</span></span>
        </div>
      </div>
      <div class="detail-actions">
        ${ui.hideStartCourse ? "" : `<button type="button" class="btn-primary">Start course</button>`}
        ${renderDecisionButtons(ui)}
      </div>
    </div>
    <div class="fit-row">
      <span class="fit-badge">${escapeHtml(course.badge)}</span>
      <span class="muted">${escapeHtml(course.covers_line)}</span>
    </div>
    <p class="lead-reason">${escapeHtml(course.explanation.summary)}</p>`;

  const body = renderExplanationBox(contentSet, course, ui);
  const about = renderAboutCourse(course, ui);
  const below = renderBelowRow(contentSet, course, isExplained);

  return `<section class="detail-col">${head}${body}${about}${below}</section>`;
}

// Every course in the list gets its own reasoned explanation (one path for
// the content set's own selected course's secondary skill, or the single
// best-matching skill for any other course -- see scripts/content_sets.py's
// build_single_skill_explanation) -- so Save/Not for me are always backed by
// a visible "why", not just for the one course spec §5.4 calls out.
function renderAboutCourse(course, ui) {
  const terms = course.taught_skills.filter((ts) => ts.band !== "unused").map((ts) => ts.skill_name);
  const highlighted = highlightEvidence(course.description, terms);
  return `
    <section class="about-course ${ui.expanded ? "expanded" : ""}">
      <h3>About this course</h3>
      <p>${highlighted}</p>
      ${ui.expanded ? `<span class="hint">Highlighted: the parts of the description our suggestion is based on.</span>` : ""}
    </section>`;
}

function renderExplanationBox(contentSet, course, ui) {
  const explanation = course.explanation;
  const toggleLabel = ui.expanded ? "Hide the details" : "See the details";
  let heading, bodyHtml;

  if (ui.variant === "A") {
    heading = "Why this course";
    // One "Report a mistake" for the whole explanation, not one per bullet --
    // it covers everything above it (the headline and, once expanded, the
    // detail bullets), so it sits once at the end rather than repeated.
    const allReportIds = [...new Set(explanation.A.detail_bullets.flatMap((b) => b.report_ids))];
    bodyHtml = `
      <p class="why-headline">${boldKnownPhrases(explanation.A.panel_prose)}</p>
      ${
        ui.expanded
          ? `<ul class="a-bullets">
              ${explanation.A.detail_bullets.map((b) => `<li>${escapeHtml(b.text)}</li>`).join("")}
            </ul>`
          : ""
      }
      <div class="why-report-row">${reportButton()}${allReportIds.map((id) => debugTag(id, ui)).join("")}</div>`;
  } else if (ui.variant === "B") {
    heading = "How this course connects to your role";
    bodyHtml =
      explanation.B.nodes.length === 4 ? renderGraphDiagram(contentSet, course, ui) : renderGraphDiagramSingle(contentSet, course, ui);
  } else {
    heading = "Rules that matched this course";
    bodyHtml = `
      <div class="c-summary-row">
        <span class="c-summary">${escapeHtml(explanation.C.header)}</span>
      </div>
      ${explanation.C.rules_matched.map((rule) => renderRuleCard(rule, ui)).join("")}
      ${ui.expanded ? `<p class="c-footnote">${escapeHtml(explanation.C.footnote)}</p>` : ""}
    `;
  }

  return `
    <section class="why-box">
      <h3>${escapeHtml(heading)}</h3>
      ${bodyHtml}
      ${renderReportArea(ui)}
      <div class="based-on-row">
        <span class="based-on-left"><b>Based on:</b>
          ${contentSet.ui.based_on_chips.map((c) => `<span class="chip-pill">${escapeHtml(c)}</span>`).join("")}
        </span>
        <button type="button" class="toggle-btn" data-action="toggle-expanded">${escapeHtml(toggleLabel)}</button>
      </div>
    </section>`;
}

// ---------------------------------------------------------------------------
// Variant B: SVG relationship diagram (always shown; only the per-edge
// "From X job ads" / "From the course description" subtext + report button
// are gated by ui.expanded)
// ---------------------------------------------------------------------------

function renderLegend(legend) {
  return legend
    .map((text, i) => {
      if (i === 0) return `<span class="legend-item"><svg width="26" height="8" aria-hidden="true"><line x1="2" y1="4" x2="24" y2="4" stroke="#3C4658" stroke-width="5" stroke-linecap="round"></line></svg>${escapeHtml(text)}</span>`;
      if (i === 1) return `<span class="legend-item"><svg width="26" height="8" aria-hidden="true"><line x1="2" y1="4" x2="24" y2="4" stroke="#8A93A3" stroke-width="2.5" stroke-dasharray="5 4"></line></svg>${escapeHtml(text)}</span>`;
      if (i === 2) return `<span class="legend-item"><svg width="14" height="14" aria-hidden="true"><circle cx="7" cy="7" r="6" fill="#EEF3FD" stroke="#1D46B8" stroke-width="1.5"></circle></svg>${escapeHtml(text)}</span>`;
      if (i === 3) return `<span class="legend-item"><svg width="14" height="14" aria-hidden="true"><circle cx="7" cy="7" r="6" fill="#FFFFFF" stroke="#3C4658" stroke-width="1.5"></circle></svg>${escapeHtml(text)}</span>`;
      return `<span class="legend-item"><svg width="14" height="14" aria-hidden="true"><circle cx="7" cy="7" r="6" fill="#26324A"></circle></svg>${escapeHtml(text)}</span>`;
    })
    .join("");
}

function renderGraphDiagram(contentSet, course, ui) {
  const b = course.explanation.B;
  const [roleNode, mainSkillNode, secondarySkillNode] = b.nodes;
  const [mainReqEdge, mainTeachEdge, secReqEdge, secTeachEdge] = b.edges;

  const roleLines = wrapLines(contentSet.role.title);
  const mainLines = wrapLines(mainSkillNode.label);
  const secondaryLines = wrapLines(secondarySkillNode.label);
  const courseLines = wrapLines(course.title, 0);

  const ariaLabel = `Diagram: ${contentSet.role.title} connects to this course through ${mainSkillNode.label} (strong connection) and ${secondarySkillNode.label} (weaker connection)`;

  // Mirrored left-right from the original layout (course on the left, role
  // on the right): every x-coordinate below is 760 - <original x>, so the
  // curve shapes and label positions stay geometrically consistent, just
  // reflected. Skill nodes sit at x=380 (the viewBox's own mirror line), so
  // their coordinates are unchanged.
  const svg = `
    <svg viewBox="0 0 760 330" class="relation-svg" role="img" aria-label="${escapeHtml(ariaLabel)}">
      <path d="M600 150 Q 510 80 426 82" stroke="#3C4658" stroke-width="5" fill="none" stroke-linecap="round"></path>
      <path d="M334 82 Q 220 80 134 140" stroke="#3C4658" stroke-width="5" fill="none" stroke-linecap="round"></path>
      <path d="M602 180 Q 510 252 420 252" stroke="#8A93A3" stroke-width="2.5" stroke-dasharray="7 6" fill="none" stroke-linecap="round"></path>
      <path d="M340 252 Q 220 252 132 185" stroke="#8A93A3" stroke-width="2.5" stroke-dasharray="7 6" fill="none" stroke-linecap="round"></path>
      <circle cx="652" cy="165" r="54" fill="#EEF3FD" stroke="#1D46B8" stroke-width="2.5"></circle>
      <text text-anchor="middle" font-size="14" font-weight="600" fill="#1B1F27">${tspans(roleLines, 652, 165, 15.5)}</text>
      <text x="652" y="239" text-anchor="middle" font-size="11" font-weight="700" letter-spacing="0.05em" fill="#1D3F99">YOUR TARGET ROLE</text>
      <circle cx="380" cy="82" r="46" fill="#FFFFFF" stroke="#3C4658" stroke-width="2"></circle>
      <text text-anchor="middle" font-size="13" font-weight="600" fill="#1B1F27">${tspans(mainLines, 380, 82, 15.5)}</text>
      <circle cx="380" cy="252" r="40" fill="#FFFFFF" stroke="#8A93A3" stroke-width="2"></circle>
      <text text-anchor="middle" font-size="13" font-weight="600" fill="#1B1F27">${tspans(secondaryLines, 380, 252, 15.5)}</text>
      <circle cx="80" cy="165" r="58" fill="#26324A" stroke="#26324A" stroke-width="2"></circle>
      <text text-anchor="middle" font-size="15" font-weight="700" fill="#FFFFFF"><tspan x="80" y="170.2">This course</tspan></text>
      <circle cx="80" cy="165" r="65" fill="none" stroke="#1D46B8" stroke-width="2.5"></circle>
      <text x="80" y="269.5" text-anchor="middle" font-size="12" fill="#4A5160">${tspans(courseLines, 80, 269.5, 15)}</text>
    </svg>`;

  const edgeSubtext = (edge) =>
    ui.expanded ? `<br><span class="edge-sub-source">${escapeHtml(edge.source_label)}</span><br>${reportButton()}${debugTag(edge.report_id, ui)}` : "";

  const labels = `
    <span class="edge-label-float" style="left:67.5%;top:24%"><b>${escapeHtml(mainReqEdge.label.split(" ")[0])}</b> asked for${edgeSubtext(mainReqEdge)}</span>
    <span class="edge-label-float" style="left:32.5%;top:24%"><b>${escapeHtml(mainTeachEdge.label)}</b>${edgeSubtext(mainTeachEdge)}</span>
    <span class="edge-label-float" style="left:65%;top:80%"><b>${escapeHtml(secReqEdge.label.split(" ")[0])}</b> asked for${edgeSubtext(secReqEdge)}</span>
    <span class="edge-label-float" style="left:32.5%;top:79%"><b>${escapeHtml(secTeachEdge.label)}</b>${edgeSubtext(secTeachEdge)}</span>`;

  return `
    <div class="diagram-wrap">
      <div class="diagram-canvas">${svg}${labels}</div>
      <div class="legend-row">${renderLegend(b.legend)}</div>
    </div>`;
}

// Single-skill diagram for a non-selected list course's explanation (beyond
// the spec's mockups, which only ever show the two-skill case) -- same
// course-on-the-left / role-on-the-right convention, just one skill in the
// middle and one connecting line instead of two.
function renderGraphDiagramSingle(contentSet, course, ui) {
  const b = course.explanation.B;
  const [roleNode, skillNode] = b.nodes;
  const [reqEdge, teachEdge] = b.edges;

  const roleLines = wrapLines(contentSet.role.title);
  const skillLines = wrapLines(skillNode.label);
  const courseLines = wrapLines(course.title, 0);

  const ariaLabel = `Diagram: ${contentSet.role.title} connects to this course through ${skillNode.label}`;
  const isStrong = reqEdge.strength === "strong";
  const lineColor = isStrong ? "#3C4658" : "#8A93A3";
  const strokeWidth = isStrong ? 5 : 2.5;
  const dash = isStrong ? "" : ' stroke-dasharray="7 6"';

  const svg = `
    <svg viewBox="0 0 760 230" class="relation-svg relation-svg-single" role="img" aria-label="${escapeHtml(ariaLabel)}">
      <path d="M598 115 Q 500 115 426 115" stroke="${lineColor}" stroke-width="${strokeWidth}" fill="none" stroke-linecap="round"${dash}></path>
      <path d="M334 115 Q 220 115 138 115" stroke="${lineColor}" stroke-width="${strokeWidth}" fill="none" stroke-linecap="round"${dash}></path>
      <circle cx="652" cy="115" r="54" fill="#EEF3FD" stroke="#1D46B8" stroke-width="2.5"></circle>
      <text text-anchor="middle" font-size="14" font-weight="600" fill="#1B1F27">${tspans(roleLines, 652, 115, 15.5)}</text>
      <text x="652" y="189" text-anchor="middle" font-size="11" font-weight="700" letter-spacing="0.05em" fill="#1D3F99">YOUR TARGET ROLE</text>
      <circle cx="380" cy="115" r="46" fill="#FFFFFF" stroke="${lineColor}" stroke-width="2"></circle>
      <text text-anchor="middle" font-size="13" font-weight="600" fill="#1B1F27">${tspans(skillLines, 380, 115, 15.5)}</text>
      <circle cx="80" cy="115" r="58" fill="#26324A" stroke="#26324A" stroke-width="2"></circle>
      <text text-anchor="middle" font-size="15" font-weight="700" fill="#FFFFFF"><tspan x="80" y="120.2">This course</tspan></text>
      <circle cx="80" cy="115" r="65" fill="none" stroke="#1D46B8" stroke-width="2.5"></circle>
      <text x="80" y="219.5" text-anchor="middle" font-size="12" fill="#4A5160">${tspans(courseLines, 80, 219.5, 15)}</text>
    </svg>`;

  const edgeSubtext = (edge) =>
    ui.expanded ? `<br><span class="edge-sub-source">${escapeHtml(edge.source_label)}</span><br>${reportButton()}${debugTag(edge.report_id, ui)}` : "";

  const labels = `
    <span class="edge-label-float" style="left:67.5%;top:38%"><b>${escapeHtml(reqEdge.label.split(" ")[0])}</b> asked for${edgeSubtext(reqEdge)}</span>
    <span class="edge-label-float" style="left:32%;top:38%"><b>${escapeHtml(teachEdge.label)}</b>${edgeSubtext(teachEdge)}</span>`;

  return `
    <div class="diagram-wrap">
      <div class="diagram-canvas diagram-canvas-single">${svg}${labels}</div>
      <div class="legend-row">${renderLegend(b.legend)}</div>
    </div>`;
}

// ---------------------------------------------------------------------------
// Variant C: rule cards
// ---------------------------------------------------------------------------

function renderRuleCard(rule, ui) {
  const isWeak = rule.strength === "Weaker match";
  const conditions = rule.conditions
    .map(
      (cond) => `
      <li>
        <span class="cond-line">${checkIcon(isWeak)}<span><span class="cond-text">${escapeHtml(cond.label)}</span> <b>${escapeHtml(cond.value)}</b></span></span>
        ${ui.expanded ? `<span class="cond-detail">${boldKnownPhrases(cond.source_text)} &middot; ${reportButton()}${debugTag(cond.report_id, ui)}</span>` : ""}
      </li>`
    )
    .join("");
  const count = rule.also_matched_count;

  return `
    <div class="rule-card ${isWeak ? "weaker" : ""}">
      <div class="rule-head">
        <span class="rule-label">${escapeHtml(rule.ui_label)}</span>
        <span class="rule-strength">${escapeHtml(rule.strength)}</span>
      </div>
      <span class="rule-title">${escapeHtml(rule.name)}</span>
      <span class="conditions-heading">Conditions met for this course</span>
      <ul class="conditions-list">${conditions}</ul>
      <span class="rule-footer">This rule also matched ${count} other course${count === 1 ? "" : "s"} in your list. <a href="#" data-action="show-matched">Show them</a></span>
    </div>`;
}

function checkIcon(isWeak) {
  const stroke = isWeak ? "#8F430A" : "#1D3F99";
  return `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="${stroke}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" class="check-icon"><path d="M5 12.5l4.5 4.5L19 7.5"></path></svg>`;
}

function renderReportArea(ui) {
  if (ui.report === "open") {
    return `
      <div class="report-dialog" role="dialog" aria-label="Report a mistake">
        <span style="font-weight:700">What's wrong with this reason?</span>
        <label><input type="radio" name="mistake"> This skill isn't needed for my role</label>
        <label><input type="radio" name="mistake"> This course doesn't really teach this</label>
        <label><input type="radio" name="mistake"> Something else</label>
        <textarea placeholder="Tell us more (optional)" rows="2"></textarea>
        <div class="row">
          <button type="button" class="btn-send" data-action="send-report">Send</button>
          <button type="button" class="btn-cancel" data-action="close-report">Cancel</button>
        </div>
      </div>`;
  }
  if (ui.report === "sent") {
    return `
      <div class="report-sent">
        <span>Thanks, this helps us improve suggestions.</span>
        <button type="button" class="report-link" data-action="close-report">Close</button>
      </div>`;
  }
  return "";
}

function renderBelowRow(contentSet, course, isExplained) {
  const learnCol = `
    <div class="below-col">
      <h3>What you'll learn</h3>
      <ol>${course.learning_outcomes.map((o) => `<li>${escapeHtml(o)}</li>`).join("")}</ol>
    </div>`;

  if (!isExplained || !contentSet.alternates.length) {
    return `<div class="below-row">${learnCol}</div>`;
  }

  const mainSkillName = contentSet.paths.find((p) => p.which === "main").skill_name;
  const altCol = `
    <div class="below-col">
      <h3>Other courses that teach ${escapeHtml(mainSkillName)}</h3>
      ${contentSet.alternates
        .map((c) => `<span class="alt-link"><span class="title">${escapeHtml(c.title)}</span><span class="meta">${escapeHtml(c.meta_line)}</span></span>`)
        .join("")}
    </div>`;

  return `<div class="below-row">${learnCol}${altCol}</div>`;
}

// ---------------------------------------------------------------------------
// W0 (warm-up): no badge/summary/explanation/toggle/report at all (spec §9)
// ---------------------------------------------------------------------------

const W0_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function w0DurationLabel(minutes) {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  if (h && m) return `${h}h ${String(m).padStart(2, "0")}m`;
  if (h) return `${h}h`;
  return `${m}m`;
}

function w0UpdatedLabel(updated) {
  const [y, m] = updated.split("-");
  return `${W0_MONTHS[parseInt(m, 10) - 1]} ${y}`;
}

function w0MetaLine(course) {
  return `${course.level} · ${w0DurationLabel(course.duration_min)} · Updated ${w0UpdatedLabel(course.updated)}`;
}

function renderW0ListColumn(w0, ui) {
  return `
    <section class="list-col">
      <div class="list-head">
        <h1>Course catalog</h1>
        <p>Find one that takes less than an hour, open it, and decide whether you'd save it.</p>
      </div>
      ${w0.courses
        .map(
          (c) => `
        <a href="#" class="course-card ${c.id === ui.viewingCourseId ? "selected" : ""}" data-select-course="${c.id}">
          <span class="course-title">${escapeHtml(c.title)}</span>
          <span class="course-meta"><span class="dur-chip">${escapeHtml(w0DurationLabel(c.duration_min))}</span>${escapeHtml(c.level)} &middot; Updated ${escapeHtml(w0UpdatedLabel(c.updated))}</span>
        </a>`
        )
        .join("")}
    </section>`;
}

function renderW0DetailColumn(w0, ui) {
  const course = findCourse(w0.courses, ui.viewingCourseId) || w0.courses[0];
  return `
    <section class="detail-col">
      <div class="detail-head">
        <div class="detail-head-main">
          <div aria-hidden="true" class="course-image-placeholder">Course image</div>
          <div class="detail-titles">
            <h2>${escapeHtml(course.title)}</h2>
            <span class="detail-sub">${escapeHtml(w0MetaLine(course))}</span>
            <span class="instructor-line">By <b>[Instructor name]</b> &middot; [Learning platform]<span class="cert-pill">${certIcon()}Certificate of completion</span></span>
          </div>
        </div>
        <div class="detail-actions">
          ${ui.hideStartCourse ? "" : `<button type="button" class="btn-primary">Start course</button>`}
          ${renderDecisionButtons(ui)}
        </div>
      </div>
      <section class="about-course">
        <h3>About this course</h3>
        <p>${escapeHtml(course.description)}</p>
      </section>
      <div class="below-row">
        <div class="below-col">
          <h3>What you'll learn</h3>
          <ol>${course.learning_outcomes.map((o) => `<li>${escapeHtml(o)}</li>`).join("")}</ol>
        </div>
      </div>
    </section>`;
}

// ---------------------------------------------------------------------------
// Survey page (NASA-TLX + transparency), shown after each round in the pilot
// build in place of the comparative-study docx's Qualtrics step. Shared here
// (not duplicated into pilot/app.js) so the prototype's "preview as
// participant" mode can show the exact same page a real participant sees.
// Callers own the `answers` object (id -> number) and re-render around this;
// these functions never touch any app-specific state directly.
// ---------------------------------------------------------------------------

// NASA-TLX (raw/unweighted -- report each subscale and the mean of the six;
// Performance is anchored Perfect(0)-Failure(100) like every other subscale,
// so higher always means more load and nothing needs reverse-coding).
const NASA_TLX_ITEMS = [
  { id: "mental_demand", label: "Mental Demand", question: "How mentally demanding was the task?", lowLabel: "Very Low", highLabel: "Very High" },
  { id: "physical_demand", label: "Physical Demand", question: "How physically demanding was the task?", lowLabel: "Very Low", highLabel: "Very High" },
  { id: "temporal_demand", label: "Temporal Demand", question: "How hurried or rushed was the pace of the task?", lowLabel: "Very Low", highLabel: "Very High" },
  { id: "performance", label: "Performance", question: "How successful were you in accomplishing what you were asked to do?", lowLabel: "Perfect", highLabel: "Failure" },
  { id: "effort", label: "Effort", question: "How hard did you have to work to accomplish your level of performance?", lowLabel: "Very Low", highLabel: "Very High" },
  { id: "frustration", label: "Frustration", question: "How insecure, discouraged, irritated, stressed, and annoyed were you?", lowLabel: "Very Low", highLabel: "Very High" },
];

// Transparency items (Shin & Park 2019 FAT framework), 1-5 Likert.
const TRANSPARENCY_ITEMS = [
  { id: "understanding", label: "Understanding", question: "I understand why this recommendation was suggested to me." },
  { id: "trust_judgement", label: "Trust judgement", question: "The explanation gives me enough information to judge whether the recommendation is trustworthy." },
  { id: "trust", label: "Trust", question: "I trust this recommendation." },
  { id: "provenance", label: "Provenance", question: "The explanation shows me where the underlying information came from." },
  { id: "contestability", label: "Contestability", question: "I feel I could challenge or question this recommendation if I disagreed with it." },
  { id: "overall_transparency", label: "Overall transparency", question: "Overall, this interface feels transparent about how it reached its recommendation." },
];
const LIKERT_LABELS = ["Strongly disagree", "Disagree", "Neither agree nor disagree", "Agree", "Strongly agree"];

function allSurveyItemIds() {
  return [...NASA_TLX_ITEMS, ...TRANSPARENCY_ITEMS].map((i) => i.id);
}

function surveyComplete(answers) {
  return allSurveyItemIds().every((id) => answers[id] !== undefined);
}

function renderSurveyPage(variant, answers) {
  const tlxRows = NASA_TLX_ITEMS.map((item) => {
    const val = answers[item.id];
    return `
    <div class="survey-item">
      <div class="survey-question"><b>${escapeHtml(item.label)}.</b> ${escapeHtml(item.question)}</div>
      <div class="survey-slider-row">
        <span class="survey-scale-label">${escapeHtml(item.lowLabel)}</span>
        <input type="range" min="0" max="100" step="1" value="${val ?? 50}" data-survey-slider="${item.id}" class="survey-slider" aria-label="${escapeHtml(item.label)}">
        <span class="survey-scale-label">${escapeHtml(item.highLabel)}</span>
        <span class="survey-slider-value" data-slider-value-for="${item.id}">${val ?? "Not yet answered"}</span>
      </div>
    </div>`;
  }).join("");

  const likertRows = TRANSPARENCY_ITEMS.map((item) => {
    const val = answers[item.id];
    return `
    <div class="survey-item">
      <div class="survey-question"><b>${escapeHtml(item.label)}.</b> ${escapeHtml(item.question)}</div>
      <div class="survey-likert-row">
        ${LIKERT_LABELS.map(
          (lbl, i) => `
          <label class="survey-likert-option">
            <input type="radio" name="likert-${item.id}" value="${i + 1}" data-survey-radio="${item.id}" ${val === i + 1 ? "checked" : ""}>
            <span class="survey-likert-text">${i + 1} &middot; ${escapeHtml(lbl)}</span>
          </label>`
        ).join("")}
      </div>
    </div>`;
  }).join("");

  return `
    <section class="survey-form">
      <p class="simple-note" style="font-style:normal">Please answer about the round you just finished (variant ${escapeHtml(variant)}). There are no right or wrong answers.</p>
      <div class="survey-section">
        <h2>NASA-TLX workload questionnaire</h2>
        ${tlxRows}
      </div>
      <div class="survey-section">
        <h2>Transparency questionnaire</h2>
        <p class="simple-note" style="font-style:normal">Rate how much you agree with each statement.</p>
        ${likertRows}
      </div>
    </section>`;
}

function wireSurveyEvents(content, answers, onChange) {
  content.querySelectorAll("[data-survey-slider]").forEach((el) => {
    el.addEventListener("input", () => {
      const id = el.dataset.surveySlider;
      answers[id] = Number(el.value);
      const valueEl = content.querySelector(`[data-slider-value-for="${id}"]`);
      if (valueEl) valueEl.textContent = el.value;
      if (onChange) onChange();
    });
  });
  content.querySelectorAll("[data-survey-radio]").forEach((el) => {
    el.addEventListener("change", () => {
      answers[el.dataset.surveyRadio] = Number(el.value);
      if (onChange) onChange();
    });
  });
}

// ---------------------------------------------------------------------------
// Event wiring (delegated, re-attached on every render since content is rebuilt)
// ---------------------------------------------------------------------------

function wireContentEvents(content, onSelectCourse, onAction) {
  content.querySelectorAll("[data-select-course]").forEach((el) => {
    el.addEventListener("click", (e) => {
      e.preventDefault();
      onSelectCourse(el.dataset.selectCourse);
    });
  });
  const on = (action, handler) => {
    content.querySelectorAll(`[data-action="${action}"]`).forEach((el) => el.addEventListener("click", handler));
  };
  on("save", () => onAction("save"));
  on("not-for-me", () => onAction("not-for-me"));
  on("toggle-expanded", () => onAction("toggle-expanded"));
  on("open-report", (e) => {
    e.preventDefault();
    onAction("open-report");
  });
  on("send-report", () => onAction("send-report"));
  on("close-report", () => onAction("close-report"));
  on("show-matched", (e) => e.preventDefault());
}
