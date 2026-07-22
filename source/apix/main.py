import pkgutil
import importlib
from fastapi import FastAPI, APIRouter
import uvicorn
from fastapi.responses import JSONResponse

import apix.router as routers_pkg
from apix.common.lifespan.auto_init import auto_init
from apix.core.event.event_loop import apix_event_loop
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

    auto_load_router(app)

    await apix_event_loop.start()
    await auto_init.start()
    
    yield

    await auto_init.stop()
    await apix_event_loop.stop()

    await Logger.stop()


def create_app() -> FastAPI:
    app = FastAPI(title="APIX AGENT", version="1.0.0", lifespan=lifespan)
    return app


if __name__ == "__main__":
    app = create_app()

    @app.get("/health")
    def health_check():
        return JSONResponse({"status": "ok", "service": "agent-service"})

    uvicorn.run(app, host="0.0.0.0", port=5091, reload=False)
