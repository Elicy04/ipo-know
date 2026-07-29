from importlib import import_module
from pathlib import Path

for p in Path(__path__[0]).glob("*.py"):
    if p.stem != "__init__":
        import_module(f".{p.stem}", __name__)
