"""What one run of an add works on."""

from dataclasses import dataclass
from pathlib import Path

from boilerplate.composition.adding.add_plan import AddPlan
from boilerplate.composition.adding.add_request import AddRequest
from boilerplate.repository.release_checkouts import ReleaseCheckouts


@dataclass(frozen=True)
class AddInputs:
    """The project, the request, the plan made for it and the checkouts it reads.

    Attributes:
        project: The user's checkout.
        request: What the user asked of the add.
        plan: What the pre-staging checks decided.
        checkouts: The release checkouts the plan's view reads, kept for the lock
            written at the end.
    """

    project: Path
    request: AddRequest
    plan: AddPlan
    checkouts: ReleaseCheckouts
