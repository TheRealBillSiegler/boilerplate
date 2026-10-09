"""Build one-off template layers for the add tests the family cannot express."""

from collections.abc import Mapping
from pathlib import Path

from tests.boilerplate.templates.conftest import build_layer_repo

_EXCLUDE = """\
_exclude:
  - "/copier.yaml"
  - "/copier.yml"
  - "/boilerplate.yml"
  - "~*"
  - "*.py[co]"
  - __pycache__
  - .git
  - .DS_Store
  - .svn
"""
_ANSWERS = (
    "# Changes here will be overwritten by Copier; NEVER EDIT MANUALLY\n"
    "{{ _copier_answers|to_nice_yaml -}}\n"
)


# Writes into ``dist/``, which a core-based project ignores, then exits non-zero.
IGNORED_THEN_FAILING_TASK = """\
_tasks:
  - command:
      - "{{ _copier_python }}"
      - -c
      - "import pathlib; pathlib.Path('dist').mkdir(); pathlib.Path('dist/out.txt').write_text('out'); raise SystemExit(3)"
"""


def build_layer(
    root: Path,
    name: str,
    *,
    extends: str = "core",
    copier: str = "",
    files: Mapping[str, str] | None = None,
) -> Path:
    """Build a single-release layer into a tagged git repository.

    Args:
        root: A directory to build under.
        name: The layer's name; its answers file is ``.copier-answers.<name>.yml``.
        extends: The ``extends`` reference the layer declares.
        copier: Further ``copier.yml`` text, such as questions and ``_tasks``.
        files: Further template files, keyed by their path in the template.

    Returns:
        The layer's repository, tagged ``1.0.0``.
    """
    release = root / "releases" / name
    release.mkdir(parents=True)
    (release / "boilerplate.yml").write_text(
        f'schema_version: "1"\n\nname: {name}\nversion: 1.0.0\n'
        f"description: A one-off layer.\nextends: [{extends}]\n",
        encoding="utf-8",
    )
    (release / "copier.yml").write_text(
        f"_answers_file: .copier-answers.{name}.yml\n\n{_EXCLUDE}\n{copier}",
        encoding="utf-8",
    )
    (release / "{{_copier_conf.answers_file}}.jinja").write_text(
        _ANSWERS, encoding="utf-8"
    )
    for path, text in (files or {}).items():
        target = release / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return build_layer_repo(root / "repos" / name, {"1.0.0": release})
