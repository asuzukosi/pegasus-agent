from src.config.config import Config
from src.tools.registry import ToolRegistry
from src.utils.logger import logger
import sys
import importlib.util
import inspect
from src.tools.base import Tool

class ToolDiscoveryManager:
    def __init__(self, config: Config, registry: ToolRegistry) -> None:
        self._config = config
        self._registry = registry

    def discover(self) -> None:
        tools_path = self._config.cwd / "tools" # TODO: add suppor for global tool discovery
        if not tools_path.exists():
            logger.warning(f"Tools path does not exist: {tools_path}")
            return
        for tool_file in tools_path.glob("**/*.py"):
            if tool_file.parent.name.startswith("__"):
                continue
            module_name = 'discovered_tools_' + tool_file.stem
            spec = importlib.util.spec_from_file_location(module_name, tool_file)
            if spec is None:
                logger.warning(f"Failed to discover tool {tool_file}: {spec}")
                continue
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if inspect.isclass(attr) and \
                    issubclass(attr, Tool) and \
                    attr is not Tool  and \
                    attr.__module__ == module_name:
                    self._registry.register(attr(self._config))