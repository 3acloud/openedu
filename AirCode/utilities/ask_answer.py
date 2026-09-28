import os
import json
import requests
import threading
threadLock = threading.Lock()
subworkflows = []
subwfhandle = 0
pauseworkflows = []
triggerworkflows = []
backworkflows = []

asks = []
askhandle = 0


def send_answer(sendhandle, answer):
    import re
    threadLock.acquire()
    i = 0
    while i < len(asks):
        [clienturl, ask, streamid, handle] = asks[i]
        if sendhandle == handle:
            threadLock.release()

            # --- 新增文件上传逻辑开始 ---
            try:
                pattern = r'(?:%7B|\{)[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}(?:%7D|\})\.\w+'
                #pattern = r'\{[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}\}\.\w+'
                matches = re.findall(pattern, answer)  # 返回所有匹配的文件名列表
                matches = set(matches)
                for tFileName in matches:
                    tFileName = tFileName.replace("%7B", "{")
                    tFileName = tFileName.replace("%7D", "}")
                    # 此时 tFileName 已经是提取出的 {guid}.ext 格式
                        
                    # 拼接文件路径
                    file_path = "SERVERFILES/" + tFileName
                        
                    # 生成上传URL
                    upload_url = clienturl.replace('/answer', '/upload')
                    # 检查文件是否存在并上传
                    if os.path.exists(file_path):
                        with open(file_path, 'rb') as f:
                            # 构建上传的files参数
                            files = {'file': (tFileName, f)}
                            # 发送上传请求，这里可以根据服务端要求添加 data={'streamid': streamid}
                            requests.post(
                                upload_url, 
                                files=files
                            )
            except Exception as e:
                # 文件上传失败不应阻塞后续的文本回复发送，这里选择忽略或打印日志
                pass
            # --- 新增文件上传逻辑结束 ---

            headers = {
                'Content-Type': 'application/json'
            }
            request = {}
            request["streamid"] = streamid
            request["answer"] = answer
    
            try:
                requests.post(
                    clienturl, 
                    headers=headers, 
                    data=json.dumps(request)
                )
            except Exception as e:
                pass
            return
        i += 1
    threadLock.release()

def Ask():
    threadLock.acquire()

    i = 0
    while i < len(subworkflows):
        [workflow, node_id, zll, subhandle, state] = subworkflows[i]
        if state == -1:
            state = 1
            subworkflows[i] = [workflow, node_id, zll, subhandle, state]
            threadLock.release()
            return zll, subhandle
        i += 1

    ask = ""
    handle = 0
    i = 0
    while i < len(asks):
        [clienturl, ask, streamid, handle] = asks[i]
        if ask != '':
            asks[i] = [clienturl, '', streamid, handle]
            break
        handle = 0
        i += 1
    threadLock.release()

    return ask, handle


def Answer(vText, handle:int, streamrunid:str):
    if (handle < 0):
        threadLock.acquire()
        i = 0
        ret = True
        while i < len(subworkflows):
            [mainworkflow, node_id, zll, subhandle, state] = subworkflows[i]
            if handle == subhandle:
                if (mainworkflow.nodesout.get(node_id) == False):
                    ret = False
                    handle = mainworkflow.data["wid"]
                else:
                    ret = True
                break
            i += 1
        threadLock.release()
        if ret:
            return
    if vText == None:
        return

    threadLock.acquire()
    i = 0
    ret = False
    while i < len(backworkflows):
        [streamid, backtext, tempfiles, backhandle, state, username, createtime] = backworkflows[i]
        if streamid == streamrunid:
            backtext.append(vText)
            ret = True
            break
        i += 1
    threadLock.release()
    if ret:
        return

    if (type(vText) == list):
        send_answer(handle, "\n".join(vText))
    else:
        send_answer(handle, vText)

def Finish(handle:int, streamrunid:str):
    if (handle < 0):
        threadLock.acquire()
        i = 0
        while i < len(subworkflows):
            [workflow, node_id, zll, subhandle, state] = subworkflows[i]
            if handle == subhandle:
                state = 0
                subworkflows[i] = [workflow, node_id, zll, subhandle, state]
                break
            i += 1
        threadLock.release()
        return
    
    threadLock.acquire()
    i = 0
    ret = False
    socketname = ""
    while i < len(backworkflows):
        [streamid, backtext, tempfiles, backhandle, state, username, createtime] = backworkflows[i]
        if streamid == streamrunid:
            state = 1
            backworkflows[i] = [streamid, backtext, tempfiles, backhandle, state, username, createtime]
            socketname = username
            ret = True
            break
        i += 1
    threadLock.release()
    if ret:
        BackFinish(socketname, streamrunid)
        return

    send_answer(handle, '')
    threadLock.acquire()
    i = 0
    while i < len(asks):
        [clienturl, ask, streamid, askhandle] = asks[i]
        if handle == askhandle:
            asks.remove(asks[i])
            break
        i += 1
    threadLock.release()


def SetSocketName(vSocketName, handle:int):
    pass

def BackFinish(vSocketName, streamrunid):
    pass

