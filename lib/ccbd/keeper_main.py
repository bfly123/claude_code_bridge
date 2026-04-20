from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path

_LIB_ROOT = Path(__file__).resolve().parents[1]
if str(_LIB_ROOT) not in sys.path:
    sys.path.insert(0, str(_LIB_ROOT))

from ccbd.keeper import ProjectKeeper


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog='python -m ccbd.keeper_main')
    parser.add_argument('--project', required=True)
    args = parser.parse_args(argv)

    app = ProjectKeeper(args.project)
    try:
        return app.run_forever()
    except KeyboardInterrupt:
        return 130
    except Exception:
        traceback.print_exc(file=sys.stderr)
        raise


if __name__ == '__main__':
    raise SystemExit(main())
