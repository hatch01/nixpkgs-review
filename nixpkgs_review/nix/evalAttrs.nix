{ attr-json, pkgs-overlay ? "" }:

with builtins;
mapAttrs (
  system: attrs:
  let
    pkgs-base = import <nixpkgs> {
      inherit system;
      config = import (getEnv "NIXPKGS_CONFIG") // {
        allowBroken = false;
      };
    };

    # When pkgs-overlay is set (e.g. "pkgsCross.aarch64-multiplatform"),
    # resolve that sub-package-set so all lookups happen inside it.
    pkgs =
      if pkgs-overlay != "" then
        let
          overlay-result = pkgs-base.lib.attrByPath (pkgs-base.lib.splitString "." pkgs-overlay) null pkgs-base;
        in
        if overlay-result == null then
          throw "nixpkgs-review: package set '${pkgs-overlay}' not found in nixpkgs for system '${system}'"
        else
          overlay-result
      else
        pkgs-base;

    # Always use lib from the base package set — it is not platform-specific.
    inherit (pkgs-base) lib;

    # nix-eval-jobs only shows derivations, so create an empty one to return
    fake =
      extra:
      derivation {
        name = "fake";
        system = "fake";
        builder = "fake";
      }
      // extra;

    pkgOrFake =
      name: pkg:
      let
        maybeDerivation = tryEval (lib.isDerivation pkg);
        maybePath = tryEval pkg.outPath;
        extra = {
          exists = true;
          broken = !maybeDerivation.success || !maybeDerivation.value || !maybePath.success;
        };
      in
      lib.nameValuePair name (
        builtins.addErrorContext "while evaluating the attribute `${name}`" (
          if extra.broken then fake extra else pkg // extra
        )
      );

    getProperties =
      name:
      let
        attrPath = lib.splitString "." name;
        maybePkg = tryEval (lib.attrByPath attrPath null pkgs);
        pkg = maybePkg.value;
        exists = lib.hasAttrByPath attrPath pkgs;
      in
      # some packages are set to null or throw if they aren't compatible with a platform or package set
      if !maybePkg.success || pkg == null then
        [
          (lib.nameValuePair name (fake {
            inherit exists;
            broken = true;
          }))
        ]
      else if !lib.isDerivation pkg then
        if !lib.isAttrs pkg then
          # if it is not a package, ignore it (it is probably something like overrideAttrs)
          [ ]
        else
          lib.flatten (lib.mapAttrsToList (name': _: getProperties "${name}.${name'}") pkg)
      else
        [ (pkgOrFake name pkg) ];
  in
  listToAttrs (concatMap getProperties attrs) // { recurseForDerivations = true; }
) (fromJSON (readFile attr-json))