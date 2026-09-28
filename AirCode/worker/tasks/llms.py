from typing import Union
import asyncio
import os
import shutil
import uuid
import re

from utilities.ask_answer import Answer
from utilities.workflow import Workflow
from worker.tasks import task

import subprocess
from types import SimpleNamespace


def gen_image(inputfile, outputfile):
    instruction = f"根据文件'{inputfile}'里的Prompt（UTF-8格式文本），生成图片输出到'{outputfile}'。"
    ps_command = f'codex exec --skip-git-repo-check "{instruction}"'

    cmd = [
        "pwsh",
        "-NoProfile",
        "-Command",
        ps_command
    ]

    try:
        # 使用 Popen 以便实时打印输出并同时收集全部内容
        proc = subprocess.Popen(
            cmd,
            cwd='SERVERFILES',
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            errors='replace'
        )
    except FileNotFoundError:
        return False

    for line in proc.stdout:
        print(line, end='')       # 实时输出到终端

    # 等待进程结束
    returncode = proc.wait()

    if returncode != 0:
        return False

    return True



def edit_image(imagefile, inputfile, outputfile):
    if imagefile.lower().endswith(".zip"):
        instruction = f"根据文件'{inputfile}'里的Prompt（UTF-8格式文本），处理压缩包'{imagefile}'里的图片，结果输出到'{outputfile}'。"
    else:
        instruction = f"根据文件'{inputfile}'里的Prompt（UTF-8格式文本），编辑图片'{imagefile}'，结果输出到'{outputfile}'。"
    ps_command = f'codex exec --skip-git-repo-check "{instruction}"'

    cmd = [
        "pwsh",
        "-NoProfile",
        "-Command",
        ps_command
    ]

    try:
        # 使用 Popen 以便实时打印输出并同时收集全部内容
        proc = subprocess.Popen(
            cmd,
            cwd='SERVERFILES',
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            errors='replace'
        )
    except FileNotFoundError:
        return False

    for line in proc.stdout:
        print(line, end='')       # 实时输出到终端

    # 等待进程结束
    returncode = proc.wait()

    if returncode != 0:
        return False

    return True


@task
def image_ai(
    workflow_data: dict,
    node_id: str,
):
    workflow = Workflow(workflow_data)
    level = workflow.get_node_field_value(node_id, "Level")
    prompt = workflow.get_node_field_value(node_id, "Prompt")

    fields = workflow.get_node_fields(node_id)
    for field in fields:
        if field in ("输出"):
            continue
        if workflow.get_node_field_value(node_id, field) == "BranchSkip":
            workflow.update_node_field_value(node_id, "输出", "BranchSkip")
            return workflow.data

    input_prompt: Union[str, list] = workflow.get_node_field_value(node_id, "Prompt")
    if isinstance(input_prompt, str):
        prompts = [input_prompt]
    elif isinstance(input_prompt, list):
        prompts = input_prompt

    init_image = workflow.get_node_field_value(node_id, "Init Image")
    if init_image == None:
        init_image = workflow.get_node_field_value(node_id, "init_image")
    if init_image == None:
        init_image = ""
    results = []
    gened = False
    for prompt in prompts:
        inputfile = "{" + str(uuid.uuid4()) + "}.txt" 
        with open(f"SERVERFILES/{inputfile}", "w", encoding='utf-8') as f:
            f.write(prompt)
        outputfile = "{" + str(uuid.uuid4()) + "}.jpg" 
        workflow.data["tempfiles"].append(f"SERVERFILES/{inputfile}")
        workflow.data["tempfiles"].append(f"SERVERFILES/{outputfile}")
        if init_image == "":
            gened = gen_image(inputfile, outputfile)
        else:
            init_image = init_image.replace('Image://', 'SERVERFILES/', 1) if init_image.startswith('Image://') else init_image
            init_image = init_image.replace('File://', 'SERVERFILES/', 1) if init_image.startswith('File://') else init_image
            if init_image.find("SERVERFILES") == -1:
                init_image = "SERVERFILES/" + init_image
            workflow.data["tempfiles"].append(init_image)
            gened = edit_image(init_image, inputfile, outputfile)
        if gened:
            if os.path.exists(f"SERVERFILES/{outputfile}"):
                results.append("Image://" + outputfile)
                if (workflow.nodesout.get(node_id) == False):
                    if workflow_data["answered"]:
                        Answer("\n", workflow_data["wid"], workflow_data["streamrunid"])
                    else:
                        workflow_data["answered"] = True
                    Answer("Image://" + outputfile, workflow_data["wid"], workflow_data["streamrunid"])
            else:
                gened = False
                break
        else:
            break
    if gened:
        output = results[0] if isinstance(input_prompt, str) else results
        workflow.update_node_field_value(node_id, "输出", output)
        return workflow.data



async def ltask(workflow,node_id,responses,i,prompt):
    inputfile = "{" + str(uuid.uuid4()) + "}.txt" 
    with open(f"SERVERFILES/{inputfile}", "w", encoding='utf-8') as f:
        f.write(prompt)
    outputfile = "{" + str(uuid.uuid4()) + "}.txt" 
    workflow.data["tempfiles"].append(f"SERVERFILES/{inputfile}")
    workflow.data["tempfiles"].append(f"SERVERFILES/{outputfile}")
    tokens_used = run_codex(inputfile, outputfile)
    if tokens_used > 0:
        if os.path.exists(f"SERVERFILES/{outputfile}"):
            with open(f"SERVERFILES/{outputfile}", "r", encoding="utf-8") as f:
                responses[i] = SimpleNamespace(output_text=f.read().rstrip('\n'))
            return
    else:
        if run_grok(inputfile, outputfile):
            if os.path.exists(f"SERVERFILES/{outputfile}"):
                with open(f"SERVERFILES/{outputfile}", "r", encoding="utf-8") as f:
                    responses[i] = SimpleNamespace(output_text=f.read().rstrip('\n'))
                return



def read_ximage(imagefile, inputfile, outputfile):
    instruction = f"根据文件'{inputfile}'里的Prompt（UTF-8格式文本），理解图片'{imagefile}'，结果输出到'{outputfile}'。"

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


def read_image(imagefile, inputfile, outputfile):
    instruction = f"根据文件'{inputfile}'里的Prompt（UTF-8格式文本），理解图片'{imagefile}'，结果输出到'{outputfile}'。"
    ps_command = f'codex exec --skip-git-repo-check "{instruction}"'

    cmd = [
        "pwsh",
        "-NoProfile",
        "-Command",
        ps_command
    ]

    try:
        # 使用 Popen 以便实时打印输出并同时收集全部内容
        proc = subprocess.Popen(
            cmd,
            cwd='SERVERFILES',
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            errors='replace'
        )
    except FileNotFoundError:
        return 0

    # 实时打印输出，并保存所有行以便后续解析
    full_output = []
    for line in proc.stdout:
        print(line, end='')       # 实时输出到终端
        full_output.append(line)

    # 等待进程结束
    returncode = proc.wait()

    if returncode != 0:
        return 0

    # 提取 tokens used 数值
    output_text = ''.join(full_output)
    tokens = extract_tokens_used(output_text)
    if tokens is None:
        tokens = 0
    return tokens


@task
def l_ai(
    workflow_data: dict,
    node_id: str,
):
    workflow = Workflow(workflow_data)

    fields = workflow.get_node_fields(node_id)
    for field in fields:
        if field in ("输出"):
            continue
        if workflow.get_node_field_value(node_id, field) == "BranchSkip":
            workflow.update_node_field_value(node_id, "输出", "BranchSkip")
            return workflow.data

    input_image = workflow.get_node_field_value(node_id, "Image")
    if input_image == None:
        input_image = ""
    if input_image != "":
        if isinstance(input_image, str):
            parts = [x.strip() for x in re.split(r'[;,]', input_image) if x.strip()]
            input_image = parts if len(parts) > 1 else parts[0]
        if isinstance(input_image, str):
            images = [input_image]
        elif isinstance(input_image, list):
            images = input_image
        results = []
        for image in images:
            image = image.replace('Image://', 'SERVERFILES/', 1) if image.startswith('Image://') else image
            image = image.replace('File://', 'SERVERFILES/', 1) if image.startswith('File://') else image
            if image.find("SERVERFILES") == -1:
                image = "SERVERFILES/" + image
            workflow.data["tempfiles"].append(image)
            prompt = workflow.get_node_field_value(node_id, "Prompt")

            inputfile = "{" + str(uuid.uuid4()) + "}.txt" 
            with open(f"SERVERFILES/{inputfile}", "w", encoding='utf-8') as f:
                f.write(prompt)
            outputfile = "{" + str(uuid.uuid4()) + "}.txt" 
            workflow.data["tempfiles"].append(f"SERVERFILES/{inputfile}")
            workflow.data["tempfiles"].append(f"SERVERFILES/{outputfile}")
            tokens_used = read_image(image, inputfile, outputfile)
            if tokens_used > 0:
                if os.path.exists(f"SERVERFILES/{outputfile}"):
                    with open(f"SERVERFILES/{outputfile}", "r", encoding="utf-8") as f:
                        output=f.read()
            else:
                if read_ximage(image, inputfile, outputfile):
                    if os.path.exists(f"SERVERFILES/{outputfile}"):
                        with open(f"SERVERFILES/{outputfile}", "r", encoding="utf-8") as f:
                            output=f.read()

            results.append(output)
        result = results if isinstance(input_image, list) else results[0]
        workflow.update_node_field_value(node_id, "输出", result)
        if (workflow.nodesout.get(node_id) == False):
            if workflow_data["answered"]:
                Answer("\n", workflow_data["wid"], workflow_data["streamrunid"])
            else:
                workflow_data["answered"] = True
            Answer(result, workflow_data["wid"], workflow_data["streamrunid"])
        return workflow.data

    input_prompt: Union[str, list] = workflow.get_node_field_value(node_id, "Prompt")

    if isinstance(input_prompt, str):
        prompts = [input_prompt]
    elif isinstance(input_prompt, list):
        prompts = input_prompt

    nodeout = workflow.nodesout.get(node_id)

    results = []
    if (nodeout == False):
        pass
    else:
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            # 当前线程没有事件循环，创建一个新的
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        tasks = []
        responses = {}
        i = 0
        for prompt in prompts:
            tasks.append(loop.create_task(ltask(workflow,node_id,responses,i,prompt)))
            i += 1
        if tasks:
            loop.run_until_complete(asyncio.wait(tasks))
        i = 0
        for prompt in prompts:
            try:
                if hasattr(responses[i], 'output_text'):
                    result = responses[i].output_text
                else:
                    result = responses[i].choices[0].message.content
                result = result.encode('gbk',errors='ignore').decode('gbk').encode('utf-8').decode('utf-8')
            except Exception:
                result = ""
            results.append(result)
            i += 1

    output = results[0] if isinstance(input_prompt, str) else results
    workflow.update_node_field_value(node_id, "输出", output)
    return workflow.data



def run_claude(inputfile, outputfile):
    """在 SERVERFILES 中调用 Claude Code，按退出码返回是否成功。"""
    instruction = (
        f"处理'{inputfile}'里的请求（UTF-8格式文本），输出到'{outputfile}'。"
        "绝对不允许列出当前目录下的所有项目。使用UTF-8。"
    )

    cmd = [
        "claude",
        "--dangerously-skip-permissions",
        "--output-format",
        "text",
        "-p",
        instruction,
    ]

    # Claude Code 通过环境变量禁用自动更新。
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


def run_grok(inputfile, outputfile):
    instruction = f"处理'{inputfile}'里的请求（UTF-8格式文本），输出到'{outputfile}'。绝对不允许列出当前目录下的所有项目。使用UTF-8。"

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


def run_codex(inputfile, outputfile):
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
        f"用补丁方式创建文件并输出到'{outputfile}'。"
        "绝对不允许列出当前目录下的所有项目。使用UTF-8。"
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
    except (FileNotFoundError, OSError):
        return 0

    full_output = []

    if proc.stdout is not None:
        for line in proc.stdout:
            print(line, end="")
            full_output.append(line)

    returncode = proc.wait()

    if returncode != 0:
        return 0

    output_text = "".join(full_output)
    tokens = extract_tokens_used(output_text)

    return tokens if tokens is not None else 0


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

