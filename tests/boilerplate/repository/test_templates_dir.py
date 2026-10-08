"""Unit tests for ``assemble_templates_dir``."""

from pathlib import Path

from boilerplate.repository.templates_dir import assemble_templates_dir


def make_layer(root: Path, name: str, files: dict[str, str]) -> Path:
    """Write `files` under `root / name` and return the folder."""
    folder = root / name
    for relative, text in files.items():
        path = folder / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
    return folder


class TestAssembleTemplatesDir:
    def test_puts_each_layer_in_a_folder_of_its_name(self, tmp_path: Path) -> None:
        """Copy every checkout to ``<dest>/<layer>`` so discovery finds it by name."""
        core = make_layer(tmp_path / "src", "any-folder", {"copier.yml": "core\n"})
        app = make_layer(tmp_path / "src", "other-folder", {"sub/app.txt": "app\n"})

        templates = assemble_templates_dir({"core": core, "app": app}, tmp_path / "out")

        assert sorted(p.name for p in templates.iterdir()) == ["app", "core"]
        assert (templates / "core" / "copier.yml").read_text(
            encoding="utf-8"
        ) == "core\n"
        assert (templates / "app" / "sub" / "app.txt").is_file()

    def test_leaves_git_history_and_bytecode_behind(self, tmp_path: Path) -> None:
        """Copy content only: a ``.git`` folder reads as a git source."""
        core = make_layer(
            tmp_path / "src",
            "core",
            {
                "copier.yml": "core\n",
                ".git/HEAD": "ref\n",
                "pkg/__pycache__/x.pyc": "bytes\n",
            },
        )

        templates = assemble_templates_dir({"core": core}, tmp_path / "out")

        assert sorted(
            p.relative_to(templates / "core").as_posix()
            for p in (templates / "core").rglob("*")
            if p.is_file()
        ) == ["copier.yml"]

    def test_creates_the_destination_when_it_is_missing(self, tmp_path: Path) -> None:
        """Make the folder, parents included."""
        core = make_layer(tmp_path / "src", "core", {"copier.yml": "core\n"})

        templates = assemble_templates_dir({"core": core}, tmp_path / "a" / "b")

        assert (templates / "core" / "copier.yml").is_file()
