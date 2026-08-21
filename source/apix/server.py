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
from apix.core.event import EVENT_PIPE, APIX_EVENT_LOOP
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


async def lifespan(app: FastAPI):
    await Logger.start()
    try:
        auto_load_router(app)

        await EVENT_PIPE.start()
        await APIX_EVENT_LOOP.start()
        await auto_init.start()

        yield
    finally:
        # The gateway must learn that this node is unavailable before the
        # remaining services and event dispatcher are torn down.
        try:
            await EVENT_PIPE.stop()
        finally:
            try:
                await auto_init.stop()
            finally:
                try:
                    await APIX_EVENT_LOOP.stop()
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
