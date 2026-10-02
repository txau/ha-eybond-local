from __future__ import annotations

from pathlib import Path
import sys
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from custom_components.eybond_local.drivers.modbus_catalog import ModbusCatalogDriver  # noqa: E402
from custom_components.eybond_local.drivers.read_result import (  # noqa: E402
    DriverReadMode,
    DriverReadResult,
)
from custom_components.eybond_local.fixtures.transport import FixtureTransport  # noqa: E402
from custom_components.eybond_local.models import ProbeTarget  # noqa: E402


def _full_values(result: DriverReadResult) -> dict[str, object]:
    if type(result) is not DriverReadResult or result.mode is not DriverReadMode.FULL:
        raise AssertionError("catalog runtime read must be an exact FULL result")
    return result.values


def _target() -> ProbeTarget:
    return ProbeTarget(devcode=1, collector_addr=255, device_addr=1)


def _ges_holding_registers() -> dict[int, int]:
    # Community map: 0x7530=30000 V*0.1, 0x7531 current*0.1 signed, 0x7532 SOC%.
    return {
        30000: 541,  # 54.1 V
        30001: 0xFF9C,  # -10.0 A as int16
        30002: 96,
    }


def _transport(registers: dict[int, int] | None = None) -> FixtureTransport:
    return FixtureTransport(
        registers=_ges_holding_registers() if registers is None else registers,
        input_registers={},
        command_responses=None,
        probe_target=_target(),
    )


class SumryGes7530CatalogTests(unittest.IsolatedAsyncioTestCase):
    async def test_probe_matches_community_battery_anchors(self) -> None:
        driver = ModbusCatalogDriver()
        inverter = await driver.async_probe(_transport(), _target())

        assert inverter is not None
        self.assertEqual(inverter.driver_key, "modbus_catalog")
        self.assertEqual(inverter.variant_key, "sumry_ges_7530")
        self.assertEqual(inverter.register_schema_name, "sumry_ges_7530/base.json")
        detection = inverter.details["catalog_detection"]
        self.assertEqual(detection["surface_key"], "sumry_ges_7530_read_only")
        self.assertIn("identity.sumry_ges_battery_voltage_raw", detection["evidence"])

    async def test_read_values_decodes_battery_voltage(self) -> None:
        driver = ModbusCatalogDriver()
        transport = _transport()
        inverter = await driver.async_probe(transport, _target())
        assert inverter is not None

        values = _full_values(await driver.async_read_values(transport, inverter))
        self.assertEqual(values["battery_voltage"], 54.1)
        self.assertEqual(values["battery_current"], -10.0)
        self.assertEqual(values["battery_percent"], 96)

    async def test_probe_rejects_out_of_envelope_battery_voltage(self) -> None:
        registers = _ges_holding_registers()
        registers[30000] = 1200  # 120.0 V — outside 48 V GES envelope
        driver = ModbusCatalogDriver()
        inverter = await driver.async_probe(_transport(registers), _target())
        self.assertIsNone(inverter)


if __name__ == "__main__":
    unittest.main()
