"""Build the view a layer renders under from a composition.

A composition rooted at a layer holds that layer and its ancestors, so its
merged questionnaire and importable extension union is the layer's *scoped*
view; rooted at the composition's final layer, it is the *full* view.
"""

from collections.abc import Sequence
from pathlib import PurePosixPath

from boilerplate.composition.models.composition import Composition
from boilerplate.composition.models.composition_layer import CompositionLayer
from boilerplate.composition.views.ancestor_extension import AncestorExtension
from boilerplate.composition.views.extension_module_name import extension_module_name
from boilerplate.composition.views.layer_view import LayerView


def is_layer_local_extension(spec: str) -> bool:
    """Return whether a ``_jinja_extensions`` entry only works in its own layer.

    ``copier_template_extensions`` accepts filepath-style loader specs
    (``_extensions/context.py:ContextUpdater``) that it resolves relative to
    the rendering template's directory — such a spec cannot be shared with a
    sibling layer whose tree lacks the file. Importable specs (a dotted
    module path, with or without a ``:ClassName`` suffix) resolve identically
    from any layer and are safe to share.

    Args:
        spec: One ``_jinja_extensions`` list entry.

    Returns:
        True when the module portion is not a plain dotted import path.

    Examples:
        >>> is_layer_local_extension("_extensions/context.py:ContextUpdater")
        True
        >>> is_layer_local_extension(
        ...     "copier_template_extensions.TemplateExtensionLoader"
        ... )
        False
        >>> is_layer_local_extension("pkg.module.slugify:SlugifyExtension")
        False
    """
    module_part = spec.split(":", 1)[0]
    return not all(part.isidentifier() for part in module_part.split("."))


def _ancestor_extensions(layer: CompositionLayer) -> tuple[AncestorExtension, ...]:
    """Return the file-path extension specs `layer` declares, as release files."""
    raw = layer.values.get("_jinja_extensions")
    specs = [str(e) for e in raw] if isinstance(raw, list) else []
    found: list[AncestorExtension] = []
    for spec in specs:
        if not is_layer_local_extension(spec):
            continue
        file, _, class_name = spec.partition(":")
        relative = PurePosixPath(file).as_posix()
        found.append(
            AncestorExtension(
                layer=layer.name,
                release=layer.version,
                path=layer.path / relative,
                module=extension_module_name(layer.name, layer.version, relative),
                class_name=class_name or None,
            )
        )
    return tuple(found)


def build_layer_view(composition: Composition) -> LayerView:
    """Return the merged view of `composition`.

    Args:
        composition: A composition resolved and composed from the layer whose
            view is wanted.

    Returns:
        The merged questions and the importable extension union, and the
        file-path extension specs of every layer but the last as the files at
        their releases; the last layer's own file-path specs are left to
        Copier.
    """
    raw = composition.final.get("_jinja_extensions")
    extensions = (
        tuple(str(e) for e in raw if not is_layer_local_extension(str(e)))
        if isinstance(raw, list)
        else ()
    )
    ancestor_extensions = tuple(
        extension
        for layer in composition.layers[:-1]
        for extension in _ancestor_extensions(layer)
    )
    return LayerView(
        dict(composition.merged_questions_schema), extensions, ancestor_extensions
    )


def view_config(
    view: LayerView, extra: Sequence[str] = (), **config: object
) -> dict[str, object]:
    """Return `config` with the view's extensions, then `extra`, as Jinja extensions.

    The ancestors' registered file-path extensions come between the view's
    importable ones and `extra`; the render must register them
    (``registered_ancestor_extensions``) for the specs to import.

    Args:
        view: The view whose importable and ancestor extensions apply.
        extra: Further extension specs, appended after the view's.
        **config: Template configuration to carry through unchanged.

    Returns:
        `config`, plus a ``jinja_extensions`` entry when any extension applies.

    Examples:
        >>> view_config(LayerView({}, ("pkg.mod:Ext",)), ("other.mod",), tasks=[])
        {'tasks': [], 'jinja_extensions': ['pkg.mod:Ext', 'other.mod']}
        >>> view_config(LayerView({}, ()))
        {}
    """
    extensions = [
        *view.extensions,
        *(extension.spec for extension in view.ancestor_extensions),
        *extra,
    ]
    if extensions:
        config["jinja_extensions"] = extensions
    return config
