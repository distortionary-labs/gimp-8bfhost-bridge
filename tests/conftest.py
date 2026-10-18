import os
import shutil
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES = os.path.join(ROOT, "tests", "fixtures")

# The package lives inside the plug-in folder GIMP loads.
sys.path.insert(0, os.path.join(ROOT, "gimp-8bfhost-bridge"))
sys.path.insert(0, os.path.join(ROOT, "tests"))

from fixture_pipl import pipl_sidecar  # noqa: E402

LIBRARY_SUFFIX = ".dylib" if sys.platform == "darwin" else ".so"


def _compiler():
    for name in (os.environ.get("CC"), "cc", "gcc", "clang"):
        if name and shutil.which(name):
            return name
    return None


@pytest.fixture(scope="session")
def eightbf_host():
    """A dynamically linked 8bf-host, from $EIGHTBF_HOST.

    Release builds for Linux are static and cannot load native .so
    filters, so these tests need a build from ``cargo build``.
    """
    path = os.environ.get("EIGHTBF_HOST")
    if not path:
        pytest.skip("set EIGHTBF_HOST to a dynamically linked 8bf-host to run this test")
    return path


@pytest.fixture(scope="session")
def filter_folder(tmp_path_factory):
    """A folder with the test filter built natively, as "Tests/Invert" and "Tests/Error"."""
    compiler = _compiler()
    if compiler is None or sys.platform == "win32":
        pytest.skip("needs a C compiler on a Unix host")
    folder = tmp_path_factory.mktemp("plugins")
    source = os.path.join(FIXTURES, "testfilter.c")
    for name, entry in (("Invert", "InvertMain"), ("Error", "ErrorMain")):
        library = folder / (name.lower() + LIBRARY_SUFFIX)
        command = [compiler, "-shared", "-fPIC", "-O1", "-o", str(library), source]
        subprocess.run(command, check=True)
        (folder / (library.name + ".pipl")).write_bytes(pipl_sidecar(name, "Tests", entry))
    return str(folder)
