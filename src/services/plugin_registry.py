import os
import importlib
import inspect
from typing import List, Type
from src.services.base_evaluator import BaseEvaluator

def load_custom_plugins() -> List[BaseEvaluator]:
    """
    Scans src/plugins/ folder, dynamically imports all modules,
    and returns instantiated objects of classes inheriting from BaseEvaluator.
    """
    plugins = []
    plugins_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "plugins")
    
    if not os.path.exists(plugins_dir):
        os.makedirs(plugins_dir, exist_ok=True)
        return plugins

    for filename in os.listdir(plugins_dir):
        if filename.endswith(".py") and filename != "__init__.py":
            module_name = f"src.plugins.{filename[:-3]}"
            try:
                module = importlib.import_module(module_name)
                # Reload module to handle code hotupdates in development
                importlib.reload(module)
                
                for _, obj in inspect.getmembers(module, inspect.isclass):
                    if issubclass(obj, BaseEvaluator) and obj is not BaseEvaluator:
                        try:
                            # Instantiate plugin class
                            plugins.append(obj())
                        except Exception as instantiate_err:
                            print(f"Error instantiating plugin class {obj.__name__}: {instantiate_err}")
            except Exception as import_err:
                print(f"Error loading custom plugin module {module_name}: {import_err}")
                
    return plugins
