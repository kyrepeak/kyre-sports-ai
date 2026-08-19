"""PRA V3.3 UI wiring for the inherited Step-4 availability panel."""
from __future__ import annotations

import wnba_availability_v33 as availability
import wnba_pra_hub_v27 as hub27

# The inherited Step-4 page imported V2.7 availability by module name. Repoint
# that display/read path so the page and downstream model use the exact same
# V3.3 status resolver.
hub27.availability = availability
