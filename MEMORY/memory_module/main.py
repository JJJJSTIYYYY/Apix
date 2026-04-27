import os
import pkgutil
import importlib
from fastapi import FastAPI, APIRouter
import uvicorn
import routers as routers_pkg
from fastapi.responses import JSONResponse

from core.domain.init_server import _init_server_, _close_server_


def auto_load(app: FastAPI):
    pkg_path = routers_pkg.__path__

    for _, module_name, _ in pkgutil.iter_modules(pkg_path):
        full_name = f"routers.{module_name}"
        print(f"[auto_load] Load module: {full_name}")

        module = importlib.import_module(full_name)

        for attr in dir(module):
            obj = getattr(module, attr)
            if isinstance(obj, APIRouter):
                app.include_router(obj)
                print(f"✔ Router register: {full_name}.{attr}")

async def lifespan(app: FastAPI):
    auto_load(app)
    await _init_server_()
    yield
    await _close_server_()

def create_app() -> FastAPI:
    app = FastAPI(title="APIX AGENT MEMORY CALL MODULE", version="1.0.0", lifespan=lifespan)
    return app


if __name__ == "__main__":
    app = create_app()

    @app.get("/health")
    def health_check():
        return JSONResponse({"status": "ok", "service": "memory-service"})

    uvicorn.run(app, host="0.0.0.0", port=5093, reload=False)
