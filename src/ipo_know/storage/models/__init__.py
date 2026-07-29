"""Models 子包, 自动发现并加载所有数据表模型模块."""

import importlib
import pathlib


for p in pathlib.Path(__path__[0]).glob("*.py"):
    if p.stem != "__init__":
        importlib.import_module(f".{p.stem}", __name__)
