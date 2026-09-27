from contextlib import asynccontextmanager

import pkgutil
import importlib
from urllib.parse import urlparse
from fastapi import FastAPI, APIRouter
import uvicorn
from fastapi.responses import JSONResponse

from apix.common.utils.version import print_logo
from apix.config.base_config import BASE_URL, NODE_ID
import apix.router as routers_pkg
from apix.common.lifespan.auto_init import auto_init
from apixis.core.event import get_event_pipe, get_event_loop, start_core
from apix.common.utils.logger import Logger, logger


def auto_load_router(app: FastAPI):
    pkg_path = routers_pkg.__path__

    for _, module_name, _ in pkgutil.iter_modules(pkg_path):
        full_name = f"apix.router.{module_name}"
        logger.success(f"Load router module: {full_name}")

        module = importlib.import_module(full_name)

        for attr in dir(module):
            obj = getattr(module, attr)
            if isinstance(obj, APIRouter):
                app.include_router(obj)
                logger.success(f"✔ Router register: {full_name}.{attr}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    event_pipe = event_loop = None
    await Logger.start()
    try:
        auto_load_router(app)

        event_pipe = get_event_pipe()
        event_loop = get_event_loop()
        await start_core()
        await auto_init.start()

        yield
    finally:
        # The gateway must learn that this node is unavailable before the
        # remaining services and event dispatcher are torn down.
        try:
            if event_pipe is not None:
                await event_pipe.stop()
        finally:
            try:
                await auto_init.stop()
            finally:
                try:
                    if event_loop is not None:
                        await event_loop.stop()
                finally:
                    await Logger.stop()


def create_app() -> FastAPI:
    app = FastAPI(title="APIX AGENT", version="1.0.0", lifespan=lifespan)

    @app.get("/health")
    def health_check():
        return JSONResponse({"status": "ok", "service": str(NODE_ID)})

    return app


if __name__ == "__main__":
    app = create_app()

    parsed = urlparse(BASE_URL)

    host = parsed.hostname or "0.0.0.0"
    port = parsed.port or 2712

    print_logo()
    
    uvicorn.run(app, host=host, port=port, reload=False)
