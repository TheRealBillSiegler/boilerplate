"""Unit tests for the Boilerplate CLI's custom exceptions."""

import pytest

from boilerplate.common.exceptions import (
    ActionRequiredError,
    BoilerplateError,
    DestinationNotEmptyError,
    DirectoryValidationError,
    InteractiveRenderFailedError,
    InvalidDataError,
    InvalidTemplateSpecifierError,
    InvalidVersionError,
    MetadataValidationError,
    MissingRequiredAnswersError,
    NonInteractiveRequiresForceError,
    TemplateNotFoundError,
    UserCancelledError,
)
from boilerplate.composition.graph.exceptions import (
    DependencyCycleError,
    DependencyNotFoundError,
)
from boilerplate.composition.merging.exceptions import MergeConflictError
from boilerplate.settings.profile import ProfileError


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
    """Verifies each concrete error carries its registered BP code.

    The codes are the stable public contract registered in
    docs/design/07-operational-quality.md §Error Code Registry.
    """

    @pytest.mark.parametrize(
        ("exception_class", "expected_code"),
        [
            (DirectoryValidationError, "BP_CONFIG_DIR_INVALID"),
            (TemplateNotFoundError, "BP_RESOLVE_TEMPLATE_NOT_FOUND"),
            (InvalidVersionError, "BP_VERSION_INVALID"),
            (DestinationNotEmptyError, "BP_RENDER_DEST_NOT_EMPTY"),
            (NonInteractiveRequiresForceError, "BP_INPUT_FORCE_REQUIRED"),
            (InvalidTemplateSpecifierError, "BP_INPUT_SPECIFIER_INVALID"),
            (MetadataValidationError, "BP_RESOLVE_METADATA_INVALID"),
            (MissingRequiredAnswersError, "BP_INPUT_ANSWERS_MISSING"),
            (InvalidDataError, "BP_INPUT_DATA_INVALID"),
            (InteractiveRenderFailedError, "BP_RENDER_PROMPT_FAILED"),
            (DependencyNotFoundError, "BP_RESOLVE_DEP_NOT_FOUND"),
            (DependencyCycleError, "BP_GRAPH_CYCLE"),
            (MergeConflictError, "BP_RESOLVE_MERGE_CONFLICT"),
            (ProfileError, "BP_CONFIG_PROFILE_INVALID"),
            (UserCancelledError, "BP_RENDER_USER_CANCELLED"),
        ],
    )
    def test_error_code_matches_registry(
        self, exception_class: type[BoilerplateError], expected_code: str
    ) -> None:
        """Each concrete exception defaults to its registered phase-tagged code."""
        assert exception_class("boom").error_code == expected_code

    def test_no_flat_numeric_codes_remain(self) -> None:
        """Codes follow BP_{PHASE}_{DESCRIPTOR}, not flat BP1xx/2xx/3xx scheme."""
        code = DestinationNotEmptyError("boom").error_code
        assert code is not None
        assert code.startswith("BP_")


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
