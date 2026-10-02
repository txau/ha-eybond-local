"""Runtime values derived from decoded Sumry/GES 0x7530 telemetry."""

from __future__ import annotations

from typing import Any


def derive_sumry_ges_runtime_values(values: dict[str, Any]) -> dict[str, Any]:
    """Return derived keys that are not direct Modbus registers.

    Community ESPHome maps compute several power sensors from V×I (and similar)
    rather than dedicated holding registers.
    """

    derived: dict[str, Any] = {}

    l1 = _product_watts(values.get("mains_voltage_l1"), values.get("mains_current_l1"))
    if l1 is not None:
        derived["mains_power_l1"] = l1

    l2 = _product_watts(values.get("mains_voltage_l2"), values.get("mains_current_l2"))
    if l2 is not None:
        derived["mains_power_l2"] = l2

    if l1 is not None and l2 is not None:
        derived["mains_power_total"] = int(round(l1 + l2))
    elif l1 is not None:
        derived["mains_power_total"] = l1
    elif l2 is not None:
        derived["mains_power_total"] = l2

    return derived


def _product_watts(voltage: Any, current: Any) -> int | None:
    if not isinstance(voltage, (int, float)) or not isinstance(current, (int, float)):
        return None
    return int(round(float(voltage) * float(current)))
