import re
import os
import shutil
import uuid
import subprocess
import ast
import hashlib
import chardet

from utilities.ws_client import send_ws_message
import asyncio
from pathlib import Path

from utilities.ask_answer import Answer
from utilities.workflow import Workflow
from worker.tasks import task
import math


def get_hash(text):
    # 创建一个hash对象
    hasher = hashlib.sha256()

    # 更新hash对象以包含文本
    hasher.update(text.encode('utf-8'))

    # 获取哈希值
    hash_value = hasher.hexdigest()

    return hash_value

def run_code(code,handle):
    try:
        code = '''import sys
import io

# 强制使用 UTF-8 编码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
''' + code
        result = subprocess.check_output(["python", "-c", code], stderr=subprocess.STDOUT, timeout=60, cwd="SERVERFILES/"+str(handle))
        return result.decode("utf-8")
    except subprocess.CalledProcessError as e:
        return e.output.decode("utf-8")
    except subprocess.TimeoutExpired:
        return "Timeout error: code execution took too long"

def illegal_import(code,allowed_modules):
    """
    判断代码中是否import了除允许的库之外的库
    :param code: 要判断的代码
    :param allowed_modules: 允许的库列表
    :return: True表示import了除允许的库之外的库，False表示未import或仅import了允许的库
    """
    # 将代码解析为抽象语法树
    try:
        tree = ast.parse(code)
    except Exception:
        return True

    # 遍历语法树中的所有import语句
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            # 处理import语句
            for alias in node.names:
                # 检查每个导入的库是否在允许的库列表中
                library = alias.name.split('.')[0]
                if library not in allowed_modules:
                    return True

        elif isinstance(node, ast.ImportFrom):
            # 处理import from语句
            # 检查导入的库是否在允许的库列表中
            library = node.module.split('.')[0]
            if library not in allowed_modules:
                return True

    return False


def exec_codex(inputfile, outputfile):
    project_dir = os.path.abspath("SERVERFILES")

    codex_executable = (
        shutil.which("codex.cmd")
        or shutil.which("codex.exe")
        or shutil.which("codex")
    )

    if codex_executable is None:
        return 0

    instruction = (
        f"处理'{inputfile}'里的请求（UTF-8格式文本），"
        f"结果文本输出到'{outputfile}'。"
        "如果需要输出文档或图片，那么文件名为以花括号包裹的UUID4字符串加扩展名，"
        "存放到当前目录下。绝对不允许列出当前目录下的所有项目。使用UTF-8。"
    )

    cmd = [
        codex_executable,
        "-C", project_dir,
        "-c", f"projects.'{project_dir}'.trust_level=\"trusted\"",
        "--sandbox", "danger-full-access",
        "--ask-for-approval", "never",
    ]

    cmd.extend([
        "exec",
        "--skip-git-repo-check",
        instruction,
    ])

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=project_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as e:
        return 0

    full_output = []

    assert proc.stdout is not None
    for line in proc.stdout:
        print(line, end="")
        full_output.append(line)

    returncode = proc.wait()

    if returncode != 0:
        return 0

    output_text = "".join(full_output)
    tokens = extract_tokens_used(output_text)

    return tokens if tokens is not None else 0


def exec_claude(inputfile, outputfile):
    """在 SERVERFILES 中调用 Claude Code，按进程退出码返回是否成功。"""
    instruction = (
        f"处理'{inputfile}'里的请求（UTF-8格式文本），结果文本输出到'{outputfile}'。"
        "如果需要输出文档或图片，那么文件名为以花括号包裹的UUID4字符串加扩展名，"
        "存放到当前目录下。绝对不允许列出当前目录下的所有项目。使用UTF-8。"
    )

    cmd = [
        "claude",
        "--dangerously-skip-permissions",
        "--output-format",
        "text",
        "-p",
        instruction,
    ]

    # Claude Code 使用环境变量禁用自动更新。
    env = os.environ.copy()
    env["DISABLE_AUTOUPDATER"] = "1"

    try:
        proc = subprocess.Popen(
            cmd,
            cwd="SERVERFILES",
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError:
        return False

    with proc:
        for line in proc.stdout:
            print(line, end="", flush=True)

    return proc.returncode == 0


def exec_grok(inputfile, outputfile):
    instruction = (
        f"处理'{inputfile}'里的请求（UTF-8格式文本），结果文本输出到'{outputfile}'。"
        "如果需要输出文档或图片，那么文件名为以花括号包裹的UUID4字符串加扩展名，"
        "存放到当前目录下。绝对不允许列出当前目录下的所有项目。使用UTF-8。"
    )

    cmd = [
        "grok",
        "--no-auto-update",
        "--always-approve",
        "--output-format",
        "plain",
    ]
    cmd.extend(["-p", instruction])

    try:
        proc = subprocess.Popen(
            cmd,
            cwd="SERVERFILES",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError:
        return False

    for line in proc.stdout:
        print(line, end="")

    return proc.wait() == 0

def extract_tokens_used(text):
    """
    从文本中查找 'tokens used' 后的数字（允许逗号分隔），返回整数。
    例如: "tokens used\n61,887" -> 61887
    """

    # 检查模型容量已满的情况（不区分大小写）
    if 'selected model is at capacity.' in text.lower():
        return None
    
    # 匹配模式：tokens used 后面可能紧跟换行，然后是数字（可能含逗号）
    match = re.search(r'tokens used\s*[\r\n]+\s*([\d,]+)', text, re.IGNORECASE)
    if match:
        number_str = match.group(1)
        # 移除逗号，转为整数
        return int(number_str.replace(',', ''))
    # 尝试另一种简单模式：同一行内的 "tokens used: 61,887" 或 "tokens used 61887"
    match = re.search(r'tokens used[:\s]+([\d,]+)', text, re.IGNORECASE)
    if match:
        number_str = match.group(1)
        return int(number_str.replace(',', ''))
    return None


def CallCodex(prompt,workflow):
    result = ""
    try:
        inputfile = "{" + str(uuid.uuid4()) + "}.txt" 
        with open(f"SERVERFILES/{inputfile}", "w", encoding='utf-8') as f:
            f.write(prompt)
        outputfile = "{" + str(uuid.uuid4()) + "}.txt" 
        workflow.data["tempfiles"].append(f"SERVERFILES/{inputfile}")
        workflow.data["tempfiles"].append(f"SERVERFILES/{outputfile}")
        tokens_used = exec_codex(inputfile, outputfile)
        if tokens_used > 0:
            if os.path.exists(f"SERVERFILES/{outputfile}"):
                with open(f"SERVERFILES/{outputfile}", "r", encoding="utf-8") as f:
                    result = f.read()
        else:
            if exec_grok(inputfile, outputfile):
                if os.path.exists(f"SERVERFILES/{outputfile}"):
                    with open(f"SERVERFILES/{outputfile}", "r", encoding="utf-8") as f:
                        result = f.read()
    except:
        pass
    return result



def detect_encoding(file_path):
    with open(file_path, 'rb') as file:
        raw_data = file.read()
    result = chardet.detect(raw_data)
    return result['encoding']

def read_file(file_path):
    with open(file_path, 'r', encoding="utf-8") as file:
        return file.read()


IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp', '.ico'}

def is_image_filename(filename: str) -> bool:
    """判断文件名是否为图片文件（基于扩展名）"""
    ext = os.path.splitext(filename)[1].lower()  # 获取扩展名并转小写
    return ext in IMAGE_EXTENSIONS

@task
def task_agent(
    workflow_data: dict,
    node_id: str,
):
    workflow = Workflow(workflow_data)
    claw = workflow.get_node_field_value(node_id, "APIKey")
    if claw == None:
        claw = ""
    taskdesc = workflow.get_node_field_value(node_id, "任务描述")
    outtype = workflow.get_node_field_value(node_id, "输出类型")
    if outtype == "" or outtype == None:
        outtype = ""
    file = workflow.get_node_field_value(node_id, "文件")
    if file == "" or file == None:
        filedesc = ""
    else:
        workflow.data["tempfiles"].append("SERVERFILES/" + file)
        filedesc = f'以及文件"{file}"'

    skills = ""
    if claw != "":
        skillcsv = asyncio.run(send_ws_message(claw, "技能表"))
        if skillcsv != "":
            prompt = f'''{skillcsv}
---
上面是可用的技能csv表，下面是我的请求，请选择技能来满足我的要求，只返回选择后的逗号分隔的baseDir，如果没有匹配的技能则返回空字符串，不要其它说明文字。
---
{taskdesc}'''
            baseDirs = CallCodex(prompt,workflow)
            if baseDirs == "空字符串":
                baseDirs = ""
            baseDirs = baseDirs.strip()
            baseDirs = baseDirs.strip('"\'')
            if baseDirs != "":
                skills = asyncio.run(send_ws_message(claw, "技能信息," + baseDirs))

                pattern = r'\{[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}\}\.\w+'
                matches = re.findall(pattern, skills)  # 返回所有匹配的文件名列表
                matches = set(matches)
                for filename in matches:
                    if not os.path.exists("SERVERFILES/" + filename):
                        asyncio.run(send_ws_message(claw, "技能文件," + filename, timeout=1000))

    result = ""
    try:
        prompt = f'''"""{taskdesc}"""
根据上面三重引号内的要求{filedesc}，得出结果（过程中不需要人工确认）。'''
        if outtype == "文本":
            prompt = prompt + "如果结果是Markdown格式文本并且其中包含图片或文件，那么图片或文件链接是http://127.0.0.1:3130/download/图片或文件名，图片或文件名为以花括号包裹的UUID4字符串加扩展名，图片或文件链接要按Markdown链接语法。"
        if skills != "":
            prompt = prompt + "\n===\n" +skills
        inputfile = "{" + str(uuid.uuid4()) + "}.txt" 
        with open(f"SERVERFILES/{inputfile}", "w", encoding='utf-8') as f:
            f.write(prompt)
        outputfile = "{" + str(uuid.uuid4()) + "}.txt" 
        workflow.data["tempfiles"].append(f"SERVERFILES/{inputfile}")
        workflow.data["tempfiles"].append(f"SERVERFILES/{outputfile}")
        tokens_used = exec_codex(inputfile, outputfile)
        if tokens_used > 0:
            if os.path.exists(f"SERVERFILES/{outputfile}"):
                with open(f"SERVERFILES/{outputfile}", "r", encoding="utf-8") as f:
                    result = f.read()
        else:
            if exec_grok(inputfile, outputfile):
                if os.path.exists(f"SERVERFILES/{outputfile}"):
                    with open(f"SERVERFILES/{outputfile}", "r", encoding="utf-8") as f:
                        result = f.read()
    except:
        pass

    # 正则匹配GUID格式的文件名：{8-4-4-4-12}.扩展名
    pattern = r'\{[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}\}\.\w+'
    matches = re.findall(pattern, result)  # 返回所有匹配的文件名列表
    matches = set(matches)
    for filename in matches:
        if outtype != "文本":
            if is_image_filename(filename):
                output = "Image://" + filename
            else:
                output = "File://" + filename
            result = output
        workflow.data["tempfiles"].append("SERVERFILES/" + filename)

    workflow.update_node_field_value(node_id, "输出", result)
    if (workflow.nodesout.get(node_id) == False):
        if workflow_data["answered"]:
            Answer("\n", workflow_data["wid"], workflow_data["streamrunid"])
        else:
            workflow_data["answered"] = True
        Answer(result, workflow_data["wid"], workflow_data["streamrunid"])
    return workflow.data



@task
def code_interpreter(
    workflow_data: dict,
    node_id: str,
):
    workflow = Workflow(workflow_data)
    claw = workflow.get_node_field_value(node_id, "APIKey")
    if claw == None:
        claw = ""

    fields = workflow.get_node_fields(node_id)
    for field in fields:
        if field in ("输出"):
            continue
        if workflow.get_node_field_value(node_id, field) == "BranchSkip":
            workflow.update_node_field_value(node_id, "输出", "BranchSkip")
            return workflow.data

    codedesc = workflow.get_node_field_value(node_id, "自然语言")
    pure_code = ""
    resultdesc = ""
    outfile = ""
    filein = ""
    fileout = ""
    cache = workflow.get_node_field_value(node_id, "使用缓存")
    show = workflow.get_node_field_value(node_id, "显示代码")
    if cache == "是":
        hash = get_hash(codedesc)
        try:
            pure_code = read_file("CACHE/cicode_" + hash + ".txt")
        except Exception:
            pass
        try:
            resultdesc = read_file("CACHE/cidesc_" + hash + ".txt")
        except Exception:
            pass
        try:
            filein = read_file("CACHE/cifilein_" + hash + ".txt")
        except Exception:
            pass
        try:
            fileout = read_file("CACHE/cifileout_" + hash + ".txt")
            if fileout != "":
                outfile = "是"
        except Exception:
            pass
    if pure_code != "":
        file = workflow.get_node_field_value(node_id, "文件")
        if not os.path.exists("SERVERFILES/" + file):
            file = ""
        if file != "" and file != None:
            workflow.data["tempfiles"].append("SERVERFILES/" + file)
            file = os.path.basename(file)
            shutil.copy("SERVERFILES/" + file, "SERVERFILES/" + str(workflow_data["wid"]) + "/" + file)
            pure_code = pure_code.replace(filein, file)
        if fileout != "":
            newfileout = "{" + str(uuid.uuid4()) + "}"
            pure_code = pure_code.replace(fileout, newfileout)
        result = run_code(pure_code, workflow_data["wid"])
        if result.find("Timeout error:") != -1:
            result = ""
        if result.find("Traceback ") != -1:
            result = ""
        if resultdesc == "" and show == "是":
            prompt = f'''我的请求：
"""{codedesc}"""
你的代码：
```Python
{pure_code}
```
请根据上面的我的请求以及你的代码，为我阐述你是如何实现我的请求的。'''
            resultdesc = CallCodex(prompt,workflow)
    else:
        prompt = f'''"""{codedesc}"""
上面这个需求是否输出文件或图表或者处理图片？只回答是、否。'''
        outfile = CallCodex(prompt,workflow)
        filein = ""
        fileout = ""

        file = workflow.get_node_field_value(node_id, "文件")
        if not os.path.exists("SERVERFILES/" + file):
            file = ""
        if file == "" or file == None:
            filedesc = ""
        else:
            workflow.data["tempfiles"].append("SERVERFILES/" + file)
            file = os.path.basename(file)
            shutil.copy("SERVERFILES/" + file, "SERVERFILES/" + str(workflow_data["wid"]) + "/" + file)
            filein = file
            filedesc = f'以及文件"{filein}"'
        i = 0
        while i < 2:
            i += 1
            if "是" in outfile:
                fileout = "{" + str(uuid.uuid4()) + "}"
                prompt = f'''"""{codedesc}"""
根据上面三重引号内的代码要求{filedesc}，编写运行在Windows上的Python 3的程序来满足要求。程序只生成一个文档或图片。文件名为大括号包裹的"{fileout}"+后缀，存放在当前目录下。程序最后print这个文件名。要求支持中文字体。不要显示窗口。不能import os。不能import shutil。不能import sys。
只需要输出用```包含的代码，绝对不要写其它非代码内容。'''
            else:
                prompt = f'''"""{codedesc}"""
根据上面三重引号内的代码要求{filedesc}，编写运行在Windows上的Python 3的程序来满足要求。程序最后print结果文本。要求支持中文字体。不要显示窗口。不能import os。不能import shutil。不能import sys。不能写文件。
只需要输出用```包含的代码，绝对不要写其它非代码内容。'''

            pure_code = ""
            errdesc = ""
            result = ""
            j = 0
            while j < 2:
                j += 1 

                errdesc = ""
                code = CallCodex(prompt,workflow)
                #pattern = r"```.*?\n(.*?)\n```"
                pattern = r"^\s*```(?:[^\n]*\n)?(.*?)(?:\n)?```\s*$"
                code_block_search = re.search(pattern, code, re.DOTALL)

                if code_block_search:
                    pure_code = code_block_search.group(1)
                else:
                    pure_code = code

                allowed_modules = ['music21','mido','requests','skimage','moviepy','abc','copy','dataclasses','typing','zipfile','io','pyaudio','pygame','seaborn','functools','gzip','xml.etree.ElementTree','enum','collections','itertools','csv','json','datetime','pytesseract','pyzbar','xmindparser','pptx','speech_recognition','lxml','skimage','matplotlib','sympy','imageio','wordcloud','PIL','hashlib','string','math','random','cv2','base64','uuid','qrcode','re','BeautifulSoup4','pandas','numpy','scipy','scikit-learn','openpyxl','jieba','mammoth','pypdf','openpyxl','python-pptx','python-docx','htmldocx','markdown2']
                if illegal_import(pure_code, allowed_modules):
                    errdesc = "Error"
                    pure_code = ""
                    break

                result = run_code(pure_code, workflow_data["wid"])
                if result.find("Timeout error:") != -1:
                    result = ""
                    break
                if result.find("Traceback ") != -1:
                    errdesc = result
                    result = ""
                    prompt = f'''"""{pure_code}"""
上面的代码报错
""""{errdesc}""
请根据错误信息检查一下代码，并返回正确的代码。只输出修正后的代码，绝对不要写其它非代码内容。上面的代码是根据下面的代码要求编写的：{codedesc}'''
                if result != "":
                    break
            if errdesc == "":
                break

        resultdesc = ""
        if pure_code != "" and show == "是":
            prompt = f'''我的请求：
"""{codedesc}"""
你的代码：
```Python
{pure_code}
```
请根据上面的我的请求以及你的代码，为我阐述你是如何实现我的请求的。'''
            resultdesc = CallCodex(prompt,workflow)
        if pure_code != "" and result != "":
            hash = get_hash(codedesc)
            try:
                with open("CACHE/cicode_" + hash + ".txt", "w", encoding='utf-8') as file:
                    file.write(pure_code)
                with open("CACHE/cidesc_" + hash + ".txt", "w", encoding='utf-8') as file:
                    file.write(resultdesc)
                with open("CACHE/cifilein_" + hash + ".txt", "w", encoding='utf-8') as file:
                    file.write(filein)
                with open("CACHE/cifileout_" + hash + ".txt", "w", encoding='utf-8') as file:
                    file.write(fileout)
            except Exception:
                pass

    if "是" in outfile:
        # 正则匹配GUID格式的文件名：{8-4-4-4-12}.扩展名
        pattern = r'\{[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}\}\.\w+'
        match = re.search(pattern, result)
        if match:
            result = match.group()
        else:
            result = ""

        #lines = result.split('\n')
        #result = ""
        #for line in reversed(lines):
        #    if line.strip() != '':
        #        result = line.strip()
        #        break
        if result != "":
            basename = os.path.basename(result)
            try:
                shutil.copy("SERVERFILES/" + str(workflow_data["wid"]) + "/" + basename, "SERVERFILES/" + basename)

                filename, extension = os.path.splitext(basename)
                if extension == ".png" or extension == ".jpg" or extension == ".gif":
                    result = "Image://" + filename + extension
                else:
                    result = "File://输出" + extension + filename + extension
            except Exception:
                pass
            workflow.data["tempfiles"].append("SERVERFILES/" + basename)
    workflow.update_node_field_value(node_id, "输出", result)
    if pure_code == "" or result == "":
        return workflow.data
    file_name = "{" + str(uuid.uuid4()) + "}.py"
    output_folder = Path("SERVERFILES")
    local_file = output_folder / file_name
    with open(local_file, "wb") as txt_file:
        txt_file.write(pure_code.encode("utf-8"))
    workflow.update_node_field_value(node_id, "代码", file_name)
    if (workflow.nodesout.get(node_id) == False):
        if workflow_data["answered"]:
            Answer("\n", workflow_data["wid"], workflow_data["streamrunid"])
        else:
            workflow_data["answered"] = True
        Answer(result, workflow_data["wid"], workflow_data["streamrunid"])
        if show == "是":
            Answer("\n", workflow_data["wid"], workflow_data["streamrunid"])
            output = "File://代码.py" + file_name
            Answer(output, workflow_data["wid"], workflow_data["streamrunid"])
            if resultdesc != "":
                Answer("\n", workflow_data["wid"], workflow_data["streamrunid"])
                Answer(resultdesc, workflow_data["wid"], workflow_data["streamrunid"])
    return workflow.data



