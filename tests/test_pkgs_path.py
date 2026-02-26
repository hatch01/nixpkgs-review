"""Tests for the --pkgs / cross_pkg_set cross-compilation feature.

Unit tests (no Nix invocation needed) cover:
- CLI flag parsing
- build_shell_file_args argument generation

Integration tests cover:
- rev + --pkgs builds from the alternative sub-attribute set
- pr  + --pkgs builds from the alternative sub-attribute set
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, mock_open, patch

import pytest

from nixpkgs_review.cli import main, parse_args
from nixpkgs_review.nix import build_shell_file_args

if TYPE_CHECKING:
    from .conftest import Helpers, Nixpkgs


# ---------------------------------------------------------------------------
# CLI flag parsing
# ---------------------------------------------------------------------------


def test_pkgs_flag_defaults_to_none_for_rev() -> None:
    args = parse_args("nixpkgs-review", ["rev", "HEAD"])
    assert args.pkgs is None


def test_pkgs_flag_defaults_to_none_for_pr() -> None:
    args = parse_args("nixpkgs-review", ["pr", "1234"])
    assert args.pkgs is None


def test_pkgs_flag_defaults_to_none_for_wip() -> None:
    args = parse_args("nixpkgs-review", ["wip"])
    assert args.pkgs is None


@pytest.mark.parametrize(
    "pkgs_value",
    [
        "pkgsMusl",
        "pkgsStatic",
        "pkgsCross.aarch64-multiplatform",
        "pkgsCross.armv7l-hf-multiplatform",
        "pkgsAlt",
    ],
)
def test_pkgs_flag_parsed_for_rev(pkgs_value: str) -> None:
    args = parse_args("nixpkgs-review", ["rev", "HEAD", "--pkgs", pkgs_value])
    assert args.pkgs == pkgs_value


@pytest.mark.parametrize(
    "pkgs_value",
    [
        "pkgsMusl",
        "pkgsCross.aarch64-multiplatform",
        "pkgsAlt",
    ],
)
def test_pkgs_flag_parsed_for_pr(pkgs_value: str) -> None:
    args = parse_args("nixpkgs-review", ["pr", "--pkgs", pkgs_value, "1234"])
    assert args.pkgs == pkgs_value


# ---------------------------------------------------------------------------
# build_shell_file_args
# ---------------------------------------------------------------------------


def test_build_shell_file_args_without_pkgs_path() -> None:
    """When cross_pkg_set is None, no pkgs-path argument should be emitted."""
    with tempfile.TemporaryDirectory() as tmpdir:
        Path(tmpdir).joinpath("nixpkgs").mkdir()
        args = build_shell_file_args(
            cache_dir=Path(tmpdir),
            attrs_per_system={"x86_64-linux": ["hello"]},
            local_system="x86_64-linux",
            nixpkgs_config=Path(tmpdir) / "config.nix",
            cross_pkg_set=None,
        )
    assert "pkgs-path" not in args


def test_build_shell_file_args_with_pkgs_path() -> None:
    """When cross_pkg_set is set, --argstr pkgs-path <value> must be present."""
    with tempfile.TemporaryDirectory() as tmpdir:
        Path(tmpdir).joinpath("nixpkgs").mkdir()
        args = build_shell_file_args(
            cache_dir=Path(tmpdir),
            attrs_per_system={"x86_64-linux": ["hello"]},
            local_system="x86_64-linux",
            nixpkgs_config=Path(tmpdir) / "config.nix",
            cross_pkg_set="pkgsCross.aarch64-multiplatform",
        )
    assert "--argstr" in args
    idx = args.index("pkgs-path")
    assert args[idx - 1] == "--argstr"
    assert args[idx + 1] == "pkgsCross.aarch64-multiplatform"


@pytest.mark.parametrize(
    "cross_pkg_set",
    [
        "pkgsMusl",
        "pkgsStatic",
        "pkgsCross.aarch64-multiplatform",
        "pkgsCross.armv7l-hf-multiplatform",
        "pkgsAlt",
    ],
)
def test_build_shell_file_args_pkgs_path_value_preserved(cross_pkg_set: str) -> None:
    """The exact cross_pkg_set string must be forwarded without modification."""
    with tempfile.TemporaryDirectory() as tmpdir:
        Path(tmpdir).joinpath("nixpkgs").mkdir()
        args = build_shell_file_args(
            cache_dir=Path(tmpdir),
            attrs_per_system={"x86_64-linux": ["hello"]},
            local_system="x86_64-linux",
            nixpkgs_config=Path(tmpdir) / "config.nix",
            cross_pkg_set=cross_pkg_set,
        )
    idx = args.index("pkgs-path")
    assert args[idx + 1] == cross_pkg_set


def test_build_shell_file_args_standard_args_still_present_with_pkgs_path() -> None:
    """Standard argstr arguments must still be present when cross_pkg_set is set."""
    with tempfile.TemporaryDirectory() as tmpdir:
        Path(tmpdir).joinpath("nixpkgs").mkdir()
        args = build_shell_file_args(
            cache_dir=Path(tmpdir),
            attrs_per_system={"x86_64-linux": ["hello"]},
            local_system="x86_64-linux",
            nixpkgs_config=Path(tmpdir) / "config.nix",
            cross_pkg_set="pkgsAlt",
        )
    # All standard args must still be present
    for required in ("local-system", "nixpkgs-path", "nixpkgs-config-path", "attrs-path"):
        assert required in args


# ---------------------------------------------------------------------------
# Integration tests: rev + --pkgs
# ---------------------------------------------------------------------------


def _commit_changes(message: str = "example-change") -> None:
    """Stage all changes and create a git commit."""
    subprocess.run(["git", "add", "."], check=True)
    subprocess.run(["git", "commit", "-m", message], check=True)


def test_rev_command_with_pkgs(helpers: Helpers) -> None:
    """rev --pkgs pkgsAlt resolves pkg1 from the alternative package set."""
    with helpers.nixpkgs() as nixpkgs:
        nixpkgs.path.joinpath("pkg1.txt").write_text("foo")
        _commit_changes()
        path = main(
            "nixpkgs-review",
            [
                "rev",
                "HEAD",
                "--remote",
                str(nixpkgs.remote),
                "--run",
                "exit 0",
                "--build-graph",
                "nix",
                "--package",
                "pkg1",
                "--pkgs",
                "pkgsAlt",
            ],
        )
        helpers.assert_built(path, "pkg1")


# ---------------------------------------------------------------------------
# Integration tests: pr + --pkgs
# ---------------------------------------------------------------------------


def _setup_pr_repo(nixpkgs: Nixpkgs) -> tuple[str, str, str]:
    subprocess.run(["git", "checkout", "-b", "pull/1/head"], check=True)
    nixpkgs.path.joinpath("pkg1.txt").write_text("foo")
    _commit_changes()
    subprocess.run(["git", "checkout", "-b", "pull/1/merge", "master"], check=True)
    subprocess.run(["git", "merge", "--no-ff", "pull/1/head"], check=True)
    subprocess.run(["git", "push", str(nixpkgs.remote), "pull/1/merge"], check=True)

    base = subprocess.run(
        ["git", "rev-parse", "HEAD^1"], check=True, capture_output=True, text=True
    ).stdout.strip()
    head = subprocess.run(
        ["git", "rev-parse", "HEAD^2"], check=True, capture_output=True, text=True
    ).stdout.strip()
    merge = subprocess.run(
        ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()
    return base, head, merge


def _make_mock_pr(base: str, head: str, merge: str) -> dict[str, Any]:
    return {
        "number": 1,
        "head": {"ref": "example-branch", "sha": head, "label": "user:example-branch"},
        "base": {"ref": "master", "sha": base, "label": "NixOS:master"},
        "merge_commit_sha": merge,
        "title": "test PR",
        "html_url": "https://github.com/NixOS/nixpkgs/pull/1",
        "user": {"login": "test-user"},
        "state": "open",
        "body": "test body",
        "diff_url": "https://github.com/NixOS/nixpkgs/pull/1.diff",
        "draft": False,
    }


_MOCK_DIFF = (
    "diff --git a/pkg1.txt b/pkg1.txt\n"
    "new file mode 100644\n"
    "index 0000000..1910281\n"
    "--- /dev/null\n"
    "+++ b/pkg1.txt\n"
    "@@ -0,0 +1 @@\n"
    "+foo"
)


@patch("nixpkgs_review.http_requests.urlopen")
def test_pr_local_eval_with_pkgs(
    mock_urlopen: MagicMock,
    helpers: Helpers,
) -> None:
    """pr --pkgs pkgsAlt resolves pkg1 from the alternative package set."""
    with helpers.nixpkgs() as nixpkgs:
        base, head, merge = _setup_pr_repo(nixpkgs)

        mock_urlopen.side_effect = [
            mock_open(read_data=json.dumps(_make_mock_pr(base, head, merge)).encode())(),
            mock_open(read_data=_MOCK_DIFF.encode())(),
        ]

        path = main(
            "nixpkgs-review",
            [
                "pr",
                "--remote",
                str(nixpkgs.remote),
                "--eval",
                "local",
                "--run",
                "exit 0",
                "--build-graph",
                "nix",
                "--package",
                "pkg1",
                "--pkgs",
                "pkgsAlt",
                "1",
            ],
        )
        helpers.assert_built(path, "pkg1")
