"""Build the view a layer renders under from a composition.

A composition rooted at a layer holds that layer and its ancestors, so its
merged questionnaire and importable extension union is the layer's *scoped*
view; rooted at the composition's final layer, it is the *full* view. An update
step asks the scoped view's questions under the full view's definitions.
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


def declaring_layers(composition: Composition) -> dict[str, str]:
    """Return the layer that declares each question of `composition`.

    Each layer's recorded ``values`` hold the questions accumulated up to it, so
    the first layer to hold a question declares it; a later layer that holds it
    only overrides it.

    Args:
        composition: A resolved and composed set of layers.

    Returns:
        The declaring layer's name, keyed by question name.
    """
    owners: dict[str, str] = {}
    for layer in composition.layers:
        for name in layer.values:
            if not name.startswith("_"):
                owners.setdefault(name, layer.name)
    return owners


def build_layer_view(composition: Composition) -> LayerView:
    """Return the merged view of `composition`.

    Args:
        composition: A composition resolved and composed from the layer whose
            view is wanted.

    Returns:
        The merged questions and the importable extension union, and the
        file-path extension specs of every layer but the last as the files at
        their releases; the last layer's own file-path specs are left to
        Copier. It also names the layer that declares each question and
        carries the accumulated ``_secret_questions``.
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
    secrets = composition.final.get("_secret_questions")
    return LayerView(
        dict(composition.merged_questions_schema),
        extensions,
        ancestor_extensions,
        declaring_layers(composition),
        frozenset(str(name) for name in secrets)
        if isinstance(secrets, list)
        else frozenset(),
    )


def build_step_view(scoped: Composition, full: Composition) -> LayerView:
    """Return the view an update step renders a layer under.

    The step asks the questions of the layer's scope, with each question's
    definition and default taken from the full composition's merged schema, so a
    descendant's override sets the default of a question an ancestor adds, in the
    ancestor's step.

    Args:
        scoped: The composition rooted at the layer being updated: the layer and
            its ancestors.
        full: The full composition, which holds `scoped`'s layers; both at the
            versions the view is for.

    Returns:
        The scoped view with each question's definition replaced by the full
        schema's. Extensions, ancestor extension files and declaring layers
        follow the scope.
    """
    view = build_layer_view(scoped)
    full_questions = full.merged_questions_schema
    questions = {name: full_questions[name] for name in view.questions}
    return view._replace(questions=questions)


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
