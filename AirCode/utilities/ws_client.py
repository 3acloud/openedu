# ws_client.py
import asyncio
import json
import uuid
import os
import struct
from pathlib import Path
import websockets
import concurrent.futures
import threading

# 分块大小（64KB）
CHUNK_SIZE = 64 * 1024

# 并发消费者数量（可根据需要调整）
TEXT_CONSUMER_COUNT = 10      # 文本消息并发数
FILE_CONSUMER_COUNT = 2       # 文件传输并发数


class WebSocketClient:
    def __init__(self, api_key: str, server_url: str):
        self.api_key = api_key
        self.server_url = server_url
        self.ws = None
        self.pending = {}          # message_id -> asyncio.Future
        self.receiving_files = {}   # file_id -> 接收状态字典
        self.heartbeat_task = None
        self.receive_task = None    # 保存接收任务以便外部等待

    async def connect(self):
        """连接服务器并注册"""
        self.ws = await websockets.connect(self.server_url)
        # 发送注册消息
        await self.ws.send(json.dumps({"type": "register", "apiKey": self.api_key}))

        # 创建 SERVERFILES 目录
        Path("SERVERFILES").mkdir(exist_ok=True)

        # 启动心跳（每30秒发送ping）
        self.heartbeat_task = asyncio.create_task(self._heartbeat())

        # 启动消息接收循环
        self.receive_task = asyncio.create_task(self._receive_messages())

    async def _heartbeat(self):
        """定时发送ping保持连接"""
        try:
            while True:
                await asyncio.sleep(30)
                if self.ws and self.ws.open:
                    await self.ws.ping()
        except asyncio.CancelledError:
            pass
        except Exception:
            # 心跳异常直接退出，由外层重连
            pass

    async def _receive_messages(self):
        """处理所有收到的消息（文本和二进制）"""
        try:
            async for message in self.ws:
                if isinstance(message, bytes):
                    await self._handle_binary(message)
                    continue

                try:
                    data = json.loads(message)
                    msg_type = data.get("type")

                    if msg_type == "register_ack":
                        pass
                    elif msg_type == "from":
                        from_api = data["fromApiKey"]
                        content = data["content"]
                        msg_id = data["messageId"]
                        print(f"收到来自 {from_api} 的消息: {content}")

                        reply = f"自动回复: 收到你的消息 \"{content}\""
                        await self.ws.send(json.dumps({
                            "type": "response",
                            "targetApiKey": from_api,
                            "targetMessageId": msg_id,
                            "content": reply
                        }))

                    elif msg_type == "file_start":
                        from_api = data["fromApiKey"]
                        file_id = data["fileId"]
                        file_name = data["fileName"]
                        file_size = data["fileSize"]
                        total_chunks = data["totalChunks"]
                        msg_id = data["messageId"]

                        temp_path = Path(os.path.join("SERVERFILES", f"{file_id}.tmp"))
                        f = open(temp_path, "wb")
                        self.receiving_files[file_id] = {
                            "file": f,
                            "temp_path": temp_path,
                            "file_name": file_name,
                            "total_chunks": total_chunks,
                            "received_chunks": 0,
                            "from_api": from_api,
                            "message_id": msg_id
                        }

                    elif msg_type == "response":
                        target_id = data["targetMessageId"]
                        content = data["content"]
                        future = self.pending.get(target_id)
                        if future:
                            future.set_result(content)
                            del self.pending[target_id]
                        else:
                            print(f"收到未知 messageId 的响应: {target_id}")

                    elif msg_type == "error":
                        print("服务器错误:", data["message"])

                except Exception as e:
                    print("处理消息时出错:", e)
        except websockets.exceptions.ConnectionClosed:
            print("连接已关闭，接收任务结束")
        except asyncio.CancelledError:
            pass
        finally:
            # 确保所有 pending 请求失败
            for future in self.pending.values():
                if not future.done():
                    future.set_exception(Exception("连接关闭"))
            self.pending.clear()

    async def _handle_binary(self, data: bytes):
        """处理二进制消息（文件块）"""
        if len(data) < 16 + 16 + 4:
            print("二进制消息长度不足，丢弃")
            return

        target_key_bytes = data[:16]
        target_key = target_key_bytes.hex()
        if target_key != self.api_key:
            print(f"收到不是发给自己的二进制消息，目标: {target_key}")
            return

        file_id_bytes = data[16:32]
        file_id = file_id_bytes.hex()
        chunk_index = int.from_bytes(data[32:36], "big")
        chunk_data = data[36:]

        recv_info = self.receiving_files.get(file_id)
        if not recv_info:
            print(f"未找到文件接收记录，fileId: {file_id}")
            return

        await asyncio.to_thread(recv_info["file"].write, chunk_data)
        recv_info["received_chunks"] += 1

        if recv_info["received_chunks"] == recv_info["total_chunks"]:
            await asyncio.to_thread(recv_info["file"].close)

            final_path = Path(os.path.join("SERVERFILES", recv_info["file_name"]))
            if final_path.exists():
                base = final_path.stem
                suffix = final_path.suffix
                counter = 1
                while final_path.exists():
                    final_path = final_path.with_name(f"{base}_{counter}{suffix}")
                    counter += 1

            await asyncio.to_thread(os.rename, recv_info["temp_path"], final_path)

            print(f"文件接收完成: {final_path}")

            await self.ws.send(json.dumps({
                "type": "response",
                "targetApiKey": recv_info["from_api"],
                "targetMessageId": recv_info["message_id"],
                "content": f"文件已保存至 {final_path}"
            }))

            del self.receiving_files[file_id]

    async def send_and_wait(self, target_api_key: str, content: str, timeout: float = 10.0):
        message_id = str(uuid.uuid4().hex)
        future = asyncio.get_running_loop().create_future()
        self.pending[message_id] = future

        try:
            await self.ws.send(json.dumps({
                "type": "message",
                "targetApiKey": target_api_key,
                "content": content,
                "messageId": message_id
            }))
        except Exception as e:
            del self.pending[message_id]
            raise

        try:
            response = await asyncio.wait_for(future, timeout)
            return response
        except asyncio.TimeoutError:
            del self.pending[message_id]
            raise Exception("等待响应超时")

    async def send_file(self, target_api_key: str, file_path: str, timeout: float = 60.0):
        if not os.path.isfile(file_path):
            raise Exception(f"文件不存在: {file_path}")

        file_size = os.path.getsize(file_path)
        file_name = os.path.basename(file_path)
        file_id = str(uuid.uuid4().hex).replace("-", "")
        total_chunks = (file_size + CHUNK_SIZE - 1) // CHUNK_SIZE
        message_id = str(uuid.uuid4().hex)

        future = asyncio.get_running_loop().create_future()
        self.pending[message_id] = future

        await self.ws.send(json.dumps({
            "type": "file_start",
            "targetApiKey": target_api_key,
            "fileId": file_id,
            "fileName": file_name,
            "fileSize": file_size,
            "chunkSize": CHUNK_SIZE,
            "totalChunks": total_chunks,
            "messageId": message_id
        }))

        target_key_bytes = bytes.fromhex(target_api_key)
        file_id_bytes = bytes.fromhex(file_id)

        with open(file_path, "rb") as f:
            chunk_index = 0
            while True:
                chunk = f.read(CHUNK_SIZE)
                if not chunk:
                    break

                header = bytearray()
                header.extend(target_key_bytes)
                header.extend(file_id_bytes)
                header.extend(struct.pack(">I", chunk_index))

                await self.ws.send(header + chunk)
                chunk_index += 1

        try:
            response = await asyncio.wait_for(future, timeout)
            return response
        except asyncio.TimeoutError:
            del self.pending[message_id]
            raise Exception("等待文件传输响应超时")

    async def close(self):
        """关闭连接，清理任务"""
        for future in self.pending.values():
            if not future.done():
                future.set_exception(Exception("连接关闭"))
        self.pending.clear()

        for file_id, recv in self.receiving_files.items():
            try:
                recv["file"].close()
                os.unlink(recv["temp_path"])
            except:
                pass
        self.receiving_files.clear()

        if self.heartbeat_task:
            self.heartbeat_task.cancel()
        if self.receive_task:
            self.receive_task.cancel()
        if self.ws:
            await self.ws.close()


# 全局变量
_ws_loop = None
_request_queue = None          # 文本消息请求队列
_file_request_queue = None      # 文件传输请求队列
_ready = threading.Event()

async def _handle_requests(client):
    """处理文本消息请求（支持取消安全）"""
    global _request_queue
    while True:
        current_future = None
        try:
            target, content, future, timeout = await _request_queue.get()
            current_future = future
            response = await client.send_and_wait(target, content, timeout)
            if not future.done():
                future.set_result(response)
        except asyncio.CancelledError:
            if current_future and not current_future.done():
                current_future.set_exception(asyncio.CancelledError())
            raise
        except Exception as e:
            if current_future and not current_future.done():
                current_future.set_exception(e)
        finally:
            current_future = None

async def _handle_file_requests(client):
    """处理文件传输请求（支持取消安全）"""
    global _file_request_queue
    while True:
        current_future = None
        try:
            target, file_path, future, timeout = await _file_request_queue.get()
            current_future = future
            response = await client.send_file(target, file_path, timeout)
            if not future.done():
                future.set_result(response)
        except asyncio.CancelledError:
            if current_future and not current_future.done():
                current_future.set_exception(asyncio.CancelledError())
            raise
        except Exception as e:
            if current_future and not current_future.done():
                current_future.set_exception(e)
        finally:
            current_future = None

async def send_ws_message(target: str, content: str, timeout: float = 10.0):
    """供外部调用的发送文本消息函数（线程安全）"""
    global _ws_loop, _request_queue
    if _ws_loop is None or _request_queue is None:
        if not _ready.wait(timeout=5):
            raise RuntimeError("WebSocket client not ready")
    future = concurrent.futures.Future()
    asyncio.run_coroutine_threadsafe(
        _request_queue.put((target, content, future, timeout)),
        _ws_loop
    )
    return await asyncio.wrap_future(future)

async def send_ws_file(target: str, file_path: str, timeout: float = 60.0):
    """供外部调用的发送文件函数（线程安全）"""
    global _ws_loop, _file_request_queue
    if _ws_loop is None or _file_request_queue is None:
        if not _ready.wait(timeout=5):
            raise RuntimeError("WebSocket client not ready")
    future = concurrent.futures.Future()
    asyncio.run_coroutine_threadsafe(
        _file_request_queue.put((target, file_path, future, timeout)),
        _ws_loop
    )
    return await asyncio.wrap_future(future)


def start_websocket_thread(api_key: str, server_url: str):
    """启动 WebSocket 线程（由 main.py 调用）"""
    async def run_client():
        global _ws_loop, _request_queue, _file_request_queue, _ready
        _ws_loop = asyncio.get_running_loop()
        retry_delay = 1
        max_delay = 60

        while True:
            # 重置就绪状态，新连接准备中
            _ready.clear()

            # 创建新的请求队列
            _request_queue = asyncio.Queue()
            _file_request_queue = asyncio.Queue()

            client = WebSocketClient(api_key, server_url)
            text_consumers = []
            file_consumers = []

            try:
                await client.connect()
                print("WebSocket 连接成功")
                retry_delay = 1  # 重置重试延迟

                # 启动多个消费者任务实现并发
                for _ in range(TEXT_CONSUMER_COUNT):
                    task = asyncio.create_task(_handle_requests(client))
                    text_consumers.append(task)
                for _ in range(FILE_CONSUMER_COUNT):
                    task = asyncio.create_task(_handle_file_requests(client))
                    file_consumers.append(task)

                # 队列已就绪，允许外部发送请求
                _ready.set()

                # 等待连接关闭（通过 ws.wait_closed 或任一消费者异常）
                wait_closed_task = asyncio.create_task(client.ws.wait_closed())
                all_tasks = [wait_closed_task] + text_consumers + file_consumers
                done, pending = await asyncio.wait(
                    all_tasks,
                    return_when=asyncio.FIRST_COMPLETED
                )

                # 取消所有未完成的任务
                for task in pending:
                    task.cancel()
                await asyncio.gather(*pending, return_exceptions=True)

                # 关闭客户端
                await client.close()
                print("连接已关闭，准备重连...")

            except Exception as e:
                print(f"连接异常: {e}，将在 {retry_delay} 秒后重试...")
                # 取消所有消费者任务
                for task in text_consumers + file_consumers:
                    task.cancel()
                await asyncio.gather(*[t for t in text_consumers+file_consumers if not t.done()], return_exceptions=True)
                await client.close()
            finally:
                # 确保 _ready 被清除（可能已被设置，但连接已断开）
                _ready.clear()

                # 清空队列，将所有未处理的请求标记为异常
                def fail_queue(queue):
                    while not queue.empty():
                        try:
                            item = queue.get_nowait()
                            # item 结构: (target, content, future, timeout)
                            future = item[2]
                            if not future.done():
                                future.set_exception(ConnectionError("WebSocket connection lost"))
                        except asyncio.QueueEmpty:
                            break

                fail_queue(_request_queue)
                fail_queue(_file_request_queue)

            # 指数退避重连
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, max_delay)

    def thread_target():
        asyncio.run(run_client())

    thread = threading.Thread(target=thread_target, daemon=True)
    thread.start()
    return thread
