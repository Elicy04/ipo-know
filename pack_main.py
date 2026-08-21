"""PyInstaller 打包入口.

冻结环境下必须先执行 freeze_support, 否则 native 模式
的子进程会无限循环.
"""

import multiprocessing


if __name__ == '__main__':
    multiprocessing.freeze_support()

    from ipo_know.ui.main import main

    main()
