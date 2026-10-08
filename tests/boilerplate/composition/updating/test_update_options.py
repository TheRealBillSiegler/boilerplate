"""The defaults of a layer update's run options."""

from boilerplate.composition.updating import ScopedWorker, UpdateOptions


class TestUpdateOptions:
    def test_defaults_skip_tasks_and_silence_copier(self) -> None:
        options = UpdateOptions()

        assert (options.skip_tasks, options.quiet) == (True, True)

    def test_default_worker_renders_under_per_ref_views(self) -> None:
        assert UpdateOptions().worker_type is ScopedWorker
