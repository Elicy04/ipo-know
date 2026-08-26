"""知识库检索与问答抽象层.

以工厂函数按目标平台装配查询后端 (Protocol 契约),
风格与操作面板 ``_build_aligner`` 保持一致.
"""

from typing import cast

from loguru import logger

from ipo_know.clients.aliyun_knowledge.client import AliyunKnowledgeClient
from ipo_know.clients.viking_knowledge import VikingKnowledgeClient
from ipo_know.config.config import AliyunKnowledgeSettings
from ipo_know.config.config import VikingKnowledgeSettings
from ipo_know.kb_query.aliyun_backend import AliyunQueryBackend
from ipo_know.kb_query.base import QueryBackend
from ipo_know.kb_query.dto import ChatStreamEvent
from ipo_know.kb_query.dto import SearchHit
from ipo_know.kb_query.volc_backend import VolcQueryBackend
from ipo_know.ui.config_store import GUIConfigStore


__all__ = [
    'ChatStreamEvent',
    'QueryBackend',
    'SearchHit',
    'create_query_backend',
]


def create_query_backend(
    platform: str, store: GUIConfigStore
) -> QueryBackend:
    """按目标平台构造知识库查询后端.

    Args:
        platform: 平台标识 (aliyun/volc).
        store: GUI 配置持久化存储实例, 用于读取已保存
            配置并构造对应平台客户端.

    Returns:
        对应平台的查询后端实例.

    Raises:
        ValueError: 平台标识不受支持时抛出.
    """
    logger.debug('构造查询后端 | platform={}', platform)
    if platform == 'volc':
        client_kwargs = store.get_volc_client_kwargs()
        client = VikingKnowledgeClient(**client_kwargs)  # type: ignore[arg-type]
        volc_cfg = cast(
            VikingKnowledgeSettings, client_kwargs['config']
        )
        return VolcQueryBackend(
            client=client,
            service_resource_id=volc_cfg.service_resource_id,
        )
    if platform == 'aliyun':
        client_kwargs = store.get_aliyun_client_kwargs()
        client_ak = AliyunKnowledgeClient(**client_kwargs)  # type: ignore[arg-type]
        aliyun_cfg = cast(
            AliyunKnowledgeSettings, client_kwargs['config']
        )
        return AliyunQueryBackend(
            client=client_ak,
            api_key=aliyun_cfg.api_key,
            agent_id=aliyun_cfg.agent_id,
        )
    raise ValueError(f'不支持的目标平台: {platform}')
