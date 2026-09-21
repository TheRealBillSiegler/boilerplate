"""Tests for boilerplate.cli.seams."""

from boilerplate.cli.seams import Seams
from boilerplate.composition.rendering.engine import RenderEngine


class TestSeams:
    """`Seams`'s default `renderer` factory."""

    def test_the_default_renderer_is_the_copier_engine(self) -> None:
        """With no injection the CLI drives Copier.

        Fails if the default factory changes.
        """
        assert isinstance(Seams().renderer, RenderEngine)
