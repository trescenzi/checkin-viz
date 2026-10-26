import os
import sys
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch

os.environ.setdefault("DB_CONNECT_STRING", "postgresql://postgres:password@localhost/projects")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from slash_commands import medal_case
import medals
import test_personal_tier_medal as fixtures


def standing(medal_name, owner="123", emoji="💪"):
    return NS(medal_name=medal_name, discord_id=owner, medal_emoji=emoji)


class MedalCaseCommandTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.ctx = NS(author=NS(id=123), defer=AsyncMock(), followup=NS(send=AsyncMock()))
        self.challenger = NS(id=42, tz="Asia/Tokyo")
        self.week = NS(id=7, challenge_id=2)

    async def test_private_case_contains_only_users_current_stealable_medals(self):
        record = NS(tier="T15", record_date=date(2026, 10, 25))
        rows = [
            standing("highest_tier_week"), standing("earliest_for_week", "456"),
            standing("green", emoji="🟩"), standing("highest_tier_personal", emoji="🏆"),
        ]
        with patch.object(medal_case, "challenger_by_discord_id", return_value=self.challenger) as lookup, patch.object(
            medal_case, "get_current_challenge_week", return_value=self.week
        ) as week_lookup, patch.object(medals, "get_current_week_medal_standings", return_value=rows) as holders, patch.object(
            medals, "get_personal_tier_record", return_value=record
        ) as personal, patch.object(medals, "update_medal_table") as update:
            await medal_case.send_medal_case(self.ctx)
        self.ctx.defer.assert_awaited_once_with(ephemeral=True)
        lookup.assert_called_once_with("123")
        week_lookup.assert_called_once_with("Asia/Tokyo")
        holders.assert_called_once_with(2, 7)
        personal.assert_called_once_with(42)
        update.assert_not_called()
        self.ctx.followup.send.assert_awaited_once()
        content = self.ctx.followup.send.call_args.args[0]
        self.assertTrue(self.ctx.followup.send.call_args.kwargs["ephemeral"])
        self.assertIn("Highest Weekly Tier", content)
        self.assertIn("Highest Ever Personal Tier: T15", content)
        self.assertIn("October 25, 2026", content)
        self.assertNotIn("Earliest Weekly Check-in", content)
        self.assertNotIn("Green Week", content)
        self.assertEqual(content.count("Highest Ever Personal Tier"), 1)

    async def test_record_is_shown_between_challenges(self):
        with patch.object(medal_case, "challenger_by_discord_id", return_value=self.challenger), patch.object(
            medal_case, "get_current_challenge_week", return_value=None
        ), patch.object(medals, "get_current_week_medal_standings") as holders, patch.object(
            medals, "get_personal_tier_record", return_value=NS(tier="T0", record_date=date(2025, 1, 2))
        ):
            await medal_case.send_medal_case(self.ctx)
        holders.assert_not_called()
        content = self.ctx.followup.send.call_args.args[0]
        self.assertIn("no active challenge week", content)
        self.assertIn("Highest Ever Personal Tier: T0", content)
        self.assertTrue(self.ctx.followup.send.call_args.kwargs["ephemeral"])

    async def test_unregistered_user_gets_private_explanation(self):
        with patch.object(medal_case, "challenger_by_discord_id", return_value=None), patch.object(
            medals, "get_personal_tier_record"
        ) as personal:
            await medal_case.send_medal_case(self.ctx)
        personal.assert_not_called()
        self.assertIn("aren't registered", self.ctx.followup.send.call_args.args[0])
        self.assertTrue(self.ctx.followup.send.call_args.kwargs["ephemeral"])

    async def test_database_failure_stays_private_and_does_not_expose_error(self):
        with patch.object(medal_case, "challenger_by_discord_id", side_effect=RuntimeError("private DB details")):
            with self.assertLogs(level="ERROR"):
                await medal_case.send_medal_case(self.ctx)
        self.assertIn("try /medal-case", self.ctx.followup.send.call_args.args[0])
        self.assertNotIn("private DB details", self.ctx.followup.send.call_args.args[0])
        self.assertTrue(self.ctx.followup.send.call_args.kwargs["ephemeral"])

    def test_empty_case_has_clear_messages(self):
        content = medal_case.build_medal_case([], None)
        self.assertIn("aren't currently holding any stealable medals", content)
        self.assertIn("No personal tier record yet", content)

    async def test_command_is_registered_with_requested_name(self):
        import bot
        self.assertEqual(bot.medal_case_command.name, "medal-case")
        with patch.object(medal_case, "send_medal_case", new_callable=AsyncMock) as send:
            await bot.medal_case_command.callback(self.ctx)
        send.assert_awaited_once_with(self.ctx)


@unittest.skipUnless(os.environ.get("TEST_DB_CONNECT_STRING"), "Set TEST_DB_CONNECT_STRING to run PostgreSQL tests")
class MedalCasePostgresTests(unittest.TestCase):
    setUp = fixtures.PersonalTierPostgresTests.setUp
    checkin = fixtures.PersonalTierPostgresTests.checkin

    def test_all_time_record_uses_numeric_tier_first_date_and_original_timezone(self):
        self.checkin(1, "T9", "2025-01-01T12:00Z", week=1)
        self.checkin(2, "T14", "2025-01-02T01:30Z", week=1, tz="America/Los_Angeles")
        self.checkin(3, "T14", "2026-01-02T12:00Z", tz="Asia/Tokyo")
        record = medals.get_personal_tier_record(1)
        self.assertEqual(record.tier, "T14")
        self.assertEqual(record.record_date, date(2025, 1, 1))
        self.assertIsNone(medals.get_personal_tier_record(2))

    def test_personal_record_excludes_invalid_tiers_and_automatic_mulligans(self):
        self.checkin(1, "T15", "2025-01-01T12:00Z", week=1)
        self.conn.execute("INSERT INTO challenger_challenges VALUES (1, 1, 1)")
        self.checkin(2, "invalid", "2026-01-01T12:00Z")
        self.checkin(3, "T0", "2026-01-02T12:00Z")
        self.assertEqual(medals.get_personal_tier_record(1).tier, "T0")

    def award(self, name, checkin_id, owner, week=2):
        self.conn.execute(
            "INSERT INTO medals (medal, checkin_id, challenger_id, challenge_id, challenge_week_id, emoji) "
            "VALUES (%s, %s, %s, 2, %s, '💪')", [name, checkin_id, owner, week],
        )

    def test_stolen_medal_only_shows_current_owner_even_with_tied_award_times(self):
        self.checkin(1, "T5", "2026-01-01T12:00Z")
        self.checkin(2, "T6", "2026-01-02T12:00Z", challenger=2)
        self.award("highest_tier_week", 1, 1)
        self.award("highest_tier_week", 2, 2)
        rows = medals.get_current_week_medal_standings(2, 2)
        self.assertEqual([(row.medal_name, row.discord_id) for row in rows], [("highest_tier_week", "456")])

    def test_old_weekly_medals_expire_but_challenge_medals_carry_between_weeks(self):
        self.checkin(1, "T5", "2026-01-01T12:00Z")
        self.checkin(2, "T6", "2026-01-08T12:00Z", week=3, challenger=2)
        self.award("highest_tier_week", 1, 1)
        self.award("highest_tier_challenge", 1, 1)
        self.award("highest_tier_week", 2, 2, week=3)
        rows = medals.get_current_week_medal_standings(2, 3)
        self.assertEqual(
            {(row.medal_name, row.discord_id) for row in rows},
            {("highest_tier_challenge", "123"), ("highest_tier_week", "456")},
        )


if __name__ == "__main__":
    unittest.main()
