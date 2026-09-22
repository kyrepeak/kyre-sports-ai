"""PRA V3.3 UI wiring for the inherited Step-4 availability panel."""
from __future__ import annotations

import wnba_availability_v33 as availability
import wnba_pra_hub_v27 as hub27


class _AvailabilityUIProxy:
    """Delegate to V3.3 while translating diagnostics for the older V2.7 UI."""
    def __getattr__(self, name):
        return getattr(availability, name)

    def availability_diagnostics(self, day):
        d = dict(availability.availability_diagnostics(day) or {})
        # The inherited panel called a healthy feed CONNECTED. V3.3's stronger
        # integrity terminology calls the same successful state VERIFIED.
        if str(d.get("state") or "").upper() == "VERIFIED":
            d["state"] = "CONNECTED"
        d.setdefault("injury_designations", int(d.get("hard_out") or 0) + int(d.get("uncertain") or 0))
        # Older UI counted team sides with five explicit starters.
        teams = int(d.get("teams") or 0)
        starters = int(d.get("confirmed_starters") or 0)
        d.setdefault("lineups_confirmed", min(teams, starters // 5) if teams else 0)
        return d


# The inherited Step-4 page imported V2.7 availability by module name. Repoint
# that display/read path so the page and downstream model use the exact same
# V3.3 status resolver, while keeping its existing panel contract intact.
hub27.availability = _AvailabilityUIProxy()
