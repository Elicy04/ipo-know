"""通用文件下载器.

提供基于 httpx 流式下载的文件获取能力,
支持单文件下载和并发批量下载,
内置自动重试和文件名冲突处理.
仅接受传参, 不与项目其他模块耦合.
"""

import pathlib
from concurrent import futures
from urllib import parse

import httpx
import tenacity
from loguru import logger


class Downloader:
    """通用文件下载器.

    接受文件 URL 或 URL 列表, 将文件流式下载到指定目录.
    每个下载独立创建 httpx.Client, 天然支持多线程并发.

    Attributes:
        download_dir: 文件保存目录.
        max_workers: 并发下载线程数.
        timeout: 单文件下载超时 (秒).
        max_retries: 最大重试次数.
    """

    def __init__(
        self,
        download_dir: str | pathlib.Path,
        max_workers: int = 4,
        timeout: float = 60.0,
        max_retries: int = 3,
    ) -> None:
        """初始化下载器.

        Args:
            download_dir: 文件保存目录 (必传).
            max_workers: 并发下载线程数.
            timeout: 单文件下载超时 (秒).
            max_retries: 最大重试次数.

        Raises:
            ValueError: download_dir 为空时抛出.
        """
        dir_str = str(download_dir).strip()
        if not dir_str:
            raise ValueError('download_dir 不能为空')

        self.download_dir = pathlib.Path(dir_str)
        self.download_dir.mkdir(parents=True, exist_ok=True)

        self._max_workers = max_workers
        self._timeout = timeout
        self._max_retries = max_retries

        logger.info(
            '下载器初始化 | download_dir={} | max_workers={} | '
            'timeout={}s | max_retries={}',
            str(self.download_dir),
            max_workers,
            timeout,
            max_retries,
        )

    # ==================================================
    # 公开接口
    # ==================================================
    def download(self, url: str) -> pathlib.Path:
        """下载单个文件.

        Args:
            url: 文件下载链接.

        Returns:
            下载文件的本地路径.

        Raises:
            ValueError: URL 为空或无法提取有效文件名时抛出.
            httpx.HTTPStatusError: 服务端返回 4xx/5xx, 重试耗尽后抛出.
            httpx.RequestError: 网络层错误, 重试耗尽后抛出.
        """
        if not url:
            raise ValueError('URL 不能为空')

        file_path = self._resolve_file_path(url)
        logger.info('开始下载 | url={} | file={}', url, file_path.name)

        retry_decorator = tenacity.retry(
            stop=tenacity.stop_after_attempt(self._max_retries),
            wait=tenacity.wait_exponential(multiplier=1, min=1, max=30),
            retry=tenacity.retry_if_exception_type(
                (httpx.HTTPStatusError, httpx.RequestError),
            ),
            reraise=True,
            before_sleep=tenacity.before_sleep_log(logger, 'WARNING'),
        )

        @retry_decorator
        def _do() -> pathlib.Path:
            with (
                httpx.Client(
                    follow_redirects=True,
                    timeout=httpx.Timeout(self._timeout),
                ) as client,
                client.stream('GET', url) as response,
            ):
                response.raise_for_status()
                with open(file_path, 'wb') as f:
                    for chunk in response.iter_bytes(
                        chunk_size=8192,
                    ):
                        f.write(chunk)
            return file_path

        result = _do()
        logger.info('下载完成 | {}', file_path.name)
        return result

    def download_many(self, urls: list[str]) -> list[pathlib.Path]:
        """并发下载多个文件.

        使用线程池并发执行, 单个失败不影响其他任务.
        调用方可通过对比输入列表长度判断是否有遗漏.

        Args:
            urls: 文件下载链接列表.

        Returns:
            成功下载的文件本地路径列表 (失败项被跳过).

        Raises:
            ValueError: URL 列表为空时抛出.
        """
        if not urls:
            raise ValueError('URL 列表不能为空')

        logger.info(
            '开始批量下载 | 共 {} 个文件 | 并发数={}',
            len(urls),
            self._max_workers,
        )

        results: list[pathlib.Path] = []

        with futures.ThreadPoolExecutor(
            max_workers=self._max_workers,
        ) as executor:
            future_map: dict[futures.Future[pathlib.Path], str] = {}
            for url in urls:
                future = executor.submit(self.download, url)
                future_map[future] = url

            for future in futures.as_completed(future_map):
                url = future_map[future]
                try:
                    file_path = future.result()
                    results.append(file_path)
                except Exception:
                    logger.exception('下载失败, 已跳过 | url={}', url)

        logger.info(
            '批量下载结束 | 成功={}/{}',
            len(results),
            len(urls),
        )
        return results

    # ==================================================
    # 内部方法
    # ==================================================
    def _resolve_file_path(self, url: str) -> pathlib.Path:
        """从 URL 提取文件名并解析为本地唯一路径.

        文件名提取: URL 路径末段 → URL 解码 → 去除非法字符.
        若目标文件已存在, 自动追加 _1, _2 等递增编号.

        Args:
            url: 文件下载链接.

        Returns:
            不冲突的本地文件路径.

        Raises:
            ValueError: URL 无法提取有效文件名时抛出.
        """
        parsed = parse.urlparse(url)
        raw_name = parsed.path.rstrip('/').split('/')[-1] if parsed.path else ''

        if not raw_name:
            raise ValueError(f'无法从 URL 提取文件名: {url}')

        filename = parse.unquote(raw_name)

        illegal = '<>:"|?*'
        for ch in illegal:
            filename = filename.replace(ch, '_')

        base_path = self.download_dir / filename
        return self._ensure_unique_path(base_path)

    @staticmethod
    def _ensure_unique_path(base_path: pathlib.Path) -> pathlib.Path:
        """若路径已存在, 追加递增编号生成不冲突的路径.

        Args:
            base_path: 目标文件路径.

        Returns:
            保证不存在的文件路径.
        """
        if not base_path.exists():
            return base_path

        stem = base_path.stem
        suffix = base_path.suffix
        parent = base_path.parent

        n = 1
        while True:
            candidate = parent / f'{stem}_{n}{suffix}'
            if not candidate.exists():
                logger.warning(
                    '文件名冲突, 已重命名: {} → {}',
                    base_path.name,
                    candidate.name,
                )
                return candidate
            n += 1
