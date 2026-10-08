"""How an update of one layer runs."""

from pydantic import BaseModel, ConfigDict

from boilerplate.composition.updating.scoped_worker import ScopedWorker


class UpdateOptions(BaseModel):
    """The knobs of a layer update that do not change what it renders.

    Attributes:
        skip_tasks: Whether to skip the layer's own post-generation tasks.
        quiet: Whether to silence Copier's progress output.
        worker_type: The worker class to update with.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    skip_tasks: bool = True
    quiet: bool = True
    worker_type: type[ScopedWorker] = ScopedWorker
