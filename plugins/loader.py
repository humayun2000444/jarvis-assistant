"""
JARVIS Plugin Loader
Scans the plugins/ directory for Python files with a register() function.

Each plugin should define:
    def register(app: dict) -> None:
        # app contains: 'commands', 'quick_commands', 'scheduled_jobs'
        pass

Example plugin (plugins/my_plugin.py):
    def register(app):
        app['commands']['mycommand'] = {
            'description': 'My custom command',
            'handler': lambda args: print("Hello from plugin!")
        }
"""
import importlib
import importlib.util
import os
from pathlib import Path
from typing import Dict, Any, Callable, List

import logging

logger = logging.getLogger("jarvis.plugins")


class PluginRegistry:
    """Registry for plugin-provided extensions"""

    def __init__(self):
        self.commands: Dict[str, Dict[str, Any]] = {}
        self.quick_commands: Dict[str, Dict[str, Any]] = {}
        self.scheduled_jobs: List[Dict[str, Any]] = []
        self._loaded_plugins: List[str] = []

    def to_app_dict(self) -> Dict[str, Any]:
        """Return dict passed to plugin register() functions"""
        return {
            'commands': self.commands,
            'quick_commands': self.quick_commands,
            'scheduled_jobs': self.scheduled_jobs,
        }

    @property
    def loaded_plugins(self) -> List[str]:
        return list(self._loaded_plugins)


_registry = PluginRegistry()


def load_plugins(plugin_dir: Path = None) -> PluginRegistry:
    """
    Load all plugins from the plugins directory.

    Args:
        plugin_dir: Path to plugins directory. Defaults to plugins/ in project root.

    Returns:
        PluginRegistry with all loaded extensions.
    """
    if plugin_dir is None:
        plugin_dir = Path(__file__).parent

    if not plugin_dir.exists():
        return _registry

    app = _registry.to_app_dict()

    for plugin_file in sorted(plugin_dir.glob("*.py")):
        # Skip __init__.py and loader.py
        if plugin_file.name.startswith("_") or plugin_file.name == "loader.py":
            continue

        plugin_name = plugin_file.stem
        try:
            spec = importlib.util.spec_from_file_location(
                f"plugins.{plugin_name}", plugin_file
            )
            if spec is None or spec.loader is None:
                continue

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            if hasattr(module, 'register') and callable(module.register):
                module.register(app)
                _registry._loaded_plugins.append(plugin_name)
                logger.info(f"Loaded plugin: {plugin_name}")
            else:
                logger.warning(f"Plugin {plugin_name} has no register() function, skipping")

        except Exception as e:
            logger.error(f"Failed to load plugin {plugin_name}: {e}")

    return _registry


def get_registry() -> PluginRegistry:
    """Get the plugin registry"""
    return _registry
