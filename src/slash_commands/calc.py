import discord
import math
import asyncio
import logging
import os
from datetime import datetime
from time import monotonic
from zoneinfo import ZoneInfo
from base_queries import challenger_by_discord_id
from simpleeval import simple_eval
from checkin_submission import save_checkin, send_checkin_feedback


class SubmitCheckinView(discord.ui.View):
    def __init__(self, owner_id, tier, timezone_name):
        super().__init__(timeout=600, disable_on_timeout=True)
        self.owner_id = owner_id
        self.tier = tier
        self.children[0].label = f"Submit {tier} Check-in"
        self.timezone = ZoneInfo(timezone_name)
        self.created_date = datetime.now(self.timezone).date()
        self.expires_at = monotonic() + 600
        self.saved = None
        self.attempted = False
        self.lock = asyncio.Lock()

    @discord.ui.button(label="Submit This Check-in", style=discord.ButtonStyle.success)
    async def submit(self, button, interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This calculator result belongs to another user.", ephemeral=True)
            return
        await interaction.response.defer()
        async with self.lock:
            if self.attempted:
                await interaction.followup.send("This submission has already been processed. Check your result before submitting again.", ephemeral=True)
                return
            if monotonic() >= self.expires_at or datetime.now(self.timezone).date() != self.created_date:
                button.disabled = True
                await interaction.edit_original_response(content="This result has expired. Run /calculate_tier again.", view=self)
                self.stop()
                return
            try:
                channel_id = int(os.environ["ALLOWED_MESSAGE_CHANNEL_ID"])
                channel = interaction.client.get_channel(channel_id)
                if channel is None:
                    channel = await interaction.client.fetch_channel(channel_id)
                if interaction.guild_id != channel.guild.id:
                    raise ValueError("Please use the calculator in the challenge server.")
            except Exception:
                logging.exception("Cannot resolve calculator check-in channel")
                await interaction.followup.send("Cannot access the check-in channel. Nothing was submitted.", ephemeral=True)
                return
            self.attempted = True
            button.disabled = True
            try:
                self.saved = await asyncio.to_thread(
                    save_checkin, f"{self.tier} check-in", self.tier,
                    self.owner_id, require_active_member=True,
                )
            except ValueError as exc:
                self.attempted = False
                button.disabled = False
                await interaction.followup.send(str(exc), ephemeral=True)
                return
            except Exception:
                # A connection error at commit can have an ambiguous outcome.
                # Do not allow this result to insert again automatically.
                logging.exception("Calculator check-in save failed")
                await interaction.edit_original_response(content="Could not confirm whether your check-in saved. Check /chart before trying again.", view=self)
                self.stop()
                return
            button.label = "Submitted"
            status = f"Submitted {self.tier}."
            try:
                message = await channel.send(
                    f"<@{self.owner_id}> {self.tier} check-in",
                    allowed_mentions=discord.AllowedMentions(users=[discord.Object(id=self.owner_id)]),
                )
            except Exception:
                logging.exception("Calculator check-in saved but public confirmation failed")
                status = f"Your {self.tier} check-in was saved, but public confirmation failed. Do not submit it again."
            else:
                try:
                    await send_checkin_feedback(message, self.tier, self.saved)
                except Exception:
                    logging.exception("Calculator check-in saved but medal feedback failed")
                    status = f"Your {self.tier} check-in was saved and posted, but medal feedback failed. Do not submit it again."
            self.stop()
            await interaction.edit_original_response(content=status, view=self)


class Modal(discord.ui.Modal):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.add_item(discord.ui.InputText(label="Calories Burnt"))
        self.add_item(discord.ui.InputText(label="Time Spent"))

    async def callback(self, interaction: discord.Interaction):
        id = interaction.user.id
        challenger = challenger_by_discord_id(str(id))

        if challenger is None or not challenger.bmr or challenger.bmr <= 0:
            await interaction.response.send_message("Please register and set a valid BMR before using the calculator.", ephemeral=True)
            return

        try:
            calories = simple_eval(self.children[0].value)
            time = simple_eval(self.children[1].value)
            if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0 for value in (calories, time)):
                raise ValueError("Invalid input")
        except Exception:
            await interaction.response.send_message("Enter non-negative numbers or arithmetic expressions for calories and minutes.", ephemeral=True)
            return
        calTier = self.tier_for_calories(challenger.bmr, calories)
        timeTier = self.tier_for_time(time)
        calToNextTier = self.calories_for_next_tier(challenger.bmr, calTier) - calories
        timeToNextTier = self.time_for_next_tier(timeTier) - time

        embed = discord.Embed()
        embed.add_field(
            name="\u200b",
            value=f"**Calories:** T{calTier}\n+{calToNextTier:g} cals to next tier",
            inline=True,
        )
        embed.add_field(
            name="\u200b",
            value=f"**Time:** T{timeTier}\n+{timeToNextTier:g} mins to next tier",
            inline=True,
        )

        selected_tier = f"T{max(calTier, timeTier)}"
        view = SubmitCheckinView(id, selected_tier, challenger.tz)
        await interaction.response.send_message(
            content="## Tier Results", embeds=[embed], ephemeral=True, view=view
        )

    def calories_for_next_tier(self, bmr, currentTier):
        nextTier = currentTier + 1
        return math.floor((((5*(nextTier - 1))/100)+0.15) * bmr)

    def time_for_next_tier(self, currentTier):
        nextTier = currentTier + 1
        return math.floor(15 * (nextTier + 1))

    def tier_for_calories(self, bmr, calories):
        return max(0, math.floor((20*(calories + 1))/bmr - 2))

    def tier_for_time(self, time):
        return max(0, math.floor(time/15-1))
