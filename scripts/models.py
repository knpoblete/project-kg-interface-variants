"""Entity/triple dataclasses matching spec §3 of mockups/SYNTHETIC_DATA_SPEC.md field-for-field."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Sector:
    id: str
    name: str

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name}


@dataclass
class Job:
    id: str
    title: str
    sector_id: str
    role_basis: str = ""

    def to_dict(self) -> dict:
        return {"id": self.id, "title": self.title, "sector_id": self.sector_id, "role_basis": self.role_basis}


@dataclass
class Skill:
    id: str
    name: str
    aliases: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "aliases": list(self.aliases)}


@dataclass
class Course:
    id: str
    title: str
    level: str  # Beginner | Intermediate | Advanced
    duration_min: int
    updated: str  # YYYY-MM, within the last 18 months
    description: str
    learning_outcomes: list[str]  # exactly 4
    # Constant on every course (spec §4.1) so they can't confound the comparison.
    provider: str = "[Learning platform]"
    instructor: str = "[Instructor name]"
    certificate: bool = True
    thumbnail: None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "level": self.level,
            "duration_min": self.duration_min,
            "updated": self.updated,
            "description": self.description,
            "learning_outcomes": list(self.learning_outcomes),
            "provider": self.provider,
            "instructor": self.instructor,
            "certificate": self.certificate,
            "thumbnail": self.thumbnail,
        }


@dataclass
class Triple:
    head: str
    relation: str  # requires | teaches | in_sector
    tail: str
    confidence: float
    provenance: dict = field(default_factory=dict)

    def to_csv_row(self) -> dict:
        return {"head": self.head, "relation": self.relation, "tail": self.tail, "confidence": self.confidence}

    def to_dict(self) -> dict:
        return {
            "head": self.head,
            "relation": self.relation,
            "tail": self.tail,
            "confidence": self.confidence,
            "provenance": self.provenance,
        }
