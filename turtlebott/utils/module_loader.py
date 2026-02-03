"""Module loading and management utilities."""

import importlib
import inspect
from ..utils.logger import setup_logger
from ..config import settings, modules

logger = setup_logger("module_loader")

MODULES = modules

def is_enabled(module_name: str) -> bool:
    """Check if a module is enabled in the config."""
    experiments = settings.config.get("experiments_config", {})
    module_config = experiments.get(module_name, {})
    return module_config.get("enabled", False)


def get_module_doc(module_name: str) -> str:
    """Return the top-level docstring for a module, or a fallback."""
    try:
        module = importlib.import_module(f"turtlebott.modules.{module_name}")
        return inspect.getdoc(module) or "No description provided."
    except Exception as e:
        logger.warning(f"Failed to read docstring for module '{module_name}': {e}")
        return "Failed to load description."


async def load_modules(bot) -> None:
    """Load all enabled modules from the modules folder."""
    logger.info("Loading modules...")
    
    # Loop through modules and load enabled ones
    for module in MODULES:
        # Check if the module has a config entry
        if module not in settings.config.get("experiments_config", {}):
            logger.warning(f"Module '{module}' not found in config.yml! Skipping... (Are you sure it exists?)")
            continue
        
        if is_enabled(module):
            logger.info(f"Loading module: {module}")
            try:
                await bot.load_extension(f"turtlebott.modules.{module}")
            except Exception as e:
                logger.error(f"Failed to load module '{module}': {e}")
    
    # Log warnings if no modules are available or all are disabled
    if not MODULES:
        logger.warning("No modules found! That's not supposed to happen..")
    elif all(not is_enabled(m) for m in MODULES):
        logger.warning("All modules are disabled in config.yml!")
    else:
        logger.info("All enabled modules loaded successfully.")


def get_all_modules() -> list[str]:
    """Return the list of all available modules."""
    return MODULES.copy()


def get_enabled_modules() -> list[str]:
    """Return a list of enabled modules."""
    return [module for module in MODULES if is_enabled(module)]


def get_disabled_modules() -> list[str]:
    """Return a list of disabled modules."""
    return [module for module in MODULES if not is_enabled(module)]
