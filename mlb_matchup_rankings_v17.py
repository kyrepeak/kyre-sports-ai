"""MLB Statcast feed V1.7.1 — shared fast cache + V1.5 compatibility hook.

Keeps V1.5 data contract while avoiding repeated slow Savant requests. Successful
player-season frames are cached for an hour; failures are cached briefly so a
slow/unavailable Savant endpoint cannot repeatedly stall the Streamlit page.
"""
from __future__ import annotations

import io
import pandas as pd
import requests
import streamlit as st

import mlb_matchup_rankings_v15 as base

VERSION = "MLB Statcast Feed V1.7.1"
SAVANT_CSV = base.SAVANT_CSV
_savant_params = base._savant_params
_bullpen_profile = base._bullpen_profile

_SESSION = requests.Session()
_SESSION.headers.update({
    "User-Agent":"Mozilla/5.0 (compatible; KyreSportsAI/1.0)",
    "Accept":"text/csv,text/plain,*/*",
    "Referer":"https://baseballsavant.mlb.com/statcast_search",
})

@st.cache_data(ttl=3600, show_spinner=False)
def _statcast_success(player_id, year, player_type):
    """One short Savant attempt; successful frames are shared by every matchup."""
    if not player_id:
        return None
    try:
        r=_SESSION.get(SAVANT_CSV, params=_savant_params(player_id,year,player_type), timeout=(4,10))
        r.raise_for_status()
        text=(r.text or "").lstrip("\ufeff").strip()
        if not text or text[:1] in ("<","{"):
            return None
        df=pd.read_csv(io.StringIO(text),low_memory=False)
        required={"pitch_type","batter","pitcher"}
        if df.empty or not required.issubset(set(map(str,df.columns))):
            return None
        idcol="batter" if player_type=="batter" else "pitcher"
        ids=pd.to_numeric(df[idcol],errors="coerce")
        filtered=df.loc[ids==int(player_id)].copy()
        return filtered if not filtered.empty else df
    except Exception:
        return None

@st.cache_data(ttl=120, show_spinner=False)
def _statcast_failure_guard(player_id, year, player_type):
    """Briefly remember failures so reruns/buttons do not hammer a slow endpoint."""
    df=_statcast_success(player_id,year,player_type)
    if df is None:
        return {"status":"PENDING","rows":0,"frame":None,"error":"Statcast temporarily unavailable; fast cache will retry shortly","http_status":None,"query_type":"details","cache":"MISS"}
    return {"status":"VERIFIED","rows":len(df),"frame":df,"error":"","http_status":200,"query_type":"details","cache":"SHARED"}

def _statcast_rows(player_id, year, player_type):
    return _statcast_failure_guard(int(player_id) if player_id else 0,int(year),str(player_type))

def _install_hotfixes():
    """Compatibility shim expected by rankings V1.6+.

    Preserve V1.5's runtime monkeypatch behavior, but point all Statcast calls to
    this module's shared fast cache instead of the older 18/28-second fetcher.
    """
    try:
        base._install_hotfixes()
    except Exception:
        pass
    base._savant_params = _savant_params
    base._statcast_rows = _statcast_rows
    base._bullpen_profile = _bullpen_profile
    try:
        base.base._savant_params = _savant_params
        base.base._statcast_rows = _statcast_rows
    except Exception:
        pass
    try:
        base.bpbase._bullpen_profile = _bullpen_profile
    except Exception:
        pass
