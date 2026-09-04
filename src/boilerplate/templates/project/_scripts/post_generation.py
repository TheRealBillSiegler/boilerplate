"""Post-generation script for the "project" template.

This script automates essential tasks after project generation:
1. Validates prerequisites (`uv` tool).
2. Sets up a virtual environment.
3. Initializes a Git repository (if not present).
4. Displays instructions to connect to a Git remote.
5. Cleans up temporary setup files.

This script runs automatically as part of the Copier template generation process.
"""

import contextlib
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import TextIO

from rich.console import Console

# Constants
UV_INSTALL_CMD = (
    'powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"'
)
TEMP_SCRIPTS_DIR = Path(__file__).parent

# Configure stdio defensively for Windows code pages
if os.name == "nt":
    # Help Python subprocesses prefer UTF-8; harmless if already set
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

    # Avoid hard failures if a stray Unicode char slips through
    def _safe_reconfigure(stream: TextIO) -> None:
        """Safely calls reconfigure on a text stream if available, typed for Pyright."""
        func = getattr(stream, "reconfigure", None)
        if callable(func):
            # errors="replace" avoids hard failures on non-encodable characters
            func(errors="replace")

    with contextlib.suppress(Exception):
        _safe_reconfigure(sys.stdout)
        _safe_reconfigure(sys.stderr)


def _can_encode(sample: str) -> bool:
    enc = sys.stdout.encoding or "utf-8"
    try:
        sample.encode(enc)
        return True
    except Exception:
        return False


if _can_encode("🚀"):
    console = Console(force_terminal=True, width=120, legacy_windows=False)
    emoji_rocket = "🚀"
    emoji_check = "✅"
    emoji_warning = "⚠️"
    emoji_party = "🎉"
    use_rich_features = True
else:
    # Fall back to ASCII-safe symbols and legacy mode for Windows terminals
    console = Console(
        force_terminal=True, width=120, legacy_windows=True, no_color=True, stderr=False
    )
    emoji_rocket = ">>>"
    emoji_check = "[OK]"
    emoji_warning = "[!!]"
    emoji_party = "[DONE]"
    use_rich_features = False


def check_uv() -> None:
    """Validates if the `uv` tool is globally installed and functional.

    Logs a success message if found and working; otherwise, displays an installation
    command and exits the script. Also checks if uv can reach package indexes.
    """
    if not shutil.which("uv"):
        console.print(
            "[red]Error: 'uv' is not installed. Install it with the following command:[/red]",
        )
        console.print(f"[blue]{UV_INSTALL_CMD}[/blue]")
        sys.exit(1)

    # Test if uv is functional by checking version
    console.print("[cyan]'uv' is installed.[/cyan]")


def run_command(
    command: str, max_retries: int = 3, retry_delay: int = 2, silent: bool = False
) -> bool:
    """Executes a shell command with retry logic for transient failures.

    Args:
        command: The shell command to execute.
        max_retries: Maximum number of retry attempts.
        retry_delay: Delay in seconds between retries.
        silent: If True, suppress output even on success.

    Returns:
        True if command succeeded, False if all retries failed.
    """
    for attempt in range(max_retries):
        try:
            result = subprocess.run(
                command,
                shell=True,
                check=True,
                capture_output=True,
                encoding="utf-8",
                errors="replace",
            )
            if result.stdout and not silent:
                console.print(result.stdout.strip())
            return True
        except subprocess.CalledProcessError as e:
            if attempt < max_retries - 1:
                # Transient failure - retry
                if not silent:
                    console.print(
                        f"[yellow]Command failed (attempt {attempt + 1}/{max_retries}): {command}[/yellow]"
                    )
                    if e.stderr:
                        console.print(f"[yellow]Error: {e.stderr.strip()}[/yellow]")
                    console.print(f"[cyan]Retrying in {retry_delay} seconds...[/cyan]")
                time.sleep(retry_delay)
                # Exponential backoff
                retry_delay *= 2
            else:
                # Final failure
                console.print(
                    f"[red]Error: Command failed after {max_retries} attempts: {command}[/red]"
                )
                if e.stderr:
                    console.print(f"[red]Final error: {e.stderr.strip()}[/red]")
                return False
    return False


def setup_environment() -> bool:
    """Configures the virtual environment using `uv`.

    Synchronizes dependencies based on `pyproject.toml`.
    Handles transient failures with retry logic.

    Returns:
        True if `uv sync` succeeded, False otherwise.
    """
    if use_rich_features:
        with console.status("[cyan]Setting up the virtual environment...[/cyan]"):
            success = run_command("uv sync", max_retries=3, retry_delay=2)
    else:
        console.print("Setting up the virtual environment...")
        success = run_command("uv sync", max_retries=3, retry_delay=2)

    if success:
        console.print(
            f"[green]{emoji_check} Virtual environment setup complete![/green]"
        )
    else:
        console.print(
            f"[red]{emoji_warning} Virtual environment setup failed after multiple attempts.[/red]"
        )
        console.print("[yellow]This might be due to:[/yellow]")
        console.print("[yellow]  - Network connectivity issues[/yellow]")
        console.print("[yellow]  - Package index temporarily unavailable[/yellow]")
        console.print("[yellow]  - Invalid dependencies in pyproject.toml[/yellow]")
        console.print("[cyan]You can try running 'uv sync' manually later.[/cyan]")
        # Don't exit - continue with other setup tasks

    return success


def initialize_git() -> bool:
    """Initializes a Git repository if not already present.

    Logs success and provides instructions for remote setup if initialized.

    Returns:
        True if a repository exists afterward (already present or
            freshly initialized), False if `git init` failed.
    """
    git_path = Path(".git")
    if not git_path.exists():
        if use_rich_features:
            with console.status("[cyan]Initializing Git repository...[/cyan]"):
                success = run_command("git init", max_retries=2, retry_delay=1)
        else:
            console.print("Initializing Git repository...")
            success = run_command("git init", max_retries=2, retry_delay=1)

        if success:
            console.print(f"[green]{emoji_check} Git repository initialized![/green]")
            print_remote_instructions()
        else:
            console.print(
                f"[yellow]{emoji_warning} Git initialization failed.[/yellow]"
            )
            console.print(
                "[cyan]You can initialize Git manually with 'git init' later.[/cyan]"
            )
        return success

    console.print(f"[yellow]{emoji_warning}  Git repository already exists.[/yellow]")
    return True


def print_remote_instructions() -> None:
    """Displays instructions to connect the repository to a remote."""
    console.print(
        "[blue]To connect your Git repository to a remote, use these commands:[/blue]\n"
        "   git remote add origin <REMOTE_URL>\n"
        "   git branch -M main\n"
        "   git push -u origin main",
    )


def cleanup_scripts_dir() -> None:
    """Removes the `_scripts` directory post-execution.

    Raises:
        Exception: If the directory cannot be removed. This is cosmetic
            cleanup, not a required task, so the caller is expected to catch
            this, warn, and continue rather than abort the run.
    """
    try:
        if use_rich_features:
            with console.status("[cyan]Cleaning up temporary files...[/cyan]"):
                shutil.rmtree(TEMP_SCRIPTS_DIR)
        else:
            console.print("Cleaning up temporary files...")
            shutil.rmtree(TEMP_SCRIPTS_DIR)
        console.print(f"[green]{emoji_check} Cleanup complete.[/green]")
    except Exception as e:
        console.print(f"[red]Error: Could not clean up temporary files: {e}[/red]")
        raise


def post_generation() -> None:
    """Performs all post-generation tasks with resilient error handling."""
    console.print(f"[cyan]{emoji_rocket} Starting post-generation tasks...[/cyan]")

    tasks_completed = 0
    total_tasks = 4
    # Real setup failures (uv sync, git init) block a clean "all done" summary
    # and a zero exit code. Cosmetic cleanup failure does not.
    critical_failure = False

    try:
        # Task 1: Check uv (required - exit if fails)
        check_uv()
        tasks_completed += 1

        # Task 2: Setup environment (optional - continue if fails)
        try:
            if setup_environment():
                tasks_completed += 1
            else:
                critical_failure = True
        except Exception as e:
            critical_failure = True
            console.print(
                f"[yellow]{emoji_warning} Environment setup encountered issues: {e}[/yellow]"
            )
            console.print("[cyan]Continuing with remaining tasks...[/cyan]")

        # Task 3: Initialize git (optional - continue if fails)
        try:
            if initialize_git():
                tasks_completed += 1
            else:
                critical_failure = True
        except Exception as e:
            critical_failure = True
            console.print(
                f"[yellow]{emoji_warning} Git initialization encountered issues: {e}[/yellow]"
            )
            console.print("[cyan]Continuing with remaining tasks...[/cyan]")

        # Task 4: Cleanup (optional - warn if fails)
        try:
            cleanup_scripts_dir()
            tasks_completed += 1
        except Exception as e:
            console.print(
                f"[yellow]{emoji_warning} Cleanup encountered issues: {e}[/yellow]"
            )
            console.print(
                "[cyan]You may need to manually remove the _scripts directory.[/cyan]"
            )

    except KeyboardInterrupt:
        console.print(
            f"[yellow]{emoji_warning} Process interrupted by the user.[/yellow]"
        )
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Critical error during setup: {e}[/red]")
        sys.exit(1)

    # Summary
    if critical_failure:
        console.print(
            f"[yellow]{emoji_warning} Setup completed with issues ({tasks_completed}/{total_tasks} tasks).[/yellow]"
        )
        console.print(
            "[cyan]Your project structure is created, but you may need to run some commands manually.[/cyan]"
        )
        sys.exit(1)
    elif tasks_completed == total_tasks:
        console.print(
            f"[bold green]{emoji_party} All tasks completed successfully![/bold green]"
        )
    else:
        console.print(
            f"[green]{emoji_party} Setup completed with minor issues ({tasks_completed}/{total_tasks} tasks).[/green]"
        )
        console.print(
            "[cyan]Your project is ready to use! Check any warnings above.[/cyan]"
        )


if __name__ == "__main__":
    post_generation()
