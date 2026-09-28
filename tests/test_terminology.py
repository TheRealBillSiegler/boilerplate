"""Guard the project's single term list against synonym drift in the docs.

`CONTEXT.md`'s Language section names, for each term, the synonyms to avoid
and (for two terms) a carve-out phrase that names something else entirely.
This module fails when a doc outside `docs/design/`, `docs/intentions/`, and
`docs/products/` (which, per `docs/agents/domain.md`, describe target state
rather than current usage) defines one of those avoided synonyms as its own
term, and passes definitions that match a carve-out phrase instead. A term
counts as "defined" either as a bold definition-list entry or a glossary
table row, bold or not, under a `Term` header column.
"""

import re
from pathlib import Path
from typing import Final

REPO_ROOT: Final[Path] = Path(__file__).resolve().parent.parent
CONTEXT_MD: Final[Path] = REPO_ROOT / "CONTEXT.md"
DOCS_ROOT: Final[Path] = REPO_ROOT / "docs"
_EXCLUDED_DOC_ROOTS: Final[tuple[Path, ...]] = (
    DOCS_ROOT / "design",
    DOCS_ROOT / "intentions",
    DOCS_ROOT / "products",
)

_SECTION_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"<!-- --8<-- \[start:language\] -->\n(.*?)"
    r"<!-- --8<-- \[end:language\] -->",
    re.DOTALL,
)
_AVOID_LINE_PATTERN: Final[re.Pattern[str]] = re.compile(r"^_Avoid_:\s*(.+)$")
_CARVE_OUT_LINE_PATTERN: Final[re.Pattern[str]] = re.compile(
    r'^_Carve-out_:\s*"([^"]+)"'
)
_DEFINED_TERM_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    # A definition-list style term: **Term**: ... (or **Term**: alone).
    re.compile(r"^\*\*([^*]+)\*\*:"),
    # A glossary table row: | **Term** | ... |
    re.compile(r"^\|\s*\*\*([^*]+)\*\*\s*\|"),
)
_TABLE_ROW_PATTERN: Final[re.Pattern[str]] = re.compile(r"^\|\s*([^|]+?)\s*\|")
_TABLE_SEPARATOR_PATTERN: Final[re.Pattern[str]] = re.compile(r"^\|[\s:-]+\|")


def _iter_term_table_rows(lines: list[str]) -> list[tuple[int, str]]:
    """Yield each first-column entry of a table headed "Term".

    Composition tables such as `docs/templates-hub/composition.md`'s
    Concepts table define terms as plain (unbolded) table cells under a
    `Term` header, which `_DEFINED_TERM_PATTERNS` alone cannot see.

    Args:
        lines: The document's lines, in order.

    Returns:
        `(line_number, term)` pairs, one per data row of a `Term`-headed
        table; `line_number` is 1-indexed.
    """
    rows: list[tuple[int, str]] = []
    in_term_table = False
    expect_separator = False
    for line_number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if expect_separator:
            expect_separator = False
            if _TABLE_SEPARATOR_PATTERN.match(stripped):
                continue
            in_term_table = False
        row_match = _TABLE_ROW_PATTERN.match(stripped)
        if row_match is None:
            in_term_table = False
            continue
        first_cell = row_match.group(1).strip()
        if not in_term_table:
            if first_cell.lower() == "term":
                in_term_table = True
                expect_separator = True
            continue
        rows.append((line_number, first_cell.strip("*").strip()))
    return rows


def _avoided_terms_and_carve_outs() -> tuple[frozenset[str], frozenset[str]]:
    """Return CONTEXT.md's avoided synonyms and its carve-out phrases.

    Returns:
        A pair of `(avoided_terms, carve_outs)`, both lower-cased.
    """
    text = CONTEXT_MD.read_text(encoding="utf-8")
    match = _SECTION_PATTERN.search(text)
    assert match is not None, (
        "CONTEXT.md is missing its [start:language]/[end:language] markers"
    )
    section = match.group(1)

    avoided: set[str] = set()
    carve_outs: set[str] = set()
    for line in section.splitlines():
        stripped = line.strip()
        avoid_match = _AVOID_LINE_PATTERN.match(stripped)
        if avoid_match is not None:
            avoided.update(
                term.strip().lower() for term in avoid_match.group(1).split(",")
            )
            continue
        carve_out_match = _CARVE_OUT_LINE_PATTERN.match(stripped)
        if carve_out_match is not None:
            carve_outs.add(carve_out_match.group(1).strip().lower())

    assert avoided, "CONTEXT.md's Language section has no _Avoid_ lines"
    return frozenset(avoided), frozenset(carve_outs)


def _iter_non_design_docs() -> list[Path]:
    """Return every Markdown file under `docs/`, excluding target-state docs.

    `docs/design/`, `docs/intentions/`, and `docs/products/` describe target
    state rather than current usage (`docs/agents/domain.md`), so a defined
    term there is not the drift this guard checks for.

    Returns:
        Paths sorted for stable output.
    """
    return sorted(
        path
        for path in DOCS_ROOT.rglob("*.md")
        if not any(root in path.parents for root in _EXCLUDED_DOC_ROOTS)
    )


class TestAvoidedSynonymsStayOutOfDocs:
    def test_no_doc_outside_design_defines_an_avoided_synonym(self) -> None:
        avoided, carve_outs = _avoided_terms_and_carve_outs()

        violations: list[str] = []
        for doc_path in _iter_non_design_docs():
            relative_path = doc_path.relative_to(REPO_ROOT).as_posix()
            lines = doc_path.read_text(encoding="utf-8").splitlines()
            defined_terms: list[tuple[int, str]] = []
            for line_number, line in enumerate(lines, start=1):
                for pattern in _DEFINED_TERM_PATTERNS:
                    term_match = pattern.match(line)
                    if term_match is not None:
                        defined_terms.append((line_number, term_match.group(1).strip()))
            defined_terms.extend(_iter_term_table_rows(lines))

            for line_number, term in defined_terms:
                term_lower = term.lower()
                if term_lower in carve_outs:
                    continue
                if term_lower in avoided:
                    violations.append(
                        f"{relative_path}:{line_number} defines {term_lower!r}, "
                        "which CONTEXT.md lists as a synonym to avoid"
                    )

        assert not violations, "\n".join(violations)


class TestTermTableRowDetection:
    def test_extracts_unbolded_rows_from_a_term_headed_table(self) -> None:
        lines = [
            "| Term | Meaning |",
            "|------|---------|",
            "| Layer | A composition node. |",
            "| Overlay | Something else entirely. |",
            "",
            "| Other | Not a term table. |",
        ]

        assert _iter_term_table_rows(lines) == [
            (3, "Layer"),
            (4, "Overlay"),
        ]

    def test_strips_bold_markers_from_an_already_bold_row(self) -> None:
        lines = [
            "| Term | Meaning |",
            "|------|---------|",
            "| **Layer** | A composition node. |",
        ]

        assert _iter_term_table_rows(lines) == [(3, "Layer")]
