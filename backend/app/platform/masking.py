"""Field-level masking, applied when a row is serialized.

The unmasked value never leaves the process for a caller who is not allowed to
see it, so there is nothing for the frontend to accidentally render.
"""

from app.platform.identity import Identity

MASKED_SSN = "***-**-****"


def mask_ssn(ssn: str | None) -> str | None:
    """``900-12-3456`` becomes ``***-**-3456``; the last four stay visible so a
    reviewer can still match a document against a record."""
    if not ssn:
        return ssn
    digits = [c for c in ssn if c.isdigit()]
    if len(digits) < 4:
        return MASKED_SSN
    return f"***-**-{''.join(digits[-4:])}"


def can_see_ssn(identity: Identity) -> bool:
    """Compliance seniors only.

    Deliberately not "level is senior": the admin is also a senior, and
    DESIGN.md §5 gives admin no customer data at all.
    """
    return identity.in_group("compliance", "senior")


def ssn_for(identity: Identity, ssn: str | None) -> str | None:
    return ssn if can_see_ssn(identity) else mask_ssn(ssn)
