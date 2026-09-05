import discord
import os


def environment_flag(environ, name, default=False):
    value = environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def discord_development_config(environ):
    enabled = environment_flag(environ, "DISCORD_DEVELOPMENT_MODE")
    if not enabled:
        return {}, None

    channel_id = environ.get("ALLOWED_MESSAGE_CHANNEL_ID")
    if not channel_id:
        raise RuntimeError(
            "Discord development mode requires ALLOWED_MESSAGE_CHANNEL_ID"
        )

    sync_commands = environment_flag(environ, "DISCORD_SYNC_COMMANDS")
    return {"auto_sync_commands": sync_commands}, str(channel_id)


def command_channel_is_allowed(channel_id, development_channel_id):
    return development_channel_id is None or str(channel_id) == development_channel_id


intents = discord.Intents.default()
intents.message_content = True

bot_options, development_channel_id = discord_development_config(os.environ)
bot = discord.Bot(intents=intents, **bot_options)


if development_channel_id is not None:

    @bot.check
    def development_channel_only(ctx):
        return command_channel_is_allowed(ctx.channel_id, development_channel_id)
