"""Comprehension-check items + Qualtrics export (spec §8). P1-P9 only -- D0
is a demo and W0 has no explanations to check comprehension of.

Spec §8's "no distractor repeats across a participant's C1-C3" is under-
specified for a role with only 4 requires>=0.40 skills outside the 6 used as
main/secondary (exactly the filler pool each role has, spec §5.1's 4-6
strong/4-6 weak band leaves little headroom for more without crowding the
skill list). This module's reading, flagged in the generated README/review
sheets for Katherine to confirm: no identical 3-distractor combination is
reused for the SAME item number (2 or 3) across a participant's three rounds
-- not that every one of the up to 18 distractor slots must be a globally
unique skill, which isn't achievable within spec §5.1's skill budget.
"""

from __future__ import annotations

import hashlib
import random

from content_sets import ContentSet
from roles_data import ExpandedRole

ITEM1_QUESTION = "Why was this course recommended to you?"
ITEM1_WRONG_OPTIONS = [
    "It's similar to courses you've viewed before",
    "It's popular with other learners",
    "It's new or recently updated",
    "Not sure",
]
ITEM2_QUESTION = "Which skill was the recommendation mainly based on?"
ITEM3_QUESTION = "Was there a secondary reason? If so, which skill?"
ITEM3_NO_SECONDARY = "No secondary reason"
ITEM4_QUESTION_TEMPLATE = "If this course did not cover {secondary}, would it still be recommended?"
ITEM4_OPTIONS = ["Yes", "No", "Not sure"]

# The filler-skill pool (spec §5.1's "enough skills ... plus distractors for
# the comprehension check") -- the only skills a role requires (>=0.40) that
# are never a main/secondary skill in any of the participant's content sets.
FILLER_SLOTS = ["strongfiller1", "strongfiller2", "weakfiller1", "weakfiller2"]


def _seeded_rng(seed: int, participant_id: str, content_set_id: str, item: int) -> random.Random:
    digest = hashlib.sha256(f"{seed}:{participant_id}:{content_set_id}:item{item}".encode()).hexdigest()
    return random.Random(int(digest, 16) % (2**32))


def _shuffle_with_correct(seed, participant_id, content_set_id, item, options, correct_value):
    rng = _seeded_rng(seed, participant_id, content_set_id, item)
    shuffled = options[:]
    rng.shuffle(shuffled)
    return shuffled, shuffled.index(correct_value)


def _distractor_names(expanded: ExpandedRole, content_set_num: int, item: int) -> list[str]:
    offset = ((content_set_num - 1) + (0 if item == 2 else 2)) % 4
    rotated = FILLER_SLOTS[offset:] + FILLER_SLOTS[:offset]
    return [expanded.skill_name_by_slot[s] for s in rotated[:3]]


def build_items(seed: int, participant_id: str, cs: ContentSet, expanded: ExpandedRole, role_title: str) -> list[dict]:
    content_set_num = int(cs.content_set_id[1:])
    items = []

    options1 = [f"It teaches a skill that {role_title} job ads ask for", *ITEM1_WRONG_OPTIONS]
    shuffled1, correct1 = _shuffle_with_correct(seed, participant_id, cs.content_set_id, 1, options1, options1[0])
    items.append({"item": 1, "question": ITEM1_QUESTION, "options": shuffled1, "correct_index": correct1})

    options2 = [cs.main.skill_name, *_distractor_names(expanded, content_set_num, 2)]
    shuffled2, correct2 = _shuffle_with_correct(seed, participant_id, cs.content_set_id, 2, options2, cs.main.skill_name)
    items.append({"item": 2, "question": ITEM2_QUESTION, "options": shuffled2, "correct_index": correct2})

    options3 = [ITEM3_NO_SECONDARY, cs.secondary.skill_name, *_distractor_names(expanded, content_set_num, 3)]
    shuffled3, correct3 = _shuffle_with_correct(seed, participant_id, cs.content_set_id, 3, options3, cs.secondary.skill_name)
    items.append({"item": 3, "question": ITEM3_QUESTION, "options": shuffled3, "correct_index": correct3})

    question4 = ITEM4_QUESTION_TEMPLATE.format(secondary=cs.secondary.skill_name)
    shuffled4, correct4 = _shuffle_with_correct(seed, participant_id, cs.content_set_id, 4, ITEM4_OPTIONS, "Yes")
    items.append({"item": 4, "question": question4, "options": shuffled4, "correct_index": correct4})

    return items


def ground_truth_payload(participant_id: str, cs: ContentSet, items: list[dict]) -> dict:
    return {"participant_id": participant_id, "content_set": cs.content_set_id, "items": items}


def qualtrics_rows(participant_id: str, cs: ContentSet, items: list[dict]) -> list[dict]:
    rows = []
    for it in items:
        row = {
            "participant_id": participant_id,
            "content_set": cs.content_set_id,
            "item": it["item"],
            "question": it["question"],
            "correct_index": it["correct_index"],
        }
        for i in range(5):
            row[f"option_{i + 1}"] = it["options"][i] if i < len(it["options"]) else ""
        rows.append(row)
    return rows
