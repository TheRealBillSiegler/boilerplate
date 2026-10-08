"""A resolution whose layers apply in an order the caller fixes."""

from boilerplate.composition.resolution.models.resolution import Resolution


class OrderedResolution(Resolution):
    """The resolution of several roots, applied in the order a project records.

    A project that adds layers one after another has no single root to resolve
    from, and the toposort of its dependency map visits independent roots in name
    order. The project's lock already lists its layers in the order their files
    were rendered, which is the order a later render must follow.

    Attributes:
        layer_order: The layers' names in the order to apply them; each name's
            resolved specifier takes its place in ``execution_sequence``.
    """

    layer_order: tuple[str, ...]

    @property
    def execution_sequence(self) -> list[str]:
        """Sequence to apply templates: the layers, in ``layer_order``."""
        by_name = {specifier.split("@", 1)[0]: specifier for specifier in self.deps}
        return [by_name[name] for name in self.layer_order]
