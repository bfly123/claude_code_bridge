from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path

_LIB_ROOT = Path(__file__).resolve().parents[1]
if str(_LIB_ROOT) not in sys.path:
    sys.path.insert(0, str(_LIB_ROOT))

from ccbd.app import CcbdApp


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog='python -m ccbd.main')
    parser.add_argument('--project', required=True)
    args = parser.parse_args(argv)

    app = CcbdApp(args.project)
    try:
        app.serve_forever()
    except KeyboardInterrupt:
        app.shutdown()
        return 130
    except Exception:
        traceback.print_exc(file=sys.stderr)
        raise
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
