{
  config ? (
    let configFile = builtins.getEnv "NIXPKGS_CONFIG";
    in
      if configFile != "" && builtins.pathExists configFile then
        import configFile
      else
        { }),
  system ? null, # deadnix: skip
}@args:
with import ./config.nix;
let
  currentSystem = if system != null then system else builtins.currentSystem;

  stdenv = {
    inherit mkDerivation;
  };

  mkShell = attrs: mkDerivation (attrs // {
    name = attrs.name or "shell";
    buildCommand = "echo 'mock shell' > $out";
  });

  bashInteractive = mkDerivation {
    name = "bash-interactive";
    buildCommand = ''
      mkdir -p $out/bin
      ln -s ${shell} $out/bin/bash
    '';
  };

  buildEnv = args: mkDerivation {
    inherit (args) name paths;
    buildCommand = ''
      mkdir -p $out
      ln -s $paths $out
    '';
  };

  packages = lib.genAttrs' (lib.range 1 (config.pkgCount or 1)) (
    i:
    lib.nameValuePair "pkg${toString i}" (mkDerivation {
      name = "pkg${toString i}";
      buildCommand = ''
        cat ${./pkg1.txt} > $out
      '';
    }));
in
packages // {
  inherit lib mkShell bashInteractive stdenv buildEnv;
  # A mock alternative package set used by tests for the --pkgs flag
  # (simulates pkgsCross.*, pkgsMusl, pkgsStatic, etc.)
  pkgsAlt = packages // { inherit lib mkShell bashInteractive stdenv buildEnv; };
}
