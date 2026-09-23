"""Named defence configurations for G4 (docs/preregistration.md, G4 entry) as NetBeaconSim keyword arguments.

``d1``: the wrap fix (unwrapped clock, takeover refreshes last_classified, packet-gap timestamp keeps bits [41:10]).
``d3cR``: D1 plus credit-based rent admission at R packets per second (deployable variant); ``d3a``: D1 plus
age-only eviction; ``d3rR``: D1 plus the literal cumulative-rate predicate (emulator-only). D2 (a secret
irreducible polynomial) is a property of the benign hash, not a NetBeaconSim switch, so it is run as the ``k0`` mode.
"""

from __future__ import annotations

import re

__all__ = ["DEFENCES", "defence_kwargs"]

D1 = {"wrap_window": False, "takeover_refresh": True, "fix_ipd_wrap": True}
DEFENCES = ("d1", "d3a", "d3c<R>", "d3r<R>")


def defence_kwargs(name: str | None) -> dict:
    """Keyword arguments for :class:`NetBeaconSim`; ``None`` or ``""`` is the shipped design."""
    if not name:
        return {}
    if name == "d1":
        return dict(D1)
    if name == "d3a":
        return {**D1, "rent": "age"}
    m = re.fullmatch(r"d3([cr])(\d+)", name)
    if m:
        return {**D1, "rent": "credit" if m.group(1) == "c" else "rate", "rent_rmin": float(m.group(2))}
    raise ValueError(f"unknown defence {name!r}")
