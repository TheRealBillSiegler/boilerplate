"""Guard the project's single term list against synonym drift in the docs.

`CONTEXT.md`'s Language section names, for each term, the synonyms to avoid
and (for two terms) a carve-out phrase that names something else entirely.
This module fails when a doc outside `docs/design/` (which describes target
state, not current usage) defines one of those avoided synonyms as its own
term, and passes definitions that match a carve-out phrase instead.
"""

import re
from pathlib import Path
from typing import Final

REPO_ROOT: Final[Path] = Path(__file__).resolve().parent.parent
CONTEXT_MD: Final[Path] = REPO_ROOT / "CONTEXT.md"
DOCS_ROOT: Final[Path] = REPO_ROOT / "docs"
DESIGN_DOCS_ROOT: Final[Path] = DOCS_ROOT / "design"

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
    """Return every Markdown file under `docs/`, excluding `docs/design/`.

    Returns:
        Paths sorted for stable output.
    """
    return sorted(
        path for path in DOCS_ROOT.rglob("*.md") if DESIGN_DOCS_ROOT not in path.parents
    )


class TestAvoidedSynonymsStayOutOfDocs:
    def test_no_doc_outside_design_defines_an_avoided_synonym(self) -> None:
        avoided, carve_outs = _avoided_terms_and_carve_outs()

        violations: list[str] = []
        for doc_path in _iter_non_design_docs():
            relative_path = doc_path.relative_to(REPO_ROOT).as_posix()
            for line_number, line in enumerate(
                doc_path.read_text(encoding="utf-8").splitlines(), start=1
            ):
                for pattern in _DEFINED_TERM_PATTERNS:
                    term_match = pattern.match(line)
                    if term_match is None:
                        continue
                    term = term_match.group(1).strip().lower()
                    if term in carve_outs:
                        continue
                    if term in avoided:
                        violations.append(
                            f"{relative_path}:{line_number} defines {term!r}, "
                            "which CONTEXT.md lists as a synonym to avoid"
                        )

        assert not violations, "\n".join(violations)
