{
  description = "Isolated local ai agent dev env";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = {self, nixpkgs}:
    let
      system = "aarch64-linux";
      pkgs = import nixpkgs {inherit system;};

      agentEnv = pkgs.buildEnv {
        name = "agent-tools";
        paths = with pkgs; [
          bash
          coreutils
          gnugrep
          gnused
          findutils
          gnutar
          box64
          file
          qemu
          # qemu-user
        ];
      };

      closure = pkgs.closureInfo {
        rootPaths = [agentEnv];
      };
    in
  {
    devShells.${system}.default = pkgs.mkShell {
      packages = with pkgs; [
        bash
        nushell
        bubblewrap
        # coreutils
        # findutils
        # strace
        (python3.withPackages (ps: [ps.ollama ps.toml]))
      ];


      AGENT_ENV = "${agentEnv}";
      AGENT_CLOSURE = "${closure}/store-paths";

      shellHook = ''
          exec nu
        '';
    };
  };
}
