"""The legacy engine must remain usable without the integrated SOL checkout."""

import subprocess
import sys
from pathlib import Path


def test_engine_import_without_sol():
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import importlib.abc
import sys

class MissingSOL(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in {"sol", "Frontier_OS"}:
            raise ModuleNotFoundError("Integrated workspace deliberately unavailable", name=fullname)

sys.meta_path.insert(0, MissingSOL())
from excitons import ExcitonEngine
import firmWare.ExcitonEngine as package
assert package.ExcitonEngine is ExcitonEngine
assert "firmWare.ExcitonEngine.geodesic_navigator" not in sys.modules
try:
    package.RiemannianGeodesicNavigator
except ModuleNotFoundError as exc:
    assert exc.name in {"sol", "Frontier_OS"}, exc
else:
    raise AssertionError("Integrated navigation must require SOL")
""",
        ],
        cwd=root,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
