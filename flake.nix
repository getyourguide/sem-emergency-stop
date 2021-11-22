{
  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/31ffc50c";
    flake-utils.url = "github:numtide/flake-utils/7e5bf3925";
  };

  outputs = { self, nixpkgs, flake-utils }:
  flake-utils.lib.eachDefaultSystem (system:
  let
    pkgs = nixpkgs.legacyPackages.${system};
  in
  rec {
    packages = flake-utils.lib.flattenTree {
      sem-emergency-stop = pkgs.stdenv.mkDerivation {
        name = "sem-emergency-stop";
        src = self;

        buildInputs = [ pkgs.python3 pkgs.makeWrapper ];
        phases = [ "unpackPhase" "installPhase" "postFixup" ];
        installPhase = ''
          python -m venv $out
          $out/bin/pip install .
        '';

        postFixup = ''
          wrapProgram $out/bin/sem-emergency-stop --prefix LD_LIBRARY_PATH : "${pkgs.lib.makeLibraryPath [ pkgs.stdenv.cc.cc.lib ]}"
        '';

        meta = {
          description = "sem-emergency-stop";
          platforms = pkgs.lib.platforms.linux ++ pkgs.lib.platforms.darwin;
        };
      };
    };

    apps.sem-emergency-stop = flake-utils.lib.mkApp { drv = packages.sem-emergency-stop; };
    apps.ses-reset-auth = flake-utils.lib.mkApp { drv = packages.sem-emergency-stop; name = "ses-reset-auth"; };
    apps.ses-create-org-token = flake-utils.lib.mkApp { drv = packages.sem-emergency-stop; name = "ses-create-org-token"; };
    defaultApp = apps.sem-emergency-stop;
    defaultPackage = packages.sem-emergency-stop;
  }
  );
}
