"""Composition: build artifacts from a resolved template set.

Defines the domain ``Composer`` that turns a ``Resolution`` into a
``Composition`` for downstream rendering or display. No I/O.
"""
# Spec: docs/design/04-composition-engine.md §Stage 3 — Composer

from collections.abc import Callable
from logging import getLogger
from typing import cast

from boilerplate.composition.merging import CopierConfigMerger
from boilerplate.composition.models import Composition, CompositionGraph, GraphNode
from boilerplate.composition.models.composition import CompositionLayer
from boilerplate.composition.models.json_types import JSON, JSONLike, ensure_json
from boilerplate.composition.resolution import Resolution
from boilerplate.composition.serialization import (
    extract_complete_copier_config,
    serialize_for_yaml,
)
from boilerplate.composition.tasks import TASKS_KEY
from boilerplate.models.template_info import TemplateInfo

_logger = getLogger(__name__)


class Composer:
    """Layers and merges template configurations - domain operation."""

    def __init__(
        self,
        extract_config: Callable[[TemplateInfo], dict[str, object]] | None = None,
    ) -> None:
        """Initializes the composer with optional config extraction function.

        Args:
            extract_config: Function to extract a complete copier config mapping
                from a TemplateInfo. Defaults to ``extract_complete_copier_config``.
        """

        def _default_extract_config(t: TemplateInfo) -> dict[str, object]:
            return extract_complete_copier_config(t.copier_template)

        self._extract_config = extract_config or _default_extract_config
        self._merger = CopierConfigMerger()

    def _compute_delta(
        self, before: dict[str, JSON] | None, after: dict[str, JSON] | None
    ) -> dict[str, JSON] | None:
        """Computes delta between two states."""
        # Normalize inputs - simplify None handling
        before = before or {}
        after = after or {}

        if not before and not after:
            return None

        out: dict[str, JSON] = {}
        # Preserve key insertion order
        all_keys = list(before.keys()) + [k for k in after if k not in before]

        for key in all_keys:
            before_val = before.get(key)
            after_val = after.get(key)

            # Skip if key was removed or unchanged
            if after_val is None or before_val == after_val:
                continue

            # Handle new or changed keys
            if before_val is None:
                out[key] = after_val
            else:
                out[key] = self._compute_value_delta(before_val, after_val)

        return out or None

    def _compute_value_delta(self, before: JSON, after: JSON) -> JSON:
        """Computes delta for a specific value, handling different types."""
        if isinstance(before, dict) and isinstance(after, dict):
            nested = self._compute_delta(before, after)
            return nested or after
        return after

    def _build_graph(
        self, resolution: Resolution, sequence: list[str]
    ) -> CompositionGraph:
        """Builds the composition graph from resolution and sequence."""
        nodes: dict[str, GraphNode] = {}
        for specifier, template_info in resolution.templates.items():
            if specifier in sequence:
                nodes[specifier] = GraphNode(
                    name=template_info.name,
                    version=str(template_info.meta.version),
                    path=template_info.location,
                )

        edges: dict[str, list[str]] = {}
        for parent, children in resolution.deps.items():
            # Declaration order carries sibling-precedence semantics (see
            # docs/design/04-composition-engine.md, diamond-dependencies
            # section); never sort.
            edges[parent] = list(dict.fromkeys(children))

        return CompositionGraph(nodes=nodes, edges=edges, sequence=sequence)

    def compose(
        self,
        resolution: Resolution,
        *,
        include_states: bool = False,
        include_deltas: bool = False,
    ) -> Composition:
        """Composes resolved templates into an ordered, layered Composition.

        Walks ``resolution.execution_sequence``, extracts each template's
        complete copier config, and merges cumulatively: later layers
        override question values; coordination keys (``_tasks``,
        ``_secret_questions``, ``_jinja_extensions``,
        ``_min_copier_version``) merge per ``CopierConfigMerger``;
        layer-local underscore keys are dropped from ``final`` but kept in
        their own layer's ``values``. Sequence entries missing from
        ``resolution.templates`` are skipped. Pure computation — no I/O,
        no rendering.

        Args:
            resolution: Resolved template set with a
                dependency-ordered ``execution_sequence``.
            include_states: Populate ``CompositionLayer.state_after``
                with the full merged state after each layer.
            include_deltas: Populate ``CompositionLayer.delta`` with
                changes versus the previous layer's state (always a dict,
                ``{}`` when unchanged; ``_tasks`` never appears — it is
                excluded from layer values).

        Returns:
            Dependency graph, execution sequence, per-layer values
                (cumulative questions plus that layer's own directives,
                ``_tasks`` excluded), and the ``final`` merged schema used
                for rendering.
        """
        sequence = resolution.execution_sequence
        layer_count = len(sequence)

        # Log composition details for debugging
        _logger.debug(
            "Starting composition: %d layers, states=%s, deltas=%s",
            layer_count,
            include_states,
            include_deltas,
        )

        templates_in_sequence = [
            resolution.templates[s] for s in sequence if s in resolution.templates
        ]
        raw_configs = [self._extract_config(t) for t in templates_in_sequence]

        # Build final schema once
        final_schema = self._merger.merge(
            [serialize_for_yaml(cfg) for cfg in raw_configs]
        )

        # Single-pass layer building
        layers = []
        cumulative_state: dict[str, object] = {}
        previous_full_state: dict[str, object] | None = (
            {} if include_states or include_deltas else None
        )

        for template, raw_config in zip(
            templates_in_sequence, raw_configs, strict=True
        ):
            # Extract questions (non-underscore keys)
            layer_questions = {
                k: v for k, v in raw_config.items() if not k.startswith("_")
            }

            # Detect and log configuration conflicts
            conflicts = set(layer_questions.keys()) & set(cumulative_state.keys())
            if conflicts:
                _logger.debug(
                    "Layer %s overrides %d existing configurations: %s",
                    template.name,
                    len(conflicts),
                    sorted(list(conflicts)[:3]),
                )

            # Log unusual layer characteristics
            _logger.debug(
                "Processing layer %s with %d settings",
                template.name,
                len(layer_questions),
            )

            cumulative_state = self._merger.merge([cumulative_state, layer_questions])

            # Extract layer directives (underscore keys except _tasks)
            layer_directives = {
                k: v
                for k, v in raw_config.items()
                if k.startswith("_") and k != TASKS_KEY
            }
            layer_values = {**cumulative_state, **layer_directives}

            # Conditional state/delta computation
            current_full_state: dict[str, object] | None = None
            if include_states or include_deltas:
                merge_inputs = [previous_full_state or {}, layer_values]
                current_full_state = self._merger.merge(merge_inputs)

            state_after = (
                current_full_state.copy()
                if include_states and current_full_state
                else None
            )
            delta = None
            if include_deltas:
                computed_delta = self._compute_delta(
                    cast(dict[str, JSON] | None, previous_full_state),
                    cast(dict[str, JSON] | None, current_full_state),
                )
                delta = (
                    computed_delta or {}
                )  # Ensure always a dict when deltas are requested

            layer = CompositionLayer(
                name=template.name,
                version=str(template.meta.version),
                path=template.location,
                values=cast(dict[str, JSON], ensure_json(cast(JSONLike, layer_values))),
                state_after=cast(
                    dict[str, JSON] | None, ensure_json(cast(JSONLike, state_after))
                )
                if state_after
                else None,
                delta=delta,
            )
            layers.append(layer)

            if include_states or include_deltas:
                previous_full_state = current_full_state

        graph = self._build_graph(resolution, sequence)

        # Uniform minimal logging (no timing heuristics)
        _logger.debug("Composition completed: %d layers", layer_count)

        return Composition(
            graph=graph,
            sequence=sequence,
            layers=layers,
            final=cast(dict[str, JSON], ensure_json(cast(JSONLike, final_schema))),
        )


__all__ = ["Composer"]
