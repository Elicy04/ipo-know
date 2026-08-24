"""目标平台公共常量与配置前置校验.

抽取自操作面板, 供操作面板及后续检索/问答面板
复用: 统一的目标平台选项, 与启动前"必填配置项
是否齐备"的校验逻辑.
"""

from ipo_know.ui.config_store import GUIConfigStore


# 上传对齐的目标平台选项.
PLATFORM_OPTIONS: dict[str, str] = {
    'aliyun': '阿里云百炼',
    'volc': '火山引擎 VikingDB',
}

# 阿里云平台启动前必须已配置的字段: (字段名, 展示名).
_ALIYUN_REQUIRED_FIELDS: tuple[tuple[str, str], ...] = (
    ('ak', 'AK'),
    ('sk', 'SK'),
    ('workspace_id', 'Workspace ID'),
    ('index_id', 'Index ID'),
)

# 火山引擎平台必须已配置的凭证字段: (字段名, 展示名).
# 另需 resource_id 与 collection_name 至少其一, 单独校验.
_VOLC_REQUIRED_FIELDS: tuple[tuple[str, str], ...] = (
    ('ak', 'AK'),
    ('sk', 'SK'),
)


def missing_config_items(
    store: GUIConfigStore, platform: str
) -> list[str]:
    """按目标平台检查已保存配置中的必填项.

    Args:
        store: GUI 配置持久化存储实例.
        platform: 目标平台标识 (aliyun/volc).

    Returns:
        缺失的必填配置项展示名列表, 空列表表示均已配置.
    """
    data = store.load()
    if platform == 'volc':
        raw = data.get('viking_knowledge', {})
        volc_data = raw if isinstance(raw, dict) else {}
        missing: list[str] = []
        for key, label in _VOLC_REQUIRED_FIELDS:
            value = volc_data.get(key)
            if not str(value or '').strip():
                missing.append(label)
        resource_id = str(
            volc_data.get('resource_id') or ''
        ).strip()
        collection_name = str(
            volc_data.get('collection_name') or ''
        ).strip()
        if not resource_id and not collection_name:
            missing.append('Resource ID 或 Collection Name')
        return missing
    raw = data.get('aliyun_knowledge', {})
    ak_data = raw if isinstance(raw, dict) else {}
    missing = []
    for key, label in _ALIYUN_REQUIRED_FIELDS:
        value = ak_data.get(key)
        if not str(value or '').strip():
            missing.append(label)
    return missing
