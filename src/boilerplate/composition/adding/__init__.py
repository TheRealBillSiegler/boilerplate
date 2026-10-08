"""Adding: the pieces that add one template layer to a composed project."""

from boilerplate.composition.adding.add_outcome import AddOutcome
from boilerplate.composition.adding.add_request import AddRequest
from boilerplate.composition.adding.add_status import AddStatus
from boilerplate.composition.adding.layer_adder import LayerAdder

__all__ = [
    "AddOutcome",
    "AddRequest",
    "AddStatus",
    "LayerAdder",
]
