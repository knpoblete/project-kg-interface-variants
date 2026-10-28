#!/usr/bin/env python3
"""Validate data/synthetic/ against mockups/SYNTHETIC_DATA_SPEC.md (v2, §12).

Usage:
    python scripts/validate.py --dir data/synthetic
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

from wording import BANNED_WORDS, confidence_band

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
PARTICIPANT_IDS = [f"P{i}" for i in range(1, 10)]
# D0 (the demo/pilot participant) now goes through the exact same generation
# path as P1-P9 and gets the exact same per-content-set checks -- except
# check_order's Latin-square balance, which is specifically about the 9
# counterbalanced study participants and was never meant to include D0.
ALL_IDS = PARTICIPANT_IDS + ["D0"]

CONFIDENCE_SHAPED_NUMBER = re.compile(r"\b0\.\d{1,3}\b|\b1\.0+\b|\b\d{1,3}\s?%\b|\b\d+/\d+\b")
BANNED_WORD_PATTERNS = [re.compile(r"\b" + re.escape(w) + r"\b", re.IGNORECASE) for w in BANNED_WORDS]
FORBIDDEN_COURSE_FIELDS = {"rating", "ratings", "reviews", "review_count", "learners", "learner_count", "enrollment", "enrollments", "students", "popularity"}


def _load_json(path: Path):
    return json.loads(path.read_text())


def _load_participant_sets(out_dir: Path, pid: str) -> list[dict]:
    return [_load_json(out_dir / "sets" / f"{pid}-C{i}.json") for i in (1, 2, 3)]


def _load_participants_cfg() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "participants.yaml").read_text())


def _load_order_cfg() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "order.yaml").read_text())


# ---------------------------------------------------------------------------
# §12.1 schema + confidence ranges + course constants + no trust-shortcut fields
# ---------------------------------------------------------------------------


def check_schema_and_ranges(out_dir: Path) -> tuple[bool, list[str]]:
    errors = []
    entities = _load_json(out_dir / "kg" / "entities.json")

    for job in entities["jobs"]:
        for field in ("id", "title", "sector_id", "role_basis"):
            if field not in job:
                errors.append(f"job missing field '{field}': {job}")
        if not job.get("role_basis"):
            errors.append(f"job {job.get('id')} has empty role_basis")
    for skill in entities["skills"]:
        for field in ("id", "name", "aliases"):
            if field not in skill:
                errors.append(f"skill missing field '{field}': {skill}")
    for sector in entities["sectors"]:
        for field in ("id", "name"):
            if field not in sector:
                errors.append(f"sector missing field '{field}': {sector}")

    for course in entities["courses"]:
        for field in ("id", "title", "level", "duration_min", "updated", "description", "learning_outcomes", "provider", "instructor", "certificate", "thumbnail"):
            if field not in course:
                errors.append(f"course missing field '{field}': {course.get('id')}")
                continue
        if "learning_outcomes" in course and len(course["learning_outcomes"]) != 4:
            errors.append(f"course {course['id']} has {len(course['learning_outcomes'])} learning_outcomes, expected 4")
        if course.get("level") not in ("Beginner", "Intermediate", "Advanced"):
            errors.append(f"course {course['id']} has invalid level {course.get('level')!r}")
        if course.get("provider") != "[Learning platform]":
            errors.append(f"course {course['id']} provider != '[Learning platform]': {course.get('provider')!r}")
        if course.get("instructor") != "[Instructor name]":
            errors.append(f"course {course['id']} instructor != '[Instructor name]': {course.get('instructor')!r}")
        if course.get("certificate") is not True:
            errors.append(f"course {course['id']} certificate != true: {course.get('certificate')!r}")
        if course.get("thumbnail") is not None:
            errors.append(f"course {course['id']} thumbnail != null: {course.get('thumbnail')!r}")
        forbidden = FORBIDDEN_COURSE_FIELDS & set(course.keys())
        if forbidden:
            errors.append(f"course {course['id']} has forbidden trust-shortcut field(s): {forbidden}")

    triples = _load_json(out_dir / "kg" / "triples.json")
    for t in triples:
        for field in ("head", "relation", "tail", "confidence", "provenance"):
            if field not in t:
                errors.append(f"triple missing field '{field}': {t}")
                continue
        conf = t.get("confidence")
        if conf is None or not (0.0 <= conf <= 1.0):
            errors.append(f"triple confidence out of [0,1]: {t}")
        if t.get("relation") not in ("requires", "teaches", "in_sector"):
            errors.append(f"triple has unknown relation {t.get('relation')!r}: {t}")
        prov = t.get("provenance", {})
        if t.get("relation") == "requires":
            for field in ("source", "n_ads_sampled", "n_ads_mentioning"):
                if field not in prov:
                    errors.append(f"requires triple missing provenance '{field}': {t}")
        if t.get("relation") == "teaches":
            if "source" not in prov:
                errors.append(f"teaches triple missing provenance 'source': {t}")
            span = prov.get("evidence_span")
            if not isinstance(span, dict) or not {"text", "start", "end"} <= set(span.keys()):
                errors.append(f"teaches triple's evidence_span isn't a {{text,start,end}} dict: {t}")

    with (out_dir / "kg" / "triples.csv").open() as f:
        rows = list(csv.DictReader(f))
    if len(rows) != len(triples):
        errors.append(f"triples.csv has {len(rows)} rows but triples.json has {len(triples)}")

    return not errors, errors


# ---------------------------------------------------------------------------
# §12.2 evidence_span substring + offsets
# ---------------------------------------------------------------------------


def check_evidence(out_dir: Path) -> tuple[bool, list[str]]:
    errors = []
    entities = _load_json(out_dir / "kg" / "entities.json")
    desc_by_course = {c["id"]: c["description"] for c in entities["courses"]}
    triples = _load_json(out_dir / "kg" / "triples.json")
    for t in triples:
        if t["relation"] != "teaches":
            continue
        span = t["provenance"].get("evidence_span", {})
        desc = desc_by_course.get(t["head"], "")
        text, start, end = span.get("text", ""), span.get("start"), span.get("end")
        if text not in desc:
            errors.append(f"evidence_span {text!r} not found in description of {t['head']}")
            continue
        if not isinstance(start, int) or not isinstance(end, int) or desc[start:end] != text:
            errors.append(f"evidence_span offsets [{start}:{end}] don't match text {text!r} for {t['head']}")
    return not errors, errors


# ---------------------------------------------------------------------------
# §12.3 role skill distribution (§5.1), derived from the global triples export
# ---------------------------------------------------------------------------


def check_skill_distribution(out_dir: Path) -> tuple[bool, list[str]]:
    errors = []
    participants_cfg = _load_participants_cfg()
    triples = _load_json(out_dir / "kg" / "triples.json")
    for pid, cfg in participants_cfg.items():
        job_id = cfg.get("job_id")
        if not job_id:
            continue  # W0 has no role
        requires = [t for t in triples if t["relation"] == "requires" and t["head"] == job_id]
        n = len(requires)
        if not (10 <= n <= 14):
            errors.append(f"{pid}: {n} skills, expected 10-14")
        counts = {"strong": 0, "weak": 0, "unused": 0}
        for t in requires:
            counts[confidence_band(t["confidence"])] += 1
        if not (4 <= counts["strong"] <= 6):
            errors.append(f"{pid}: {counts['strong']} strong (>=0.70) skills, expected 4-6")
        if not (4 <= counts["weak"] <= 6):
            errors.append(f"{pid}: {counts['weak']} weak (0.40-0.69) skills, expected 4-6")
        if not (1 <= counts["unused"] <= 2):
            errors.append(f"{pid}: {counts['unused']} unused (<0.40) skills, expected 1-2")
    return not errors, errors


# ---------------------------------------------------------------------------
# §12.4 content sets: 2 paths, selected in position 1, no reuse, matching limits
# ---------------------------------------------------------------------------


def check_content_sets(out_dir: Path) -> tuple[bool, list[str]]:
    errors = []
    for pid in ALL_IDS:
        sets = _load_participant_sets(out_dir, pid)
        all_course_ids = []
        all_skill_ids = []
        scores, durations, desc_lens = [], [], []
        for s in sets:
            cs_id = s["content_set"]
            if len(s["paths"]) != 2:
                errors.append(f"{pid}/{cs_id}: expected 2 paths, got {len(s['paths'])}")
                continue
            whichs = sorted(p["which"] for p in s["paths"])
            if whichs != ["main", "secondary"]:
                errors.append(f"{pid}/{cs_id}: expected main+secondary paths, got {whichs}")
            for p in s["paths"]:
                expected_band = "strong" if p["which"] == "main" else "weak"
                if confidence_band(p["requires_confidence"]) != expected_band:
                    errors.append(f"{pid}/{cs_id}: requires band mismatch for {p['skill_name']}")
                if confidence_band(p["teaches_confidence"]) != expected_band:
                    errors.append(f"{pid}/{cs_id}: teaches band mismatch for {p['skill_name']}")
                all_skill_ids.append(p["skill_id"])
            if s["courses"][0]["id"] != s["selected_course_id"]:
                errors.append(f"{pid}/{cs_id}: selected course is not in position 1")
            all_course_ids.extend(c["id"] for c in s["courses"] + s["alternates"])
            scores.append(s["course_score"])
            durations.append(s["courses"][0]["duration_min"])
            desc_lens.append(len(s["courses"][0]["description"].split()))

        if len(all_course_ids) != len(set(all_course_ids)):
            errors.append(f"{pid}: a course is reused across C1-C3: {all_course_ids}")
        if len(all_skill_ids) != len(set(all_skill_ids)):
            errors.append(f"{pid}: a main/secondary skill is reused across C1-C3: {all_skill_ids}")
        if scores and max(scores) - min(scores) > 0.10 + 1e-9:
            errors.append(f"{pid}: course_score spread {max(scores) - min(scores):.4f} exceeds 0.10")
        if durations and max(durations) - min(durations) > 30:
            errors.append(f"{pid}: selected-course duration spread {max(durations) - min(durations)} exceeds 30 min")
        if desc_lens and max(desc_lens) - min(desc_lens) > 15:
            errors.append(f"{pid}: selected-course description length spread {max(desc_lens) - min(desc_lens)} exceeds 15 words")
        for n in desc_lens:
            if not (50 <= n <= 90):
                errors.append(f"{pid}: a selected-course description is {n} words, expected 50-90")
    return not errors, errors


# ---------------------------------------------------------------------------
# §12.5 A/B/C name the same two skills, strengths and sources
# ---------------------------------------------------------------------------


def check_cross_variant_consistency(out_dir: Path) -> tuple[bool, list[str]]:
    errors = []
    for pid in ALL_IDS:
        sets = _load_participant_sets(out_dir, pid)
        for s in sets:
            cs_id = s["content_set"]
            main = next(p for p in s["paths"] if p["which"] == "main")
            secondary = next(p for p in s["paths"] if p["which"] == "secondary")
            expected = {main["requires_report_id"], main["teaches_report_id"], secondary["requires_report_id"], secondary["teaches_report_id"]}

            a_ids = set()
            for b in s["explanation"]["A"]["detail_bullets"]:
                a_ids.update(b["report_ids"])
            if a_ids != expected:
                errors.append(f"{pid}/{cs_id}: variant A report_ids {a_ids} != {expected}")

            b_ids = {e["report_id"] for e in s["explanation"]["B"]["edges"]}
            if b_ids != expected:
                errors.append(f"{pid}/{cs_id}: variant B report_ids {b_ids} != {expected}")
            for e in s["explanation"]["B"]["edges"]:
                is_main = e["report_id"] in (main["requires_report_id"], main["teaches_report_id"])
                if e["strength"] != ("strong" if is_main else "weaker"):
                    errors.append(f"{pid}/{cs_id}: variant B edge strength mismatch for {e['report_id']}")

            c_ids = set()
            for r in s["explanation"]["C"]["rules_matched"]:
                for cond in r["conditions"]:
                    c_ids.add(cond["report_id"])
                    is_main = cond["report_id"] in (main["requires_report_id"], main["teaches_report_id"])
                    if r["strength"] != ("Strong match" if is_main else "Weaker match"):
                        errors.append(f"{pid}/{cs_id}: variant C rule strength mismatch for {cond['report_id']}")
            if c_ids != expected:
                errors.append(f"{pid}/{cs_id}: variant C report_ids {c_ids} != {expected}")
    return not errors, errors


# ---------------------------------------------------------------------------
# Beyond spec: every course's own explanation (not just the content set's
# selected one) is internally self-consistent -- A/B/C reference the same
# report_ids as each other, and B's edge strength / C's rule strength agree.
# ---------------------------------------------------------------------------


def check_per_course_explanations(out_dir: Path) -> tuple[bool, list[str]]:
    errors = []

    def check_course(label, course):
        if "explanation" not in course:
            return
        exp = course["explanation"]
        a_ids = set()
        for b in exp["A"]["detail_bullets"]:
            a_ids.update(b["report_ids"])
        b_ids = {e["report_id"] for e in exp["B"]["edges"]}
        c_ids = {cond["report_id"] for r in exp["C"]["rules_matched"] for cond in r["conditions"]}
        if not (a_ids == b_ids == c_ids):
            errors.append(f"{label}: report_ids disagree across variants (A={a_ids}, B={b_ids}, C={c_ids})")
        if len(exp["C"]["rules_matched"]) == 1:
            # Single-skill explanation: there's only one band, so both of B's
            # edges and the one rule must agree on it.
            b_strengths = {e["strength"] for e in exp["B"]["edges"]}
            c_strength = exp["C"]["rules_matched"][0]["strength"]
            if len(b_strengths) != 1:
                errors.append(f"{label}: variant B edges have inconsistent strengths {b_strengths}")
            else:
                expected_c_strength = "Strong match" if next(iter(b_strengths)) == "strong" else "Weaker match"
                if c_strength != expected_c_strength:
                    errors.append(f"{label}: variant C rule strength {c_strength!r} doesn't match variant B strength {b_strengths}")

    for pid in ALL_IDS:
        for s in _load_participant_sets(out_dir, pid):
            for c in s["courses"]:
                check_course(f"{pid}/{s['content_set']}/{c['id']}", c)

    return not errors, errors


# ---------------------------------------------------------------------------
# §12.6 also_matched_count recount
# ---------------------------------------------------------------------------


def _requires_band_map(out_dir: Path, job_id: str) -> dict:
    triples = _load_json(out_dir / "kg" / "triples.json")
    return {t["tail"]: confidence_band(t["confidence"]) for t in triples if t["relation"] == "requires" and t["head"] == job_id}


def _course_eligibility_from_payload(course: dict, requires_band: dict) -> dict:
    has_strong = False
    has_weak = False
    for ts in course["taught_skills"]:
        rb = requires_band.get(ts["skill_id"])
        if rb == "strong" and ts["band"] == "strong":
            has_strong = True
        if rb == "weak" and ts["band"] == "weak":
            has_weak = True
    return {"strong": has_strong, "weak": has_weak}


def check_rules_recount(out_dir: Path) -> tuple[bool, list[str]]:
    errors = []
    participants_cfg = _load_participants_cfg()
    for pid in ALL_IDS:
        job_id = participants_cfg[pid]["job_id"]
        requires_band = _requires_band_map(out_dir, job_id)
        for s in _load_participant_sets(out_dir, pid):
            cs_id = s["content_set"]
            others = s["courses"][1:]
            for rule in s["explanation"]["C"]["rules_matched"]:
                key = "strong" if rule["strength"] == "Strong match" else "weak"
                recount = sum(1 for c in others if _course_eligibility_from_payload(c, requires_band)[key])
                if recount != rule["also_matched_count"]:
                    errors.append(f"{pid}/{cs_id}/{rule['ui_label']}: also_matched_count {rule['also_matched_count']} != recount {recount}")
    return not errors, errors


# ---------------------------------------------------------------------------
# §12.7 comprehension checks
# ---------------------------------------------------------------------------


def check_comprehension(out_dir: Path) -> tuple[bool, list[str]]:
    errors = []
    participants_cfg = _load_participants_cfg()
    for pid in ALL_IDS:
        job_id = participants_cfg[pid]["job_id"]
        requires_band = _requires_band_map(out_dir, job_id)
        sets = _load_participant_sets(out_dir, pid)
        main_secondary_names = set()
        for s in sets:
            for p in s["paths"]:
                main_secondary_names.add(p["skill_name"])

        item2_distractor_combos = []
        item3_distractor_combos = []
        for i, s in enumerate(sets, start=1):
            gt = _load_json(out_dir / "ground_truth" / f"{pid}-C{i}.json")
            main_name = next(p["skill_name"] for p in s["paths"] if p["which"] == "main")
            secondary_name = next(p["skill_name"] for p in s["paths"] if p["which"] == "secondary")
            items_by_num = {it["item"]: it for it in gt["items"]}

            for item_num, item in items_by_num.items():
                if len(set(item["options"])) != len(item["options"]):
                    errors.append(f"{pid}/C{i}/item{item_num}: duplicate option values {item['options']}")
                if not (0 <= item["correct_index"] < len(item["options"])):
                    errors.append(f"{pid}/C{i}/item{item_num}: correct_index out of range")

            it2 = items_by_num[2]
            if it2["options"][it2["correct_index"]] != main_name:
                errors.append(f"{pid}/C{i}/item2: correct answer {it2['options'][it2['correct_index']]!r} != main skill {main_name!r}")
            distractors2 = [o for o in it2["options"] if o != main_name]
            for d in distractors2:
                if requires_band.get(_skill_id_by_name(out_dir, job_id, d)) not in ("strong", "weak"):
                    errors.append(f"{pid}/C{i}/item2: distractor {d!r} isn't a >=0.40 role skill")
                if d in main_secondary_names:
                    errors.append(f"{pid}/C{i}/item2: distractor {d!r} is a main/secondary skill in one of this participant's sets")
            item2_distractor_combos.append(tuple(sorted(distractors2)))

            it3 = items_by_num[3]
            if it3["options"][it3["correct_index"]] != secondary_name:
                errors.append(f"{pid}/C{i}/item3: correct answer {it3['options'][it3['correct_index']]!r} != secondary skill {secondary_name!r}")
            distractors3 = [o for o in it3["options"] if o not in (secondary_name, "No secondary reason")]
            for d in distractors3:
                if requires_band.get(_skill_id_by_name(out_dir, job_id, d)) not in ("strong", "weak"):
                    errors.append(f"{pid}/C{i}/item3: distractor {d!r} isn't a >=0.40 role skill")
                if d in main_secondary_names:
                    errors.append(f"{pid}/C{i}/item3: distractor {d!r} is a main/secondary skill in one of this participant's sets")
            item3_distractor_combos.append(tuple(sorted(distractors3)))

            it1 = items_by_num[1]
            if it1["options"][it1["correct_index"]] != f"It teaches a skill that {s['role']['title']} job ads ask for":
                errors.append(f"{pid}/C{i}/item1: unexpected correct option {it1['options'][it1['correct_index']]!r}")

            it4 = items_by_num[4]
            if it4["options"][it4["correct_index"]] != "Yes":
                errors.append(f"{pid}/C{i}/item4: correct option should be 'Yes'")

        if len(set(item2_distractor_combos)) != len(item2_distractor_combos):
            errors.append(f"{pid}: item2 distractor combination repeats across C1-C3: {item2_distractor_combos}")
        if len(set(item3_distractor_combos)) != len(item3_distractor_combos):
            errors.append(f"{pid}: item3 distractor combination repeats across C1-C3: {item3_distractor_combos}")

    return not errors, errors


_SKILL_ID_CACHE: dict[tuple[str, str], str | None] = {}


def _skill_id_by_name(out_dir: Path, job_id: str, name: str) -> str | None:
    key = (job_id, name)
    if key in _SKILL_ID_CACHE:
        return _SKILL_ID_CACHE[key]
    triples = _load_json(out_dir / "kg" / "triples.json")
    entities = _load_json(out_dir / "kg" / "entities.json")
    name_by_id = {sk["id"]: sk["name"] for sk in entities["skills"]}
    result = None
    for t in triples:
        if t["relation"] == "requires" and t["head"] == job_id and name_by_id.get(t["tail"]) == name:
            result = t["tail"]
            break
    _SKILL_ID_CACHE[key] = result
    return result


# ---------------------------------------------------------------------------
# §12.8 wording: banned words / no digits from confidence values
# ---------------------------------------------------------------------------


def _course_strings(course: dict) -> list[tuple[str, str]]:
    out = [
        (f"courses[{course['id']}].title", course["title"]),
        (f"courses[{course['id']}].meta_line", course["meta_line"]),
        (f"courses[{course['id']}].meta_no_duration", course["meta_no_duration"]),
        (f"courses[{course['id']}].dur", course["dur"]),
        (f"courses[{course['id']}].badge", course["badge"]),
        (f"courses[{course['id']}].covers_line", course["covers_line"]),
        (f"courses[{course['id']}].rules_matched", course["rules_matched"]),
        (f"courses[{course['id']}].description", course["description"]),
    ]
    for i, lo in enumerate(course["learning_outcomes"]):
        out.append((f"courses[{course['id']}].learning_outcomes[{i}]", lo))
    return out


def _explanation_strings(cs_id: str, explanation: dict) -> list[tuple[str, str]]:
    out = [(f"{cs_id}.summary", explanation["summary"])]
    a = explanation["A"]
    out.append((f"{cs_id}.A.panel_prose", a["panel_prose"]))
    for i, b in enumerate(a["detail_bullets"]):
        out.append((f"{cs_id}.A.detail_bullets[{i}]", b["text"]))
    out.append((f"{cs_id}.A.card_reason", a["card_reason"]))
    b_ = explanation["B"]
    out.append((f"{cs_id}.B.card_path", b_["card_path"]))
    for n in b_["nodes"]:
        out.append((f"{cs_id}.B.nodes[{n['id']}].label", n["label"]))
    for i, e in enumerate(b_["edges"]):
        out.append((f"{cs_id}.B.edges[{i}].label", e["label"]))
        out.append((f"{cs_id}.B.edges[{i}].source_label", e["source_label"]))
    for i, legend in enumerate(b_["legend"]):
        out.append((f"{cs_id}.B.legend[{i}]", legend))
    c_ = explanation["C"]
    out.append((f"{cs_id}.C.header", c_["header"]))
    out.append((f"{cs_id}.C.footnote", c_["footnote"]))
    for r in c_["rules_matched"]:
        out.append((f"{cs_id}.C.rules[{r['ui_label']}].name", r["name"]))
        for i, cond in enumerate(r["conditions"]):
            out.append((f"{cs_id}.C.rules[{r['ui_label']}].conditions[{i}].label", cond["label"]))
            out.append((f"{cs_id}.C.rules[{r['ui_label']}].conditions[{i}].value", cond["value"]))
            out.append((f"{cs_id}.C.rules[{r['ui_label']}].conditions[{i}].source_text", cond["source_text"]))
    return out


def _ui_strings(ui: dict) -> list[tuple[str, str]]:
    out = [("ui.role_bar", ui["role_bar"]), ("ui.sort_line", ui["sort_line"])]
    for i, chip in enumerate(ui["based_on_chips"]):
        out.append((f"ui.based_on_chips[{i}]", chip))
    return out


def check_wording(out_dir: Path) -> tuple[bool, list[str]]:
    errors = []

    def scan(pid, pairs):
        for field_path, text in pairs:
            for pattern in BANNED_WORD_PATTERNS:
                if pattern.search(text):
                    errors.append(f"{pid}/{field_path}: banned word {pattern.pattern!r} in {text!r}")
            if CONFIDENCE_SHAPED_NUMBER.search(text):
                errors.append(f"{pid}/{field_path}: confidence-shaped number in {text!r}")

    for pid in ALL_IDS:
        for s in _load_participant_sets(out_dir, pid):
            pairs = list(_ui_strings(s["ui"])) + list(_explanation_strings(s["content_set"], s["explanation"]))
            for c in s["courses"] + s["alternates"]:
                pairs.extend(_course_strings(c))
                if "explanation" in c:
                    pairs.extend(_explanation_strings(f"{s['content_set']}/{c['id']}", c["explanation"]))
            scan(pid, pairs)

    # W0 courses are plain Course.to_dict() (spec §9: no badge/meta_line/etc. --
    # W0 never goes through generate.py's course_card() enrichment), so only
    # scan the base fields that actually exist.
    w0 = _load_json(out_dir / "sets" / "W0.json")
    pairs = []
    for c in w0["courses"]:
        pairs.append((f"courses[{c['id']}].title", c["title"]))
        pairs.append((f"courses[{c['id']}].description", c["description"]))
        for i, lo in enumerate(c["learning_outcomes"]):
            pairs.append((f"courses[{c['id']}].learning_outcomes[{i}]", lo))
    scan("W0", pairs)

    return not errors, errors


# ---------------------------------------------------------------------------
# §12.9 privacy/realism -- blocklist
# ---------------------------------------------------------------------------


def _blocklist_terms() -> list[str]:
    path = REPO_ROOT / "config" / "blocklist.txt"
    return [line.strip() for line in path.read_text().splitlines() if line.strip() and not line.strip().startswith("#")]


def check_blocklist(out_dir: Path) -> tuple[bool, list[str]]:
    errors = []
    terms = _blocklist_terms()
    patterns = [(t, re.compile(r"\b" + re.escape(t) + r"\b", re.IGNORECASE)) for t in terms]
    text_files = (
        list((out_dir / "sets").glob("*.json"))
        + list((out_dir / "review").glob("*.md"))
        + list((out_dir / "ground_truth").glob("*.json"))
        + list((out_dir / "qualtrics").glob("*.csv"))
        + [out_dir / "README.md", out_dir / "kg" / "entities.json"]
    )
    for path in text_files:
        if not path.exists():
            continue
        content = path.read_text()
        for term, pattern in patterns:
            if pattern.search(content):
                errors.append(f"{path.relative_to(out_dir)}: blocklisted term {term!r} found")
    return not errors, errors


# ---------------------------------------------------------------------------
# §12.10 order: each variant in each position exactly 3 times across P1-P9
# ---------------------------------------------------------------------------


def check_order(out_dir: Path) -> tuple[bool, list[str]]:
    errors = []
    order_cfg = _load_order_cfg()
    counts = {}
    for pid in PARTICIPANT_IDS:
        order = order_cfg[pid]
        if len(order) != 3 or sorted(order) != ["A", "B", "C"]:
            errors.append(f"{pid}: order.yaml entry {order!r} isn't a permutation of A/B/C")
            continue
        for position, variant in enumerate(order, start=1):
            counts[(variant, position)] = counts.get((variant, position), 0) + 1
        for i, s_cs in zip((1, 2, 3), _load_participant_sets(out_dir, pid)):
            if s_cs["position"] != i or s_cs["variant"] != order[i - 1]:
                errors.append(f"{pid}/C{i}: stored position/variant ({s_cs['position']}/{s_cs['variant']}) != order.yaml ({i}/{order[i - 1]})")
    for variant in "ABC":
        for position in (1, 2, 3):
            n = counts.get((variant, position), 0)
            if n != 3:
                errors.append(f"variant {variant} at position {position} appears {n} times across P1-P9, expected 3")
    return not errors, errors


# ---------------------------------------------------------------------------
# §12.11 determinism
# ---------------------------------------------------------------------------


def check_determinism(out_dir: Path, seed: int, participants: str) -> tuple[bool, list[str]]:
    errors = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp) / "rerun"
        subprocess.run(
            [sys.executable, str(HERE / "generate.py"), "--seed", str(seed), "--participants", participants, "--out", str(tmp_dir)],
            check=True,
            cwd=str(HERE),
        )
        original_files = sorted(p.relative_to(out_dir) for p in out_dir.rglob("*") if p.is_file())
        rerun_files = sorted(p.relative_to(tmp_dir) for p in tmp_dir.rglob("*") if p.is_file())
        if original_files != rerun_files:
            errors.append(f"file sets differ: only-in-original={set(original_files) - set(rerun_files)}, only-in-rerun={set(rerun_files) - set(original_files)}")
            return not errors, errors
        for rel in original_files:
            if (out_dir / rel).read_bytes() != (tmp_dir / rel).read_bytes():
                errors.append(f"{rel}: differs between original run and same-seed rerun")
    return not errors, errors


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", default=str(REPO_ROOT / "data" / "synthetic"))
    parser.add_argument("--seed", type=int, default=2026, help="seed to assume was used for --dir, for the determinism check")
    parser.add_argument("--participants", default="all", help="participants to assume were generated into --dir")
    parser.add_argument("--skip-determinism", action="store_true", help="skip the (slower) determinism re-run check")
    args = parser.parse_args()

    out_dir = Path(args.dir)
    if not out_dir.is_absolute():
        out_dir = REPO_ROOT / out_dir

    checks = [
        ("schema_and_ranges", lambda: check_schema_and_ranges(out_dir)),
        ("evidence", lambda: check_evidence(out_dir)),
        ("skill_distribution", lambda: check_skill_distribution(out_dir)),
        ("content_sets", lambda: check_content_sets(out_dir)),
        ("cross_variant_consistency", lambda: check_cross_variant_consistency(out_dir)),
        ("per_course_explanations", lambda: check_per_course_explanations(out_dir)),
        ("rules_recount", lambda: check_rules_recount(out_dir)),
        ("comprehension", lambda: check_comprehension(out_dir)),
        ("wording", lambda: check_wording(out_dir)),
        ("blocklist", lambda: check_blocklist(out_dir)),
        ("order", lambda: check_order(out_dir)),
    ]
    if not args.skip_determinism:
        checks.append(("determinism", lambda: check_determinism(out_dir, args.seed, args.participants)))

    all_ok = True
    for name, fn in checks:
        ok, errors = fn()
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {name}")
        for e in errors[:20]:
            print(f"    - {e}")
        if len(errors) > 20:
            print(f"    ... and {len(errors) - 20} more")
        all_ok = all_ok and ok

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
