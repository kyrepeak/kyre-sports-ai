"""MLB Pitcher Strikeouts O/U V1.0.1 compile-safe bridge.

Loads the isolated V1.0 engine as source, fixes three conditional numeric formatters
in the result-card HTML, then executes the corrected module. No other market is touched.
"""
from pathlib import Path

_path = Path(__file__).with_name("mlb_pitcher_k_hub_v10.py")
source = _path.read_text(encoding="utf-8")
source = source.replace(
    "{r['season_k9']:.1f if r.get('season_k9') is not None else '—'}",
    "{_e(round(float(r.get('season_k9')),1) if r.get('season_k9') is not None else '—')}",
)
source = source.replace(
    "{float(l10k):.1f if l10k is not None else '—'}",
    "{_e(round(float(l10k),1) if l10k is not None else '—')}",
)
source = source.replace(
    "{float(l5k):.1f if l5k is not None else '—'}",
    "{_e(round(float(l5k),1) if l5k is not None else '—')}",
)
source = source.replace('MODEL_VERSION = "Pitcher K V1.0"', 'MODEL_VERSION = "Pitcher K V1.0.1"')
source = source.replace('Pitcher Strikeouts O/U — V1.0', 'Pitcher Strikeouts O/U — V1.0.1')

exec(compile(source, "mlb_pitcher_k_hub_v101_compiled.py", "exec"), globals(), globals())
