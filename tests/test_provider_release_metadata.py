"""Release identities and uploadable requirements for the provider worker."""

import ast
import json
from pathlib import Path

from packaging.requirements import Requirement
from packaging.version import Version

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib


ROOT = Path(__file__).resolve().parents[1]


def test_worker_release_uses_a_new_consistent_version():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    value = ast.literal_eval(
        next(
            line.split("=", 1)[1].strip()
            for line in (ROOT / "cognitive_castle/version.py").read_text().splitlines()
            if line.startswith("__version__")
        )
    )
    assert Version(value) > Version("3.4.1"), "3.4.1 already identifies a historical release"
    assert project["version"] == value
    for relative in (".claude-plugin/plugin.json", ".codex-plugin/plugin.json"):
        assert json.loads((ROOT / relative).read_text())["version"] == value
    marketplace = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text())
    assert marketplace["plugins"][0]["version"] == value


def test_worker_distribution_requires_only_index_dependencies():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    requirements = list(project["dependencies"])
    for extra in project["optional-dependencies"].values():
        requirements.extend(extra)
    assert all(Requirement(value).url is None for value in requirements), (
        "Public package indexes reject direct URL Requires-Dist entries; "
        "provision the optional spaCy language model explicitly"
    )
