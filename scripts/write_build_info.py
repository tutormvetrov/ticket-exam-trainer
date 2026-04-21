from __future__ import annotations

import argparse
from pathlib import Path

from app.build_info import write_runtime_build_info


def main() -> int:
    parser = argparse.ArgumentParser(description="Write runtime build_info.json for packaged builds.")
    parser.add_argument("--output", required=True, help="Target build_info.json path.")
    parser.add_argument("--version", default="", help="Release version or tag (v-prefix is allowed).")
    parser.add_argument("--commit", default="", help="Commit hash to embed.")
    parser.add_argument("--built-at", default="", help="ISO timestamp for build time.")
    args = parser.parse_args()

    info = write_runtime_build_info(
        Path(args.output),
        version=args.version,
        commit=args.commit,
        built_at=args.built_at,
    )
    print(info.release_label)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
