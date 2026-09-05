"""Every test runs against a freshly generated small catalogue.

The fixture points LEDGER_DB at a temporary file, so a test run never depends on
— or disturbs — whatever the reader has in data/generated/.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
GENERATOR = REPO_ROOT / "data" / "generate.py"


def _load_generator():
    spec = importlib.util.spec_from_file_location("ledger_datagen", GENERATOR)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session", autouse=True)
def catalogue(tmp_path_factory) -> Path:
    path = tmp_path_factory.mktemp("catalogue") / "ledger.db"
    _load_generator().build("small", path)
    os.environ["LEDGER_DB"] = str(path)
    return path


@pytest.fixture
def client():
    from fastmcp import Client

    from ledger.server import mcp

    return Client(mcp)
