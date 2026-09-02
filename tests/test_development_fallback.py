import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


os.environ.setdefault("DB_CONNECT_STRING", "postgresql://postgres:password@localhost/projects")
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

import main


class DevelopmentDateFallbackTests(unittest.TestCase):
    def test_disabled_fallback_preserves_current_values(self):
        challenge = SimpleNamespace(id=29)
        challenge_week = SimpleNamespace(id=203, challenge_id=29)

        with patch.dict(
            os.environ, {"DEV_FALLBACK_TO_LATEST_CHALLENGE": "false"}
        ), patch.object(main, "fetchone") as fetchone:
            result = main.apply_development_date_fallback(challenge, challenge_week)

        self.assertEqual(result, (challenge, challenge_week, False))
        fetchone.assert_not_called()

    def test_enabled_fallback_loads_latest_challenge_and_its_latest_week(self):
        challenge = SimpleNamespace(id=29)
        challenge_week = SimpleNamespace(id=203, challenge_id=29)

        with patch.dict(
            os.environ, {"DEV_FALLBACK_TO_LATEST_CHALLENGE": "true"}
        ), patch.object(
            main, "fetchone", side_effect=[challenge, challenge_week]
        ) as fetchone:
            result = main.apply_development_date_fallback(None, None)

        self.assertEqual(result, (challenge, challenge_week, True))
        self.assertEqual(fetchone.call_count, 2)
        self.assertIn('order by "end" desc', fetchone.call_args_list[0].args[0])
        self.assertEqual(fetchone.call_args_list[1].args[1], [29])

    def test_enabled_fallback_does_not_replace_an_active_week(self):
        challenge = SimpleNamespace(id=29)
        challenge_week = SimpleNamespace(id=203, challenge_id=29)

        with patch.dict(
            os.environ, {"DEV_FALLBACK_TO_LATEST_CHALLENGE": "yes"}
        ), patch.object(main, "fetchone") as fetchone:
            result = main.apply_development_date_fallback(challenge, challenge_week)

        self.assertEqual(result, (challenge, challenge_week, False))
        fetchone.assert_not_called()


if __name__ == "__main__":
    unittest.main()
