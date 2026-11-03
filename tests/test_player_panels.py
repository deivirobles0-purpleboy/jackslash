"""Pruebas locales sin conexión a Discord ni a PostgreSQL."""

import ast
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

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

    async def test_cooldown_disables_game_without_panel_bells(self):
        game = GamePanel(1, 100, None)
        with patch("modules.player_panels._cooldown", new=AsyncMock(return_value=9999999999)):
            await game.refresh()
        container = game.children[0]
        rows = [child for child in container.children if child.__class__.__name__ == "ActionRow"]
        self.assertEqual(len(rows), 4)
        self.assertTrue(all(len(row.children) == 1 for row in rows))
        self.assertTrue(all(row.children[0].disabled for row in rows))
        self.assertFalse(any("🔔" in row.children[0].label for row in rows))

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
        self.assertTrue(all(len(row.children) == 1 for row in rows))

    def test_consult_panel_stacks_its_buttons(self):
        panel = SimplePanel(1, "consultar")
        rows = [child for child in panel.children[0].children
                if child.__class__.__name__ == "ActionRow"]
        self.assertEqual(len(rows), 6)
        self.assertTrue(all(len(row.children) == 1 for row in rows))
        self.assertIn("Panel de consultas Purplejack", str(panel.to_components()))

    def test_game_panel_has_no_redundant_start_notice(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / "modules" / "player_panels.py").read_text(encoding="utf-8")
        self.assertNotIn("Iniciando **", source)

    def test_reminder_prompt_is_v2_with_one_explicit_game(self):
        from core.game_reminders import ReminderPrompt
        prompt = ReminderPrompt(42, "dados", 9999999999)
        self.assertEqual(prompt.to_components()[0]["type"], 17)
        self.assertIn("Dados", str(prompt.to_components()))
        self.assertEqual(prompt.timeout, 15)

    async def test_reminder_confirmation_persists_and_deletes_after_three_seconds(self):
        from core.game_reminders import ReminderPrompt
        prompt = ReminderPrompt(42, "dados", 9999999999)
        button = prompt.children[0].children[1].children[0]
        message = SimpleNamespace(edit=AsyncMock(), delete=AsyncMock())
        interaction = SimpleNamespace(
            user=SimpleNamespace(id=42),
            response=SimpleNamespace(defer=AsyncMock()),
            followup=SimpleNamespace(send=AsyncMock()),
            message=message,
        )
        with patch("core.game_reminders.database.get_game_cooldown",
                   new=AsyncMock(return_value=9999999999)), \
             patch("core.game_reminders.set_reminder", new=AsyncMock()) as save, \
             patch("core.game_reminders.asyncio.sleep", new=AsyncMock()) as sleep:
            await button.callback(interaction)
        save.assert_awaited_once_with(42, "dados", 9999999999)
        sleep.assert_awaited_once_with(3)
        message.edit.assert_awaited_once()
        message.delete.assert_awaited_once()

    async def test_reminder_prompt_expires_after_fifteen_seconds(self):
        from core.game_reminders import ReminderPrompt, _delete_prompt_after
        prompt = ReminderPrompt(42, "memo", 9999999999)
        prompt.message = SimpleNamespace(delete=AsyncMock())
        with patch("core.game_reminders.asyncio.sleep", new=AsyncMock()) as sleep:
            await _delete_prompt_after(prompt, 15)
        sleep.assert_awaited_once_with(15)
        prompt.message.delete.assert_awaited_once()

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

    async def test_slash_migration_verifies_guild_before_global_cleanup(self):
        import bot as bot_module

        events = []
        local = [SimpleNamespace(name=name)
                 for name in bot_module._REQUIRED_PLAYER_COMMANDS]
        old_global = [SimpleNamespace(name="comando_viejo")]

        async def sync(*, guild=None):
            events.append("sync_guild" if guild else "sync_global")
            return []

        async def fetch_commands(*, guild=None):
            events.append("fetch_guild" if guild else "fetch_global")
            if guild:
                return local
            return old_global if events.count("fetch_global") == 1 else []

        def clear_commands(*, guild=None):
            events.append("clear_global")

        tree = SimpleNamespace(
            get_commands=lambda: local,
            copy_global_to=lambda **kwargs: events.append("copy_to_guild"),
            sync=sync,
            fetch_commands=fetch_commands,
            clear_commands=clear_commands,
        )
        client = SimpleNamespace(
            tree=tree, user="TestBot", guilds=[SimpleNamespace(id=int(bot_module.GUILD_ID))],
            get_guild=lambda guild_id: object(),
        )
        await bot_module.sync_slash_commands(client)
        self.assertLess(events.index("sync_guild"), events.index("clear_global"))
        self.assertLess(events.index("fetch_guild"), events.index("clear_global"))
        self.assertLess(events.index("clear_global"), events.index("sync_global"))

    async def test_slash_migration_rejects_wrong_guild_without_deleting(self):
        import bot as bot_module
        tree = SimpleNamespace(clear_commands=unittest.mock.Mock(), sync=AsyncMock())
        client = SimpleNamespace(
            tree=tree, user="TestBot", guilds=[], get_guild=lambda guild_id: None,
        )
        with self.assertRaisesRegex(RuntimeError, "no es un servidor conectado"):
            await bot_module.sync_slash_commands(client)
        tree.clear_commands.assert_not_called()
        tree.sync.assert_not_awaited()

    async def test_slash_migration_keeps_globals_if_guild_is_incomplete(self):
        import bot as bot_module
        local = [SimpleNamespace(name=name)
                 for name in bot_module._REQUIRED_PLAYER_COMMANDS]
        tree = SimpleNamespace(
            get_commands=lambda: local,
            copy_global_to=unittest.mock.Mock(),
            sync=AsyncMock(),
            fetch_commands=AsyncMock(return_value=local[:-1]),
            clear_commands=unittest.mock.Mock(),
        )
        client = SimpleNamespace(
            tree=tree, user="TestBot",
            guilds=[SimpleNamespace(id=int(bot_module.GUILD_ID))],
            get_guild=lambda guild_id: object(),
        )
        with self.assertRaisesRegex(RuntimeError, "no registró todos"):
            await bot_module.sync_slash_commands(client)
        tree.clear_commands.assert_not_called()
        self.assertEqual(tree.sync.await_count, 1)

    async def test_startup_diagnostics_report_stage_without_secrets(self):
        import bot as bot_module

        async def healthy():
            return 42

        async def broken():
            raise RuntimeError(f"falló con {bot_module.TOKEN}")

        self.assertEqual(await bot_module._startup_step("prueba correcta", healthy()), 42)
        with self.assertLogs("purplejack", level="ERROR") as captured:
            with self.assertRaises(RuntimeError) as raised:
                await bot_module._startup_step("prueba fallida", broken())
        self.assertIn("[STARTUP:ERROR] prueba fallida", captured.output[0])
        self.assertIn("[REDACTADO]", captured.output[0])
        self.assertNotIn(bot_module.TOKEN, captured.output[0])
        self.assertNotIn(bot_module.TOKEN, str(raised.exception))

    def test_shutdown_signal_does_not_block_startup_when_unavailable(self):
        import bot as bot_module

        supported = SimpleNamespace(add_signal_handler=Mock())
        self.assertTrue(bot_module._register_shutdown_signal(supported))
        supported.add_signal_handler.assert_called_once()

        unsupported = SimpleNamespace(
            add_signal_handler=Mock(side_effect=NotImplementedError),
        )
        with self.assertLogs("purplejack", level="WARNING") as captured:
            self.assertFalse(bot_module._register_shutdown_signal(unsupported))
        self.assertIn("[STARTUP:SIGNAL]", captured.output[0])

    def test_squarecloud_runs_bot_entrypoint_directly(self):
        root = Path(__file__).resolve().parents[1]
        config = (root / "squarecloud.app").read_text(encoding="utf-8")
        self.assertIn("MAIN=bot.py", config.splitlines())
        source = (root / "bot.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        self.assertTrue(any(
            isinstance(node, ast.If)
            and any(isinstance(child, ast.Call)
                    and isinstance(child.func, ast.Name)
                    and child.func.id == "run_bot"
                    for child in ast.walk(node))
            for node in tree.body
        ))

    def test_help_lists_only_available_slash_entry_points(self):
        from modules.economy import (
            NAVE_COMMAND_PAGES, NAVE_INFO_DESCRIPTION,
            NaveHelpView, _build_nave_commands_embed,
        )
        self.assertEqual(len(NAVE_COMMAND_PAGES), 3)
        self.assertIn("/consultar", NAVE_INFO_DESCRIPTION)
        for page in range(len(NAVE_COMMAND_PAGES)):
            embed = _build_nave_commands_embed(page)
            self.assertLessEqual(len(embed.fields[0].value), 1024)
            self.assertNotIn("!", embed.fields[0].value)
            self.assertNotIn("Prefijo", embed.footer.text)
            self.assertLessEqual(len(embed), 6000)
        self.assertEqual(len(NaveHelpView(1).children), 4)

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
            channel=SimpleNamespace(),
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
             patch("modules.roulette.random.choice", return_value="1"), \
             patch("modules.roulette.send_game_reminder_prompt",
                   new=AsyncMock(side_effect=lambda *args: events.append("prompt"))):
            await Roulette.ruleta.callback(Roulette(None), context, 100, "red")
        self.assertEqual(events, ["message", "settle", "cooldown", "message", "prompt"])


if __name__ == "__main__":
    unittest.main()
