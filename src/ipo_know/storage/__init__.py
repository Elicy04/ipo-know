from .models.base_model import Base
from .session import engine, SessionLocal
# 关键：导入models包，触发内部所有模型加载
from .models import *

__all__ = ["Base", "engine", "SessionLocal"]
