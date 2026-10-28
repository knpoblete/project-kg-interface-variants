"""Single source of truth for turning confidence bands into participant-facing
phrases (spec v2 §6). Every one of A/B/C's renderers in content_sets.py calls
these same functions on the same two Paths, so cross-variant consistency
(validate.py check 5) is structural rather than coincidental.

Never show raw confidence numbers or KG jargon in participant-facing text --
BANNED_WORDS below is also what scripts/validate.py scans for.
"""

from __future__ import annotations

STRONG_THRESHOLD = 0.70
WEAK_RANGE = (0.40, 0.69)

BANNED_WORDS = ["knowledge graph", "triple", "relation", "confidence", "path", "link", "score", "algorithm"]

REPORT_ACTION = "Report a mistake"
NOT_FOR_ME = "Not for me"
ROLE_BAR = "We suggest courses based on the role you picked and real job ads."
TOGGLE_SEE = "See the details"
TOGGLE_HIDE = "Hide the details"
LEGEND_STRONG = "Strong connection"
LEGEND_WEAKER = "Weaker connection"
LEGEND_ROLE = "Your role"
LEGEND_SKILL = "Skill employers want"
LEGEND_COURSE = "Recommended course"
RULE_FOOTNOTE = "We use the same small set of rules to suggest courses for every role. A rule matches when all of its conditions are met."
RULE_SUMMARY = "2 rules matched: 1 strong, 1 weaker"
RULE_A_LABEL = "Rule A"
RULE_B_LABEL = "Rule B"
RULE_A_STRENGTH = "Strong match"
RULE_B_STRENGTH = "Weaker match"
RULE_A_TITLE = "Courses that teach a skill your role needs"
RULE_B_TITLE = "Courses that cover part of a skill your role needs"
CONDITIONS_HEADING = "Conditions met for this course"
ABOUT_HIGHLIGHT_NOTE = "Highlighted: the parts of the description our suggestion is based on."


def confidence_band(conf: float) -> str:
    """'strong' | 'weak' | 'unused' -- same thresholds for requires and teaches (spec §4.1/§4.2)."""
    if conf >= STRONG_THRESHOLD:
        return "strong"
    if WEAK_RANGE[0] <= conf <= WEAK_RANGE[1]:
        return "weak"
    return "unused"


def requires_phrase(band: str) -> str:
    return "often" if band == "strong" else "sometimes"


def teaches_noun_phrase(band: str) -> str:
    return "main topic" if band == "strong" else "covered in part"


def teaches_verb_phrase(band: str) -> str:
    return "teaches it" if band == "strong" else "covers some of it"


def badge(has_strong_path: bool) -> str:
    return "Great fit" if has_strong_path else "Good fit"


def covers_line(n: int) -> str:
    return f"Covers {n} skill{'' if n == 1 else 's'} employers ask for"


def sort_line(role_title: str) -> str:
    return f"Best fit first, based on the skills employers ask for in {role_title} job ads."


def based_on_chips(role_title: str) -> list[str]:
    return [f"{role_title} job ads", "Course description"]


def toggle_label(expanded: bool) -> str:
    return TOGGLE_HIDE if expanded else TOGGLE_SEE


def plural_role(role_title: str) -> str:
    """A bare '+s' is not a general English pluralizer, but it is verified correct
    for all 10 confirmed role titles in config/participants.yaml (Consultants, UX
    Researchers, Product Designers, Communications Specialists, Architectural
    Visualisers, HR Managers, Senior Software Engineers, Data Engineering Leads,
    UX Designers). Revisit if a future role title is irregular."""
    return role_title + "s"


def duration_label(minutes: int) -> str:
    h, m = divmod(minutes, 60)
    if h and m:
        return f"{h}h {m:02d}m"
    if h:
        return f"{h}h"
    return f"{m}m"


def updated_label(updated: str) -> str:
    """'2026-02' -> 'Feb 2026'."""
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    year, month = updated.split("-")
    return f"{months[int(month) - 1]} {year}"


def course_meta_line(level: str, duration_min: int, updated: str) -> str:
    return f"{level} · {duration_label(duration_min)} · Updated {updated_label(updated)}"


def course_meta_no_duration(level: str, updated: str) -> str:
    """Card-list meta line now that duration is its own chip -- the detail header
    still uses course_meta_line() (full string, duration included inline)."""
    return f"{level} · Updated {updated_label(updated)}"


CONDITION_REQUIRES_LABEL = "A skill your role needs:"
CONDITION_TEACHES_DETAIL = "From the course description"


def condition_teaches_label(band: str) -> str:
    return "Main topic of this course:" if band == "strong" else "Partly covered in this course:"


def reason_text(skill_name: str, role_title: str, band: str) -> str:
    """'Teaches X, which comes up often/sometimes in Role job ads.' -- band-aware
    so it works for a weak-band skill too (summary_text below always wants the
    main/strong phrasing; a single-skill explanation for a non-selected course
    may be either band)."""
    return f"Teaches {skill_name}, which comes up {requires_phrase(band)} in {role_title} job ads."


def summary_text(main_skill: str, role_title: str) -> str:
    """Shared across all three variants (spec §6/§7): names only the MAIN
    reason -- the secondary reason only appears inside each variant's own
    panel, deliberately (comprehension item 3 tests whether the format
    conveyed it)."""
    return reason_text(main_skill, role_title, "strong")


def card_path_line(role_title: str, main_skill: str) -> str:
    return f"{role_title} → {main_skill.capitalize()} → This course"


def source_label_requires(role_title: str) -> str:
    return f"From {role_title} job ads"


SOURCE_LABEL_TEACHES = "From the course description"


def report_id(participant_id: str, content_set: str, which: str, relation: str) -> str:
    """which: 'main' | 'secondary'. e.g. 'P4-C2-main-requires' (spec §10)."""
    return f"{participant_id}-{content_set}-{which}-{relation}"
