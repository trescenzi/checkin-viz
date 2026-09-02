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
import base_queries


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

    def test_challenger_mulligan_uses_latest_challenge_in_development(self):
        latest_challenge = SimpleNamespace(id=29)
        mulligan = SimpleNamespace(mulligan=123)

        with patch.dict(
            os.environ, {"DEV_FALLBACK_TO_LATEST_CHALLENGE": "true"}
        ), patch.object(
            main, "fetchone", side_effect=[None, latest_challenge, mulligan]
        ) as fetchone:
            result = main.challenger_mulligan_for_display(18)

        self.assertIs(result, mulligan)
        self.assertEqual(fetchone.call_count, 3)
        self.assertIn("CURRENT_DATE", fetchone.call_args_list[0].args[0])
        self.assertIn('order by "end" desc', fetchone.call_args_list[1].args[0])
        self.assertEqual(fetchone.call_args_list[2].args[1], [18, 29])

    def test_challenger_mulligan_does_not_fall_back_in_production(self):
        with patch.dict(
            os.environ, {"DEV_FALLBACK_TO_LATEST_CHALLENGE": "false"}
        ), patch.object(main, "fetchone", return_value=None) as fetchone:
            result = main.challenger_mulligan_for_display(18)

        self.assertIsNone(result)
        fetchone.assert_called_once()

    def test_shared_challenge_query_falls_back_for_local_services(self):
        latest_challenge = SimpleNamespace(id=29)

        with patch.dict(
            os.environ, {"DEV_FALLBACK_TO_LATEST_CHALLENGE": "true"}
        ), patch.object(
            base_queries, "fetchone", side_effect=[None, latest_challenge]
        ) as fetchone:
            result = base_queries.get_current_challenge()

        self.assertIs(result, latest_challenge)
        self.assertEqual(fetchone.call_count, 2)
        self.assertIn('order by "end" desc', fetchone.call_args_list[1].args[0])

    def test_shared_week_query_falls_back_for_local_services(self):
        latest_week = SimpleNamespace(id=203, challenge_id=29)

        with patch.dict(
            os.environ, {"DEV_FALLBACK_TO_LATEST_CHALLENGE": "true"}
        ), patch.object(
            base_queries, "fetchone", side_effect=[None, latest_week]
        ) as fetchone:
            result = base_queries.get_current_challenge_week()

        self.assertIs(result, latest_week)
        self.assertEqual(fetchone.call_count, 2)
        self.assertIn('order by "end" desc', fetchone.call_args_list[1].args[0])

    def test_shared_queries_do_not_fall_back_in_production(self):
        with patch.dict(
            os.environ, {"DEV_FALLBACK_TO_LATEST_CHALLENGE": "false"}
        ), patch.object(base_queries, "fetchone", return_value=None) as fetchone:
            challenge = base_queries.get_current_challenge()
            challenge_week = base_queries.get_current_challenge_week()

        self.assertIsNone(challenge)
        self.assertIsNone(challenge_week)
        self.assertEqual(fetchone.call_count, 2)


if __name__ == "__main__":
    unittest.main()
