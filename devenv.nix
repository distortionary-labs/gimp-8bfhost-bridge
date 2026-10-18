{ pkgs, lib, config, inputs, ... }:

{
  # gcc builds the test filter. GIMP 3 itself (for `make gimp-smoke`) and
  # 8bf-host are not packaged here: install GIMP 3 or point GIMP_CONSOLE at
  # one, and point EIGHTBF_HOST at a build of 8bf-host.
  packages = with pkgs; [ git gcc ruff zip ];

  languages.python = {
    enable = true;
    # The unit tests do not import GIMP, so any Python 3 GIMP 3 ships works.
    package = pkgs.python312.withPackages (ps: [ ps.pytest ]);
  };
}
