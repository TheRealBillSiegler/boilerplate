"""Scope a composition to one layer and its ancestors."""
# Spec: docs/design/04-composition-engine.md §Per-Layer Render Loop

from boilerplate.composition.composer import Composer
from boilerplate.composition.graph import DependencyMap
from boilerplate.composition.models.composition import Composition
from boilerplate.composition.resolution.models import Resolution
from boilerplate.integrations.copier_types import Template
from boilerplate.models.template_info import TemplateInfo
from boilerplate.models.template_meta import TemplateMeta


def _ancestor_specifiers(composition: Composition, specifier: str) -> set[str]:
    """Return `specifier` and every specifier its ``extends`` chain reaches."""
    reached: set[str] = set()
    pending = [specifier]
    while pending:
        current = pending.pop()
        if current not in reached:
            reached.add(current)
            pending.extend(composition.graph.edges.get(current, []))
    return reached


def scope_composition(composition: Composition, layer: str) -> Composition:
    """Return the composition rooted at `layer`: that layer and its ancestors.

    The merged questions, accumulated tasks and merged extensions of the result
    are the layer's scoped view. The layers are composed again from their
    templates, so a sibling's or a descendant's question, task or extension
    never reaches the result.

    Args:
        composition: A composition that holds `layer`.
        layer: The name of the layer whose scope is wanted.

    Returns:
        The composition of `layer` and its ancestors, in topological order.

    Raises:
        KeyError: If `layer` is not in `composition`.
    """
    nodes = composition.graph.nodes
    root = next(spec for spec, node in nodes.items() if node.name == layer)
    kept = _ancestor_specifiers(composition, root)
    templates: dict[str, TemplateInfo] = {}
    for spec in kept:
        node = nodes[spec]
        templates[spec] = TemplateInfo(
            name=node.name,
            meta=TemplateMeta.load(node.path),
            location=node.path,
            copier_template=Template(url=str(node.path)),
        )
    deps: DependencyMap = {
        spec: list(composition.graph.edges.get(spec, [])) for spec in kept
    }
    return Composer().compose(Resolution(deps=deps, templates=templates))
