"""Recordatorios opt-in de cooldown de juegos, persistidos para reinicios."""

import asyncio
import logging
import time

import discord

from core import database

logger = logging.getLogger(__name__)
GAME_NAMES = {
    "ruleta": "Ruleta",
    "dados": "Dados",
    "bj": "Blackjack",
    "memo": "Memoria",
}


async def init_game_reminders() -> None:
    async with database.pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS game_cooldown_reminders (
                user_id BIGINT NOT NULL,
                game TEXT NOT NULL,
                expires_at DOUBLE PRECISION NOT NULL,
                sent_at DOUBLE PRECISION,
                claim_until DOUBLE PRECISION NOT NULL DEFAULT 0,
                PRIMARY KEY (user_id, game)
            )
        """)


async def reminder_enabled(user_id: int, game: str, expires_at: float) -> bool:
    async with database.pool.acquire() as conn:
        value = await conn.fetchval(
            "SELECT 1 FROM game_cooldown_reminders "
            "WHERE user_id=$1 AND game=$2 AND expires_at=$3 AND sent_at IS NULL",
            user_id, game, expires_at,
        )
    return bool(value)


async def set_reminder(user_id: int, game: str, expires_at: float) -> None:
    if game not in GAME_NAMES or expires_at <= time.time():
        raise ValueError("El cooldown ya no está activo.")
    async with database.pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO game_cooldown_reminders
                (user_id, game, expires_at, sent_at, claim_until)
            VALUES ($1, $2, $3, NULL, 0)
            ON CONFLICT (user_id, game) DO UPDATE
            SET expires_at=EXCLUDED.expires_at, sent_at=NULL, claim_until=0
        """, user_id, game, expires_at)


async def cancel_reminder(user_id: int, game: str) -> None:
    async with database.pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM game_cooldown_reminders WHERE user_id=$1 AND game=$2",
            user_id, game,
        )


async def _claim_due(now: float) -> list[dict]:
    async with database.pool.acquire() as conn:
        rows = await conn.fetch("""
            UPDATE game_cooldown_reminders AS reminder
            SET claim_until=$1 + 300
            WHERE (user_id, game) IN (
                SELECT user_id, game FROM game_cooldown_reminders
                WHERE sent_at IS NULL AND expires_at <= $1 AND claim_until <= $1
                ORDER BY expires_at LIMIT 20 FOR UPDATE SKIP LOCKED
            )
            RETURNING reminder.user_id, reminder.game, reminder.expires_at
        """, now)
    return [dict(row) for row in rows]


async def game_reminder_worker(bot: discord.Client) -> None:
    await bot.wait_until_ready()
    while not bot.is_closed():
        try:
            for reminder in await _claim_due(time.time()):
                user_id, game, expires_at = (
                    reminder["user_id"], reminder["game"], reminder["expires_at"]
                )
                current_expiry = (
                    await database.get_command_cooldown("user", user_id, "memo")
                    if game == "memo"
                    else await database.get_game_cooldown(user_id, game)
                )
                if current_expiry != expires_at:
                    async with database.pool.acquire() as conn:
                        if current_expiry > time.time():
                            await conn.execute(
                                "UPDATE game_cooldown_reminders "
                                "SET expires_at=$4, claim_until=0 "
                                "WHERE user_id=$1 AND game=$2 AND expires_at=$3",
                                user_id, game, expires_at, current_expiry,
                            )
                        else:
                            await conn.execute(
                                "DELETE FROM game_cooldown_reminders "
                                "WHERE user_id=$1 AND game=$2 AND expires_at=$3",
                                user_id, game, expires_at,
                            )
                    continue
                try:
                    user = await bot.fetch_user(user_id)
                    await user.send(
                        f"🔔 Ya puedes volver a jugar **{GAME_NAMES[game]}** "
                        "en PurpleSlash."
                    )
                    result = time.time()
                except (discord.Forbidden, discord.NotFound):
                    result = -1  # DM cerrados: no insistir ni generar spam.
                except Exception:
                    logger.exception("Fallo al avisar cooldown de %s a %s", game, user_id)
                    continue  # El lease permitirá reintentar después de 5 minutos.
                async with database.pool.acquire() as conn:
                    await conn.execute("""
                        UPDATE game_cooldown_reminders SET sent_at=$4
                        WHERE user_id=$1 AND game=$2 AND expires_at=$3
                    """, user_id, game, expires_at, result)
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Fallo en worker de recordatorios de juegos")
        await asyncio.sleep(30)
