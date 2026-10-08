"""What one run of the update walk works on."""

from dataclasses import dataclass
from pathlib import Path

from boilerplate.composition.updating.update_request import UpdateRequest
from boilerplate.composition.updating.walk.walk_plan import WalkPlan
from boilerplate.repository.release_checkouts import ReleaseCheckouts


@dataclass(frozen=True)
class WalkInputs:
    """The project, the request, the plan made for it and the checkouts it reads.

    Attributes:
        project: The user's checkout.
        request: What the user asked of the update.
        plan: What the pre-walk checks decided.
        checkouts: The release checkouts the plan's views read, kept for the
            lock written at the end.
    """

    project: Path
    request: UpdateRequest
    plan: WalkPlan
    checkouts: ReleaseCheckouts
