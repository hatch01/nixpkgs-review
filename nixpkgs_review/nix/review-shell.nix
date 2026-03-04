{
  local-system,
  nixpkgs-config-path,
  # Path to Nix file containing the Nixpkgs config
  attrs-path,
  # Path to Nix file containing a list of attributes to build
  nixpkgs-path,
  # Path to this review's nixpkgs
  pkgs-overlay ? "",
  # Optional alternative package set, e.g. "pkgsMusl" or "pkgsCross.aarch64-multiplatform"
  local-pkgs ? import nixpkgs-path {
    system = local-system;
    config = import nixpkgs-config-path;
  },
  lib ? local-pkgs.lib,
}:

let

  nixpkgs-config = import nixpkgs-config-path;
  extractPackagesForSystem =
    system: system-attrs:
    let
      system-pkg-base = import nixpkgs-path {
        inherit system;
        config = nixpkgs-config;
      };
      system-pkg =
        if pkgs-overlay != "" then
          let
            overlay-result = lib.attrByPath (lib.splitString "." pkgs-overlay) null system-pkg-base;
          in
          if overlay-result == null then
            throw "nixpkgs-review: package set '${pkgs-overlay}' not found in nixpkgs for system '${system}'"
          else
            overlay-result
        else
          system-pkg-base;
    in
    map (attrString: lib.attrByPath (lib.splitString "." attrString) null system-pkg) system-attrs;
  attrs = lib.flatten (lib.mapAttrsToList extractPackagesForSystem (import attrs-path));
  supportIgnoreSingleFileOutputs = (lib.functionArgs local-pkgs.buildEnv) ? ignoreSingleFileOutputs;
  env = local-pkgs.buildEnv (
    {
      name = "env";
      paths = attrs;
      ignoreCollisions = true;
    }
    // lib.optionalAttrs supportIgnoreSingleFileOutputs {
      ignoreSingleFileOutputs = true;
    }
  );
in
(import nixpkgs-path { }).mkShell {
  name = "review-shell";
  preferLocalBuild = true;
  allowSubstitutes = false;
  dontWrapQtApps = true;
  # see test_rev_command_with_pkg_count
  packages = if builtins.length attrs > 50 then [ env ] else attrs;
}
