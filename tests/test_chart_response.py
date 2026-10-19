import os
import struct
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch

os.environ.setdefault("DB_CONNECT_STRING", "postgresql://postgres:password@localhost/projects")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import bot
import chart


class ChartResponseTests(unittest.IsolatedAsyncioTestCase):
    async def test_private_embed_references_complete_png_with_no_disk_cache(self):
        days = [chart.DataUnit(day, 1, True, None, "T3", False) for day in chart.weekdays]
        participant = chart.CheckinChartData("Example", days, 7, 5, False, "")
        with patch.object(chart, "knocked_out", return_value=[]):
            svg = chart.checkin_chart(
                [participant], 1000, 600, 1, False, False,
                {"Example": 5}, ("23:59", "00:00", None, (1, "")),
                {"Example": 7}, 35, 7,
            )

        uploaded = []

        async def capture_upload(**kwargs):
            attachment = kwargs["file"]
            self.assertTrue(kwargs["ephemeral"])
            # Covers the old /src/static/... filename leaking into Discord.
            self.assertEqual(attachment.filename, "chart-210.png")
            self.assertNotIn("/", attachment.filename)
            self.assertEqual(
                kwargs["embed"].image.url, f"attachment://{attachment.filename}"
            )
            uploaded.append(attachment.fp.read())

        ctx = NS(followup=NS(send=AsyncMock(side_effect=capture_upload)))
        with patch("builtins.open", side_effect=AssertionError("Must not read a cached chart")):
            await bot.send_current_chart(ctx, svg, 210)

        png = uploaded[0]
        self.assertEqual(png[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(struct.unpack(">II", png[16:24]), (1001, 600))
        self.assertEqual(png[-8:], b"IEND\xaeB`\x82")

    async def test_defer_happens_before_chart_generation(self):
        ctx = NS(defer=AsyncMock(), followup=NS(send=AsyncMock()))

        async def generate(context):
            context.defer.assert_awaited_once_with(ephemeral=True)

        with patch.object(bot, "generate_current_chart", side_effect=generate):
            await bot.get_chart.callback(ctx)

    async def test_render_error_returns_specific_message_without_uploading_stale_image(self):
        ctx = NS(defer=AsyncMock(), followup=NS(send=AsyncMock()))
        with patch.object(bot, "generate_current_chart", side_effect=RuntimeError("Render failed")):
            with self.assertLogs(level="ERROR"):
                await bot.get_chart.callback(ctx)
        ctx.followup.send.assert_awaited_once()
        self.assertIn("try /chart again", ctx.followup.send.call_args.args[0])
        self.assertNotIn("file", ctx.followup.send.call_args.kwargs)

    async def test_no_active_challenge_returns_message(self):
        ctx = NS(followup=NS(send=AsyncMock()))
        with patch.object(bot, "get_current_challenge", return_value=None), patch.object(
            bot, "get_current_challenge_week", return_value=None
        ):
            await bot.generate_current_chart(ctx)
        ctx.followup.send.assert_awaited_once_with(
            "There is no active challenge week right now.", ephemeral=True
        )


if __name__ == "__main__":
    unittest.main()
