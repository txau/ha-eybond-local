"""Runtime values derived from decoded Sumry/GES 0x7530 telemetry."""

from __future__ import annotations

from typing import Any


def derive_sumry_ges_runtime_values(values: dict[str, Any]) -> dict[str, Any]:
    """Return derived keys that are not direct Modbus registers.

    Line active power L1/L2 come from protocol registers 0x7574/0x7575.
    Total is summed here because the map has no dedicated total register.
    """

    derived: dict[str, Any] = {}
    l1 = values.get("mains_power_l1")
    l2 = values.get("mains_power_l2")
    if isinstance(l1, (int, float)) and isinstance(l2, (int, float)):
        derived["mains_power_total"] = int(round(float(l1) + float(l2)))
    elif isinstance(l1, (int, float)):
        derived["mains_power_total"] = int(round(float(l1)))
    elif isinstance(l2, (int, float)):
        derived["mains_power_total"] = int(round(float(l2)))
    return derived
