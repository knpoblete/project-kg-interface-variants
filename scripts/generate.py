#!/usr/bin/env python3
"""Generate data/synthetic/ per mockups/SYNTHETIC_DATA_SPEC.md (v2, §11).

Usage:
    python scripts/generate.py --seed 2026 --out data/synthetic
    python scripts/generate.py --participants P1,P2,D0 --out /tmp/check
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import yaml

from comprehension import build_items, ground_truth_payload, qualtrics_rows
from content_sets import (
    build_content_set,
    build_explanation,
    build_explanation_for_course,
    course_display_info,
    course_rule_eligibility,
    rules_matched_label,
)
from models import Course
from roles_data import ExpandedRole, SectorRegistry, SkillRegistry, build_w0_courses, expand_role
from wording import (
    ROLE_BAR,
    based_on_chips,
    confidence_band,
    course_meta_line,
    course_meta_no_duration,
    duration_label,
    sort_line,
)

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent


def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text())


def course_taught_skills(course_id: str, expanded: ExpandedRole) -> list[dict]:
    out = []
    for (cid, sid), t in expanded.teaches_map.items():
        if cid != course_id:
            continue
        out.append(
            {
                "skill_id": sid,
                "skill_name": expanded.skill_name_by_id[sid],
                "teaches_confidence": t,
                "band": confidence_band(t),
            }
        )
    out.sort(key=lambda s: -s["teaches_confidence"])
    return out


def course_card(course: Course, expanded: ExpandedRole, explanation: dict | None = None) -> dict:
    info = course_display_info(course.id, expanded)
    card = {
        **course.to_dict(),
        "meta_line": course_meta_line(course.level, course.duration_min, course.updated),
        "dur": duration_label(course.duration_min),
        "meta_no_duration": course_meta_no_duration(course.level, course.updated),
        "badge": info["badge"],
        "covers_line": info["covers_line"],
        "rules_matched": rules_matched_label(info["eligibility"]),
        "taught_skills": course_taught_skills(course.id, expanded),
    }
    if explanation is not None:
        # Every course in a displayed list gets its own reasoned explanation --
        # beyond spec §5.4's letter (which only requires one explained course
        # per content set), so Save/Not for me are always backed by a visible
        # "why", not just the one course the spec calls out.
        card["explanation"] = explanation
    return card


def role_block(job_id, role_title, expanded, context_note):
    return {
        "job_id": job_id,
        "title": role_title,
        "sector": expanded.sector.name,
        "role_basis": expanded.role_basis,
        "context_note": context_note,
    }


def ui_block(role_title):
    return {"role_bar": ROLE_BAR, "sort_line": sort_line(role_title), "based_on_chips": based_on_chips(role_title)}


def skills_block(expanded: ExpandedRole) -> list[dict]:
    return [
        {"skill_id": sid, "name": expanded.skill_name_by_id[sid], "requires_confidence": conf, "band": confidence_band(conf)}
        for sid, conf in sorted(expanded.requires_map.items(), key=lambda kv: -kv[1])
    ]


def paths_block(cs) -> list[dict]:
    out = []
    for p in (cs.main, cs.secondary):
        out.append(
            {
                "skill_id": p.skill_id,
                "skill_name": p.skill_name,
                "which": p.which,
                "requires_confidence": p.requires_conf,
                "teaches_confidence": p.teaches_conf,
                "requires_report_id": p.requires_report_id,
                "teaches_report_id": p.teaches_report_id,
                "evidence_span": p.evidence_span,
            }
        )
    return out


# ---------------------------------------------------------------------------
# P1-P9: one file per content set
# ---------------------------------------------------------------------------


def build_participant(participant_id, role_title, job_id, context_note, seed, order, skill_registry, sector_registry):
    expanded = expand_role(participant_id, role_title, job_id, seed, skill_registry, sector_registry)
    content_sets = [build_content_set(participant_id, i, expanded) for i in (1, 2, 3)]
    course_slug_by_id = {cid: slug for slug, cid in expanded.course_id_by_slug.items()}

    set_payloads = []
    ground_truths = []
    qualtrics_all_rows = []
    for position, cs in enumerate(content_sets, start=1):
        variant = order[position - 1]
        explanation = build_explanation(role_title, cs, expanded)
        courses_by_id = {c.id: c for c in expanded.courses}
        courses_payload = [
            course_card(courses_by_id[cid], expanded, build_explanation_for_course(role_title, participant_id, cs, cid, expanded, course_slug_by_id))
            for cid in cs.course_ids
        ]
        alt_ids = [expanded.course_id_by_slug[f"c{position}_alt_a"], expanded.course_id_by_slug[f"c{position}_alt_b"]]
        alternates_payload = [course_card(courses_by_id[cid], expanded) for cid in alt_ids]
        items = build_items(seed, participant_id, cs, expanded, role_title)

        payload = {
            "participant_id": participant_id,
            "content_set": cs.content_set_id,
            "position": position,
            "variant": variant,
            "role": role_block(job_id, role_title, expanded, context_note),
            "ui": ui_block(role_title),
            "courses": courses_payload,  # position 1 = selected course
            "selected_course_id": cs.selected_course_id,
            "course_score": cs.course_score,
            "paths": paths_block(cs),
            "explanation": explanation,
            # "Other courses that teach [main skill]" (spec §5.4) -- never in
            # the list itself, only ever shown alongside the selected course.
            "alternates": alternates_payload,
        }
        set_payloads.append(payload)
        ground_truths.append(ground_truth_payload(participant_id, cs, items))
        qualtrics_all_rows.extend(qualtrics_rows(participant_id, cs, items))

    return expanded, set_payloads, ground_truths, qualtrics_all_rows


# ---------------------------------------------------------------------------
# W0: flat catalog, no job/skills/triples/explanation (spec §9)
# ---------------------------------------------------------------------------


def build_w0() -> dict:
    courses = build_w0_courses()
    return {"participant_id": "W0", "courses": [c.to_dict() for c in courses]}, courses


# ---------------------------------------------------------------------------
# Review sheet + README
# ---------------------------------------------------------------------------


def _explanation_markdown(explanation: dict) -> list[str]:
    lines = []
    lines.append(f"**Shared summary:** {explanation['summary']}")
    lines.append("")
    lines.append("**A — Natural language**")
    lines.append(f"> {explanation['A']['panel_prose']}")
    for b in explanation["A"]["detail_bullets"]:
        lines.append(f"- {b['text']}")
    lines.append(f"- Card reason: {explanation['A']['card_reason']}")
    lines.append("")
    lines.append("**B — Graph**")
    lines.append(f"- Card path: {explanation['B']['card_path']}")
    for e in explanation["B"]["edges"]:
        lines.append(f"- {e['label']} ({e['strength']}) — {e['source_label']}")
    lines.append("")
    lines.append("**C — Rule-based**")
    for r in explanation["C"]["rules_matched"]:
        lines.append(f"- {r['ui_label']} ({r['strength']}): {r['name']} — skill: {r['skill']}, also matched {r['also_matched_count']} other course(s)")
    lines.append(f"- {explanation['C']['header']}")
    return lines


def build_review_markdown_participant(participant_id, role_title, expanded, set_payloads, ground_truths) -> str:
    lines = [f"# Review sheet — {participant_id} ({role_title})", ""]
    lines.append(f"**role_basis:** {expanded.role_basis}")
    lines.append(f"**sector:** {expanded.sector.name}")
    lines.append(f"**synthetic n_ads_sampled:** {expanded.n_ads_sampled} (synthetic, not a real job-ad count)")
    lines.append("")
    lines.append("## Skills")
    lines.append("")
    lines.append("| Skill | requires confidence | band |")
    lines.append("|---|---|---|")
    for sid, conf in sorted(expanded.requires_map.items(), key=lambda kv: -kv[1]):
        lines.append(f"| {expanded.skill_name_by_id[sid]} | {conf:.2f} | {confidence_band(conf)} |")
    lines.append("")
    for set_payload, gt in zip(set_payloads, ground_truths):
        courses_by_id = {c["id"]: c for c in set_payload["courses"]}
        selected = courses_by_id[set_payload["selected_course_id"]]
        lines.append(f"## {set_payload['content_set']} — {selected['title']}")
        lines.append(f"Shown to this participant in variant **{set_payload['variant']}** (position {set_payload['position']}).")
        lines.append("List: " + ", ".join(c["title"] for c in set_payload["courses"]))
        lines.append("Alternates ('Other courses that teach...'): " + ", ".join(c["title"] for c in set_payload["alternates"]))
        lines.append("")
        lines.extend(_explanation_markdown(set_payload["explanation"]))
        lines.append("")
        lines.append("**Comprehension check**")
        for item in gt["items"]:
            correct = item["options"][item["correct_index"]]
            lines.append(f"- Item {item['item']}: {item['question']} (options: {', '.join(item['options'])}; correct: {correct})")
        lines.append("")
    lines.append("---")
    lines.append(
        "Katherine: please confirm this role's skill list and `role_basis` citation (spec §5.1 review), "
        "and extend `config/blocklist.txt` with any real names that must never appear in Session 2 "
        "materials. The comprehension-check distractor rotation (spec §8's \"no distractor repeats across "
        "C1-C3\") is implemented as described in `scripts/comprehension.py`'s module docstring — please "
        "confirm that reading is what you intended. The PIS/debrief wording about simulated data (spec "
        "§13) is still open and is not decided here."
    )
    return "\n".join(lines) + "\n"



def build_readme(seed: int, role_basis_rows: list[tuple[str, str, str]]) -> str:
    lines = [
        "# Synthetic data — Session 2 comparative study",
        "",
        "Generated by `scripts/generate.py` per `mockups/SYNTHETIC_DATA_SPEC.md` (v2). All data is "
        "simulated: the course catalog, course descriptions, and job-ad sample counts are fictional, "
        "authored/generated for this study, not scraped. The prototype's role bar reads 'real job ads' for "
        "narrative consistency with the mockups; whether the participant information sheet or debrief needs "
        "a line clarifying the data was simulated is spec §13, still open.",
        "",
        f"- Seed: `{seed}`",
        f"- Regenerate with: `python scripts/generate.py --seed {seed} --out data/synthetic`",
        "- Validate with: `python scripts/validate.py --dir data/synthetic`",
        "",
        "## role_basis (spec §5.1 — Katherine to sign off per role)",
        "",
        "| Participant | Role | Framework occupation basis |",
        "|---|---|---|",
    ]
    for pid, role_title, basis in role_basis_rows:
        lines.append(f"| {pid} | {role_title} | {basis} |")
    lines.append("")
    lines.append("## Thresholds (spec §5.2)")
    lines.append("")
    lines.append("| | Strong | Weaker | Not used |")
    lines.append("|---|---|---|---|")
    lines.append("| `requires` | >= 0.70 | 0.40-0.69 | < 0.40 |")
    lines.append("| `teaches` | >= 0.70 (main topic) | 0.40-0.69 (covered in part) | < 0.40 |")
    lines.append("")
    lines.append("## Open items (spec §13)")
    lines.append("")
    lines.append("1. Role/order allocation: confirmed — see `config/participants.yaml` / `config/order.yaml`.")
    lines.append("2. No deliberately-wrong reasons: every reason in every content set is plausible by construction.")
    lines.append(
        "3. Comprehension-check distractor rotation (spec §8): implemented per `scripts/comprehension.py`'s "
        "documented reading of \"no distractor repeats across C1-C3\" — flagged for Katherine to confirm."
    )
    lines.append("4. **Still open:** PIS/debrief wording about simulated data. Not built here.")
    lines.append("")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--participants", default="all", help="comma-separated participant IDs, or 'all'")
    parser.add_argument("--out", default=str(REPO_ROOT / "data" / "synthetic"))
    args = parser.parse_args()

    out_dir = Path(args.out)
    if not out_dir.is_absolute():
        out_dir = REPO_ROOT / out_dir

    participants_cfg = load_yaml(REPO_ROOT / "config" / "participants.yaml")
    order_cfg = load_yaml(REPO_ROOT / "config" / "order.yaml")

    if args.participants == "all":
        participant_ids = list(participants_cfg.keys())
    else:
        participant_ids = [p.strip() for p in args.participants.split(",") if p.strip()]

    skill_registry = SkillRegistry()
    sector_registry = SectorRegistry()

    for sub in ("kg", "sets", "ground_truth", "qualtrics", "review"):
        (out_dir / sub).mkdir(parents=True, exist_ok=True)

    all_jobs = []
    all_courses = []
    all_triples = []
    role_basis_rows = []

    for pid in participant_ids:
        cfg = participants_cfg[pid]

        if pid == "W0":
            payload, courses = build_w0()
            all_courses.extend(courses)
            (out_dir / "sets" / "W0.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
            continue

        role_title = cfg["role_title"]
        job_id = cfg["job_id"]
        context_note = cfg.get("context_note", "")
        order = order_cfg[pid]

        expanded, set_payloads, ground_truths, qualtrics_all_rows = build_participant(
            pid, role_title, job_id, context_note, args.seed, order, skill_registry, sector_registry
        )
        all_jobs.append(expanded.job)
        all_courses.extend(expanded.courses)
        all_triples.extend(expanded.triples)
        role_basis_rows.append((pid, role_title, expanded.role_basis))

        for set_payload in set_payloads:
            fname = f"{pid}-{set_payload['content_set']}.json"
            (out_dir / "sets" / fname).write_text(json.dumps(set_payload, indent=2, ensure_ascii=False) + "\n")
        for gt in ground_truths:
            fname = f"{pid}-{gt['content_set']}.json"
            (out_dir / "ground_truth" / fname).write_text(json.dumps(gt, indent=2, ensure_ascii=False) + "\n")

        with (out_dir / "qualtrics" / f"{pid}.csv").open("w", newline="") as f:
            fieldnames = ["participant_id", "content_set", "item", "question", "option_1", "option_2", "option_3", "option_4", "option_5", "correct_index"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in qualtrics_all_rows:
                writer.writerow(row)

        (out_dir / "review" / f"{pid}-review.md").write_text(
            build_review_markdown_participant(pid, role_title, expanded, set_payloads, ground_truths)
        )

    entities = {
        "jobs": [j.to_dict() for j in sorted(all_jobs, key=lambda j: j.id)],
        "skills": [s.to_dict() for s in skill_registry.all()],
        "sectors": [s.to_dict() for s in sector_registry.all()],
        "courses": [c.to_dict() for c in sorted(all_courses, key=lambda c: c.id)],
    }
    (out_dir / "kg" / "entities.json").write_text(json.dumps(entities, indent=2, ensure_ascii=False) + "\n")

    with (out_dir / "kg" / "triples.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["head", "relation", "tail", "confidence"])
        writer.writeheader()
        for t in all_triples:
            writer.writerow(t.to_csv_row())
    (out_dir / "kg" / "triples.json").write_text(
        json.dumps([t.to_dict() for t in all_triples], indent=2, ensure_ascii=False) + "\n"
    )

    if role_basis_rows:
        (out_dir / "README.md").write_text(build_readme(args.seed, role_basis_rows))

    print(f"Generated synthetic data for {len(participant_ids)} participant(s) -> {out_dir}")


if __name__ == "__main__":
    main()
