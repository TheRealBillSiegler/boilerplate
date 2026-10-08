"""Build the view a layer renders under from a composition.

A composition rooted at a layer holds that layer and its ancestors, so its
merged questionnaire and importable extension union is the layer's *scoped*
view; rooted at the composition's final layer, it is the *full* view.
"""

from collections.abc import Sequence

from boilerplate.composition.models.composition import Composition
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


def build_layer_view(composition: Composition) -> LayerView:
    """Return the merged view of `composition`.

    Args:
        composition: A composition resolved and composed from the layer whose
            view is wanted.

    Returns:
        The merged questions and the importable extension union; filepath-style
        extension specs are left out.
    """
    raw = composition.final.get("_jinja_extensions")
    extensions = (
        tuple(str(e) for e in raw if not is_layer_local_extension(str(e)))
        if isinstance(raw, list)
        else ()
    )
    return LayerView(dict(composition.merged_questions_schema), extensions)


def view_config(
    view: LayerView, extra: Sequence[str] = (), **config: object
) -> dict[str, object]:
    """Return `config` with the view's extensions, then `extra`, as Jinja extensions.

    Args:
        view: The view whose importable extensions apply.
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
    extensions = [*view.extensions, *extra]
    if extensions:
        config["jinja_extensions"] = extensions
    return config
