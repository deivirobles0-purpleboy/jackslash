import os

TOKEN = os.getenv("PURPLESLASH_DISCORD_TOKEN")
DATABASE_URL = os.getenv("PURPLESLASH_DATABASE_URL")
GUILD_ID = os.getenv("PURPLESLASH_GUILD_ID")
TEST_MODE = True  # El clon nunca ejecuta workers de canales de producción.

if not TOKEN or not DATABASE_URL or not GUILD_ID:
    raise RuntimeError(
        "PurpleSlash requiere PURPLESLASH_DISCORD_TOKEN, "
        "PURPLESLASH_DATABASE_URL y PURPLESLASH_GUILD_ID en Square Cloud."
    )
