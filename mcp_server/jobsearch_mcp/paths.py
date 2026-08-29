"""Locating the workspace on disk.

The server is useful in two very different layouts:

* run from a clone of this repository, where the portal CLIs and the profile
  markdown sit alongside the code;
* installed as a package (``pip install``/``uvx``), where the code lives in
  site-packages and the workspace is wherever the user keeps it.

Guessing wrong is a silent failure - the server starts fine and then reports
"no profile found" - so resolution is explicit and reports what it chose.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

log = logging.getLogger("jobsearch-mcp.paths")

# Files that only exist at the root of a workspace checkout.
_MARKERS = (".claude", ".agents", "jobsearch.config.json")


def workspace_root() -> Path:
    """Best guess at the workspace directory.

    Order: JOBSEARCH_HOME, then the nearest ancestor of this file containing a
    workspace marker, then the nearest ancestor of the working directory, then
    the working directory itself.
    """
    explicit = os.environ.get("JOBSEARCH_HOME")
    if explicit:
        return Path(explicit).expanduser().resolve()

    for start in (Path(__file__).resolve(), Path.cwd().resolve() / "_"):
        for parent in start.parents:
            if any((parent / m).exists() for m in _MARKERS):
                return parent
    return Path.cwd().resolve()
