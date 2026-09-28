import importlib
import subprocess
import sys


def _ensure_dependencies():
    """Install Python packages required by AirCode when they are missing."""
    dependencies = [
        ("Flask", "flask"),
        ("Flask-Cors", "flask_cors"),
        ("waitress", "waitress"),
        ("requests", "requests"),
        ("websockets", "websockets"),
        ("SpeechRecognition", "speech_recognition"),
        ("pypdf", "pypdf"),
        ("mammoth", "mammoth"),
        ("openpyxl", "openpyxl"),
        ("pathspec", "pathspec"),
        ("pandas", "pandas"),
        ("python-pptx", "pptx"),
        ("xmindparser", "xmindparser"),
        ("lxml", "lxml"),
        ("pytesseract", "pytesseract"),
        ("pyzbar", "pyzbar"),
        ("Pillow", "PIL"),
        ("markdown2", "markdown2"),
        ("qrcode", "qrcode"),
        ("edge-tts", "edge_tts"),
        ("gTTS", "gtts"),
        ("python-docx", "docx"),
        ("htmldocx", "htmldocx"),
        ("chardet", "chardet"),
    ]

    for package, module in dependencies:
        try:
            importlib.import_module(module)
        except ImportError:
            print(f"Missing module '{module}', installing package '{package}'...")
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", package]
            )
            importlib.invalidate_caches()


_ensure_dependencies()


from flask import Flask, request, Response
import time
from urllib.parse import unquote
from flask_cors import CORS
from pathlib import Path
import uuid
base_path = Path("SERVERFILES")

app = Flask(__name__)
CORS(app)  # 允许跨域请求

def set_terminal_title(title):
    """设置终端窗口的标题"""
    if sys.platform.startswith('win'):
        import ctypes
        ctypes.windll.kernel32.SetConsoleTitleW(title)
    else:
        sys.stdout.write(f"\x1b]0;{title}\x07")
        sys.stdout.flush()



import threading
import asyncio
import ctypes
import inspect
from worker import main_worker, sub_worker
from utilities.ask_answer import threadLock
from utilities.ask_answer import asks, askhandle


set_terminal_title('AirCode')

def __async_raise(thread_Id, exctype):
    #在子线程内部抛出一个异常结束线程
    #如果线程内执行的是unittest模块的测试用例， 由于unittest内部又异常捕获处理，所有这个结束线程
    #只能结束当前正常执行的unittest的测试用例， unittest的下一个测试用例会继续执行，只有结束继续
    #向unittest中添加测试用例才能使线程执行完任务，然后自动结束。
    thread_Id = ctypes.c_long(thread_Id)
    if not inspect.isclass(exctype):
        exctype = type(exctype)
    res = ctypes.pythonapi.PyThreadState_SetAsyncExc(thread_Id, ctypes.py_object(exctype))
    if res == 0:
        raise ValueError("invalid thread id")
    elif res != 1:
        ctypes.pythonapi.PyThreadState_SetAsyncExc(thread_Id, None)
        raise SystemError("PyThreadState_SEtAsyncExc failed")

def terminator(thread):
    #结束线程
    try:
        __async_raise(thread.ident, SystemExit)
    except Exception:
        pass


maxthreadcount = 30
mainthreads = []
mainthreadtimes = {}
subthreads = []
subthreadtimes = {}

for i in range(0, maxthreadcount):
    thread = threading.Thread(target=main_worker, args=(mainthreadtimes,), daemon=True)
    thread.start()
    mainthreads.append(thread)
    mainthreadtimes[thread.ident] = time.time()

    thread_loop = asyncio.new_event_loop() 
    thread = threading.Thread(target=sub_worker, args=(thread_loop,subthreadtimes,), daemon=True)
    thread.start()
    subthreads.append(thread)
    subthreadtimes[thread.ident] = time.time()

from utilities.ws_client import start_websocket_thread
ws_thread = start_websocket_thread("3788db5825704dd7ad5a2022eea8f829", "ws://127.0.0.1:3133")

def background_worker():
    """后台工作线程，处理线程管理"""
    while True:
        time.sleep(0.01)

        tercount = 0
        for thread in mainthreads:
            if time.time() - mainthreadtimes[thread.ident] > 86400:
                mainthreads.remove(thread)
                terminator(thread)
                tercount += 1
        while tercount > 0:
            tercount -= 1
            thread = threading.Thread(target=main_worker, args=(mainthreadtimes,), daemon=True)
            thread.start()
            mainthreads.append(thread)
            mainthreadtimes[thread.ident] = time.time()

        tercount = 0
        for thread in subthreads:
            if time.time() - subthreadtimes[thread.ident] > 86400:
                subthreads.remove(thread)
                terminator(thread)
                tercount += 1
        while tercount > 0:
            tercount -= 1
            thread_loop = asyncio.new_event_loop() 
            thread = threading.Thread(target=sub_worker, args=(thread_loop,subthreadtimes,), daemon=True)
            thread.start()
            subthreads.append(thread)
            subthreadtimes[thread.ident] = time.time()

def start_background_worker():
    """启动后台工作线程"""
    worker_thread = threading.Thread(target=background_worker, daemon=True)
    worker_thread.start()




def generate_guid_filename(original_filename):
    """生成GUID文件名并保留扩展名"""
    ext = original_filename.rsplit('.', 1)[1].lower() if '.' in original_filename else ''
    guid = str(uuid.uuid4())
    if ext:
        return f"{{{guid}}}.{ext}"
    return guid

def is_valid_guid_filename(filename):
    """
    判断文件名是否已经是 {GUID}.ext 格式
    """
    if '.' not in filename:
        return False
        
    try:
        # 分割文件名和扩展名
        name_part, ext = filename.rsplit('.', 1)
        
        # 检查是否以 { 开头并以 } 结尾
        if not (name_part.startswith('{') and name_part.endswith('}')):
            return False
            
        # 去除花括号，尝试解析 UUID
        uuid_str = name_part[1:-1]
        uuid.UUID(uuid_str) # 如果不是合法的UUID字符串，这里会抛出 ValueError
        
        return True
    except (ValueError, IndexError):
        return False

@app.route('/upload', methods=['POST'])
def upload_file():
    """处理文件上传"""
    if 'file' not in request.files:
        return ''
    
    file = request.files['file']
    
    if file.filename == '':
        return ''
    
    if file:
        # 判断文件名是否已经是GUID格式
        if is_valid_guid_filename(file.filename):
            guid_filename = file.filename
        else:
            # 否则生成新的GUID文件名
            guid_filename = generate_guid_filename(file.filename)
        
        # 保存文件
        filepath = base_path / guid_filename
        file.save(filepath)
        
        # 返回GUID信息
        return guid_filename
    else:
        return ''


@app.route('/ask', methods=['POST'])
def handle_ask():
    try:
        data = request.get_json(silent=True)
        clienturl = unquote(request.headers.get('ClientURL'))
        prompt = data.get('prompt', '')
        streamid = data.get('streamid', '')
        print(streamid)

        threadLock.acquire()
        global askhandle
        askhandle = askhandle + 1
        asks.append([clienturl, prompt, streamid, askhandle])
        threadLock.release()
        
        response_text = ''
        return Response(response_text, mimetype='text/plain; charset=utf-8')
    
    except Exception as e:
        error_text = f"服务器处理错误: {str(e)}"
        return Response(error_text, 
                       status=500, 
                       mimetype='text/plain; charset=utf-8')


# ----------------------
# 主程序入口
# ----------------------
if __name__ == "__main__":

    # 启动Flask服务
    app.run()
