import pkgutil
import importlib
from contextlib import asynccontextmanager

from fastapi import FastAPI, APIRouter
from fastapi.responses import JSONResponse
import uvicorn

import routers as routers_pkg
from core.task_manager import task_manager


def auto_load(app: FastAPI):
    pkg_path = routers_pkg.__path__

    # 扫描 routers 包下的所有 .py 模块
    for _, module_name, _ in pkgutil.iter_modules(pkg_path):
        full_name = f"routers.{module_name}"
        print(f"[auto_load] ✅ 加载模块: {full_name}")

        module = importlib.import_module(full_name)

        # 从模块中找出 APIRouter 对象
        for attr in dir(module):
            obj = getattr(module, attr)
            if isinstance(obj, APIRouter):
                app.include_router(obj)
                print(f"✔ 已注册路由: {full_name}.{attr}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ---------------- startup ----------------
    auto_load(app)
    await task_manager.start()
    print("[lifespan] 🚀 TaskManager started")

    yield

    # ---------------- shutdown ----------------
    await task_manager.shutdown()
    print("[lifespan] 🛑 TaskManager shutdown")


def create_app() -> FastAPI:
    app = FastAPI(
        title="APIX AGENT TOOLS CALL MODULE",
        version="1.0.0",
        lifespan=lifespan,
    )

    @app.get("/health")
    def health_check():
        return JSONResponse(
            {"status": "ok", "service": "tools-service"}
        )

    return app


if __name__ == "__main__":
    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=5092, reload=False)
