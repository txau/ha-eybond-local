from __future__ import annotations

from pathlib import Path
import sys
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from custom_components.eybond_local.drivers.sumry_ges_derived import (  # noqa: E402
    derive_sumry_ges_runtime_values,
)


class SumryGesDerivedTests(unittest.TestCase):
    def test_derives_signed_mains_power_products(self) -> None:
        derived = derive_sumry_ges_runtime_values(
            {
                "mains_voltage_l1": 120.0,
                "mains_current_l1": -2.5,
                "mains_voltage_l2": 119.5,
                "mains_current_l2": 1.0,
            }
        )
        self.assertEqual(derived["mains_power_l1"], -300)
        self.assertEqual(derived["mains_power_l2"], 120)
        self.assertEqual(derived["mains_power_total"], -180)

    def test_skips_incomplete_legs(self) -> None:
        derived = derive_sumry_ges_runtime_values(
            {
                "mains_voltage_l1": 120.0,
                "mains_current_l2": 1.0,
            }
        )
        self.assertEqual(derived, {})


if __name__ == "__main__":
    unittest.main()
