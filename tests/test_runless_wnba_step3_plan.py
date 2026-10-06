import json
from pathlib import Path
ROOT=Path(__file__).parents[1]
def test_wnba_plan_focus():
 p=json.loads((ROOT/'devsystem/runless_proof_plans/wnba-pra-repair-v1-step3-data-completeness.json').read_text());text=json.dumps(p)
 assert p['freeze_token']=='WNBA_PRA_REPAIR_V1_STEP3_FROZEN';assert p['probes'][0]['url']=='https://pickvault.streamlit.app';assert 'tests/test_wnba_pra_repair_v1_step3.py' in text;assert '/actions/' not in text;assert 'cfb' not in text.lower() and 'nba' not in text.lower().replace('wnba','')
