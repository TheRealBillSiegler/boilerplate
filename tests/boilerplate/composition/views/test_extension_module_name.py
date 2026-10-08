"""The module name an ancestor's extension file is registered under."""

import pytest

from boilerplate.composition.views import extension_module_name


class TestExtensionModuleName:
    """One name per (layer, release, file), usable as a dotted import path."""

    def test_the_same_layer_release_and_file_give_the_same_name(self) -> None:
        assert extension_module_name(
            "docs", "1.0.0", "_extensions/docfilters.py"
        ) == extension_module_name("docs", "1.0.0", "_extensions/docfilters.py")

    @pytest.mark.parametrize(
        ("layer", "release", "file"),
        [
            ("core", "1.0.0", "_extensions/docfilters.py"),
            ("docs", "1.2.0", "_extensions/docfilters.py"),
            ("docs", "1.0.0", "_extensions/other.py"),
            ("docs", "1.0.0", "other/docfilters.py"),
        ],
    )
    def test_changing_any_part_changes_the_name(
        self, layer: str, release: str, file: str
    ) -> None:
        assert extension_module_name(layer, release, file) != extension_module_name(
            "docs", "1.0.0", "_extensions/docfilters.py"
        )

    def test_spellings_that_sanitize_alike_stay_distinct(self) -> None:
        """Keep "1.0" and "1_0" apart although both read as the identifier 1_0."""
        assert extension_module_name("docs", "1.0", "a.py") != extension_module_name(
            "docs", "1_0", "a.py"
        )

    @pytest.mark.parametrize(
        ("layer", "release", "file"),
        [
            ("docs", "1.0.0", "_extensions/docfilters.py"),
            ("my-layer", "2.0.0-rc.1+build", "ext dir/Filters.v2.py"),
        ],
    )
    def test_the_name_is_a_dotted_path_of_identifiers(
        self, layer: str, release: str, file: str
    ) -> None:
        name = extension_module_name(layer, release, file)

        assert all(part.isidentifier() for part in name.split("."))

    def test_the_name_ends_with_the_files_stem(self) -> None:
        assert extension_module_name(
            "docs", "1.0.0", "_extensions/docfilters.py"
        ).endswith(".docfilters")
