"""Hand-authored per-role content for P1-P9, D0 and W0 (spec v2 §3-5).

Design for P1-P9: each role gets 12 skills (3 main / 3 secondary / 2 strong-filler
/ 2 weak-filler / 2 unused) and, per content set C1-C3, 6 courses (1 selected +
3 "other" list-mates + 2 alternates) -- 18 courses total, all distinct, per
spec §5.4's "no course reused across C1-C3". Only the 3 selected-course titles
and the 12 skill names are hand-authored per role; the 15 non-selected course
titles are template-generated from the filler/main skill names (still "generic"
per spec, and this is exactly where uniqueness-without-creativity matters most).

Confidence/duration/level values are a single reusable *template* across every
role (see CONTENT_SET_CONF / OTHER_CONF / ALT_CONF / *_META below) -- nothing
about these numbers is ever shown to a participant, so reusing them is
invisible and keeps the spec §5.4 matching constraints (score spread <=0.10,
duration +-30min, same level, description length +-15 words) true by
construction:
  - C1/C2/C3's selected courses score ~1.02/~1.00/~0.98 (spread ~0.04), all
    Intermediate, 125/130/110 minutes, same description template -> same word
    count +- a few words for skill-name-length differences.
  - the "other" list-mates and alternates are single-skill courses, which score
    far below any 2-skill selected course, so the selected course is always
    rank 1 (and the two single-skill "other" courses are deliberately given
    one strong-eligible and one weak-eligible skill, per spec §5.4, so Rule
    A/B's "also matched" counts are never both zero).

D0 (UX Designer, the demo/pilot participant) used to be exempt from the
content-set independence rule (spec §3) so it could reproduce the single
shared 4-course list hardcoded in the original mid-fi mockups. That exemption
was removed: a participant seeing the same 4 courses in all three rounds is a
real confound once D0 is used as an actual pilot session, not just a mockup
screenshot. D0 now goes through the exact same per-content-set-independent
template as P1-P9 (its NEW_ROLE_CONTENT entry below), just with its original
skill/course names reused where the mapping lined up.

W0 (warm-up) has no job/skills/triples at all -- just a flat course catalog
for a no-explanation browsing task (spec §9).
"""

from __future__ import annotations

import hashlib
import random
import re

from models import Course, Job, Sector, Skill, Triple
from wording import confidence_band

# ---------------------------------------------------------------------------
# Registries -- shared across all roles so the same real-world skill (e.g.
# "stakeholder communication", shared by P1 and P9) gets one skill: id.
# ---------------------------------------------------------------------------


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.strip().lower()).strip("_")


class SkillRegistry:
    def __init__(self):
        self._by_name: dict[str, Skill] = {}

    def get_or_create(self, name: str, aliases: list[str] | None = None) -> Skill:
        norm = name.strip().lower()
        existing = self._by_name.get(norm)
        if existing is not None:
            return existing
        skill = Skill(id=f"skill:{_slugify(norm)}", name=norm, aliases=list(aliases or []))
        self._by_name[norm] = skill
        return skill

    def all(self) -> list[Skill]:
        return sorted(self._by_name.values(), key=lambda s: s.id)


class SectorRegistry:
    def __init__(self):
        self._by_name: dict[str, Sector] = {}

    def get_or_create(self, name: str) -> Sector:
        existing = self._by_name.get(name)
        if existing is not None:
            return existing
        sector = Sector(id=f"sector:{_slugify(name)}", name=name)
        self._by_name[name] = sector
        return sector

    def all(self) -> list[Sector]:
        return sorted(self._by_name.values(), key=lambda s: s.id)


# ---------------------------------------------------------------------------
# Determinism: the only randomized quantity is each role's synthetic
# "n_ads_sampled" (spec §4.2: 80-200 per role). hashlib, not Python's salted
# hash(), so --seed reruns are byte-identical regardless of process.
# ---------------------------------------------------------------------------


def n_ads_sampled_for_role(seed: int, participant_id: str) -> int:
    digest = hashlib.sha256(f"{seed}:{participant_id}".encode()).hexdigest()
    rng = random.Random(int(digest, 16) % (2**32))
    return rng.randint(80, 200)


class RoleAuthoringError(Exception):
    """Raised when authored content doesn't land in the intended confidence
    band, or doesn't satisfy a spec §5.4 matching constraint -- a signal to
    fix roles_data.py content, never to silently relax a check."""


# ---------------------------------------------------------------------------
# Description / learning-outcomes templates (50-90 words, spec §4.1)
# ---------------------------------------------------------------------------


def _description_variant_index(title: str, n: int) -> int:
    """Deterministic (not seed-dependent -- the title itself decides it, so it's
    stable across any --seed), so the same course always reads the same way
    on every regenerate, while different courses in the same role/level don't
    all share one obviously-templated skeleton."""
    return sum(ord(ch) for ch in title) % n


# Phrasing patterns below are modelled on how real MOOC listings are actually
# written (Coursera/LinkedIn Learning/FutureLearn/Udemy course pages) -- short
# outcome-first or progression ("from X to Y") openers, plain verbs ("walks
# you through", "goes beyond") instead of one rigid skeleton -- but every word
# here is original and every title/skill/role name is synthetic; nothing is
# copied from, or attributed to, any real course or provider.
_DUAL_SKILL_TEMPLATES = [
    "{title} focuses on {skill1} for people working toward a {role_title} role, through hands-on "
    "exercises and short review checkpoints. It also introduces {skill2}, enough to apply "
    "alongside {skill1} in real {role_title} work. By the end, you'll be able to explain your "
    "approach to {skill1} and show how {skill2} supports it.",
    "{title} takes you from the basics of {skill1} to applying it on a realistic {role_title} "
    "scenario, through short lessons and hands-on practice. Along the way, you'll also get a "
    "practical introduction to {skill2}, enough to use it alongside {skill1} day to day. "
    "Expect a practical course, not a lecture-heavy one.",
    "By the end of {title}, you'll be able to apply {skill1} confidently in {role_title} work, with "
    "a working sense of where {skill2} fits alongside it. The course moves from core {skill1} "
    "technique through a few applied exercises, with a lighter look at {skill2} woven in throughout.",
]
_BEGINNER_TEMPLATES = [
    "{title} is a short introduction to {skill1} for people moving toward a {role_title} role. "
    "You'll walk through the essential vocabulary and a few guided exercises that show {skill1} "
    "in context, with no prior experience assumed. The pace is gentle, with short lessons rather "
    "than a heavy project. It's a reasonable starting point if {skill1} is new to you.",
    "{title} walks you through the basics of {skill1}, built for people new to {role_title} work. "
    "Starting from the essential vocabulary, you'll work through a handful of guided exercises "
    "that build a working sense of {skill1}, with no prior experience assumed. Expect short, "
    "practical lessons rather than a long project, with just enough depth to get you started.",
]
_ADVANCED_TEMPLATES = [
    "{title} is a focused course on {skill1} for people already working toward a {role_title} "
    "role who want to go further. You'll work through applied exercises that push past the basics "
    "and into more realistic scenarios, with less hand-holding than an introductory course. By "
    "the end, you should feel noticeably more confident applying {skill1} on your own.",
    "{title} goes beyond the basics of {skill1}, for people already working toward a {role_title} "
    "role. Through a handful of applied exercises and more realistic scenarios, you'll build the "
    "kind of judgement that only comes with practice, rather than following a fixed recipe. It's "
    "built for people who already have some grounding in {skill1} and want to go further.",
]


def _make_description(title: str, role_title: str, level: str, skill_names: list[str]) -> str:
    if len(skill_names) >= 2:
        skill1, skill2 = skill_names[0], skill_names[1]
        template = _DUAL_SKILL_TEMPLATES[_description_variant_index(title, len(_DUAL_SKILL_TEMPLATES))]
        return template.format(title=title, role_title=role_title, skill1=skill1, skill2=skill2)
    skill1 = skill_names[0]
    templates = _BEGINNER_TEMPLATES if level == "Beginner" else _ADVANCED_TEMPLATES
    template = templates[_description_variant_index(title, len(templates))]
    return template.format(title=title, role_title=role_title, skill1=skill1)


def _make_learning_outcomes(skill_names: list[str], role_title: str) -> list[str]:
    primary = skill_names[0]
    outcomes = [
        f"Applying {primary} to a real {role_title} scenario",
        f"Practicing {primary} through guided exercises",
    ]
    if len(skill_names) >= 2:
        outcomes.append(f"Getting a working introduction to {skill_names[1]}")
    else:
        outcomes.append(f"Building a short {primary} exercise from scratch")
    outcomes.append("Reviewing common mistakes and how to avoid them")
    return outcomes


def _evidence_span(description: str, skill_name: str) -> dict:
    """{text, start, end} -- spec §4.2. Picks the first literal occurrence."""
    start = description.index(skill_name)
    return {"text": skill_name, "start": start, "end": start + len(skill_name)}


# ---------------------------------------------------------------------------
# D0 (UX Designer) -- exempt from the content-set independence rule (spec §3),
# unchanged from the original build: one shared 4-course list + 6 alternates.
# ---------------------------------------------------------------------------

class ExpandedRole:
    def __init__(self):
        self.job: Job | None = None
        self.sector: Sector | None = None
        self.courses: list[Course] = []
        self.triples: list[Triple] = []
        self.requires_map: dict[str, float] = {}  # skill_id -> requires confidence
        self.teaches_map: dict[tuple[str, str], float] = {}  # (course_id, skill_id) -> teaches confidence
        self.evidence_span_map: dict[tuple[str, str], dict] = {}  # (course_id, skill_id) -> {text, start, end}
        self.skill_id_by_slot: dict[str, str] = {}
        self.skill_name_by_slot: dict[str, str] = {}
        self.skill_name_by_id: dict[str, str] = {}
        self.course_id_by_slug: dict[str, str] = {}
        self.role_basis: str = ""
        self.n_ads_sampled: int = 0


def _add_requires(result, job, skill, target, seed, participant_id, skill_registry):
    n_ads_sampled = result.n_ads_sampled
    n_mentioning = round(target * n_ads_sampled)
    stored_conf = round(n_mentioning / n_ads_sampled, 2)
    if confidence_band(stored_conf) != confidence_band(target):
        raise RoleAuthoringError(
            f"{participant_id}/{skill.name}: rounding ({target} -> {stored_conf}, "
            f"n_ads_sampled={n_ads_sampled}) crossed a confidence band boundary"
        )
    result.requires_map[skill.id] = stored_conf
    result.triples.append(
        Triple(
            head=job.id,
            relation="requires",
            tail=skill.id,
            confidence=stored_conf,
            provenance={"source": "job_ads", "n_ads_sampled": n_ads_sampled, "n_ads_mentioning": n_mentioning},
        )
    )


def _add_course(result, course_id, title, meta, taught, role_title, learning_outcomes_override=None):
    """taught: [(skill_id, skill_name, teaches_conf), ...], main skill first."""
    skill_names = [name for _, name, _ in taught]
    description = _make_description(title, role_title, meta["level"], skill_names)
    learning_outcomes = learning_outcomes_override or _make_learning_outcomes(skill_names, role_title)
    course = Course(
        id=course_id,
        title=title,
        level=meta["level"],
        duration_min=meta["duration_min"],
        updated=meta["updated"],
        description=description,
        learning_outcomes=learning_outcomes,
    )
    result.courses.append(course)
    for skill_id, skill_name, teaches_conf in taught:
        if skill_name not in description:
            raise RoleAuthoringError(f"{course_id}: evidence span '{skill_name}' not found in description")
        result.teaches_map[(course_id, skill_id)] = teaches_conf
        evidence_span = _evidence_span(description, skill_name)
        result.evidence_span_map[(course_id, skill_id)] = evidence_span
        result.triples.append(
            Triple(
                head=course_id,
                relation="teaches",
                tail=skill_id,
                confidence=teaches_conf,
                provenance={"source": "course_description", "evidence_span": evidence_span},
            )
        )
    return course


# ---------------------------------------------------------------------------
# P1-P9 and D0: per-role skills (spec §5.1) and the 3 selected-course titles.
# Everything else (9 "other" list-mates + 6 alternates per role) is
# template-generated below from these names -- see CONTENT_SET_TEMPLATE.
# ---------------------------------------------------------------------------

NEW_ROLE_CONTENT = {
    "P1": {
        "sector": "Professional Services",
        "role_basis": "ESCO occupation group 2422 Policy and planning managers / O*NET 13-1111.00 Management Analysts (generalist management-consultant profile)",
        "skills": {
            "main1": "stakeholder communication",
            "main2": "client needs analysis",
            "main3": "executive presentation skills",
            "secondary1": "negotiation",
            "secondary2": "workshop facilitation",
            "secondary3": "change management",
            "strongfiller1": "data storytelling",
            "strongfiller2": "risk assessment",
            "weakfiller1": "budget forecasting",
            "weakfiller2": "vendor management",
            "unused1": "financial modeling",
            "unused2": "procurement basics",
        },
        "selected_titles": [
            "Confident Stakeholder Communication for Consultants",
            "Client Needs Analysis in Practice",
            "Executive Presentations That Land",
        ],
    },
    "P2": {
        "sector": "Research",
        "role_basis": "ESCO 'user researcher' occupation group / O*NET-adjacent UX Researcher profile",
        "skills": {
            "main1": "usability testing",
            "main2": "research planning",
            "main3": "focus group moderation",
            "secondary1": "survey design",
            "secondary2": "qualitative data analysis",
            "secondary3": "interview technique",
            "strongfiller1": "research synthesis",
            "strongfiller2": "competitive analysis",
            "weakfiller1": "data visualization",
            "weakfiller2": "accessibility testing",
            "unused1": "statistics fundamentals",
            "unused2": "market segmentation",
        },
        "selected_titles": [
            "Running Usability Tests That Matter",
            "Research Planning for Product Teams",
            "Moderating Focus Groups",
        ],
    },
    "P3": {
        "sector": "Design",
        "role_basis": "ESCO 'product designer' occupation, extended with O*NET 15-1254.00 Web Developers front-end skill set",
        "skills": {
            "main1": "interaction design",
            "main2": "front-end implementation",
            "main3": "design systems",
            "secondary1": "api fundamentals",
            "secondary2": "prototyping",
            "secondary3": "database basics",
            "strongfiller1": "accessibility",
            "strongfiller2": "design tokens",
            "weakfiller1": "animation for interfaces",
            "weakfiller2": "performance optimization",
            "unused1": "backend architecture",
            "unused2": "devops basics",
        },
        "selected_titles": [
            "Interaction Design for Product Teams",
            "Front-End Implementation for Designers",
            "Design Systems at Scale",
        ],
    },
    "P4": {
        "sector": "Media & Communications",
        "role_basis": "O*NET 27-3031.00 Public Relations Specialists / ESCO 'communication officer'",
        "skills": {
            "main1": "video editing",
            "main2": "social media content strategy",
            "main3": "brand messaging",
            "secondary1": "copywriting",
            "secondary2": "content calendar planning",
            "secondary3": "analytics for content",
            "strongfiller1": "crisis communication",
            "strongfiller2": "media relations",
            "weakfiller1": "podcast production",
            "weakfiller2": "internal communications",
            "unused1": "media law basics",
            "unused2": "event planning",
        },
        "selected_titles": [
            "Advanced Video Editing for Communications Teams",
            "Social Media Content Strategy in Practice",
            "Brand Messaging That Resonates",
        ],
    },
    "P5": {
        "sector": "Architecture & Visualization",
        "role_basis": "O*NET 17-3011.01 Architectural Drafters, extended with a 3D-visualization/rendering skill set",
        "skills": {
            "main1": "3d rendering",
            "main2": "architectural visualization",
            "main3": "lighting and materials",
            "secondary1": "project management",
            "secondary2": "cad modeling",
            "secondary3": "client presentation",
            "strongfiller1": "animation basics",
            "strongfiller2": "real-time visualization",
            "weakfiller1": "site documentation",
            "weakfiller2": "material specification",
            "unused1": "structural engineering basics",
            "unused2": "cost estimation",
        },
        "selected_titles": [
            "3D Rendering for Architectural Projects",
            "Architectural Visualization Techniques",
            "Lighting and Materials for Realistic Renders",
        ],
    },
    "P6": {
        "sector": "Human Resources",
        "role_basis": "O*NET 11-3121.00 Human Resources Managers / ESCO 'human resources manager'",
        "skills": {
            "main1": "recruitment and selection",
            "main2": "performance management",
            "main3": "employee relations",
            "secondary1": "hr policy design",
            "secondary2": "compensation and benefits",
            "secondary3": "onboarding design",
            "strongfiller1": "diversity and inclusion practices",
            "strongfiller2": "workforce planning",
            "weakfiller1": "hr analytics",
            "weakfiller2": "employee engagement surveys",
            "unused1": "payroll basics",
            "unused2": "labor law fundamentals",
        },
        "selected_titles": [
            "Recruitment and Selection Best Practices",
            "Performance Management for HR Leaders",
            "Employee Relations in Practice",
        ],
    },
    "P7": {
        "sector": "Design",
        "role_basis": "ESCO 'product designer' occupation / O*NET 27-1021.00 Commercial and Industrial Designers (UX-leaning profile)",
        "skills": {
            "main1": "product design strategy",
            "main2": "interaction design",
            "main3": "usability testing",
            "secondary1": "visual design",
            "secondary2": "design critique",
            "secondary3": "cross-functional collaboration",
            "strongfiller1": "user research",
            "strongfiller2": "design systems",
            "weakfiller1": "accessibility auditing",
            "weakfiller2": "packaging design",
            "unused1": "financial literacy for designers",
            "unused2": "manufacturing basics",
        },
        "selected_titles": [
            "Product Design Strategy Foundations",
            "Interaction Design for Product Designers",
            "Usability Testing for Product Teams",
        ],
    },
    "P8": {
        "sector": "Software Engineering",
        "role_basis": "O*NET 15-1252.00 Software Developers (senior/lead profile)",
        "skills": {
            "main1": "system design",
            "main2": "code review practices",
            "main3": "distributed systems",
            "secondary1": "mentoring engineers",
            "secondary2": "ci/cd pipelines",
            "secondary3": "cloud infrastructure",
            "strongfiller1": "technical leadership",
            "strongfiller2": "api design",
            "weakfiller1": "performance tuning",
            "weakfiller2": "incident response",
            "unused1": "legacy mainframe maintenance",
            "unused2": "manual qa testing",
        },
        "selected_titles": [
            "System Design for Senior Engineers",
            "Effective Code Review Practices",
            "Distributed Systems Fundamentals",
        ],
    },
    "P9": {
        "sector": "Data Engineering",
        "role_basis": "O*NET 15-1243.00 Database Architects, extended with a data-engineering-lead/people-management skill set",
        "skills": {
            "main1": "data pipeline architecture",
            "main2": "change management for technical teams",
            "main3": "coaching and mentoring leads",
            "secondary1": "data governance",
            "secondary2": "stakeholder communication",
            "secondary3": "cloud data platforms",
            "strongfiller1": "etl design",
            "strongfiller2": "data quality engineering",
            "weakfiller1": "stakeholder reporting",
            "weakfiller2": "budget tracking for data teams",
            "unused1": "frontend frameworks",
            "unused2": "graphic design basics",
        },
        "selected_titles": [
            "Data Pipeline Architecture at Scale",
            "Change Management for Technical Teams",
            "Coaching and Mentoring Engineering Leads",
        ],
    },
    # D0 (demo/pilot participant): skill names reused from the original
    # mockup-fidelity build where the mapping lines up (main1-3/secondary1-3,
    # strongfiller2 = the old "design critique" background-only filler).
    # strongfiller1 ("wireframing") and weakfiller2 ("content strategy") are
    # new -- the old content had no equivalent for either slot.
    "D0": {
        "sector": "Design",
        "role_basis": "ESCO 'user experience designer' occupation / O*NET-adjacent UX/UI Designer profile",
        "skills": {
            "main1": "prototyping",
            "main2": "usability testing",
            "main3": "information architecture",
            "secondary1": "interaction design",
            "secondary2": "research planning",
            "secondary3": "accessibility",
            "strongfiller1": "wireframing",
            "strongfiller2": "design critique",
            "weakfiller1": "design systems",
            "weakfiller2": "content strategy",
            "unused1": "visual design",
            "unused2": "motion design",
        },
        "selected_titles": [
            "Prototyping Interactive Interfaces in Figma",
            "Planning and Running Usability Studies",
            "Information Architecture for Digital Products",
        ],
    },
}

# ---------------------------------------------------------------------------
# Content-set template (spec §5.4): reused identically by every role/set, only
# skill/role NAMES differ -- see module docstring for why that's safe and why
# it makes the matching constraints hold by construction.
# ---------------------------------------------------------------------------

# Per content-set-index (0,1,2) confidence for the selected course's main+secondary
# skill. Strictly decreasing course_score (1.0225 / 1.0036 / 0.9849), spread
# 0.0376 -- well inside the 0.10 budget, with margin for ad-sample rounding.
SELECTED_CONF = [
    {"main": (0.80, 0.90), "secondary": (0.55, 0.55)},
    {"main": (0.80, 0.89), "secondary": (0.54, 0.54)},
    {"main": (0.80, 0.88), "secondary": (0.53, 0.53)},
]
SELECTED_META = [
    {"level": "Intermediate", "duration_min": 125, "updated": "2026-02"},
    {"level": "Intermediate", "duration_min": 130, "updated": "2026-03"},
    {"level": "Intermediate", "duration_min": 110, "updated": "2026-01"},
]

# "Other" list-mates: single-skill courses, scored far below any 2-skill
# selected course. other_a is Rule-A-eligible (strong/strong) via strongfiller1;
# other_b and other_c are both Rule-B-eligible (weak/weak) via weakfiller1/2 --
# satisfying spec §5.4's "at least one strong path, at least one partial path"
# with margin. (unused1/2 are deliberately never taught by any course -- spec
# §5.1's "stored, never used in explanations" -- so no list course teaches
# them; a course that matched zero requires>=0.40 skills would show a
# contradictory "Good fit, Covers 0 skills" card.)
OTHER_A_CONF = (0.75, 0.85)  # strongfiller1: requires, teaches
OTHER_B_CONF = (0.50, 0.50)  # weakfiller1
OTHER_C_CONF = (0.45, 0.50)  # weakfiller2
OTHER_META = [
    {"level": "Intermediate", "duration_min": 100, "updated": "2025-12"},
    {"level": "Beginner", "duration_min": 55, "updated": "2025-10"},
    {"level": "Beginner", "duration_min": 40, "updated": "2025-09"},
]
# Title templates per content-set index, so other_a/other_b/other_c (which
# reuse the SAME filler skill across all 3 sets) still get distinct titles.
OTHER_A_TITLE_TEMPLATES = ["{skill} in Practice", "Applying {skill}", "{skill} for Practitioners"]
OTHER_B_TITLE_TEMPLATES = ["{skill} Fundamentals", "Getting Started with {skill}", "{skill} Basics"]
OTHER_C_TITLE_TEMPLATES = ["{skill}: A Short Overview", "A Short Guide to {skill}", "{skill} in Brief"]

# Alternates: teach the set's own main skill at a low (<0.40) confidence --
# "Other courses that teach [main skill]" (spec §5.4), never in the list.
ALT_TEACHES = 0.25
ALT_META = [
    {"level": "Beginner", "duration_min": 50, "updated": "2025-08"},
    {"level": "Advanced", "duration_min": 160, "updated": "2025-07"},
]
ALT_A_TITLE_TEMPLATE = "{skill} Essentials"
ALT_B_TITLE_TEMPLATE = "Advanced {skill} Techniques"

STRONG_FILLER_REQUIRES = {"strongfiller1": 0.75, "strongfiller2": 0.72}
WEAK_FILLER_REQUIRES = {"weakfiller1": 0.50, "weakfiller2": 0.45}
UNUSED_REQUIRES = {"unused1": 0.30, "unused2": 0.20}


_ACRONYM_FIXUPS = {"Hr": "HR", "Cad": "CAD", "Api": "API", "Ci/Cd": "CI/CD", "Etl": "ETL", "Qa": "QA"}
_LOWERCASE_IN_TITLES = {"and", "or", "for", "in", "of", "the", "to", "with", "a", "an"}


def _title_case_skill(name: str) -> str:
    """Proper title case: minor connector words stay lowercase (except as the
    first word), acronyms get fixed up after Python's naive .title()."""
    if not name:
        return name
    words = name.title().split(" ")
    out = []
    for i, w in enumerate(words):
        fixed = _ACRONYM_FIXUPS.get(w, w)
        if i > 0 and fixed.lower() in _LOWERCASE_IN_TITLES:
            fixed = fixed.lower()
        out.append(fixed)
    return " ".join(out)


def _expand_new_role(participant_id, role_title, job_id, seed, skill_registry, sector_registry) -> ExpandedRole:
    content = NEW_ROLE_CONTENT[participant_id]
    result = ExpandedRole()
    result.role_basis = content["role_basis"]

    sector = sector_registry.get_or_create(content["sector"])
    result.sector = sector
    job = Job(id=job_id, title=role_title, sector_id=sector.id, role_basis=result.role_basis)
    result.job = job
    result.triples.append(Triple(head=job.id, relation="in_sector", tail=sector.id, confidence=1.0, provenance={}))

    result.n_ads_sampled = n_ads_sampled_for_role(seed, participant_id)

    # ---- register all 12 skills + requires triples ----
    skill_obj = {}
    for slot, name in content["skills"].items():
        skill = skill_registry.get_or_create(name)
        skill_obj[slot] = skill
        result.skill_id_by_slot[slot] = skill.id
        result.skill_name_by_slot[slot] = skill.name
        result.skill_name_by_id[skill.id] = skill.name

    for i in range(1, 4):
        main_req, _ = SELECTED_CONF[i - 1]["main"]
        sec_req, _ = SELECTED_CONF[i - 1]["secondary"]
        _add_requires(result, job, skill_obj[f"main{i}"], main_req, seed, participant_id, skill_registry)
        _add_requires(result, job, skill_obj[f"secondary{i}"], sec_req, seed, participant_id, skill_registry)
    for slot, req in STRONG_FILLER_REQUIRES.items():
        _add_requires(result, job, skill_obj[slot], req, seed, participant_id, skill_registry)
    for slot, req in WEAK_FILLER_REQUIRES.items():
        _add_requires(result, job, skill_obj[slot], req, seed, participant_id, skill_registry)
    for slot, req in UNUSED_REQUIRES.items():
        _add_requires(result, job, skill_obj[slot], req, seed, participant_id, skill_registry)

    # ---- courses: 6 per content set x 3 sets = 18, all distinct ----
    for i in range(1, 4):
        idx = i - 1
        selected_title = content["selected_titles"][idx]
        main_skill = skill_obj[f"main{i}"]
        secondary_skill = skill_obj[f"secondary{i}"]
        _, main_teach = SELECTED_CONF[idx]["main"]
        _, sec_teach = SELECTED_CONF[idx]["secondary"]

        selected_id = f"course:{participant_id.lower()}_c{i}_selected"
        _add_course(
            result,
            selected_id,
            selected_title,
            SELECTED_META[idx],
            [(main_skill.id, main_skill.name, main_teach), (secondary_skill.id, secondary_skill.name, sec_teach)],
            role_title,
        )
        result.course_id_by_slug[f"c{i}_selected"] = selected_id

        strongfiller = skill_obj["strongfiller1"]
        other_a_title = OTHER_A_TITLE_TEMPLATES[idx].format(skill=_title_case_skill(strongfiller.name))
        other_a_id = f"course:{participant_id.lower()}_c{i}_other_a"
        _add_course(
            result,
            other_a_id,
            other_a_title,
            OTHER_META[0],
            [(strongfiller.id, strongfiller.name, OTHER_A_CONF[1])],
            role_title,
        )
        result.course_id_by_slug[f"c{i}_other_a"] = other_a_id

        weakfiller = skill_obj["weakfiller1"]
        other_b_title = OTHER_B_TITLE_TEMPLATES[idx].format(skill=_title_case_skill(weakfiller.name))
        other_b_id = f"course:{participant_id.lower()}_c{i}_other_b"
        _add_course(
            result,
            other_b_id,
            other_b_title,
            OTHER_META[1],
            [(weakfiller.id, weakfiller.name, OTHER_B_CONF[1])],
            role_title,
        )
        result.course_id_by_slug[f"c{i}_other_b"] = other_b_id

        weakfiller2 = skill_obj["weakfiller2"]
        other_c_title = OTHER_C_TITLE_TEMPLATES[idx].format(skill=_title_case_skill(weakfiller2.name))
        other_c_id = f"course:{participant_id.lower()}_c{i}_other_c"
        _add_course(
            result,
            other_c_id,
            other_c_title,
            OTHER_META[2],
            [(weakfiller2.id, weakfiller2.name, OTHER_C_CONF[1])],
            role_title,
        )
        result.course_id_by_slug[f"c{i}_other_c"] = other_c_id

        alt_a_title = ALT_A_TITLE_TEMPLATE.format(skill=_title_case_skill(main_skill.name))
        alt_a_id = f"course:{participant_id.lower()}_c{i}_alt_a"
        _add_course(result, alt_a_id, alt_a_title, ALT_META[0], [(main_skill.id, main_skill.name, ALT_TEACHES)], role_title)
        result.course_id_by_slug[f"c{i}_alt_a"] = alt_a_id

        alt_b_title = ALT_B_TITLE_TEMPLATE.format(skill=_title_case_skill(main_skill.name))
        alt_b_id = f"course:{participant_id.lower()}_c{i}_alt_b"
        _add_course(result, alt_b_id, alt_b_title, ALT_META[1], [(main_skill.id, main_skill.name, ALT_TEACHES)], role_title)
        result.course_id_by_slug[f"c{i}_alt_b"] = alt_b_id

    return result


def expand_role(participant_id, role_title, job_id, seed, skill_registry, sector_registry) -> ExpandedRole:
    return _expand_new_role(participant_id, role_title, job_id, seed, skill_registry, sector_registry)


# ---------------------------------------------------------------------------
# W0 (warm-up): flat course catalog, no job/skills/triples at all (spec §9).
# ---------------------------------------------------------------------------

W0_COURSES = [
    # (title, level, duration_min, updated, topic phrase for the description, learning_outcomes)
    (
        "Spreadsheet Basics: Getting Started",
        "Beginner",
        45,
        "2026-01",
        "navigating a spreadsheet, entering data, and saving your work",
        ["Finding your way around the spreadsheet interface", "Entering and editing data", "Saving and naming files clearly", "Avoiding a few common beginner mistakes"],
    ),
    (
        "Formulas and Functions for Beginners",
        "Beginner",
        55,
        "2025-12",
        "writing simple formulas and using common functions like SUM and AVERAGE",
        ["Writing your first formula", "Using SUM, AVERAGE and COUNT", "Copying formulas across cells safely", "Spotting and fixing formula errors"],
    ),
    (
        "Organising Data with Sorting and Filtering",
        "Beginner",
        50,
        "2025-11",
        "sorting rows, filtering data, and keeping a sheet tidy",
        ["Sorting rows by one or more columns", "Filtering to find what you need", "Keeping headers and data ranges tidy", "Undoing a sort or filter safely"],
    ),
    (
        "Introduction to Pivot Tables",
        "Intermediate",
        70,
        "2026-02",
        "summarising data with pivot tables",
        ["Building a first pivot table", "Choosing rows, columns and values", "Summarising totals and counts", "Refreshing a pivot table after data changes"],
    ),
    (
        "Charts and Visual Summaries",
        "Intermediate",
        65,
        "2025-10",
        "turning data into simple charts and visual summaries",
        ["Choosing a chart type for your data", "Building a basic chart", "Labelling axes and legends clearly", "Avoiding common chart mistakes"],
    ),
    (
        "VLOOKUP and Cross-Referencing Data",
        "Intermediate",
        80,
        "2026-03",
        "looking up and cross-referencing data across sheets with VLOOKUP",
        ["Understanding how VLOOKUP works", "Looking up values across sheets", "Avoiding common VLOOKUP errors", "Trying a simpler alternative function"],
    ),
    (
        "Conditional Formatting Essentials",
        "Beginner",
        40,
        "2025-09",
        "highlighting data automatically with conditional formatting",
        ["Highlighting values above or below a threshold", "Using colour scales and data bars", "Building a simple custom rule", "Removing or editing existing rules"],
    ),
    (
        "Cleaning Messy Spreadsheet Data",
        "Intermediate",
        75,
        "2025-08",
        "cleaning up messy data: removing duplicates, fixing formats, and more",
        ["Removing duplicate rows", "Fixing inconsistent text and number formats", "Splitting and combining columns", "Checking your cleaned data for errors"],
    ),
]


def build_w0_courses() -> list[Course]:
    courses = []
    for title, level, duration_min, updated, topic, outcomes in W0_COURSES:
        description = (
            f"{title} is a short, practical course covering {topic}. You'll follow along with example "
            f"spreadsheets and practise on your own data, with no prior spreadsheet experience assumed. "
            f"Expect brief lessons and small hands-on exercises rather than a long project, so you can fit "
            f"it into a short break and still come away with something you can use right away."
        )
        course_id = f"course:w0_{_slugify(title)}"
        courses.append(
            Course(
                id=course_id,
                title=title,
                level=level,
                duration_min=duration_min,
                updated=updated,
                description=description,
                learning_outcomes=outcomes,
            )
        )
    return courses
