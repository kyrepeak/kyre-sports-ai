from __future__ import annotations

from io import StringIO

import pandas as pd


def main() -> int:
    tables = pd.read_html(StringIO("<table><tr><th>x</th></tr><tr><td>1</td></tr></table>"))
    if len(tables) != 1 or int(tables[0].iloc[0, 0]) != 1:
        raise RuntimeError("PANDAS_READ_HTML_RESULT_INVALID")
    print("API2_RUNLESS_PANDAS_READ_HTML=GREEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
