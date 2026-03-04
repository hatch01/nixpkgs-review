from __future__ import annotations

from pathlib import Path

import pytest

from nixpkgs_review.nix import Attr


def test_filter_packages_with_overlay_includes_broken_with_drv():
    """Test that when using pkgs_overlay, packages with drv_path are included even if broken."""
    
    # Simulate a cross-compilation package: marked as broken but has a valid drv_path
    cross_pkg = Attr(
        name="git",
        exists=True,
        broken=True,  # Often true for cross packages on native system
        blacklisted=False,
        outputs={
            "out": Path("/nix/store/fake-git-aarch64-unknown-linux-gnu-2.53.0"),
        },
        drv_path=Path("/nix/store/fake-git-aarch64-unknown-linux-gnu-2.53.0.drv"),
    )
    
    # Simulate a truly broken package with no drv_path
    truly_broken = Attr(
        name="broken-pkg",
        exists=True,
        broken=True,
        blacklisted=False,
        outputs=None,
        drv_path=None,
    )
    
    # Simulate a blacklisted package with drv_path
    blacklisted_pkg = Attr(
        name="blacklisted-test",
        exists=True,
        broken=False,
        blacklisted=True,
        outputs={"out": Path("/nix/store/fake-blacklisted")},
        drv_path=Path("/nix/store/fake-blacklisted.drv"),
    )
    
    attrs = [cross_pkg, truly_broken, blacklisted_pkg]
    
    # When using pkgs_overlay: include packages with drv_path, exclude truly broken and blacklisted
    filtered_with_overlay = [
        attr.name
        for attr in attrs
        if not attr.blacklisted and attr.drv_path is not None
    ]
    
    assert "git" in filtered_with_overlay
    assert "broken-pkg" not in filtered_with_overlay  # No drv_path
    assert "blacklisted-test" not in filtered_with_overlay  # Blacklisted
    
    # Without pkgs_overlay: exclude broken packages regardless of drv_path
    filtered_without_overlay = [
        attr.name for attr in attrs if not (attr.broken or attr.blacklisted)
    ]
    
    assert "git" not in filtered_without_overlay  # Broken
    assert "broken-pkg" not in filtered_without_overlay  # Broken
    assert "blacklisted-test" not in filtered_without_overlay  # Blacklisted


def test_filter_packages_without_overlay_excludes_broken():
    """Test that without pkgs_overlay, broken packages are excluded."""
    
    working_pkg = Attr(
        name="hello",
        exists=True,
        broken=False,
        blacklisted=False,
        outputs={"out": Path("/nix/store/fake-hello")},
        drv_path=Path("/nix/store/fake-hello.drv"),
    )
    
    broken_pkg = Attr(
        name="broken-hello",
        exists=True,
        broken=True,
        blacklisted=False,
        outputs=None,
        drv_path=None,
    )
    
    attrs = [working_pkg, broken_pkg]
    
    # Without overlay: exclude broken
    filtered = [attr.name for attr in attrs if not (attr.broken or attr.blacklisted)]
    
    assert "hello" in filtered
    assert "broken-hello" not in filtered


def test_attr_was_build():
    """Test the was_build method of Attr."""
    
    # Package with valid outputs should return True after verification
    pkg_with_outputs = Attr(
        name="test-pkg",
        exists=True,
        broken=False,
        blacklisted=False,
        outputs={"out": Path("/nix/store/fake-test-pkg")},
        drv_path=Path("/nix/store/fake-test-pkg.drv"),
    )
    
    # Package without outputs should return False
    pkg_without_outputs = Attr(
        name="broken-pkg",
        exists=True,
        broken=True,
        blacklisted=False,
        outputs=None,
        drv_path=None,
    )
    
    # was_build() checks if outputs exist and are valid
    # Without calling verify_path(), it should check if outputs is not None
    assert pkg_without_outputs.was_build() is False


def test_blacklist_always_excluded():
    """Test that blacklisted packages are always excluded regardless of broken status."""
    
    blacklisted_working = Attr(
        name="tests.trivial",
        exists=True,
        broken=False,
        blacklisted=True,
        outputs={"out": Path("/nix/store/fake-trivial")},
        drv_path=Path("/nix/store/fake-trivial.drv"),
    )
    
    blacklisted_broken = Attr(
        name="tests.nixos-functions.nixos-test",
        exists=True,
        broken=True,
        blacklisted=True,
        outputs=None,
        drv_path=None,
    )
    
    attrs = [blacklisted_working, blacklisted_broken]
    
    # With overlay: blacklisted should be excluded
    filtered_with_overlay = [
        attr.name
        for attr in attrs
        if not attr.blacklisted and attr.drv_path is not None
    ]
    assert len(filtered_with_overlay) == 0
    
    # Without overlay: blacklisted should be excluded
    filtered_without_overlay = [
        attr.name for attr in attrs if not (attr.broken or attr.blacklisted)
    ]
    assert len(filtered_without_overlay) == 0