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
    # Community map samples (quky Anenji 12kW / GES 0x7530 family).
    return {
        # Battery 0x7530..
        30000: 541,  # 54.1 V
        30001: 0xFF9C,  # -10.0 A
        30002: 96,
        # PV 0x753B..
        30011: 3205,  # 320.5 V
        30012: 45,  # 4.5 A
        30013: 1442,  # W
        30014: 3180,  # 318.0 V
        30015: 40,  # 4.0 A
        30016: 1272,  # W
        # Output / load L1 0x7548.. (block 30024..30031; 30027/30031 unused)
        30024: 1205,  # 120.5 V
        30025: 85,  # 8.5 A
        30026: 6000,  # 60.00 Hz
        30027: 0,
        30028: 1020,  # W L1
        30029: 1100,  # VA
        30030: 12,  # %
        30031: 0,
        # Output L2 0x7550.. (block 30032..30038; 30034/30038 unused)
        30032: 1204,  # 120.4 V
        30033: 70,  # 7.0 A
        30034: 0,
        30035: 840,  # W
        30036: 900,  # VA
        30037: 10,  # %
        30038: 0,
        # Load total 0x755E
        30046: 1860,  # W
        # Mains 0x756A..
        30058: 1210,  # 121.0 V
        30059: 30,  # 3.0 A
        30060: 5999,  # 59.99 Hz
        30061: 1208,  # 120.8 V
        30062: 25,  # 2.5 A
        # Bus / temps / fan 0x7577..0x757E (30077 unused)
        30071: 3850,  # 385.0 V bus+
        30072: 3845,  # 384.5 V bus-
        30073: 312,  # 31.2 °C PV
        30074: 405,  # 40.5 °C inverter
        30075: 380,  # 38.0 °C transformer
        30076: 275,  # 27.5 °C environment
        30077: 0,
        30078: 35,  # fan duty %
        # CT grid 0x7584..
        30084: 500,  # W
        30085: 450,  # W
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

    async def test_read_values_decodes_pv_load_and_mains(self) -> None:
        driver = ModbusCatalogDriver()
        transport = _transport()
        inverter = await driver.async_probe(transport, _target())
        assert inverter is not None

        values = _full_values(await driver.async_read_values(transport, inverter))
        self.assertEqual(values["pv1_voltage"], 320.5)
        self.assertEqual(values["pv1_current"], 4.5)
        self.assertEqual(values["pv1_power"], 1442)
        self.assertEqual(values["pv2_voltage"], 318.0)
        self.assertEqual(values["pv2_power"], 1272)
        self.assertEqual(values["output_voltage_l1"], 120.5)
        self.assertEqual(values["output_current_l1"], 8.5)
        self.assertEqual(values["output_frequency"], 60.0)
        self.assertEqual(values["load_power_l1"], 1020)
        self.assertEqual(values["load_power_total"], 1860)
        self.assertEqual(values["output_voltage_l2"], 120.4)
        self.assertEqual(values["mains_voltage_l1"], 121.0)
        self.assertEqual(values["mains_current_l1"], 3.0)
        self.assertEqual(values["mains_frequency"], 59.99)
        self.assertEqual(values["mains_voltage_l2"], 120.8)
        self.assertEqual(values["grid_power_l1"], 500)
        self.assertEqual(values["grid_power_l2"], 450)

    async def test_read_values_decodes_temps_bus_and_fan(self) -> None:
        driver = ModbusCatalogDriver()
        transport = _transport()
        inverter = await driver.async_probe(transport, _target())
        assert inverter is not None

        values = _full_values(await driver.async_read_values(transport, inverter))
        self.assertEqual(values["bus_voltage_positive"], 385.0)
        self.assertEqual(values["bus_voltage_negative"], 384.5)
        self.assertEqual(values["pv_temperature"], 31.2)
        self.assertEqual(values["inverter_temperature"], 40.5)
        self.assertEqual(values["transformer_temperature"], 38.0)
        self.assertEqual(values["environment_temperature"], 27.5)
        self.assertEqual(values["internal_fan_duty"], 35)

    async def test_probe_rejects_out_of_envelope_battery_voltage(self) -> None:
        registers = _ges_holding_registers()
        registers[30000] = 1200  # 120.0 V — outside 48 V GES envelope
        driver = ModbusCatalogDriver()
        inverter = await driver.async_probe(_transport(registers), _target())
        self.assertIsNone(inverter)


if __name__ == "__main__":
    unittest.main()
