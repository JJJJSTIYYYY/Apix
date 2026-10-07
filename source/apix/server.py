import importlib
import pkgutil
from contextlib import asynccontextmanager
from urllib.parse import urlparse

import uvicorn
from apixis.core.event import get_event_loop, get_event_pipe, start_core
from fastapi import APIRouter, FastAPI
from fastapi.responses import JSONResponse

import apix.router as routers_pkg
from apix.common.lifespan.auto_init import auto_init
from apix.common.utils.logger import Logger, logger
from apix.common.utils.version import print_logo
from apix.config.base_config import BASE_URL


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
        # Stop event publication before application services and the dispatcher.
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
        return JSONResponse({"status": "ok", "service": "apix"})

    return app


if __name__ == "__main__":
    app = create_app()

    parsed = urlparse(BASE_URL)

    host = parsed.hostname or "0.0.0.0"
    port = parsed.port or 2712

    print_logo()
    
    uvicorn.run(app, host=host, port=port, reload=False)
