"""GUI 专属配置的 JSON 持久化存储."""

import json
import os
import pathlib
import tempfile

from loguru import logger

from ipo_know.config.config import AliyunKnowledgeSettings
from ipo_know.config.config import settings


_DEFAULT_ALIYUN_KNOWLEDGE: dict[str, object] = {
    'ak': '',
    'sk': '',
    'endpoint': 'bailian.cn-beijing.aliyuncs.com',
    'region_id': 'cn-beijing',
    'workspace_id': '',
    'index_id': '',
    'category_id': 'default',
    'parser': 'DASHSCOPE_DOCMIND',
    'timeout': 30,
}


class GUIConfigStore:
    """GUI 专属配置的 JSON 持久化存储.

    配置文件存放于 ``%LOCALAPPDATA%/ipo_know/config.json``,
    与 :class:`FileMappingStore` 使用相同的存储根目录策略.

    Attributes:
        _path: 配置文件路径.
    """

    def __init__(
        self,
        path: pathlib.Path | str | None = None,
    ) -> None:
        """初始化配置存储.

        Args:
            path: 配置文件路径, 为 None 时使用默认位置.
        """
        if path is None:
            app_data_root = os.getenv('LOCALAPPDATA')
            if app_data_root:
                base_dir = pathlib.Path(app_data_root) / 'ipo_know'
            else:
                base_dir = pathlib.Path.home() / '.ipo_know'
            path = base_dir / 'config.json'
        self._path = pathlib.Path(path)

    @property
    def path(self) -> pathlib.Path:
        """配置文件路径."""
        return self._path

    def load(self) -> dict[str, object]:
        """从 JSON 文件加载 ``aliyun_knowledge`` 配置.

        若文件不存在, 从 ``settings.aliyun_knowledge`` 读取当前值
        作为初始填充并自动写入 JSON.

        Returns:
            包含 ``aliyun_knowledge`` 键的字典.
        """
        if not self._path.exists():
            data = self._build_initial_data()
            self.save(data)
            return data
        try:
            raw = json.loads(
                self._path.read_text(encoding='utf-8')
            )
            if isinstance(raw, dict):
                return raw
        except (OSError, ValueError) as exc:
            logger.warning('GUI 配置文件读取失败, 使用默认值 | {}', exc)
        return {'aliyun_knowledge': dict(_DEFAULT_ALIYUN_KNOWLEDGE)}

    def save(self, data: dict[str, object]) -> None:
        """将配置写入 JSON 文件 (原子落盘).

        Args:
            data: 包含 ``aliyun_knowledge`` 等字段的字典.
        """
        self._path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(
            dir=self._path.parent,
            suffix='.tmp',
        )
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            pathlib.Path(tmp_path).replace(self._path)
        except BaseException:
            pathlib.Path(tmp_path).unlink(missing_ok=True)
            raise

    def get_aliyun_client_kwargs(self) -> dict[str, object]:
        """返回可直接传入 ``AliyunKnowledgeClient`` 构造函数的参数.

        Returns:
            ``{'config': AliyunKnowledgeSettings(...)}`` 形式的字典.
        """
        data = self.load()
        ak_data = data.get(
            'aliyun_knowledge', dict(_DEFAULT_ALIYUN_KNOWLEDGE)
        )
        cfg = AliyunKnowledgeSettings(**ak_data)  # type: ignore[arg-type]
        return {'config': cfg}

    def _build_initial_data(self) -> dict[str, object]:
        """从全局 settings 构建首次初始化的配置数据."""
        s = settings.aliyun_knowledge
        return {
            'aliyun_knowledge': {
                'ak': s.ak,
                'sk': s.sk,
                'endpoint': s.endpoint,
                'region_id': s.region_id,
                'workspace_id': s.workspace_id,
                'index_id': s.index_id,
                'category_id': s.category_id,
                'parser': s.parser,
                'timeout': s.timeout,
            },
        }
