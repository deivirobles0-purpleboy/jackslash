from bot import run_bot
import logging

if __name__ == "__main__":
    logging.getLogger("purplejack").info(
        "[STARTUP:ENTRY] main.py inició run_bot."
    )
    run_bot()
