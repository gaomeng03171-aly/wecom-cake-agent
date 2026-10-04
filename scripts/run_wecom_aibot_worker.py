import asyncio
import logging
import sys

from app.config import get_settings
from app.db import init_db
from app.services.wecom_aibot import (
    WeComAiBotLongConnectionWorker,
    build_wecom_aibot_ws_client,
)


async def main() -> None:
    settings = get_settings()
    if settings.auto_create_tables:
        init_db()

    ws_client = build_wecom_aibot_ws_client(settings)
    worker = WeComAiBotLongConnectionWorker(ws_client=ws_client)
    await worker.start()
    logging.getLogger(__name__).info("WeCom AiBot long-connection worker started")
    try:
        await asyncio.Event().wait()
    finally:
        await worker.stop()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
