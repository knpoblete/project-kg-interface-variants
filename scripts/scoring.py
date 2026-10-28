"""path_score / course_score / top-4 recommended_list (spec §4.3). Pure
functions: no I/O, no randomness -- determinism for these lives entirely in
the confidences roles_data.py hands in.
"""

from __future__ import annotations

from models import Course


def path_score(requires_conf: float, teaches_conf: float) -> float:
    return round(requires_conf * teaches_conf, 6)


def course_score(taught: list[tuple[str, float, float]]) -> float:
    """taught: (skill_id, requires_conf, teaches_conf) for this course's skills that
    the job also requires. course_score = sum of the top-2 path_scores (spec §4.3)."""
    scores = sorted((path_score(r, t) for _, r, t in taught), reverse=True)
    return round(sum(scores[:2]), 6)


def _updated_sort_key(updated: str) -> tuple[int, int]:
    year, month = updated.split("-")
    return (int(year), int(month))


def recommended_list(courses: list[Course], scores: dict[str, float], top_n: int = 4) -> list[Course]:
    """Sort desc by course_score, ties broken by `updated` (newer first), top N kept."""

    def key(course: Course):
        return (-scores.get(course.id, 0.0), -_updated_sort_key(course.updated)[0] * 12 - _updated_sort_key(course.updated)[1])

    return sorted(courses, key=key)[:top_n]
