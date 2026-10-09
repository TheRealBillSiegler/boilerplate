"""The layers a paused walk finished, read back from their answers files."""

from pathlib import Path

from boilerplate.composition.updating.walk.paused_layers import paused_layers

TARGETS = {"core": "1.1.0", "service": "1.2.0", "app": "1.1.0"}


def record(project: Path, layer: str, commit: str) -> None:
    (project / f".copier-answers.{layer}.yml").write_text(
        f"_commit: {commit}\n_src_path: /repos/{layer}\n", encoding="utf-8"
    )


class TestPausedLayers:
    def test_names_the_layers_at_their_target_in_walk_order(
        self, tmp_path: Path
    ) -> None:
        """Count a layer as finished when its answers file records its target."""
        record(tmp_path, "core", "1.1.0")
        record(tmp_path, "service", "1.2.0")
        record(tmp_path, "app", "1.0.0")

        assert paused_layers(tmp_path, TARGETS) == ("core", "service")

    def test_skips_an_answers_file_that_does_not_parse(self, tmp_path: Path) -> None:
        """Leave out a layer whose answers file conflict markers broke."""
        record(tmp_path, "core", "1.1.0")
        (tmp_path / ".copier-answers.service.yml").write_text(
            "<<<<<<< before\n_commit: 1.0.0\n=======\n", encoding="utf-8"
        )

        assert paused_layers(tmp_path, TARGETS) == ("core",)
