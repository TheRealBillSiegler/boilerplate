"""Enforce the CLI help-text house style from ``.claude/rules/cli-help.md``.

Two tests walk the Click command tree Typer builds from
``boilerplate.cli.cli.app`` and check every ``help=`` string this package
owns: each option, each argument, and the first line of each command's
docstring (Typer's one-liner). Framework-owned text (``--help``,
``--install-completion``, ``--show-completion``) is out of scope, as is
anything that is not a ``help=`` string (error messages, docs pages, the
app description).
"""

import re
from dataclasses import dataclass
from typing import Any, Protocol, cast

from typer.main import get_command

from boilerplate.cli import cli

_FRAMEWORK_OPTIONS = frozenset({"install_completion", "show_completion"})

_RELATION_OPENERS = (
    "Implies ",
    "Does not imply ",
    "Cannot be combined with ",
    "Requires ",
    "Equivalent to ",
)
_SECOND_SENTENCE_OPENERS = (*_RELATION_OPENERS, "May be repeated", "Required")
_BANNED_WORDS = ("will", "now", "currently", "soon", "planned", "allows")
_RELATION_KEYWORDS = "|".join(
    re.escape(opener.strip().lower()) for opener in _RELATION_OPENERS
)
_PARENTHESISED_RELATION = re.compile(
    rf"\([^)]*\b({_RELATION_KEYWORDS})\b", re.IGNORECASE
)
_MODE_LABEL = re.compile(r"\b\w+ mode:", re.IGNORECASE)

# Tenet 8: an option that behaves differently on one command may read
# differently there instead of forcing a shared text across every command
# that binds it. ``compose --quiet`` suppresses more than the global flag
# does; ``compose --output`` writes a directory, unlike other commands'
# ``--output``. The exemption names these two bindings, not the flags at
# large, so a third command later binding ``--quiet``/``--output`` is still
# checked for consistency against every other binding of that flag.
_ALLOWED_DIVERGENT_LOCATIONS = frozenset({"compose --quiet", "compose --output"})


class _CommandLike(Protocol):
    """The one attribute this module reads off a Click command."""

    help: str | None


@dataclass(frozen=True)
class _HelpString:
    """One checked ``help=`` string or command one-liner.

    Attributes:
        location: Command name plus option/argument name, for failure messages.
        text: The help text itself.
        is_one_liner: Whether this is a command's docstring first line rather
            than an option or argument's ``help=`` text.
        flag: The option's primary long flag (e.g. ``--format``); ``None``
            for arguments and one-liners, which tenet 8 does not compare.
        enum_choices: The Enum's member values when the option is
            Choice-typed; ``None`` otherwise.
    """

    location: str
    text: str
    is_one_liner: bool
    flag: str | None
    enum_choices: tuple[str, ...] | None


def _one_liner(command: _CommandLike) -> str:
    """Return a command's Typer one-liner: the docstring's first paragraph."""
    doc = command.help or ""
    first_paragraph = doc.strip().split("\n\n", 1)[0]
    return " ".join(first_paragraph.split())


def _collect_help_strings() -> list[_HelpString]:
    """Walk the app's Click command tree and collect every checked string.

    Typer 0.26+ vendors Click as a private package and its own
    ``get_command`` return type does not expose a group's ``commands``
    mapping, so the tree is walked structurally through ``Any`` rather than
    by importing the (unsupported, per ``boilerplate.cli.engine``) ``click``
    package or reaching into Typer's private vendored module.
    """
    root: Any = cast(Any, get_command(cli.app))
    strings: list[_HelpString] = []

    def add_params(command_name: str, params: list[Any]) -> None:
        for param in params:
            if param.name in _FRAMEWORK_OPTIONS:
                continue
            flag = next((o for o in param.opts if o.startswith("--")), None)
            choices = getattr(param.type, "choices", None)
            strings.append(
                _HelpString(
                    location=f"{command_name} {flag or param.name}",
                    text=param.help or "",
                    is_one_liner=False,
                    flag=flag,
                    enum_choices=tuple(choices) if choices else None,
                )
            )

    add_params("boilerplate", list(root.params))
    for name, command in sorted(root.commands.items()):
        strings.append(
            _HelpString(
                location=f"{name} (one-liner)",
                text=_one_liner(command),
                is_one_liner=True,
                flag=None,
                enum_choices=None,
            )
        )
        add_params(name, list(command.params))
    return strings


_HELP_STRINGS = _collect_help_strings()


def _check_shape(item: _HelpString) -> list[str]:
    """Check tenet 2's case and period, and tenet 3/7's length ceiling."""
    text = item.text
    violations: list[str] = []
    if not text[0].isupper():
        violations.append("must start with an upper-case letter")
    if not text.endswith("."):
        violations.append("must end with a period")
    limit = 70 if item.is_one_liner else 80
    if len(text) > limit:
        violations.append(
            f"is {len(text)} characters, over the {limit}-character limit"
        )
    return violations


def _check_forbidden_content(text: str) -> list[str]:
    """Check tenet 4's backtick/parenthesised-relation ban and tenet 6's word list."""
    violations: list[str] = []
    if "`" in text:
        violations.append("contains a backtick")
    if _PARENTHESISED_RELATION.search(text):
        violations.append("states a relation inside parentheses")
    if _MODE_LABEL.search(text):
        violations.append("uses '<word> mode:' as a label")
    lowered = text.lower()
    for word in _BANNED_WORDS:
        if re.search(rf"\b{word}\b", lowered):
            violations.append(f"uses the banned word {word!r}")
    return violations


def _check_sentence_structure(text: str) -> list[str]:
    """Check tenet 3's one-relation-sentence allowance."""
    sentence_count = text.count(". ") + 1
    if sentence_count > 2:
        return ["has more than two sentences"]
    if sentence_count == 2:
        second_sentence = text.split(". ", 1)[1]
        if not second_sentence.startswith(_SECOND_SENTENCE_OPENERS):
            return [
                "second sentence must open with a relation form, "
                "'May be repeated', or 'Required'"
            ]
    return []


def _check_enum_choices(item: _HelpString) -> list[str]:
    """Check tenet 5: an Enum-typed option names none of its own members."""
    if not item.enum_choices:
        return []
    lowered = item.text.lower()
    return [
        f"names its own enum member {choice!r}"
        for choice in item.enum_choices
        if re.search(rf"\b{re.escape(choice)}\b", lowered)
    ]


def _violations(item: _HelpString) -> list[str]:
    """Return every house-style violation ``item``'s text has, if any."""
    if not item.text:
        return ["has no help text"]

    violations = [
        *_check_shape(item),
        *_check_forbidden_content(item.text),
        *_check_sentence_structure(item.text),
        *_check_enum_choices(item),
    ]
    if item.is_one_liner and "--" in item.text:
        violations.append("names an option")
    return violations


class TestHouseStyleConformance:
    """Every collected help string obeys every tenet the guide enforces."""

    def test_every_help_string_follows_house_style(self) -> None:
        """Every option, argument, and one-liner passes every tenet the guide tests.

        See .claude/rules/cli-help.md for the tenets this enforces.
        """
        failures = {}
        for item in _HELP_STRINGS:
            reasons = _violations(item)
            if reasons:
                failures[item.location] = reasons

        assert not failures, "\n".join(
            f"{location}: {'; '.join(reasons)}"
            for location, reasons in failures.items()
        )


class TestSharedOptionConsistency:
    """An option's text matches across every command that binds it.

    Tenet 8's two named exceptions (``compose --quiet``, ``compose
    --output``) aside; see .claude/rules/cli-help.md.
    """

    def test_shared_option_text_is_consistent_across_commands(self) -> None:
        by_flag: dict[str, dict[str, str]] = {}
        for item in _HELP_STRINGS:
            if item.flag is None:
                continue
            by_flag.setdefault(item.flag, {})[item.location] = item.text

        inconsistent = {}
        for flag, texts in by_flag.items():
            checked = {
                location: text
                for location, text in texts.items()
                if location not in _ALLOWED_DIVERGENT_LOCATIONS
            }
            if len(set(checked.values())) > 1:
                inconsistent[flag] = texts

        assert not inconsistent, (
            f"these options read differently on different commands: {inconsistent}"
        )
