from core.domain.mysql_server import mysql_server
from core.domain.file_server import file_server
from core.commons.logger import logger

async def _init_server_():
    logger.info("[APP][_init_server_] start.")
    try:
        await mysql_server.init()
    except Exception as e:
        logger.exception(
            f"[APP][_init_server_] fail: {e}"
        )
        raise
    logger.success("[APP][_init_server_] finished.")

async def _close_server_():
    logger.info("[APP][_close_server_] start.")
    try:
        await mysql_server._close()
    except Exception as e:
        logger.exception(
            f"[APP][_close_server_] fail: {e}"
        )
        raise
    logger.success("[APP][_close_server_] finished.")