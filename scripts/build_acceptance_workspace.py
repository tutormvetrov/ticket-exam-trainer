from __future__ import annotations

import sys
from pathlib import Path

from tests.support.workspace_builder import create_acceptance_workspace


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/build_acceptance_workspace.py <workspace-root>")
    create_acceptance_workspace(Path(sys.argv[1]).resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

