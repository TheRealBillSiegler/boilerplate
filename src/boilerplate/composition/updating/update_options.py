"""How an update of one layer runs."""

from pydantic import BaseModel, ConfigDict

from boilerplate.composition.updating.scoped_worker import ScopedWorker


class UpdateOptions(BaseModel):
    """The knobs of a layer update that do not change what it renders.

    Attributes:
        skip_tasks: Whether to skip the layer's own post-generation tasks.
        quiet: Whether to silence Copier's progress output.
        interactive: Whether the layer's step prompts for its own questions,
            with the recorded answer as the default, as ``copier update`` does;
            otherwise every question takes its default.
        skip_answered: Whether the step asks only the questions no answers
            file records; Copier's ``skip_answered``.
        worker_type: The worker class to update with.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    skip_tasks: bool = True
    quiet: bool = True
    interactive: bool = False
    skip_answered: bool = False
    worker_type: type[ScopedWorker] = ScopedWorker
