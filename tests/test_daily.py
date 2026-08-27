"""Daily-counter tests that run without Home Assistant."""

import importlib.util
from pathlib import Path
import unittest

_PATH = Path(__file__).parents[1] / "custom_components" / "ocular_evse" / "daily.py"
_SPEC = importlib.util.spec_from_file_location("ocular_evse_daily", _PATH)
assert _SPEC and _SPEC.loader
_DAILY = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_DAILY)

roll_daily_counter = _DAILY.roll_daily_counter


class DailyCounterTests(unittest.TestCase):
    def test_same_day_preserves_count(self):
        self.assertEqual(
            roll_daily_counter("2026-08-27", 3, "2026-08-27"),
            ("2026-08-27", 3, False),
        )

    def test_new_local_day_resets_count(self):
        self.assertEqual(
            roll_daily_counter("2026-08-26", 3, "2026-08-27"),
            ("2026-08-27", 0, True),
        )

    def test_empty_date_initialises_current_day(self):
        self.assertEqual(
            roll_daily_counter("", 0, "2026-08-27"),
            ("2026-08-27", 0, True),
        )


if __name__ == "__main__":
    unittest.main()
