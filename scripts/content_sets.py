"""Content-set assembly (spec §5.4) + explanation rendering (spec §7).

Unlike the original build, the selected course's two skills are no longer
found by searching a shared recommended list -- roles_data.py authors them
directly (main{i}/secondary{i}), so this module just resolves them, sanity-
checks the bands, and renders. The "list" for a content set is always exactly
[selected, other_a, other_b, other_c] (4 courses); alternates are a separate,
not-in-the-list concept (spec §5.4).
"""

from __future__ import annotations

from dataclasses import dataclass

from roles_data import ExpandedRole, RoleAuthoringError
from scoring import course_score
from wording import (
    CONDITION_REQUIRES_LABEL,
    CONDITION_TEACHES_DETAIL,
    LEGEND_COURSE,
    LEGEND_ROLE,
    LEGEND_SKILL,
    LEGEND_STRONG,
    LEGEND_WEAKER,
    RULE_A_LABEL,
    RULE_A_STRENGTH,
    RULE_A_TITLE,
    RULE_B_LABEL,
    RULE_B_STRENGTH,
    RULE_B_TITLE,
    RULE_FOOTNOTE,
    RULE_SUMMARY,
    badge,
    card_path_line,
    condition_teaches_label,
    confidence_band,
    covers_line,
    reason_text,
    report_id,
    requires_phrase,
    source_label_requires,
    summary_text,
    teaches_noun_phrase,
    teaches_verb_phrase,
    SOURCE_LABEL_TEACHES,
)


@dataclass
class Path:
    skill_id: str
    skill_name: str
    which: str  # "main" | "secondary"
    requires_conf: float
    teaches_conf: float
    requires_report_id: str
    teaches_report_id: str
    evidence_span: dict


@dataclass
class ContentSet:
    content_set_id: str  # "C1".."C3"
    course_ids: list[str]  # the 4-course list, position 1 = selected
    selected_course_id: str
    main: Path
    secondary: Path
    course_score: float


def course_rule_eligibility(course_id: str, expanded: ExpandedRole) -> dict:
    """Whether `course_id` has >=1 skill eligible for Rule A (strong requires +
    strong teaches) and/or Rule B (weak requires + weak teaches)."""
    has_strong = False
    has_weak = False
    for (cid, sid), t in expanded.teaches_map.items():
        if cid != course_id:
            continue
        r = expanded.requires_map.get(sid)
        if r is None:
            continue
        if confidence_band(r) == "strong" and confidence_band(t) == "strong":
            has_strong = True
        if confidence_band(r) == "weak" and confidence_band(t) == "weak":
            has_weak = True
    return {"strong": has_strong, "weak": has_weak}


def primary_taught_skill(course_id: str, expanded: ExpandedRole):
    """Highest-teaches-confidence taught skill for a course: (skill_id, name, teaches_conf),
    or None. Used for non-selected list courses' card lead/path/rules text."""
    best = None
    for (cid, sid), t in expanded.teaches_map.items():
        if cid != course_id:
            continue
        if best is None or t > best[2]:
            best = (sid, expanded.skill_name_by_id[sid], t)
    return best


def rules_matched_label(eligibility: dict) -> str:
    parts = []
    if eligibility["strong"]:
        parts.append("Rule A (teaches)")
    if eligibility["weak"]:
        parts.append("Rule B (covers part)")
    return " · ".join(parts)


def course_display_info(course_id: str, expanded: ExpandedRole) -> dict:
    """badge + 'Covers N skills...' line (spec §6), computed for any course."""
    matched = 0
    eligibility = course_rule_eligibility(course_id, expanded)
    for (cid, sid), t in expanded.teaches_map.items():
        if cid != course_id:
            continue
        r = expanded.requires_map.get(sid)
        if r is None:
            continue
        if confidence_band(r) != "unused" and confidence_band(t) != "unused":
            matched += 1
    return {"badge": badge(eligibility["strong"]), "covers_line": covers_line(matched), "eligibility": eligibility}


def compute_course_score(course_id: str, expanded: ExpandedRole) -> float:
    taught = []
    for (cid, sid), t in expanded.teaches_map.items():
        if cid != course_id:
            continue
        r = expanded.requires_map.get(sid)
        if r is None:
            continue
        taught.append((sid, r, t))
    return course_score(taught)


def _make_path(participant_id: str, content_set_id: str, which: str, skill_id: str, skill_name: str, course_id: str, expanded: ExpandedRole) -> Path:
    requires_conf = expanded.requires_map[skill_id]
    teaches_conf = expanded.teaches_map[(course_id, skill_id)]
    return Path(
        skill_id=skill_id,
        skill_name=skill_name,
        which=which,
        requires_conf=requires_conf,
        teaches_conf=teaches_conf,
        requires_report_id=report_id(participant_id, content_set_id, which, "requires"),
        teaches_report_id=report_id(participant_id, content_set_id, which, "teaches"),
        evidence_span=expanded.evidence_span_map[(course_id, skill_id)],
    )


def _check_band(participant_id, content_set_id, label, requires_band, teaches_band, expected):
    if requires_band != expected or teaches_band != expected:
        raise RoleAuthoringError(
            f"{participant_id}/{content_set_id}: {label} skill isn't {expected}/{expected} "
            f"(requires={requires_band}, teaches={teaches_band})"
        )


def _build_from_resolved(participant_id, content_set_num, main_skill_id, secondary_skill_id, selected_course_id, course_ids, expanded) -> ContentSet:
    content_set_id = f"C{content_set_num}"
    _check_band(
        participant_id, content_set_id, "main",
        confidence_band(expanded.requires_map[main_skill_id]),
        confidence_band(expanded.teaches_map[(selected_course_id, main_skill_id)]),
        "strong",
    )
    _check_band(
        participant_id, content_set_id, "secondary",
        confidence_band(expanded.requires_map[secondary_skill_id]),
        confidence_band(expanded.teaches_map[(selected_course_id, secondary_skill_id)]),
        "weak",
    )
    main_path = _make_path(participant_id, content_set_id, "main", main_skill_id, expanded.skill_name_by_id[main_skill_id], selected_course_id, expanded)
    secondary_path = _make_path(participant_id, content_set_id, "secondary", secondary_skill_id, expanded.skill_name_by_id[secondary_skill_id], selected_course_id, expanded)
    return ContentSet(
        content_set_id=content_set_id,
        course_ids=course_ids,
        selected_course_id=selected_course_id,
        main=main_path,
        secondary=secondary_path,
        course_score=compute_course_score(selected_course_id, expanded),
    )


def build_content_set(participant_id: str, content_set_num: int, expanded: ExpandedRole) -> ContentSet:
    """Every participant (P1-P9 and D0): each content set gets its own
    independent 4-course list, no course reused across C1-C3 (spec §5.4)."""
    main_skill_id = expanded.skill_id_by_slot[f"main{content_set_num}"]
    secondary_skill_id = expanded.skill_id_by_slot[f"secondary{content_set_num}"]
    selected_course_id = expanded.course_id_by_slug[f"c{content_set_num}_selected"]
    course_ids = [
        selected_course_id,
        expanded.course_id_by_slug[f"c{content_set_num}_other_a"],
        expanded.course_id_by_slug[f"c{content_set_num}_other_b"],
        expanded.course_id_by_slug[f"c{content_set_num}_other_c"],
    ]
    if not course_rule_eligibility(course_ids[1], expanded)["strong"]:
        raise RoleAuthoringError(f"{participant_id}/C{content_set_num}: other_a isn't Rule-A-eligible")
    if not course_rule_eligibility(course_ids[2], expanded)["weak"]:
        raise RoleAuthoringError(f"{participant_id}/C{content_set_num}: other_b isn't Rule-B-eligible")
    return _build_from_resolved(participant_id, content_set_num, main_skill_id, secondary_skill_id, selected_course_id, course_ids, expanded)


# ---------------------------------------------------------------------------
# Explanation rendering -- shared summary + A (natural language), B (graph), C (rule-based)
# ---------------------------------------------------------------------------


def render_variant_a(role_title: str, cs: ContentSet) -> dict:
    main, secondary = cs.main, cs.secondary
    panel_prose = (
        f"{main.skill_name.capitalize()} comes up {requires_phrase('strong')} in {role_title} job ads, and "
        f"it's the {teaches_noun_phrase('strong')} of this course. {secondary.skill_name.capitalize()} comes "
        f"up {requires_phrase('weak')} in those ads, and the course {teaches_verb_phrase('weak')}."
    )
    detail_bullets = [
        {
            "text": f"From {role_title} job ads: {main.skill_name} is mentioned {requires_phrase('strong')}.",
            "report_ids": [main.requires_report_id],
        },
        {
            "text": f"From {role_title} job ads: {secondary.skill_name} is mentioned {requires_phrase('weak')}.",
            "report_ids": [secondary.requires_report_id],
        },
        {
            "text": f"From the course description: {main.skill_name} is the main topic; {secondary.skill_name} is covered in part.",
            "report_ids": [main.teaches_report_id, secondary.teaches_report_id],
        },
    ]
    card_reason = f"Teaches {main.skill_name}, which comes up {requires_phrase('strong')} in {role_title} job ads."
    return {"panel_prose": panel_prose, "detail_bullets": detail_bullets, "card_reason": card_reason}


def render_variant_b(role_title: str, cs: ContentSet) -> dict:
    main, secondary = cs.main, cs.secondary
    nodes = [
        {"id": "role", "kind": "role", "label": role_title},
        {"id": main.skill_id, "kind": "skill", "label": main.skill_name.capitalize(), "caption": "Skill employers want"},
        {"id": secondary.skill_id, "kind": "skill", "label": secondary.skill_name.capitalize(), "caption": "Skill employers want"},
        {"id": cs.selected_course_id, "kind": "course", "label": "This course", "title": None},
    ]
    edges = [
        {
            "from": "role",
            "to": main.skill_id,
            "strength": "strong",
            "label": f"{requires_phrase('strong')} asked for",
            "source_label": source_label_requires(role_title),
            "report_id": main.requires_report_id,
        },
        {
            "from": main.skill_id,
            "to": cs.selected_course_id,
            "strength": "strong",
            "label": teaches_noun_phrase("strong"),
            "source_label": SOURCE_LABEL_TEACHES,
            "report_id": main.teaches_report_id,
        },
        {
            "from": "role",
            "to": secondary.skill_id,
            "strength": "weaker",
            "label": f"{requires_phrase('weak')} asked for",
            "source_label": source_label_requires(role_title),
            "report_id": secondary.requires_report_id,
        },
        {
            "from": secondary.skill_id,
            "to": cs.selected_course_id,
            "strength": "weaker",
            "label": teaches_noun_phrase("weak"),
            "source_label": SOURCE_LABEL_TEACHES,
            "report_id": secondary.teaches_report_id,
        },
    ]
    legend = [LEGEND_STRONG, LEGEND_WEAKER, LEGEND_ROLE, LEGEND_SKILL, LEGEND_COURSE]
    card_path = card_path_line(role_title, main.skill_name)
    return {"nodes": nodes, "edges": edges, "legend": legend, "card_path": card_path}


def render_variant_c(role_title: str, cs: ContentSet, expanded: ExpandedRole) -> dict:
    main, secondary = cs.main, cs.secondary

    def make_rule(path: Path, label: str, strength: str, rule_title: str, teaches_label_band: str, rule_key: str) -> dict:
        band = "strong" if strength == RULE_A_STRENGTH else "weak"
        matched_other = sum(
            1
            for cid in cs.course_ids[1:]  # exclude the selected course itself
            if course_rule_eligibility(cid, expanded)[rule_key]
        )
        return {
            "rule_id": "R1" if label == RULE_A_LABEL else "R2",
            "ui_label": label,
            "name": rule_title,
            "strength": strength,
            "skill": path.skill_name,
            "conditions": [
                {
                    "label": CONDITION_REQUIRES_LABEL,
                    "value": path.skill_name,
                    "source_text": f"Comes up {requires_phrase(band)} in {role_title} job ads",
                    "report_id": path.requires_report_id,
                },
                {
                    "label": condition_teaches_label(teaches_label_band),
                    "value": path.skill_name,
                    "source_text": CONDITION_TEACHES_DETAIL,
                    "report_id": path.teaches_report_id,
                },
            ],
            "also_matched_count": matched_other,
        }

    rules_matched = [
        make_rule(main, RULE_A_LABEL, RULE_A_STRENGTH, RULE_A_TITLE, "strong", "strong"),
        make_rule(secondary, RULE_B_LABEL, RULE_B_STRENGTH, RULE_B_TITLE, "weak", "weak"),
    ]
    return {"rules_matched": rules_matched, "header": RULE_SUMMARY, "footnote": RULE_FOOTNOTE}


def build_explanation(role_title: str, cs: ContentSet, expanded: ExpandedRole) -> dict:
    return {
        "summary": summary_text(cs.main.skill_name, role_title),
        "A": render_variant_a(role_title, cs),
        "B": render_variant_b(role_title, cs),
        "C": render_variant_c(role_title, cs, expanded),
    }


# ---------------------------------------------------------------------------
# Single-skill explanation -- beyond spec §5.4 (which only requires exactly
# one explained, two-path course per content set), but every non-selected
# list course already has >=1 qualifying skill by construction (roles_data.py
# designs other_a/b/c that way), so there's always real evidence to show.
# Lets a participant get a reasoned "why" -- and a meaningful Save/Not for me
# decision -- for every course in the list, not just the one spec calls out.
# ---------------------------------------------------------------------------


def build_single_skill_explanation(
    role_title: str,
    participant_id: str,
    content_set_id: str,
    course_slug: str,
    course_id: str,
    skill_id: str,
    skill_name: str,
    requires_conf: float,
    teaches_conf: float,
    other_course_ids: list[str],
    expanded: ExpandedRole,
) -> dict:
    band = confidence_band(requires_conf)  # == confidence_band(teaches_conf) by roles_data.py's construction
    rule_key = "strong" if band == "strong" else "weak"
    requires_rid = report_id(participant_id, content_set_id, course_slug, "requires")
    teaches_rid = report_id(participant_id, content_set_id, course_slug, "teaches")

    teaches_clause = f"it's the {teaches_noun_phrase(band)} of this course" if band == "strong" else f"the course {teaches_verb_phrase(band)}"
    panel_prose = f"{skill_name.capitalize()} comes up {requires_phrase(band)} in {role_title} job ads, and {teaches_clause}."
    detail_bullets = [
        {"text": f"From {role_title} job ads: {skill_name} is mentioned {requires_phrase(band)}.", "report_ids": [requires_rid]},
        {
            "text": f"From the course description: {skill_name} is {teaches_noun_phrase(band) if band == 'strong' else 'covered in part'}.",
            "report_ids": [teaches_rid],
        },
    ]
    card_reason = reason_text(skill_name, role_title, band)

    strength = "strong" if band == "strong" else "weaker"
    nodes = [
        {"id": "role", "kind": "role", "label": role_title},
        {"id": skill_id, "kind": "skill", "label": skill_name.capitalize(), "caption": "Skill employers want"},
        {"id": course_id, "kind": "course", "label": "This course"},
    ]
    edges = [
        {
            "from": "role",
            "to": skill_id,
            "strength": strength,
            "label": f"{requires_phrase(band)} asked for",
            "source_label": source_label_requires(role_title),
            "report_id": requires_rid,
        },
        {
            "from": skill_id,
            "to": course_id,
            "strength": strength,
            "label": teaches_noun_phrase(band),
            "source_label": SOURCE_LABEL_TEACHES,
            "report_id": teaches_rid,
        },
    ]
    legend = [LEGEND_STRONG, LEGEND_WEAKER, LEGEND_ROLE, LEGEND_SKILL, LEGEND_COURSE]
    card_path = card_path_line(role_title, skill_name)

    rule_label = RULE_A_LABEL if band == "strong" else RULE_B_LABEL
    rule_strength = RULE_A_STRENGTH if band == "strong" else RULE_B_STRENGTH
    rule_name = RULE_A_TITLE if band == "strong" else RULE_B_TITLE
    also_matched = sum(1 for cid in other_course_ids if cid != course_id and course_rule_eligibility(cid, expanded)[rule_key])
    rule = {
        "rule_id": "R1" if band == "strong" else "R2",
        "ui_label": rule_label,
        "name": rule_name,
        "strength": rule_strength,
        "skill": skill_name,
        "conditions": [
            {
                "label": CONDITION_REQUIRES_LABEL,
                "value": skill_name,
                "source_text": f"Comes up {requires_phrase(band)} in {role_title} job ads",
                "report_id": requires_rid,
            },
            {
                "label": condition_teaches_label(band),
                "value": skill_name,
                "source_text": CONDITION_TEACHES_DETAIL,
                "report_id": teaches_rid,
            },
        ],
        "also_matched_count": also_matched,
    }
    header = f"1 rule matched: {rule_strength.split(' ')[0].lower()}"

    return {
        "summary": reason_text(skill_name, role_title, band),
        "A": {"panel_prose": panel_prose, "detail_bullets": detail_bullets, "card_reason": card_reason},
        "B": {"nodes": nodes, "edges": edges, "legend": legend, "card_path": card_path},
        "C": {"rules_matched": [rule], "header": header, "footnote": RULE_FOOTNOTE},
    }


def build_explanation_for_course(role_title: str, participant_id: str, cs: ContentSet, course_id: str, expanded: ExpandedRole, course_slug_by_id: dict) -> dict:
    """Dispatch: the content set's own selected course gets its full two-path
    explanation; every other course in the list gets a single-skill one built
    from its own best-matching skill (always exists -- see module docstring)."""
    if course_id == cs.selected_course_id:
        return build_explanation(role_title, cs, expanded)
    skill_id, skill_name, teaches_conf = primary_taught_skill(course_id, expanded)
    requires_conf = expanded.requires_map[skill_id]
    return build_single_skill_explanation(
        role_title,
        participant_id,
        cs.content_set_id,
        course_slug_by_id[course_id],
        course_id,
        skill_id,
        skill_name,
        requires_conf,
        teaches_conf,
        cs.course_ids,
        expanded,
    )
