import sys
import subprocess

# 自动检测并安装缺失的第三方模块
def check_and_install(package):
    try:
        __import__(package)
    except ImportError:
        print(f"模块 {package} 缺失，正在自动安装...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])

# 检查当前脚本所需的第三方库
check_and_install('waitress')

import threading
from waitress import serve
from app import app
from app import run_websocket_server   # 导入 WebSocket 启动函数

# 启动 WebSocket 服务器线程（守护线程，随主线程退出）
ws_thread = threading.Thread(target=run_websocket_server, daemon=True)
ws_thread.start()

# 启动 WSGI 服务器
serve(app, host='0.0.0.0', port=3130, threads=10)