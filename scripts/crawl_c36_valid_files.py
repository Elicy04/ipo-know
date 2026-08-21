"""临时脚本: 爬取 C36 有效披露文件清单.

调用 crawler 模块, 针对汽车制造业(C36)、主板+科创板、全审核状态,
拉取项目及披露文件, 按披露阶段筛选有效文件后输出 JSON 清单到
系统下载目录的 ipo_know_c36 子目录.

用法:
    uv run python crawl_c36_valid_files.py
"""

import ctypes
import sys
from pathlib import Path


# 保证未安装项目包时也能直接运行
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from ipo_know.crawler import SSEIPOCrawler


def get_windows_downloads_dir() -> Path:
    """获取 Windows 系统下载文件夹的真实路径.

    通过 shell32 的 SHGetKnownFolderPath 查询, 避免 OneDrive
    重定向等场景下 Path.home()/Downloads 与实际不一致.

    Returns:
        下载文件夹路径; 查询失败时回退用户目录下的 Downloads.
    """
    try:
        # FOLDERID_Downloads = {374DE290-123F-4565-9164-39C4925E467B}
        class GUID(ctypes.Structure):
            _fields_ = [
                ('Data1', ctypes.c_ulong),
                ('Data2', ctypes.c_ushort),
                ('Data3', ctypes.c_ushort),
                ('Data4', ctypes.c_ubyte * 8),
            ]

        folder_id = GUID(
            0x374DE290, 0x123F, 0x4565,
            (ctypes.c_ubyte * 8)(0x91, 0x64, 0x39, 0xC4,
                                 0x92, 0x5E, 0x46, 0x7B),
        )
        buf = ctypes.c_wchar_p()
        shell32 = ctypes.windll.shell32  # type: ignore[attr-defined]
        ret = shell32.SHGetKnownFolderPath(
            ctypes.byref(folder_id), 0, None, ctypes.byref(buf)
        )
        if ret == 0 and buf.value:
            path = Path(buf.value)
            ctypes.windll.ole32.CoTaskMemFree(buf)  # type: ignore[attr-defined]
            return path
    except Exception:  # 回退默认路径
        pass
    return Path.home() / 'Downloads'


def main() -> None:
    """爬取 C36 有效披露文件并输出清单 JSON."""
    download_dir = get_windows_downloads_dir() / 'ipo_know_c36'
    print(f'下载目标目录: {download_dir}')

    crawler = SSEIPOCrawler()
    files = crawler.collect()
    manifest_path = crawler.save(files, 'C36', download_dir)

    print(f'\n完成: 共 {len(files)} 个有效文件')
    print(f'清单路径: {manifest_path}')


if __name__ == '__main__':
    main()
