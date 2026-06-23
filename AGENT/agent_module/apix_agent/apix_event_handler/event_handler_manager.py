import importlib
import pkgutil

from apix_agent.commons.logger import logger


class EventHandlerManager:

    MODULE_PATH_ROOT = "apix_agent.apix_event_handler"
    SYSTEM_MODULE_PATH = MODULE_PATH_ROOT + ".system_handler"
    CUSTOM_MODULE_PATH = MODULE_PATH_ROOT + ".custom_handler"

    def __init__(self):
        self.custom_handler_pkg_path = []


    def load_system_event_handler(self):
        import apix_agent.apix_event_handler.system_handler as system_handler_pkg
        pkg_path = system_handler_pkg.__path__

        for _, module_name, _ in pkgutil.iter_modules(pkg_path):
            full_name = f"{EventHandlerManager.SYSTEM_MODULE_PATH}.{module_name}"
            logger.info(f"Load event system handler: {full_name}")

            importlib.import_module(full_name)


    def load_custom_event_handler(self):
        import apix_agent.apix_event_handler.custom_handler as custom_handler_pkg
        pkg_path = custom_handler_pkg.__path__

        for _, module_name, _ in pkgutil.iter_modules(pkg_path):
            full_name = f"{EventHandlerManager.SYSTEM_MODULE_PATH}.{module_name}"
            logger.info(f"Load event custom handler: {full_name}")

            importlib.import_module(full_name)


    def add_handle_package(path: str | list[str]):
        raise NotImplementedError()
    

event_handler_mgr = EventHandlerManager()