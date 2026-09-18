"""ledger — the server, assembled.

Importing this module is what registers everything: the modules below attach
their tools, resources and prompts to the shared instance as a side effect of
being imported. Anything that needs the server imports `mcp` from here, so
there is exactly one place where the full surface is known to be complete.
"""

from __future__ import annotations

from ledger import prompts as _prompts  # noqa: F401  (registers prompts)
from ledger import resources as _resources  # noqa: F401  (registers resources)
from ledger import scans as _scans  # noqa: F401  (registers the scan tools)
from ledger import tools as _tools  # noqa: F401  (registers tools)
from ledger import writes as _writes  # noqa: F401  (registers the write tool)
from ledger.app import mcp

__all__ = ["mcp"]
