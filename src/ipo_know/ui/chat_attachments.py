"""会话附件状态管理.

管理知识问答中的临时附件生命周期:
校验 → 上传 → 解析 → 就绪/失败.
"""

from dataclasses import dataclass
from pathlib import PurePosixPath

from loguru import logger


#: 单会话附件数量上限.
_MAX_FILE_COUNT = 10

#: 允许的附件扩展名白名单 (小写含点).
_ALLOWED_EXTENSIONS: frozenset[str] = frozenset({
    '.txt', '.pdf', '.doc', '.docx', '.md', '.pptx',
    '.ppt', '.xls', '.xlsx', '.png', '.jpg', '.jpeg',
    '.bmp', '.gif',
})

#: 单个附件大小上限 (100MB).
_MAX_FILE_SIZE = 100 * 1024 * 1024


@dataclass
class SessionFile:
    """会话临时附件状态记录.

    Attributes:
        name: 文件名 (含扩展名), 会话内唯一.
        size: 文件字节数.
        file_id: 平台侧文件 ID, 上传成功前为空字符串.
        status: 生命周期状态, 取值 ``uploading`` 上传中 /
            ``parsing`` 解析中 / ``ready`` 就绪 /
            ``failed`` 失败.
    """

    name: str
    size: int
    file_id: str = ''
    status: str = 'uploading'


class ChatAttachments:
    """知识问答会话附件状态容器.

    按文件名维护附件列表, 提供上传前校验、增删、就绪
    文件 ID 收集与整体清空能力; 状态迁移 (uploading →
    parsing → ready/failed) 由调用方直接修改
    ``SessionFile.status`` 完成.
    """

    def __init__(self) -> None:
        """初始化附件容器, 列表为空."""
        self._files: list[SessionFile] = []

    def validate(
        self, file_name: str, file_size: int
    ) -> str | None:
        """校验待添加附件是否满足上传条件.

        依次检查数量上限、扩展名白名单与大小限制, 并
        拒绝会话内同名附件.

        Args:
            file_name: 文件名 (含扩展名).
            file_size: 文件字节数.

        Returns:
            校验通过时返回 None; 否则返回可读错误信息.
        """
        if len(self._files) >= _MAX_FILE_COUNT:
            return f'附件数量已达上限 ({_MAX_FILE_COUNT} 个)'
        suffix = PurePosixPath(file_name).suffix.lower()
        if suffix not in _ALLOWED_EXTENSIONS:
            return '不支持的文件类型'
        if file_size > _MAX_FILE_SIZE:
            return (
                '文件大小超过限制 '
                f'({_MAX_FILE_SIZE // (1024 * 1024)}MB)'
            )
        if any(item.name == file_name for item in self._files):
            return '同名附件已在列表中'
        return None

    def add(
        self, file_name: str, file_size: int
    ) -> SessionFile:
        """追加附件记录, 初始状态为 ``uploading``.

        调用前应经 ``validate`` 校验.

        Args:
            file_name: 文件名 (含扩展名).
            file_size: 文件字节数.

        Returns:
            新建的附件记录.
        """
        item = SessionFile(name=file_name, size=file_size)
        self._files.append(item)
        logger.debug(
            '会话附件登记 | name={} | size={} | 现有={} 个',
            file_name, file_size, len(self._files),
        )
        return item

    def remove(self, file_name: str) -> SessionFile | None:
        """按名称移除附件记录.

        Args:
            file_name: 待移除的附件文件名.

        Returns:
            被移除的附件记录; 不存在时返回 None.
        """
        for index, item in enumerate(self._files):
            if item.name == file_name:
                removed = self._files.pop(index)
                logger.debug(
                    '会话附件移除 | name={} | 剩余={} 个',
                    file_name, len(self._files),
                )
                return removed
        return None

    def file_ids(self) -> list[str]:
        """收集就绪附件的平台侧文件 ID.

        Returns:
            ``status == 'ready'`` 的附件 ``file_id`` 列表,
            保持登记顺序.
        """
        return [
            item.file_id
            for item in self._files
            if item.status == 'ready' and item.file_id
        ]

    def clear(self) -> list[SessionFile]:
        """清空附件列表并返回被移除的记录.

        Returns:
            清空前的全部附件记录副本, 供调用方做后台
            清理 (如删除平台临时文件).
        """
        removed = self._files
        self._files = []
        if removed:
            logger.debug(
                '会话附件清空 | count={}', len(removed),
            )
        return removed

    @property
    def count(self) -> int:
        """当前附件数量."""
        return len(self._files)

    @property
    def all_files(self) -> list[SessionFile]:
        """全部附件记录的只读副本."""
        return list(self._files)
