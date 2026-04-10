import atexit
import importlib
import os
import pkgutil
from fastapi import FastAPI, APIRouter

# from app.core.websocket_list_obj import ws_list


def auto_load(app: FastAPI):
    """自动加载 routers 目录下的所有 APIRouter"""
    package_name = "routers"
    package_path = os.path.join(os.path.dirname(__file__),"app", package_name)

    if not os.path.exists(package_path):
        print(f"[auto_load] 警告: 目录 {package_path} 不存在，跳过自动加载路由")
        return

    for _, module_name, is_pkg in pkgutil.iter_modules([package_path]):
        if is_pkg:   # 如果 routers 下还有子目录，可以递归加载（后续可扩展）
            continue

        try:
            module = importlib.import_module(f"{package_name}.{module_name}")
        except ModuleNotFoundError:
            try:
                module = importlib.import_module(f"app.{package_name}.{module_name}")
            except ModuleNotFoundError:
                print(f"[auto_load] 警告: 找不到模块 {package_name}.{module_name} 和 app.{package_name}.{module_name}, 已跳过")
                continue
            except Exception as e:
                print(f"[auto_load] 警告: 导入模块 app.{package_name}.{module_name} 出错: {e}")
                continue
        except Exception as e:
            print(f"[auto_load] 警告: 导入模块 {package_name}.{module_name} 出错: {e}")
            continue

        # 遍历模块内的所有属性，找到 APIRouter
        for attr in dir(module):
            obj = getattr(module, attr)
            if isinstance(obj, APIRouter):
                app.include_router(obj)
                print(f"✔ 已注册路由: {package_name}.{module_name}.{attr}")

async def lifespan(app: FastAPI):
    # 启动逻辑
    # 这里可以放初始化操作，例如 auto_load(app)
    auto_load(app)
    yield  # 控制权交给应用

    # 关闭逻辑
    # 异步清理 websocket 列表
    # await ws_list.remove_all()

def create_app() -> FastAPI:
    app = FastAPI(title="APIX SERVICE", version="1.0.0", lifespan=lifespan)
    # auto_load(app)

    @app.get("/health")
    async def health_check():
        return {"status": "ok", "msg": "FastAPI service is running"}

    return app


if __name__ == "__main__":
    import uvicorn
    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=5090, reload=False)
