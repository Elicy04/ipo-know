"""纯 HTTP 客户端基类.

基于 httpx + hishel (HTTP 缓存) + tenacity (自动重试),
提供最简同步 HTTP 请求能力, 不包含任何业务解析逻辑.
"""

import pathlib

import hishel
import httpx
import tenacity
from loguru import logger


class BaseHttpClient:
    """纯 HTTP 客户端基类.

    封装 httpx.Client, 提供 HTTP 缓存 (hishel) 与自动重试
    (tenacity). 仅负责传输层, 不做响应解析或业务校验.

    用法:
        with BaseHttpClient(base_url='https://api.example.com') as cli:
            resp = cli.get('/endpoint', params={'key': 'value'})
            data = resp.json()
    """

    def __init__(  # noqa: ANN204  # pystyle 3.19.1: __init__ 不需要返回值注解
        self,
        base_url: str = '',
        headers: dict[str, str] | None = None,
        timeout: float = 30.0,
        cache_dir: str | pathlib.Path | None = None,
        cache_ttl: int = 3600,
        max_retries: int = 3,
    ):
        """初始化 HTTP 客户端.

        Args:
            base_url: 请求基础域名, 如 https://api.example.com.
            headers: 全局默认请求头.
            timeout: 请求超时时间, 单位秒.
            cache_dir: HTTP 缓存目录, 为 None 则不启用缓存.
            cache_ttl: 缓存有效期 (秒), 默认 1 小时.
            max_retries: 最大重试次数.
        """
        self.base_url = base_url.rstrip('/')

        transport = httpx.HTTPTransport()

        if cache_dir:
            storage = hishel.FileStorage(
                base_path=pathlib.Path(cache_dir),
                ttl=cache_ttl,
            )
            transport = hishel.CacheTransport(
                transport=transport,
                storage=storage,
            )
            logger.info(
                'HTTP 客户端初始化 | base_url={} | timeout={}s | '
                'cache_dir={} | cache_ttl={}s | max_retries={}',
                self.base_url or '(无)',
                timeout,
                cache_dir,
                cache_ttl,
                max_retries,
            )
        else:
            logger.info(
                'HTTP 客户端初始化 | base_url={} | timeout={}s | '
                'cache=off | max_retries={}',
                self.base_url or '(无)',
                timeout,
                max_retries,
            )

        self._client = httpx.Client(
            base_url=self.base_url,
            headers=headers or {},
            timeout=httpx.Timeout(timeout),
            transport=transport,
        )
        self._max_retries = max_retries

    # ==================================================
    # 请求入口
    # ==================================================
    def request(
        self,
        method: str,
        url: str,
        **kwargs: object,
    ) -> httpx.Response:
        """发送 HTTP 请求, 含自动重试.

        Args:
            method: HTTP 方法 (GET / POST / ...).
            url: 请求路径, 支持相对路径或绝对 URL.
            **kwargs: 传递给 httpx.Client.request 的额外参数.

        Returns:
            httpx.Response 对象.

        Raises:
            httpx.HTTPStatusError: 服务端返回 4xx/5xx.
            httpx.RequestError: 网络层错误 (超时/DNS/连接重置).
        """
        retry_decorator = tenacity.retry(
            stop=tenacity.stop_after_attempt(self._max_retries),
            wait=tenacity.wait_exponential(multiplier=1, min=1, max=10),
            retry=tenacity.retry_if_exception_type(
                (httpx.HTTPStatusError, httpx.RequestError)
            ),
            reraise=True,
            before_sleep=tenacity.before_sleep_log(
                logger, 'WARNING',
            ),
        )

        logger.debug('HTTP 请求 | {} {}', method, url)

        @retry_decorator
        def _do() -> httpx.Response:
            resp = self._client.request(method, url, **kwargs)  # type: ignore[arg-type]
            resp.raise_for_status()
            logger.debug(
                'HTTP 响应 | {} {} → {} ({} bytes)',
                method, url, resp.status_code,
                len(resp.content),
            )
            return resp

        return _do()

    def get(self, url: str, **kwargs: object) -> httpx.Response:
        """发送 GET 请求."""
        return self.request('GET', url, **kwargs)

    def post(self, url: str, **kwargs: object) -> httpx.Response:
        """发送 POST 请求."""
        return self.request('POST', url, **kwargs)

    # ==================================================
    # 会话管理
    # ==================================================
    def close(self) -> None:
        """关闭 HTTP 会话, 释放连接."""
        logger.debug('HTTP 客户端关闭')
        self._client.close()

    def __enter__(self) -> 'BaseHttpClient':  # noqa: D105, RUF003  # 标准 context manager 协议，行为自明
        return self

    def __exit__(self, *args: object) -> None:  # noqa: D105, RUF003  # 标准 context manager 协议，行为自明
        self.close()
