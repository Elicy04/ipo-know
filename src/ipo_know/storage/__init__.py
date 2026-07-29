"""Storage 包, 提供数据库连接、会话工厂和 ORM 模型基类."""

import ipo_know.storage.models as _models
import ipo_know.storage.session as _session


Base = _models.base_model.Base
SessionLocal = _session.SessionLocal
engine = _session.engine

__all__ = ["Base", "SessionLocal", "engine"]
