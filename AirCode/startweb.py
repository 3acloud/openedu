from waitress import serve
from app import app
from app import start_background_worker

# 启动后台工作线程
start_background_worker()

serve(app, host='0.0.0.0', port=3131)