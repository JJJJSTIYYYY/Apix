import os
import pkgutil
import importlib
from fastapi import FastAPI, APIRouter
import uvicorn
from fastapi.responses import JSONResponse

import apix_agent.routers as routers_pkg
from apix_agent.apix_agent_core.context_manager.longterm_memory import longterm_memory_manager
from apix_agent.apix_event_pipe.websocket_manager import websocket_list
from apix_agent.apix_agent_core.agent import ai_agent
from apix_agent.apix_agent_core.agent_factory.agent_creator import agent_creator
from apix_agent.apix_agent_core.agent_team_task.task_manager import task_manager
from apix_agent.apix_agent_core.sandbox_manager.agent_sandbox_manager import agent_sandbox


def auto_load(app: FastAPI):
    pkg_path = routers_pkg.__path__

    for _, module_name, _ in pkgutil.iter_modules(pkg_path):
        full_name = f"apix_agent.routers.{module_name}"
        print(f"[auto_load] ✅ 加载模块: {full_name}")

        module = importlib.import_module(full_name)

        for attr in dir(module):
            obj = getattr(module, attr)
            if isinstance(obj, APIRouter):
                app.include_router(obj)
                print(f"✔ 已注册路由: {full_name}.{attr}")

async def lifespan(app: FastAPI):
    auto_load(app)
    print("Work direction", os.getcwd())
    await websocket_list.start()
    await longterm_memory_manager.start()
    await task_manager.start()
    await agent_creator.start()
    await ai_agent.start()
    
    yield
    await websocket_list.stop()
    await agent_sandbox.cleanup_all()
    await longterm_memory_manager.stop()
    await task_manager.stop()
    await agent_creator.stop()
    await ai_agent.stop()


def create_app() -> FastAPI:
    app = FastAPI(title="APIX AGENT", version="1.0.0", lifespan=lifespan)
    return app


if __name__ == "__main__":
    app = create_app()

    @app.get("/health")
    def health_check():
        return JSONResponse({"status": "ok", "service": "agent-service"})

    uvicorn.run(app, host="0.0.0.0", port=5091, reload=False)
