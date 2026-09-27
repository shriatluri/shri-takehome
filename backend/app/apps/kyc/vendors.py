"""Mock vendors: deterministic functions over the seeded data, not clients.

Nothing here reaches the network. The IDV "vendor" is a lookup keyed by the
document quality the submitter picked, and sanctions screening is a name
comparison against the `sanctions_list` table.
"""

from dataclasses import dataclass
from difflib import SequenceMatcher

from sqlalchemy import text
from sqlalchemy.orm import Session

# DESIGN.md §7: Clear -> Passed, Blurry -> Needs review, Fake -> Failed.
IDV_VERDICTS: dict[str, tuple[str, str]] = {
    "Clear": ("Passed", "Document clear"),
    "Blurry": ("Needs review", "Document image blurry"),
    "Fake": ("Failed", "Document detected as fake"),
}


@dataclass(frozen=True)
class IdvResult:
    status: str
    reason: str


@dataclass(frozen=True)
class SanctionsMatch:
    entry_id: int
    matched_name: str
    similarity: int


def check_identity(document_quality: str) -> IdvResult:
    status, reason = IDV_VERDICTS[document_quality]
    return IdvResult(status=status, reason=reason)


def _normalize(name: str) -> str:
    return "".join(c for c in name.lower() if c.isalnum() or c.isspace())


def _similarity(left: str, right: str) -> int:
    """0-100 on the two names, case- and punctuation-insensitive.

    `SequenceMatcher` from the standard library rather than a matching library:
    the demo needs a near-miss like "Casey Lindqvist" to hit "Casey Lindquist",
    and a single ratio compared against `sanctions_match_threshold` is enough
    to show a threshold the admin can move.
    """
    return round(SequenceMatcher(None, _normalize(left), _normalize(right)).ratio() * 100)


def screen_sanctions(session: Session, full_name: str, threshold: int) -> SanctionsMatch | None:
    """The closest entry at or above the threshold, comparing name and aliases."""
    rows = session.execute(text("SELECT id, full_name, aliases FROM sanctions_list")).mappings()

    best: SanctionsMatch | None = None
    for row in rows:
        for candidate in [row["full_name"], *row["aliases"]]:
            similarity = _similarity(full_name, candidate)
            if similarity >= threshold and (best is None or similarity > best.similarity):
                best = SanctionsMatch(
                    entry_id=row["id"], matched_name=candidate, similarity=similarity
                )
    return best
