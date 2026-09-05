import os
import sys
import unittest
from pathlib import Path


os.environ.setdefault("DB_CONNECT_STRING", "postgresql://postgres:password@localhost/projects")
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from discord_bot import command_channel_is_allowed, discord_development_config


class DiscordBotDevelopmentConfigTests(unittest.TestCase):
    def test_production_config_does_not_scope_existing_commands(self):
        bot_options, channel_id = discord_development_config({})

        self.assertEqual(bot_options, {})
        self.assertIsNone(channel_id)
        self.assertTrue(command_channel_is_allowed("123", channel_id))

    def test_development_config_disables_command_sync_and_scopes_channel(self):
        bot_options, channel_id = discord_development_config(
            {
                "DISCORD_DEVELOPMENT_MODE": "true",
                "ALLOWED_MESSAGE_CHANNEL_ID": "123",
            }
        )

        self.assertEqual(bot_options, {"auto_sync_commands": False})
        self.assertEqual(channel_id, "123")
        self.assertTrue(command_channel_is_allowed(123, channel_id))
        self.assertFalse(command_channel_is_allowed(999, channel_id))

    def test_development_config_can_explicitly_enable_command_sync(self):
        bot_options, _ = discord_development_config(
            {
                "DISCORD_DEVELOPMENT_MODE": "true",
                "DISCORD_SYNC_COMMANDS": "true",
                "ALLOWED_MESSAGE_CHANNEL_ID": "123",
            }
        )

        self.assertEqual(bot_options, {"auto_sync_commands": True})

    def test_development_config_requires_channel_id(self):
        with self.assertRaisesRegex(RuntimeError, "requires"):
            discord_development_config(
                {
                    "DISCORD_DEVELOPMENT_MODE": "true",
                }
            )


if __name__ == "__main__":
    unittest.main()
