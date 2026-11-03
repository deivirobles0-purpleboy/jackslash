"""Pruebas locales sin conexión a Discord ni a PostgreSQL."""

import ast
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

os.environ.setdefault("PURPLESLASH_DISCORD_TOKEN", "test-token")
os.environ.setdefault("PURPLESLASH_DATABASE_URL", "postgresql://test:test@localhost/test")
os.environ.setdefault("PURPLESLASH_GUILD_ID", "980073134411644939")

from modules.player_panels import GamePanel, PanelContext, SimplePanel, RouletteNumber


class PanelTests(unittest.IsolatedAsyncioTestCase):
    def test_layouts_are_components_v2(self):
        for kind in ("trabajar", "consultar"):
            panel = SimplePanel(1, kind)
            self.assertEqual(len(panel.to_components()), 1)
            self.assertEqual(panel.to_components()[0]["type"], 17)
        game = GamePanel(1, 100, None)
        game.build()
        self.assertEqual(game.to_components()[0]["type"], 17)

    async def test_cooldown_disables_game_and_enables_bell(self):
        game = GamePanel(1, 100, None)
        with patch("modules.player_panels._cooldown", new=AsyncMock(return_value=9999999999)), \
             patch("modules.player_panels.reminder_enabled", new=AsyncMock(return_value=True)):
            await game.refresh()
        container = game.children[0]
        rows = [child for child in container.children if child.__class__.__name__ == "ActionRow"]
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(button.disabled for button in rows[0].children))
        self.assertTrue(all(not button.disabled for button in rows[1].children))

    def test_number_modal_range(self):
        modal = RouletteNumber(GamePanel(1, 100, None))
        self.assertEqual(modal.title, "Número de ruleta")
        self.assertEqual(modal.number.max_length, 2)

    def test_employment_panel_includes_all_employment_views(self):
        panel = SimplePanel(1, "trabajar")
        rows = [child for child in panel.children[0].children
                if child.__class__.__name__ == "ActionRow"]
        self.assertEqual(
            [button.mode for row in rows for button in row.children],
            ["trabajar", "aplicar", "renunciar", "oficina", "empleos", "exp"],
        )

    async def test_slash_context_uses_first_public_followup(self):
        interaction = SimpleNamespace(
            id=456, user=SimpleNamespace(id=1), guild=object(), client=object(),
            channel=SimpleNamespace(send=AsyncMock(return_value="second")),
            followup=SimpleNamespace(send=AsyncMock(return_value="first")),
        )
        context = PanelContext(interaction, private=False, first_followup=True)
        self.assertEqual(await context.message.reply("one"), "first")
        self.assertEqual(await context.send("two"), "second")
        interaction.followup.send.assert_awaited_once()
        interaction.channel.send.assert_awaited_once()

    def test_standalone_commands_and_message_context_registered(self):
        from modules.player_commands import PlayerCommands, robar_mensaje
        from discord import app_commands
        self.assertEqual(
            {command.name for command in PlayerCommands.__cog_app_commands__},
            {"work", "crime", "collect", "tienda", "rob", "carrera", "retar"},
        )
        self.assertIsInstance(robar_mensaje, app_commands.ContextMenu)

    def test_rob_no_longer_uses_top_positions(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / "modules" / "rob.py").read_text(encoding="utf-8")
        self.assertNotIn("get_balance_ranking", source)
        self.assertNotIn("_get_top_target", source)

    async def test_message_context_targets_message_author(self):
        from modules.player_commands import robar_mensaje
        target = SimpleNamespace(id=42)
        guild = SimpleNamespace(fetch_member=AsyncMock(return_value=target))
        executor = SimpleNamespace(_execute=AsyncMock())
        interaction = SimpleNamespace(
            guild=guild,
            response=SimpleNamespace(defer=AsyncMock()),
            client=SimpleNamespace(get_cog=lambda name: executor),
        )
        message = SimpleNamespace(author=SimpleNamespace(id=42))
        await robar_mensaje.callback(interaction, message)
        guild.fetch_member.assert_awaited_once_with(42)
        executor._execute.assert_awaited_once_with(
            interaction, "Rob", "rob", target,
        )

    def test_legacy_message_dispatch_disabled(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / "bot.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        handler = next(node for node in tree.body
                       if isinstance(node, ast.AsyncFunctionDef) and node.name == "on_message")
        self.assertEqual(len(handler.body), 2)
        self.assertNotIn("modules.adivinar", source)
        self.assertIn("intents.message_content = False", source)

    async def test_roulette_cooldown_starts_after_settlement(self):
        from modules.roulette import Roulette

        events = []
        async def settle(*args):
            events.append("settle")
            return {"ok": True}
        async def cooldown(*args):
            events.append("cooldown")
        async def send(*args, **kwargs):
            events.append("message")

        context = SimpleNamespace(
            author=SimpleNamespace(id=1, nick="Tester", display_name="Tester",
                                   mention="<@1>"),
            message=SimpleNamespace(id=123),
            send=send,
        )
        with patch("modules.roulette.cache.get_game_cooldown_cache", return_value=0), \
             patch("modules.roulette.get_game_cooldown", new=AsyncMock(return_value=0)), \
             patch("modules.roulette.get_user", new=AsyncMock(return_value={"balance": 1000})), \
             patch("modules.roulette.reserve_wager", new=AsyncMock(return_value={"ok": True, "id": "w"})), \
             patch("modules.roulette.settle_wager", new=settle), \
             patch("modules.roulette.set_game_cooldown", new=cooldown), \
             patch("modules.roulette.cache.set_game_cooldown_cache"), \
             patch("modules.roulette.asyncio.sleep", new=AsyncMock()), \
             patch("modules.roulette.random.choice", return_value="1"):
            await Roulette.ruleta.callback(Roulette(None), context, 100, "red")
        self.assertEqual(events, ["message", "settle", "cooldown", "message"])


if __name__ == "__main__":
    unittest.main()
