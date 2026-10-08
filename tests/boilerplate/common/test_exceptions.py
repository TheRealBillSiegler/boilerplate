"""Unit tests for the Boilerplate CLI's custom exceptions."""

import functools
import inspect
import re
from pathlib import Path

import pytest

import boilerplate.common.exceptions as common_exceptions_module
import boilerplate.composition.graph.exceptions as graph_exceptions_module
import boilerplate.composition.merging.exceptions as merging_exceptions_module
import boilerplate.settings.profile as profile_module
from boilerplate.common.exceptions import (
    ActionRequiredError,
    BoilerplateError,
    DestinationNotEmptyError,
    DestinationRequiredError,
    DirectoryValidationError,
    InteractiveModeRequiresTtyError,
    InteractiveRenderFailedError,
    InvalidDataError,
    InvalidTemplateSpecifierError,
    InvalidVersionError,
    MetadataValidationError,
    MissingRequiredAnswersError,
    NonInteractiveRequiresForceError,
    RecordedAnswerRejectedError,
    TemplateNotFoundError,
    UserCancelledError,
)
from boilerplate.composition.graph.exceptions import (
    DependencyCycleError,
    DependencyError,
    DependencyNotFoundError,
    VersionConflictError,
)
from boilerplate.composition.merging.exceptions import MergeConflictError
from boilerplate.settings.profile import ProfileError

REGISTRY = Path(__file__).parents[3] / "docs" / "design" / "07-operational-quality.md"

# ActionRequiredError and DependencyError are intermediate bases: neither
# overrides __init__ to set a default error_code, so instantiating either
# directly gives error_code=None. They exist to be subclassed, not raised on
# their own, so they carry no registry entry and must not be tested as if
# they did.
INTERMEDIATE_BASES = frozenset({ActionRequiredError, DependencyError})

# The class-to-code binding transcribed from each class's docstring; the
# registry names codes, not classes, so this table is the one independent
# source of the mapping. The two tests around it keep it honest: every code
# here must be registered, and every concrete class must have a row.
EXPECTED_CODES: dict[type[BoilerplateError], str] = {
    DirectoryValidationError: "BP_CONFIG_DIR_INVALID",
    TemplateNotFoundError: "BP_RESOLVE_TEMPLATE_NOT_FOUND",
    InvalidVersionError: "BP_VERSION_INVALID",
    DestinationNotEmptyError: "BP_RENDER_DEST_NOT_EMPTY",
    NonInteractiveRequiresForceError: "BP_INPUT_FORCE_REQUIRED",
    DestinationRequiredError: "BP_INPUT_DEST_REQUIRED",
    InteractiveModeRequiresTtyError: "BP_INPUT_TTY_REQUIRED",
    InvalidTemplateSpecifierError: "BP_INPUT_SPECIFIER_INVALID",
    MetadataValidationError: "BP_RESOLVE_METADATA_INVALID",
    MissingRequiredAnswersError: "BP_INPUT_ANSWERS_MISSING",
    InvalidDataError: "BP_INPUT_DATA_INVALID",
    RecordedAnswerRejectedError: "BP_INPUT_ANSWER_REJECTED",
    InteractiveRenderFailedError: "BP_RENDER_PROMPT_FAILED",
    DependencyNotFoundError: "BP_RESOLVE_DEP_NOT_FOUND",
    DependencyCycleError: "BP_GRAPH_CYCLE",
    VersionConflictError: "BP_RESOLVE_VERSION_CONFLICT",
    MergeConflictError: "BP_RESOLVE_MERGE_CONFLICT",
    ProfileError: "BP_CONFIG_PROFILE_INVALID",
    UserCancelledError: "BP_RENDER_USER_CANCELLED",
}

# A registry row carries a severity and a retryable column; the phase-prefix
# table above it in the same document does not, so anchoring on them keeps
# bare prefixes such as BP_RESOLVE_ out of the set.
_REGISTRY_CODE_LINE = re.compile(
    r"^\| `(BP_[A-Z0-9_]+)` \| [a-z]+ \| (?:yes|no) \|", re.MULTILINE
)


@functools.cache
def registered_codes() -> frozenset[str]:
    """Return every code the design-07 Error Code Registry table lists."""
    text = REGISTRY.read_text(encoding="utf-8")
    return frozenset(_REGISTRY_CODE_LINE.findall(text))


def concrete_error_classes() -> list[type[BoilerplateError]]:
    """Return every concrete BoilerplateError subclass in the exception modules."""
    modules = (
        common_exceptions_module,
        graph_exceptions_module,
        merging_exceptions_module,
        profile_module,
    )
    classes: list[type[BoilerplateError]] = []
    for module in modules:
        for obj in vars(module).values():
            if (
                inspect.isclass(obj)
                and issubclass(obj, BoilerplateError)
                and obj is not BoilerplateError
                and obj.__module__ == module.__name__
                and obj not in INTERMEDIATE_BASES
            ):
                classes.append(obj)
    classes.sort(key=lambda cls: cls.__qualname__)
    return classes


class TestBoilerplateError:
    """Tests behaviors of the base BoilerplateError exception."""

    def test_can_be_raised_with_message(self) -> None:
        """When raised with a message, the error preserves that message."""
        message = "Something went wrong in the CLI"

        with pytest.raises(BoilerplateError, match=message):
            raise BoilerplateError(message)

    def test_can_be_raised_without_message(self) -> None:
        """When raised without a message, the error still works."""
        with pytest.raises(BoilerplateError):
            raise BoilerplateError()

    def test_is_standard_exception(self) -> None:
        """The base error behaves like any standard Exception."""
        err = BoilerplateError("base message")
        assert isinstance(err, Exception)
        assert str(err) == "base message"


class TestExceptionHierarchy:
    """Tests that the exception hierarchy is correctly structured."""

    @pytest.mark.parametrize(
        "exception_class, expected_parent",
        [
            (DirectoryValidationError, BoilerplateError),
            (TemplateNotFoundError, BoilerplateError),
        ],
    )
    def test_specific_exceptions_inherit_from_base(
        self, exception_class: type[BoilerplateError], expected_parent: type[Exception]
    ) -> None:
        """All specific exceptions inherit from BoilerplateError."""
        err = exception_class("test message")
        assert isinstance(err, expected_parent)
        assert isinstance(err, Exception)

    @pytest.mark.parametrize(
        "exception_class, message",
        [
            (DirectoryValidationError, "Directory validation failed"),
            (TemplateNotFoundError, "Template could not be located"),
        ],
    )
    def test_specific_exceptions_preserve_messages(
        self, exception_class: type[BoilerplateError], message: str
    ) -> None:
        """Specific exceptions preserve their error messages."""
        err = exception_class(message)
        assert str(err) == message

    def test_can_catch_specific_exceptions_as_base_error(self) -> None:
        """Specific exceptions can be caught as BoilerplateError."""
        with pytest.raises(BoilerplateError):
            raise DirectoryValidationError("Directory issue")

        with pytest.raises(BoilerplateError):
            raise TemplateNotFoundError("Template issue")


class TestDirectoryValidationError:
    """Tests behaviors specific to directory validation failures."""

    def test_indicates_directory_problems(self) -> None:
        """When a directory validation fails, the error clearly indicates the issue."""
        directory_path = "/invalid/path"
        message = f"Directory '{directory_path}' does not exist or is invalid."

        with pytest.raises(DirectoryValidationError, match=message):
            raise DirectoryValidationError(message)


class TestTemplateNotFoundError:
    """Tests behaviors specific to template lookup failures."""

    def test_indicates_template_problems(self) -> None:
        """When a template cannot be found, the error clearly indicates the issue."""
        template_name = "missing-template"
        message = f"Template '{template_name}' could not be found"

        with pytest.raises(TemplateNotFoundError, match=message):
            raise TemplateNotFoundError(message)


class TestErrorCodeContract:
    """Each concrete error defaults to its registered BP code.

    The codes are the stable public contract registered in
    docs/design/07-operational-quality.md §Error Code Registry. EXPECTED_CODES
    binds classes to codes; the registry checks the codes, and the module scan
    checks that no class is missing from the binding.
    """

    def test_the_registry_was_found(self) -> None:
        """A moved or renamed registry fails loudly instead of registering nothing."""
        assert len(registered_codes()) > 10

    @pytest.mark.parametrize(
        ("exception_class", "expected_code"),
        EXPECTED_CODES.items(),
        ids=[cls.__name__ for cls in EXPECTED_CODES],
    )
    def test_default_code_is_the_expected_one(
        self, exception_class: type[BoilerplateError], expected_code: str
    ) -> None:
        assert exception_class("boom").error_code == expected_code

    def test_every_expected_code_is_registered(self) -> None:
        """A typo in the binding cannot pass: the registry is the source of codes."""
        assert set(EXPECTED_CODES.values()) <= registered_codes()

    def test_every_concrete_error_has_an_expected_code(self) -> None:
        """A class added without a row fails here instead of going untested."""
        assert set(concrete_error_classes()) == set(EXPECTED_CODES)


class TestSeverityAndRetryable:
    """Verifies severity and retryable metadata per the §07 registry."""

    def test_base_defaults(self) -> None:
        """Base error defaults to registry severity 'error' and retryable False."""
        err = BoilerplateError("boom")
        assert err.severity == "error"
        assert err.retryable is False

    @pytest.mark.parametrize(
        "exception_class",
        [
            # Validation errors
            DirectoryValidationError,
            InvalidVersionError,
            InvalidTemplateSpecifierError,
            MetadataValidationError,
            DestinationNotEmptyError,
            NonInteractiveRequiresForceError,
            MissingRequiredAnswersError,
            InvalidDataError,
            RecordedAnswerRejectedError,
            ProfileError,
            # Not-found errors
            TemplateNotFoundError,
            DependencyNotFoundError,
            # Conflict / cycle errors
            MergeConflictError,
            DependencyCycleError,
        ],
    )
    def test_validation_not_found_and_conflict_errors_are_not_retryable(
        self, exception_class: type[BoilerplateError]
    ) -> None:
        """Validation, not-found, and conflict errors are never retryable."""
        err = exception_class("boom")
        assert err.retryable is False
        assert err.severity == "error"


class TestActionRequiredError:
    """Verifies the recoverable-pause base error."""

    def test_is_boilerplate_error(self) -> None:
        """ActionRequiredError participates in the shared hierarchy."""
        err = ActionRequiredError("resolve conflicts first")
        assert isinstance(err, BoilerplateError)

    def test_hard_failures_are_not_action_required(self) -> None:
        """Hard-failure errors do not route to the recoverable-pause path."""
        assert not isinstance(MergeConflictError("conflict"), ActionRequiredError)


class TestMissingRequiredAnswersRemediation:
    """`--data`/`--data-file` are named as a first-class fix.

    Regression guard for the CLI answers channel: the default remediation
    is the only place a non-interactive user sees a way out that doesn't
    require editing the template.
    """

    def test_default_remediation_names_data_flags(self) -> None:
        err = MissingRequiredAnswersError("required answers missing")
        assert err.remediation is not None
        assert "--data" in err.remediation
        assert "--data-file" in err.remediation


class TestInvalidDataError:
    """`--data`/`--data-file` parse failures fail closed with a named fix."""

    def test_default_remediation_names_both_flags(self) -> None:
        err = InvalidDataError("bad --data entry")
        assert err.remediation is not None
        assert "--data" in err.remediation
        assert "--data-file" in err.remediation


class TestRecordedAnswerRejectedError:
    """A rejected recorded answer carries what a user needs to repair it."""

    def _error(self) -> RecordedAnswerRejectedError:
        return RecordedAnswerRejectedError(
            "rejected",
            layer="docs",
            question="docs_site_name",
            value="",
            reason="The site name cannot be empty.",
        )

    def test_carries_the_layer_question_value_and_reason(self) -> None:
        err = self._error()

        assert (err.layer, err.question, err.value, err.reason) == (
            "docs",
            "docs_site_name",
            "",
            "The site name cannot be empty.",
        )

    def test_remediation_names_the_set_flag_for_the_question(self) -> None:
        assert self._error().remediation == (
            "Pass a valid value with --set docs_site_name=<value>."
        )

    def test_an_explicit_remediation_wins(self) -> None:
        err = RecordedAnswerRejectedError("rejected", remediation="Do this.")

        assert err.remediation == "Do this."
