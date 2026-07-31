import pkgutil
import importlib
from urllib.parse import urlparse
from fastapi import FastAPI, APIRouter
import uvicorn
from fastapi.responses import JSONResponse

from apix.config.base_config import BASE_URL, NODE_ID
import apix.router as routers_pkg
from apix.common.lifespan.auto_init import auto_init
from apix.core.event import apix_event_loop
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


def print_logo():
    ap_color = "\033[38;2;0;200;170m"      # APIX teal
    ix_color = "\033[38;2;255;120;40m"     # APIX orange
    gray = "\033[38;2;140;140;140m"        # Light gray
    reset = "\033[0m"

    print(f"""{gray}
======================================
{reset}{ap_color}     ___      .______{reset}    {ix_color}__  ___   ___{reset}
{ap_color}    /   \\     |   _  \\{reset}  {ix_color}|  | \\  \\ /  /{reset}
{ap_color}   /  ^  \\    |  |_)  |{reset} {ix_color}|  |  \\  V  /{reset}
{ap_color}  /  /_\\  \\   |   ___/{reset}  {ix_color}|  |   >   <{reset}
{ap_color} /  _____  \\  |  |{reset}      {ix_color}|  |  /  ^  \\{reset}
{ap_color}/__/     \\__\\ | _|{reset}      {ix_color}|__| /__/ \\__\\{reset}

{gray}            Agent Platform
======================================
{reset}""")


if __name__ == "__main__":
    app = create_app()

    @app.get("/health")
    def health_check():
        return JSONResponse({"status": "ok", "service": str(NODE_ID)})

    parsed = urlparse(BASE_URL)

    host = parsed.hostname or "0.0.0.0"
    port = parsed.port or 2712

    print_logo()
    
    uvicorn.run(app, host=host, port=port, reload=False)
