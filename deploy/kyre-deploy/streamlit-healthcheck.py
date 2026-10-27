from __future__ import annotations

import os
import sys
import urllib.request


port = os.environ.get("PORT", "8501")
url = f"http://127.0.0.1:{port}/_stcore/health"

try:
    with urllib.request.urlopen(url, timeout=4) as response:
        body = response.read().decode("utf-8", errors="replace").strip().lower()
        ok = response.status == 200 and body in {"ok", "healthy"}
except Exception:
    ok = False

raise SystemExit(0 if ok else 1)
