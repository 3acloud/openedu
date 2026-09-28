import sys
import subprocess
import importlib

def _ensure_dependencies():
    dependencies = [
        ("flask", "flask"),
        ("requests", "requests"),
        ("Flask-CORS", "flask_cors"),
        ("websockets", "websockets"),
        ("PyYAML", "yaml"),
        ("duckdb", "duckdb"),
        ("pandas", "pandas")
    ]
    
    for pkg, mod in dependencies:
        try:
            importlib.import_module(mod)
        except ImportError:
            print(f"Missing module '{mod}', installing package '{pkg}'...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])
            importlib.invalidate_caches()

_ensure_dependencies()

def set_terminal_title(title):
    """设置终端窗口的标题"""
    if sys.platform.startswith('win'):
        import ctypes
        ctypes.windll.kernel32.SetConsoleTitleW(title)
    else:
        sys.stdout.write(f"\x1b]0;{title}\x07")
        sys.stdout.flush()

from flask import Flask, request, Response, send_from_directory, abort
import os
import re
import requests
import hashlib
from urllib.parse import quote
import json
import io
from urllib.parse import unquote
from flask_cors import CORS
import csv
import shutil
from pathlib import Path, PurePosixPath
import base64
import mimetypes
import uuid
import asyncio
import threading
import websockets
from http import HTTPStatus
from websockets.exceptions import InvalidHeader, InvalidUpgrade
from websockets.headers import parse_connection, parse_upgrade
import yaml
import duckdb
from zipfile import ZipFile

# 基础路径配置
base_path = Path.cwd() / "files"
base_app = Path.cwd() / "apps"
base_skill = Path.cwd() / "skills"

app = Flask(__name__)
CORS(app)  # 允许跨域请求

askstream = {}
clientbaseid = {}
otp_store = {}

skills_csv = {}

# ----------------------
# WebSocket 全局变量
# ----------------------
ws_clients = {}  # apiKey -> WebSocket 连接


set_terminal_title('AirThink')


def parse_markdown(content):
    """从 Markdown 内容中提取 YAML frontmatter 和正文；
    若无 frontmatter，则尝试从正文提取 name 和 description 构造 frontmatter。
    """
    # 尝试匹配 YAML frontmatter
    match = re.match(r'^---\r?\n([\s\S]*?)\r?\n---\r?\n', content)
    if match:
        try:
            frontmatter = yaml.safe_load(match.group(1))
            body = content[match.end():]
            return frontmatter, body
        except Exception as e:
            print('YAML 解析失败:', e)
            return None, content
    else:
        # 无 frontmatter，从正文提取 name 和 description
        frontmatter = {}
        lines = content.splitlines(keepends=True)

        # 寻找第一个一级标题（# 开头）
        title_line_idx = None
        for i, line in enumerate(lines):
            if line.lstrip().startswith('# '):
                title_line_idx = i
                break

        if title_line_idx is not None:
            title_line = lines[title_line_idx]
            # 提取标题文本（去掉 # 和首尾空白）
            name = re.sub(r'^#\s+', '', title_line).strip()
            frontmatter['name'] = name

            fst = True
            # 在标题之后寻找第一段非空文本作为描述
            description_lines = []
            for j in range(title_line_idx + 1, len(lines)):
                line = lines[j].strip()
                if not line:
                    # 空行可能结束段落
                    if description_lines:
                        break
                else:
                    # 忽略其他标题或标记
                    if line.startswith('#'):
                        if fst:
                            fst = False
                            continue
                        break
                    description_lines.append(line)

            if description_lines:
                # 将多行合并为一段（用空格连接）
                description = ' '.join(description_lines)
                frontmatter['description'] = description

        # 正文保持原样
        return frontmatter, content

def get_skill_content(base_dir):
    """获取指定技能目录下的正文内容（Markdown 说明）以及所有代码文件"""
    skill_dir = base_skill / base_dir
    skill_md_candidates = list(Path(skill_dir).rglob("SKILL.md"))
    if skill_md_candidates:
        skill_path = skill_md_candidates[0]
    else:
        return ''

    skill_content = ''
    try:
        with open(skill_path, 'r', encoding='utf-8') as f:
            content = f.read()
            _, body = parse_markdown(content)
            skill_content = body.strip()
    except FileNotFoundError:
        print(f"警告：文件不存在: {skill_path}")
    except Exception as e:
        print(f"读取文件失败 {skill_path}: {e}")

    extensions = ('.py', '.js', '.mjs', '.sh', '.md')
    code_blocks = []

    if os.path.isdir(skill_dir):
        for root_dir, _, files in os.walk(skill_dir):
            for file in files:
                if file.endswith(extensions):
                    full_path = os.path.join(root_dir, file)
                    if os.path.abspath(full_path) == os.path.abspath(skill_path):
                        continue
                    
                    rel_path = os.path.relpath(full_path, skill_dir)
                    try:
                        with open(full_path, 'r', encoding='utf-8') as f:
                            file_data = f.read().strip()
                            block = f"```\n# {rel_path}\n{file_data}\n```"
                            code_blocks.append(block)
                    except Exception as e:
                        print(f"读取文件失败 {full_path}: {e}")

    all_parts = [skill_content] + code_blocks
    return "\n\n".join([p for p in all_parts if p])

def escape_csv_field(val):
    if val is None:
        return ''
    string_val = str(val)
    if re.search(r'[,"\n\r]', string_val):
        return '"' + string_val.replace('"', '""') + '"'
    return string_val

def array_to_csv(data):
    if not data:
        return ''
    headers = ['baseDir', 'name', 'description', 'metadata']
    rows = [",".join(headers)]
    for item in data:
        metadata_str = json.dumps(item['metadata']) if item.get('metadata') else ''
        row = [
            escape_csv_field(item.get('baseDir')),
            escape_csv_field(item.get('name')),
            escape_csv_field(item.get('description')),
            escape_csv_field(metadata_str)
        ]
        rows.append(",".join(row))
    return "\n".join(rows)

def scan_skills(basename):
    """扫描用户的 skills 目录，返回技能信息数组"""
    results = []

    skills = []
    with open(base_app / basename /'skill.json', 'r', encoding='utf-8') as f:
        skills = json.load(f)

    for skill in skills:
        skill_name = skill['skill_name']
        base_dir = base_skill / f"{skill_name}"
        if os.path.isdir(base_dir):
            skill_md_candidates = list(Path(base_dir).rglob("SKILL.md"))
            if skill_md_candidates:
                skill_path = skill_md_candidates[0]
                try:
                    with open(skill_path, 'r', encoding='utf-8') as f:
                        frontmatter, body = parse_markdown(f.read())
                        if frontmatter and (frontmatter.get('name') or frontmatter.get('title')) and frontmatter.get('description'):
                            if frontmatter.get('name'):
                                name = frontmatter.get('name').replace("/", "-")
                            else:
                                name = frontmatter.get('title').replace("/", "-")
                            results.append({
                                'baseDir': skill_name,
                                'name': name,
                                'description': frontmatter.get('description'),
                                'metadata': frontmatter.get('metadata')
                            })
                except FileNotFoundError:
                    pass
                except Exception as e:
                    print(f"读取文件失败 {skill_path}: {e}")

    return results



# ----------------------
# 通用工具函数
# ----------------------

def extract_urls(text):
    # 这是一个比较通用的正则表达式，匹配 http/https 开头或 www 开头的网址
    # 它会匹配直到遇到空白字符为止
    pattern = r'(?:(?:https?://)|(?:www\.))[^\s]+'
    
    urls = re.findall(pattern, text)
    
    # 【精准化处理】
    # 正则往往会将句尾的标点（如 "baidu.com."）也匹配进去
    # 我们需要清洗掉末尾的常见标点符号
    clean_urls = []
    for url in urls:
        # strip() 去除首尾的标点符号：句号、逗号、分号、问号、感叹号、括号等
        clean_url = url.strip('.,;?!:()[]""\'’‘“”。，！？：；')
        if clean_url:
            clean_urls.append(clean_url)
            
    return clean_urls


def long_guid():
    return '{' + str(uuid.uuid4()) + '}'

def short_guid(length=16):
    """
    生成指定长度的短 GUID
    length: 期望的长度（默认16位）
    """
    # 生成 UUID 并哈希
    uuid_str = str(uuid.uuid4())
    hash_obj = hashlib.md5(uuid_str.encode())
    
    # 取哈希值的前 length 位
    return hash_obj.hexdigest()[:length]

def format_for_json(text):
    text = json.dumps(text, ensure_ascii=False)[1:-1] 
    return text

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


@app.route('/')
@app.route('/<path:filename>')
def serve_file(filename=''):
    if filename == '':
        filename = 'index.html'

    base_path = Path(base_app)

    if filename.count('_') == 2:
        filename = filename.rsplit('_', 1)[0] + '/' + filename
    else:
        # index.html 不存在时，使用 base_app 及其子目录中的第一个 .html 文件
        if filename == 'index.html' and not (base_path / filename).is_file():
            first_html = next(
                (path for path in base_path.rglob('*.html') if path.is_file()),
                None
            )
            if first_html is None:
                  abort(404)

            # send_from_directory 需要相对于 base_app 的路径
            filename = first_html.relative_to(base_path).as_posix()

    try:
        return send_from_directory(base_app, filename)
    except FileNotFoundError:
        abort(404)


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

@app.route('/download/<filename>')
def download(filename):
    try:
        return send_from_directory(
            base_path,
            filename,
            as_attachment=True,
            download_name=filename
        )
    except FileNotFoundError:
        abort(404)

def get_table_csv(request_data, request_payload, gBaseName):
    # 解析request_data，获取表名和字段信息
    tData = request_data
    pos = tData.find("/")
    
    if pos > 0:
        tTableName = tData[:pos]
        tViewName = tData[pos+1:]
    else:
        tTableName = tData
        tViewName = ""
    
    tData = tViewName
    pos = tData.find("/")
    
    if pos > 0:
        tViewName = tData[:pos]
        tFieldName = tData[pos+1:]
    else:
        tViewName = tData
        tFieldName = ""
    
    tData = tFieldName
    pos = tData.find("/")
    
    if pos > 0:
        tFieldName = tData[:pos]
        tChartType = tData[pos+1:]
    else:
        tFieldName = tData
        tChartType = ""
    
    # 处理字段列表（将中文逗号替换为英文逗号）
    tFields = request_payload.replace("，", ",")
    
    # 构建文件名
    filename = base_app / gBaseName / f"{gBaseName}_{tTableName}.csv"
    user_file = base_path / f"{gBaseName}_{tTableName}.csv"
    if user_file.exists():
        filename = user_file
    
    # 检查文件是否存在
    if not os.path.exists(filename):
        return ""
    
    try:
        # 读取CSV文件
        with open(filename, 'r', encoding='utf-8', newline='') as csvfile:
            reader = csv.reader(csvfile)
            
            # 读取标题行
            headers = next(reader, None)
            if headers is None:
                return ""  # 空文件
            
            # 如果tFields为空，返回所有字段
            if tFields.strip() == "":
                # 读取所有数据行
                rows = list(reader)
                # 转换为CSV字符串（不含标题行）
                result_lines = []
                for row in rows:
                    # 处理单元格值：如果以"ASK_"开头则置为空，并在前后加双引号
                    cleaned_row = [f'"{("" if val.startswith("ASK_") else val)}"' for val in row]
                    result_lines.append(','.join(cleaned_row))
                return '\n'.join(result_lines)
            else:
                # 分割字段列表，去除空格
                fields_list = [field.strip() for field in tFields.split(",") if field.strip()]
                
                # 确定请求的字段在标题中的索引位置
                field_indices = []
                for field in fields_list:
                    if field in headers:
                        idx = headers.index(field)
                        field_indices.append(idx)
                
                # 如果请求的字段都不存在，返回空数据
                if not field_indices:
                    return ""
                
                # 读取并筛选数据
                result_lines = []
                for row in reader:
                    # 只保留指定字段的数据，并处理"ASK_"开头的单元格
                    filtered_row = []
                    for i in field_indices:
                        val = row[i]
                        if val.startswith("ASK_"):
                            val = ''
                        if val.endswith('.md'):
                            file_path = base_path / val
                            if file_path.exists():
                                with open(file_path, 'r', encoding='utf-8') as f:
                                    val = f.read()
                        val = val.replace('"', '""')
                        # 在前后加双引号
                        filtered_row.append(f'"{val}"')
                    result_lines.append(','.join(filtered_row))
                
                return '\n'.join(result_lines)
                
    except Exception as e:
        return ""
    

def get_record_count(vData, gBaseName):
    # 解析vData，获取tTableName
    pos = vData.find("/")
    
    if pos > 0:
        tTableName = vData[:pos]
        tViewName = vData[pos+1:]
    else:
        tTableName = vData
        tViewName = ""
    
    # 构建文件名
    filename = base_app / gBaseName / f"{gBaseName}_{tTableName}.csv"
    user_file = base_path / f"{gBaseName}_{tTableName}.csv"
    if user_file.exists():
        filename = user_file
    
    # 检查文件是否存在
    if not os.path.exists(filename):
        return 0
    
    try:
        # 使用csv模块读取文件，更准确地计算记录数
        with open(filename, 'r', encoding='utf-8', newline='') as csvfile:
            reader = csv.reader(csvfile)
            
            # 跳过标题行（如果有）
            # 尝试读取第一行，如果文件为空则没有标题行
            try:
                header = next(reader)
                # 如果有标题行，从0开始计数
                record_count = 0
            except StopIteration:
                # 文件为空
                return 0
            
            # 统计剩余的行数
            record_count = sum(1 for row in reader)
            
            return record_count
            
    except Exception as e:
        return 0


def get_record_row(vData, vPayload, gBaseName):
    # 解析vPayload，获取tFieldName和tValue
    pos = vPayload.find("/")
    
    if pos > 0:
        tFieldName = vPayload[:pos]
        tValue = vPayload[pos+1:]
    else:
        tFieldName = vPayload
        tValue = ""
    
    # 解析vData，获取tTableName
    pos = vData.find("/")
    
    if pos > 0:
        tTableName = vData[:pos]
        tViewName = vData[pos+1:]
    else:
        tTableName = vData
        tViewName = ""
    
    # 构建文件名
    filename = base_app / gBaseName / f"{gBaseName}_{tTableName}.csv"
    user_file = base_path / f"{gBaseName}_{tTableName}.csv"
    if user_file.exists():
        filename = user_file
    
    # 检查文件是否存在
    if not os.path.exists(filename):
        return 0
    
    try:
        # 打开CSV文件
        with open(filename, 'r', encoding='utf-8', newline='') as csvfile:
            reader = csv.reader(csvfile)
            
            # 读取标题行
            headers = next(reader, None)
            if headers is None:
                return 0  # 空文件
            
            # 查找tFieldName在标题行中的索引位置
            if tFieldName not in headers:
                return 0  # 字段不存在
            
            field_index = headers.index(tFieldName)
            
            # 遍历数据行，查找tValue
            row_num = 2  # 第一行数据行号为2（因为标题行是第1行）
            
            for row in reader:
                # 检查行长度是否足够
                if len(row) > field_index:
                    # 比较字段值
                    if row[field_index] == tValue:
                        return row_num - 1
                row_num += 1
            
            # 未找到匹配的记录
            return 0
            
    except Exception as e:
        return 0
    

def get_record_json(vData, vPayload, gBaseName):
    """
    读取CSV文件，返回字段tFieldName的值tValue所在行的各个字段值的JSON文本
    
    参数:
    vData: 格式为 "表名/视图名"，视图名可选
    vPayload: 格式为 "字段名/字段值"
    gBaseName: 数据库基础名称
    
    返回:
    如果找到匹配的行，返回该行的JSON对象字符串
    如果未找到，返回空JSON对象字符串 "{}"
    如果发生错误，返回包含错误信息的JSON对象
    """
    
    # 解析vPayload，获取tFieldName和tValue
    pos = vPayload.find("/")
    
    if pos > 0:
        tFieldName = vPayload[:pos]
        tValue = vPayload[pos+1:]
    else:
        tFieldName = vPayload
        tValue = ""
    
    # 解析vData，获取tTableName
    pos = vData.find("/")
    
    if pos > 0:
        tTableName = vData[:pos]
        tViewName = vData[pos+1:]
    else:
        tTableName = vData
        tViewName = ""
    
    # 构建文件名
    filename = base_app / gBaseName / f"{gBaseName}_{tTableName}.csv"
    user_file = base_path / f"{gBaseName}_{tTableName}.csv"
    if user_file.exists():
        filename = user_file
    
    # 检查文件是否存在
    if not os.path.exists(filename):
        return "{}"
    
    try:
        # 打开CSV文件
        with open(filename, 'r', encoding='utf-8', newline='') as csvfile:
            # 使用csv.DictReader可以更方便地将行转换为字典
            reader = csv.DictReader(csvfile)
            
            # 遍历数据行，查找匹配的记录
            for row in reader:
                # 检查字段是否存在且值匹配
                if tFieldName in row and row[tFieldName] == tValue:
                    # 返回匹配行的JSON表示
                    return json.dumps(row, ensure_ascii=False)
            
            # 未找到匹配的记录
            return "{}"
            
    except Exception as e:
        return "{}"


def get_cell_value(vData, vPayload, gBaseName):
    """
    读取CSV文件，返回指定字段第tRow行的值
    
    参数:
    vData: 格式为 "表名/视图名"，视图名可选
    vPayload: 格式为 "字段名/行号"
    gBaseName: 数据库基础名称
    
    返回:
    返回指定字段第tRow行的值，如果行号超出范围或字段不存在，返回空字符串
    """
    
    # 解析vPayload，获取tFieldName和tRow
    pos = vPayload.find("/")
    
    if pos > 0:
        tFieldName = vPayload[:pos]
        tRow = vPayload[pos+1:]
    else:
        tFieldName = vPayload
        tRow = "1"  # 默认第1行
    
    # 解析vData，获取tTableName
    pos = vData.find("/")
    
    if pos > 0:
        tTableName = vData[:pos]
        tViewName = vData[pos+1:]
    else:
        tTableName = vData
        tViewName = ""
    
    # 转换行号为整数，并进行验证
    try:
        tRow = int(tRow)
        if tRow < 1:
            tRow = 1
    except ValueError:
        # 如果tRow不是有效数字，使用默认值1
        tRow = 1
    
    # 构建文件名
    filename = base_app / gBaseName / f"{gBaseName}_{tTableName}.csv"
    user_file = base_path / f"{gBaseName}_{tTableName}.csv"
    if user_file.exists():
        filename = user_file
    
    # 检查文件是否存在
    if not os.path.exists(filename):
        return ""
    
    try:
        # 打开CSV文件
        with open(filename, 'r', encoding='utf-8', newline='') as csvfile:
            reader = csv.reader(csvfile)
            
            # 读取标题行
            headers = next(reader, None)
            if headers is None:
                return ""  # 空文件
            
            # 查找tFieldName在标题行中的索引位置
            if tFieldName not in headers:
                return ""
            
            field_index = headers.index(tFieldName)
            
            # 遍历数据行，直到找到第tRow行
            current_row = 1  # 当前行号（从1开始计数，第1行数据）
            
            for row in reader:
                if current_row == tRow:
                    # 找到指定行，检查行长度是否足够
                    if len(row) > field_index:
                        # 获取字段值并移除回车符（\r）
                        value = row[field_index]
                        value = value.replace('\r', '')

                        if value.endswith('.md'):
                            file_path = base_path / value
                            if file_path.exists():
                                with open(file_path, 'r', encoding='utf-8') as f:
                                    value = f.read()
                                
                        return value
                    else:
                        return ""  # 行长度不够
                
                current_row += 1
            
            # 行号超出范围
            return f"行号 {tRow} 超出范围（文件共 {current_row-1} 行数据）"
            
    except Exception as e:
        return ""
    
def set_cell_value(vData, vPayload, gBaseName):
    """
    更新CSV文件中指定字段第tRow行的值为tValue
    
    参数:
    vData: 格式为 "表名/视图名"，视图名可选
    vPayload: 格式为 "字段名/行号/值" 或 "字段名/行号"
    gBaseName: 数据库基础名称
    
    返回:
    成功: 返回更新后的文件路径和成功消息
    失败: 返回错误消息
    """
    
    # 解析vPayload，获取tFieldName和tRow
    pos = vPayload.find("/")
    
    if pos > 0:
        tFieldName = vPayload[:pos]
        tRow = vPayload[pos+1:]
    else:
        tFieldName = vPayload
        tRow = "1"
    
    # 解析tRow，获取tRow和tValue
    pos = tRow.find("/")
    
    if pos > 0:
        tValue = tRow[pos+1:]
        tRow = tRow[:pos]
    else:
        tValue = ""
    
    # 解析vData，获取tTableName
    pos = vData.find("/")
    
    if pos > 0:
        tTableName = vData[:pos]
        tViewName = vData[pos+1:]
    else:
        tTableName = vData
        tViewName = ""
    
    # 构建文件名
    filename = base_app / gBaseName / f"{gBaseName}_{tTableName}.csv"
    user_file = base_path / f"{gBaseName}_{tTableName}.csv"
    if not user_file.exists() and filename.exists():
        shutil.copy2(filename, user_file)
    filename = user_file
    
    # 检查文件是否存在
    if not os.path.exists(filename):
        return ""
    
    # 转换行号为整数
    try:
        row_num = int(tRow)
        if row_num < 1:
            row_num = 1
    except ValueError:
        return ""
    
    # 检查是否有要更新的值
    if tValue == "":
        return ""
    
    try:
        # 读取CSV文件
        with open(filename, 'r', encoding='utf-8', newline='') as csvfile:
            reader = csv.reader(csvfile)
            rows = list(reader)
        
        if not rows:
            return ""
        
        # 获取标题行
        headers = rows[0]
        
        # 查找tFieldName在标题行中的索引位置
        if tFieldName not in headers:
            return ""
        
        field_index = headers.index(tFieldName)
        
        # 检查行号是否有效
        # 注意：行号1对应CSV的第2行（因为第1行是标题行）
        if row_num > len(rows) - 1:
            return ""
        
        # 更新指定行的字段值
        target_row_index = row_num  # 因为行号从1开始，但索引0是标题行
        if target_row_index < len(rows):
            # 确保行有足够的列
            if len(rows[target_row_index]) <= field_index:
                # 扩展行的列数
                rows[target_row_index].extend([''] * (field_index - len(rows[target_row_index]) + 1))
            
            # 更新字段值
            rows[target_row_index][field_index] = tValue
            
            # 写回文件
            with open(filename, 'w', encoding='utf-8', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerows(rows)
            
            return "SUCCESS"
        else:
            return ""
            
    except Exception as e:
        return ""


def delete_record(vData, vPayload, gBaseName):
    """
    删除CSV文件中第tRow行的数据（简单版本，适用于小文件）
    """
    
    tRow = vPayload
    
    # 解析vData，获取tTableName
    pos = vData.find("/")
    
    if pos > 0:
        tTableName = vData[:pos]
        tViewName = vData[pos+1:]
    else:
        tTableName = vData
        tViewName = ""
    
    # 构建文件名
    filename = base_app / gBaseName / f"{gBaseName}_{tTableName}.csv"
    user_file = base_path / f"{gBaseName}_{tTableName}.csv"
    if not user_file.exists() and filename.exists():
        shutil.copy2(filename, user_file)
    filename = user_file
    
    # 检查文件是否存在
    if not os.path.exists(filename):
        return ""
    
    # 转换行号为整数
    try:
        row_num = int(tRow)
        if row_num < 1:
            return ""
    except ValueError:
        return ""
    
    try:
        # 读取CSV文件
        with open(filename, 'r', encoding='utf-8', newline='') as csvfile:
            reader = csv.reader(csvfile)
            rows = list(reader)
        
        if not rows:
            return ""
        
        # 检查行号是否有效
        if row_num > len(rows) - 1:
            return ""
        
        # 删除指定行
        deleted_row = rows.pop(row_num)
        
        # 写回文件
        with open(filename, 'w', encoding='utf-8', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerows(rows)
        
        return "SUCCESS"
            
    except Exception as e:
        return ""


def call_workflow(request):
    url = 'http://127.0.0.1:3131/ask'
    headers = {
        'Content-Type': 'application/json',
        'ClientURL': quote('http://127.0.0.1:3130/answer')
    }
    try:
        response = requests.post(
            url, 
            headers=headers, 
            data=json.dumps(request),
            timeout=30  # 设置超时时间
        )
        response.raise_for_status()  # 如果状态码不是200，抛出异常
        return response.text
    except requests.exceptions.RequestException as e:
        raise Exception(f'请求失败: {str(e)}')
    

def fix_json_string(json_str):
    # 匹配双引号内的字符串内容（包括转义的双引号）
    pattern = re.compile(r'"(?:[^"\\]|\\.)*"')
    
    def replace_control_chars(match):
        s = match.group(0)
        inner = s[1:-1]  # 去掉双引号
        
        # 替换控制字符为JSON转义序列
        replacements = {
            '\n': '\\n',
            '\r': '\\r',
            '\t': '\\t',
            '\b': '\\b',
            '\f': '\\f'
        }
        
        for char, escaped in replacements.items():
            inner = inner.replace(char, escaped)
        
        return '"' + inner + '"'
    
    return pattern.sub(replace_control_chars, json_str)


def upload_matched_files(text):
    # --- 正则表达式定义 (保持你提供的逻辑) ---
    ext_pattern = r'\.(?:docx|pdf|pptx|xlsx|xmind|mm|txt|md|html|json|csv|srt|mp3|mp4|wav|ogg|flac|aac|wma|m4a|mpeg|amr|ac3|aiff|svg|jpg|jpeg|png|gif|bmp|tif|webp|zip|py|js|xml|yml)'
    guid_pattern = r'\{[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}\}'
    filename_pattern = f'({guid_pattern}{ext_pattern})'
    
    # 查找所有文件名
    # 注意：如果正则中有分组，findall 返回的可能是元组。这里 filename_pattern 外层有括号，直接返回字符串列表。
    filenames = re.findall(filename_pattern, text)
    
    # 去重（可选，视需求而定）
    filenames = list(set(filenames))
    
    # --- 遍历并上传 ---
    for filename in filenames:
        file_path = base_path / filename
        
        if not file_path.exists():
            continue
            
        try:
            # 打开文件并发送 POST 请求
            # 注意：'file' 是 Flask request.files['file'] 中对应的 key，
            # 如果服务器端用的是其他 key (如 'data', 'document')，请修改此处。
            with open(file_path, 'rb') as f:
                files = {'file': f} 
                response = requests.post('http://127.0.0.1:3131/upload', files=files, timeout=30)
                
            # 检查响应
            if response.status_code == 200:
                pass
                #print(f"[成功] {filename} 上传完成. 响应: {response.text}")
            else:
                pass
                #print(f"[失败] {filename} 上传失败. 状态码: {response.status_code}")
                
        except Exception as e:
            pass
            #print(f"[错误] 上传 {filename} 时发生异常: {e}")

def submit_record(vData, vPayload, gBaseName):
    """
    使用csv.reader向CSV文件首行添加一条新记录，并触发相应的工作流
    """
    
    # 解析vData，获取tTableName
    pos = vData.find("/")
    
    if pos > 0:
        tTableName = vData[:pos]
        tViewName = vData[pos+1:]
    else:
        tTableName = vData
        tViewName = ""
    
    # 构建文件名
    filename = base_app / gBaseName / f"{gBaseName}_{tTableName}.csv"
    user_file = base_path / f"{gBaseName}_{tTableName}.csv"
    if not user_file.exists() and filename.exists():
        shutil.copy2(filename, user_file)
    filename = user_file
    
    # 检查vPayload是否是有效的JSON
    try:
        record_data = json.loads(vPayload)
        if not isinstance(record_data, dict):
            return ""
    except json.JSONDecodeError as e:
        return ""
    
    success_msg = ""
    headers = [] 
    try:
        # --- 预处理：生成GUID并注入record_data ---
        # 确定字段列表以检查是否需要生成GUID
        temp_headers = []
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                try:
                    temp_headers = next(reader)
                except StopIteration:
                    pass
        
        if not temp_headers:
            temp_headers = list(record_data.keys())
            
        # 遍历字段，如果存在对应的工作流定义文件，则生成GUID作为该字段的值
        for tFieldName in temp_headers:
            json_file_path = base_app / gBaseName / f"{gBaseName}_{tTableName}_{tFieldName}.json"
            if json_file_path.exists():
                tFieldValue = record_data.get(tFieldName)
                if tFieldValue is None:
                    tFieldValue = ''
                if not is_valid_guid_filename(tFieldValue):
                    guid = str(uuid.uuid4())
                    tFieldValue = f"{guid}"
                record_data[tFieldName] = 'ASK_' + tFieldValue # 更新写入CSV的值
        # ---------------------------------------

        # 如果文件不存在，创建新文件
        if not os.path.exists(filename):
            # 创建文件并写入标题行和第一条记录
            with open(filename, 'w', encoding='utf-8', newline='') as csvfile:
                # 使用record_data的键作为标题行
                headers = list(record_data.keys())
                writer = csv.writer(csvfile)
                writer.writerow(headers)
                
                # 按照标题行的顺序创建数据行
                data_row = [record_data.get(header, "") for header in headers]
                writer.writerow(data_row)
            
            success_msg = "SUCCESS"
        
        else:
            # 读取原始文件内容
            with open(filename, 'r', encoding='utf-8', newline='') as csvfile:
                reader = csv.reader(csvfile)
                rows = list(reader)
            
            if not rows:
                # 文件为空
                headers = list(record_data.keys())
                data_row = [record_data.get(header, "") for header in headers]
                
                with open(filename, 'w', encoding='utf-8', newline='') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(headers)
                    writer.writerow(data_row)
                
                success_msg = "SUCCESS"
            else:
                # 文件已有内容
                headers = rows[0]
                
                # 准备新记录，确保与现有标题行匹配
                new_record = [record_data.get(header, "") for header in headers]
                
                # 在标题行后插入新记录
                rows.insert(1, new_record)
                
                # 写回文件
                with open(filename, 'w', encoding='utf-8', newline='') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerows(rows)
                
                success_msg = "SUCCESS"

        # --- 检查并执行字段关联的JSON工作流 ---
        # 使用CSV的headers进行遍历
        for tFieldName in headers:
            json_file_path = base_app / gBaseName / f"{gBaseName}_{tTableName}_{tFieldName}.json"

            user_json_file_path = base_path / f"{gBaseName}_{tTableName}_{tFieldName}.json"
            if user_json_file_path.exists():
                json_file_path = user_json_file_path

            if json_file_path.exists():
                try:
                    # 获取当前字段的值（如果是触发字段，此前已注入GUID）
                    tFieldValue = str(record_data.get(tFieldName, ""))

                    # 读取JSON文本
                    with open(json_file_path, 'r', encoding='utf-8') as f:
                        json_template = f.read()
                    
                    # 定义替换逻辑
                    def replace_match(match):
                        tag = match.group(1).strip() # 获取{{}}内部的字符串
                        
                        if '.' in tag:
                            # 处理关联表引用 {{关联表名.字段名}}
                            ref_table_name, ref_field_name = tag.split('.', 1)
                            ref_keyfield_name = ''
                            
                            # 1. 从表定义文件中获取关联表名对应的字段名
                            # 读取表定义文件：base_app / gBaseName / f"{gBaseName}_{tTableName}.json"
                            table_def_path = base_app / gBaseName / f"{gBaseName}_{tTableName}.json"

                            user_table_def_path = base_path / f"{gBaseName}_{tTableName}.json"
                            if user_table_def_path.exists():
                                table_def_path = user_table_def_path

                            if os.path.exists(table_def_path):
                                try:
                                    with open(table_def_path, 'r', encoding='utf-8') as tf:
                                        table_def = json.load(tf)
                                        # 查找关联表名对应的字段名
                                        field_name_for_ref_table = None
                                        for field_def in table_def.get("字段", []):
                                            if field_def.get("关联表名") == ref_table_name:
                                                field_name_for_ref_table = field_def.get("字段名")
                                                ref_keyfield_name = field_def.get("关联字段名")
                                                break
                                        
                                        if field_name_for_ref_table:
                                            # 获取新记录中对应这个字段名的值（作为外键）
                                            fk_value = record_data.get(field_name_for_ref_table)
                                        else:
                                            # 如果找不到对应字段，尝试使用关联表名作为字段名
                                            fk_value = record_data.get(ref_table_name)
                                except Exception as e:
                                    print(f"读取表定义文件出错: {str(e)}")
                                    fk_value = record_data.get(ref_table_name)
                            else:
                                # 表定义文件不存在，使用关联表名作为字段名
                                fk_value = record_data.get(ref_table_name)
                                
                            if fk_value is None:
                                return match.group(0) # 找不到外键值，不做替换
                            
                            # 2. 定位关联表的CSV文件
                            ref_csv_name = f"{gBaseName}_{ref_table_name}.csv"
                            ref_temp_path = base_path / f"{ref_csv_name}"
                            ref_base_path = base_app / gBaseName / ref_csv_name
                            
                            target_ref_file = None
                            if ref_temp_path.exists():
                                target_ref_file = ref_temp_path
                            elif ref_base_path.exists():
                                target_ref_file = ref_base_path
                                
                            if target_ref_file:
                                try:
                                    with open(target_ref_file, 'r', encoding='utf-8') as rf:
                                        ref_reader = csv.reader(rf)
                                        ref_rows = list(ref_reader)
                                        
                                        if ref_rows:
                                            ref_headers = ref_rows[0]
                                            try:
                                                target_col_idx = ref_headers.index(ref_field_name)
                                                target_keycol_idx = ref_headers.index(ref_keyfield_name)
                                                # 3. 查找第一列匹配的行
                                                for row in ref_rows[1:]:
                                                    if row and row[target_keycol_idx] == str(fk_value):
                                                        value = row[target_col_idx]

                                                        if value.endswith('.md'):
                                                            file_path = base_path / value
                                                            if file_path.exists():
                                                                with open(file_path, 'r', encoding='utf-8') as f:
                                                                    value = f.read()
                                
                                                        return format_for_json(value)
                                            except ValueError:
                                                pass # 关联表中无此字段
                                except Exception:
                                    pass # 读取关联表出错
                            return match.group(0) # 无法解析引用，保持原样
                            
                        else:
                            # 处理本表字段 {{字段名}}
                            value = str(record_data.get(tag, match.group(0)))

                            if value.endswith('.md'):
                                file_path = base_path / value
                                if file_path.exists():
                                    with open(file_path, 'r', encoding='utf-8') as f:
                                        value = f.read()
                            else:
                                csvpath = base_app / gBaseName / f"{gBaseName}_{tag}.csv"
                                user_csvpath = base_path / f"{gBaseName}_{tag}.csv"
                                if user_csvpath.exists():
                                    csvpath = user_csvpath
                                if csvpath.exists():
                                    value = str(csvpath)
                                
                            return format_for_json(value)

                    # 执行正则替换
                    processed_json_str = re.sub(r'\{\{(.*?)\}\}', replace_match, json_template)                    

                    pattern = r'\[\[(.*?)\]\]'
                    matches = re.findall(pattern, processed_json_str, re.DOTALL)
                    sql_statements = [m.strip() for m in matches]
                    for i, sql in enumerate(sql_statements, 1):
                        try:
                            df = duckdb.sql(json.loads(f'"{sql}"')).fetchdf()
                            result = df.to_csv(index=False, na_rep='')
                            processed_json_str = processed_json_str.replace('[[' + sql + ']]', result)
                        except Exception as e:
                            print(sql)

                    def replace_json_field_values(json_str):
                        # 解析JSON
                        data = json.loads(json_str, strict=False)
    
                        # 遍历所有节点
                        if "nodes" in data:
                            for node in data["nodes"]:
                                # 检查是否有input字段
                                if "input" in node and isinstance(node["input"], dict):
                                    # 遍历input字典的所有键值对
                                    for key, value in node["input"].items():
                                        # 只处理字符串类型的值
                                        if isinstance(value, str):
                                            # 使用record_data中的值替换，如果没有则保持原值
                                            fieldvalue = str(record_data.get(value, value))
                                            if fieldvalue.startswith("ASK_"):
                                                fieldvalue = fieldvalue.split("ASK_")[1]
                                            node["input"][key] = fieldvalue
    
                        # 将修改后的数据转换回JSON字符串
                        return json.dumps(data, ensure_ascii=False, indent=3)

                    # 应用双引号包裹字段名的替换
                    processed_json_str = replace_json_field_values(processed_json_str)

                    api_key = gBaseName
                    processed_json_str = processed_json_str.replace("[APIKey]", api_key)

                    streamid = long_guid()
                    askstream[streamid] = {}
                    askstream[streamid]["answer"] = ""
                    askstream[streamid]["gBaseName"] = gBaseName
                    askstream[streamid]["tTableName"] = tTableName
                    askstream[streamid]["tFieldName"] = tFieldName
                    askstream[streamid]["tFieldValue"] = tFieldValue
                    request_data = {"prompt": processed_json_str, "streamid": streamid}
                    upload_matched_files(processed_json_str)
                    call_workflow(request_data)
                    
                except Exception as wf_error:
                    #print(traceback.format_exc())
                    print(f"处理工作流 {json_file_path} 时出错: {str(wf_error)}")
        # ---------------------------------------------

        return success_msg
                    
    except Exception as e:
        return ""


def image_to_data_uri(image_path: Path) -> str:
    """
    将图片转换为Data URI格式，可直接在HTML中使用
    
    Args:
        image_path: 图片文件路径
    
    Returns:
        Data URI字符串
    """
    # 获取MIME类型
    mime_type, encoding = mimetypes.guess_type(image_path)
    if not mime_type:
        # 根据文件扩展名推断常见图片类型
        ext_to_mime = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.bmp': 'image/bmp',
            '.webp': 'image/webp',
            '.svg': 'image/svg+xml',
        }
        mime_type = ext_to_mime.get(image_path.suffix.lower(), 'image/jpeg')
    
    # 读取并编码图片
    if os.path.isfile(image_path):
        with open(image_path, 'rb') as img_file:
            base64_data = base64.b64encode(img_file.read()).decode('utf-8')
        return f"data:{mime_type};base64,{base64_data}"
    else:
        return ""


def file_to_base64(file_path: Path) -> str:
    """
    将文件转换为Base64编码的字符串
    
    Args:
        file_path: 文件路径（Path对象或字符串）
    
    Returns:
        Base64编码的字符串
    """
    if os.path.isfile(file_path):
        with open(file_path, 'rb') as file:
            file_data = file.read()
        base64_encoded = base64.b64encode(file_data)
        return base64_encoded.decode('utf-8')
    else:
        return ""
    

def read_file(request_data) -> str:
    user_file = base_path / request_data
    if user_file.exists():
        with open(user_file, 'r', encoding='utf-8') as file:
            return file.read()
    else:
        return ""    

def write_file(request_data, request_payload) -> str:
    # 构建文件名
    filename = base_path / f"{request_data}"
    
    # 将 request_payload 写入文件，如果文件不存在则创建
    try:
        filename.write_text(request_payload, encoding='utf-8')
        return f"文件已成功写入: {filename}"
    except Exception as e:
        return f"写入文件时发生错误: {str(e)}" 


@app.route('/private/<path:filename>')
def serve_private_file(filename):
    try:
        return send_from_directory(base_path, filename)
    except FileNotFoundError:
        abort(404)


import json
import shutil
from pathlib import Path, PurePosixPath
from zipfile import ZipFile


def import_app(zip_path, appclass):
      """
      将 ZIP 内 AirThink 下的 apps、files、skills 解压到 base_app。
      返回：id|name|appclass|baseDesc

      同名文件会被覆盖。
      """
      allowed_dirs = {"apps", "files", "skills"}
      target = Path.cwd()
      if appclass == '全部应用':
          appclass = ''

      with ZipFile(zip_path, "r") as archive:
          entries = archive.infolist()

          # 获取 AirThink/apps 下的第一个文件夹名称。
          base_name = None
          for entry in entries:
              parts = PurePosixPath(entry.filename).parts
              if (
                  len(parts) >= 3
                  and parts[:2] == ("AirThink", "apps")
                  and (len(parts) > 3 or entry.is_dir())
              ):
                  base_name = parts[2]
                  break

          if base_name is None:
              raise ValueError("ZIP 中未找到 AirThink/apps 下的文件夹")

          app_id, separator, name = base_name.partition("_")
          if not separator or not app_id or not name:
              raise ValueError(f"文件夹名称不符合 id_name 格式：{base_name}")

          # 先校验所有待解压路径，防止路径越界。
          copy_jobs = []
          for entry in entries:
              parts = PurePosixPath(entry.filename).parts
              if (
                  len(parts) < 2
                  or parts[0] != "AirThink"
                  or parts[1] not in allowed_dirs
              ):
                  continue

              relative_parts = parts[1:]
              if any(
                  part in {".", ".."} or "\\" in part or ":" in part
                  for part in relative_parts
              ):
                  raise ValueError(f"ZIP 中存在不安全的路径：{entry.filename}")

              destination = target.joinpath(*relative_parts).resolve()
              if target not in destination.parents:
                  raise ValueError(f"解压路径超出目标目录：{entry.filename}")

              copy_jobs.append((entry, destination))

          # utf-8-sig 同时支持普通 UTF-8 和带 BOM 的 UTF-8。
          config_path = f"AirThink/apps/{base_name}/{base_name}.json"
          try:
              config = json.loads(
                  archive.read(config_path).decode("utf-8-sig")
              )
          except KeyError as exc:
              raise ValueError(f"ZIP 中缺少配置文件：{config_path}") from exc

          if not isinstance(config, dict) or "库描述" not in config:
              raise ValueError("配置 JSON 必须是对象，且包含“库描述”属性")

          base_desc = config["库描述"]
          if not isinstance(base_desc, str):
              raise ValueError("“库描述”属性必须是字符串")

          # 保留 apps、files、skills 文件夹及内部目录结构。
          target.mkdir(parents=True, exist_ok=True)
          for entry, destination in copy_jobs:
              if entry.is_dir():
                  destination.mkdir(parents=True, exist_ok=True)
              else:
                  destination.parent.mkdir(parents=True, exist_ok=True)
                  with archive.open(entry) as source:
                      with destination.open("wb") as output:
                          shutil.copyfileobj(source, output)

      return f"{app_id}|{name}|{appclass}|{base_desc}"


@app.route('/request', methods=['POST'])
def handle_request():
    try:
        data = request.get_json(silent=True)
        request_type = data.get('type', '')
        request_data = data.get('data', '')
        request_payload = data.get('payload', '')

        if request_type == 'VerifyUserKey':
            response_text = 'No'
            if request_data:
                if os.path.exists(base_app / 'userkey.json'):
                    userkeys = []
                    with open(base_app / 'userkey.json', 'r', encoding='utf-8') as f:
                        userkeys = json.load(f)
                    if request_data in userkeys:
                        response_text = 'Yes'
                else:
                    userkeys = []
                    userkeys.append(request_data)
                    (base_app / 'userkey.json').write_text(
                        json.dumps(userkeys, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
                    response_text = 'Yes'
            return Response(response_text, mimetype='text/plain; charset=utf-8')

        if request_type == 'MyApps':
            response_text = ''
            if os.path.exists(base_app / 'myapps.txt'):
                with open(base_app / 'myapps.txt', 'r', encoding='utf-8') as f:
                    response_text = f.read()
            return Response(response_text, mimetype='text/plain; charset=utf-8')        

        if request_type == 'ImportApp':
            response_text = ''
            if os.path.exists(base_app / 'myapps.txt'):
                with open(base_app / 'myapps.txt', 'r', encoding='utf-8') as f:
                    response_text = f.read()
            apptxt = import_app(base_path / request_data, request_payload)
            if apptxt:
                if apptxt not in response_text:
                    if response_text and not response_text.endswith('\n'):
                        response_text += '\n'
                    response_text += apptxt
                    with open(base_app / 'myapps.txt', 'w', encoding='utf-8') as f:
                        f.write(response_text)
            return Response(response_text, mimetype='text/plain; charset=utf-8')        

        basename = unquote(request.headers.get('BaseName'))
        session_id_header = request.headers.get('SessionID')
        if session_id_header is not None:
            session_id = unquote(session_id_header)
        else:
            session_id = None

        if os.path.exists(base_app / 'userkey.json'):
            userkeys = []
            with open(base_app / 'userkey.json', 'r', encoding='utf-8') as f:
                userkeys = json.load(f)
            if session_id not in userkeys:
                response_text = ''
                return Response(response_text, mimetype='text/plain; charset=utf-8')
        
        if request_type == 'GetTableCSV':
            response_text = get_table_csv(request_data, request_payload, basename)
        elif request_type == 'GetRecordCount':
            response_text = str(get_record_count(request_data, basename))
        elif request_type == 'GetRecordRow':
            response_text = str(get_record_row(request_data, request_payload, basename))
        elif request_type == 'GetRecordJson':
            response_text = str(get_record_json(request_data, request_payload, basename))
        elif request_type == 'GetCellValue':
            response_text = str(get_cell_value(request_data, request_payload, basename))
            response_text = '' if response_text.startswith("ASK_") else response_text
        elif request_type == '轮询':
            response_text = str(get_cell_value(request_data, request_payload + '/1', basename))
            response_text = '' if response_text.startswith("ASK_") else response_text
        elif request_type == 'SetCellValue':
            response_text = str(set_cell_value(request_data, request_payload, basename))
        elif request_type == 'DeleteRecord':
            response_text = str(delete_record(request_data, request_payload, basename))
        elif request_type == 'SubmitRecord':
            response_text = str(submit_record(request_data, request_payload, basename))
        elif request_type == '模式':
            response_text = '亮色'
        elif request_type == 'RecordVoice':
            response_text = ''
        elif request_type == 'ImageToBase64':
            image_path = base_path / request_data
            response_text = image_to_data_uri(image_path)
        elif request_type == 'FileToBase64':
            file_path = base_path / request_data
            response_text = file_to_base64(file_path)
        elif request_type == 'ImageUrl':
            response_text = 'http://127.0.0.1/Files/' + request_data
        elif request_type == 'FileUrl':
            response_text = 'http://127.0.0.1/Files/' + request_data
        elif request_type == 'LoadFile':
            response_text = ''
        elif request_type == 'ReadFile':
            response_text = read_file(request_data)
        elif request_type == 'WriteFile':
            response_text = write_file(request_data, request_payload)
        elif request_type == 'SetAIBase':
            response_text = ''
        elif request_type == 'GetSubject':
            response_text = ''
        elif request_type == 'CreateGuid':
            guid = str(uuid.uuid4())
            response_text = f"{guid}"
        else:
            response_text = ''
        
        return Response(response_text, mimetype='text/plain; charset=utf-8')
    
    except Exception as e:
        #print(traceback.format_exc())
        error_text = f"服务器处理错误: {str(e)}"
        return Response(error_text, 
                       status=500, 
                       mimetype='text/plain; charset=utf-8')

def make_csv_row(fields):
    output = io.StringIO()
    writer = csv.writer(output, lineterminator='')
    writer.writerow(fields)
    return output.getvalue()

@app.route('/answer', methods=['POST'])
def handle_answer():
    try:
        data = request.get_json(silent=True)
        answer = data.get('answer', '')
        streamid = data.get('streamid', '')
        if answer == "":
            if streamid in askstream:
                gBaseName = askstream[streamid].get("gBaseName", '')
                tTableName = askstream[streamid].get("tTableName", '')
                tFieldName = askstream[streamid].get("tFieldName", '')
                tFieldValue = askstream[streamid].get("tFieldValue", '')

                file_base_name = f"{gBaseName}_{tTableName}"
                tFieldValue = tFieldValue.split("ASK_")[1]
                content_str = askstream[streamid].get("answer", '')
                csv_filename = f"files/{file_base_name}.csv"

                # 尝试判断是否为JSON
                is_json_content = False
                json_data = {}
                try:
                    json_data = json.loads(content_str, strict=False)
                    if isinstance(json_data, list):
                        json_data = json_data[0]
                    if isinstance(json_data, dict):
                        is_json_content = True
                except:
                    is_json_content = False
                if is_json_content:
                    # 如果是JSON文本，不写md文件，而是更新csv
                    if os.path.exists(csv_filename):
                        try:
                            updated_rows = []
                            fieldnames = []
                            target_marker = "ASK_" + tFieldValue
                            # 读取CSV寻找目标行并替换
                            with open(csv_filename, 'r', encoding='utf-8', newline='') as f:
                                reader = csv.DictReader(f)
                                fieldnames = reader.fieldnames
                                for row in reader:
                                    # 判断字段名tFieldName的字段值是否为"ASK_" + tFieldValue
                                    if row.get(tFieldName) == target_marker:
                                        if is_valid_guid_filename(tFieldValue):
                                            row[tFieldName] = tFieldValue
                                        else:
                                            row[tFieldName] = ""
                                        # 根据json文本的key和value替换单元格
                                        for key, value in json_data.items():
                                            if key in row: # 确保CSV中有此列
                                                if isinstance(value, str):
                                                    lines = value.split('\n')
                                                    for line in lines:
                                                        file_matches = re.findall(r"(?:File|Image)://.*?(\{[\w-]+\}\.[\w]+)", line)
                                                        for tFileName in file_matches:
                                                            value = tFileName
                                                            break
                                                    if '\n' in value:
                                                        # 如果value的值是多行，将value写入.md文件
                                                        tFileName = '{' + str(uuid.uuid4()) + "}.md"
                                                        with open(base_path / tFileName, 'w', encoding='utf-8') as md_file:
                                                            md_file.write(value)
                                                        row[key] = tFileName
                                                    else:
                                                        row[key] = value
                                                else:
                                                    row[key] = value
                                    updated_rows.append(row)
                            
                            # 写回CSV
                            if fieldnames:
                                with open(csv_filename, 'w', encoding='utf-8', newline='') as f:
                                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                                    writer.writeheader()
                                    writer.writerows(updated_rows)
                        except Exception as e:
                            print(f"JSON CSV Update Error: {e}")
                            pass
                else:
                    # 原有非JSON逻辑
                    replace_str = ""

                    # 判断是否以特殊前缀开头
                    if content_str.startswith("Image://"):
                        replace_str = content_str[8:] 
                        start = replace_str.find('{')
                        if start != -1:
                            replace_str = replace_str[start:] 
                    elif content_str.startswith("File://"):
                        replace_str = content_str[7:] 
                        start = replace_str.find('{')
                        if start != -1:
                            replace_str = replace_str[start:] 
                    else:
                        # 写入.md文件
                        tFileName = '{' + tFieldValue + "}.md"
                        tFileName = base_path / tFileName
                        with open(tFileName, 'w', encoding='utf-8') as f:
                            f.write(content_str)
                        
                        replace_str = "{" + tFieldValue + "}.md"
        
                    # 正则匹配GUID格式的文件名：{8-4-4-4-12}.扩展名
                    pattern = r'\{[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}\}\.\w+'
                    matches = re.findall(pattern, replace_str)  # 返回所有匹配的文件名列表
                    matches = set(matches)
                    for filename in matches:
                        replace_str = filename
                        break

                    # 构造查找的目标字符串并替换（原有字符串替换逻辑）
                    target_str = "ASK_" + tFieldValue
                    if os.path.exists(csv_filename):
                        try:
                            with open(csv_filename, 'r', encoding='utf-8') as f:
                                content = f.read()

                            if target_str in content:
                                new_content = content.replace(target_str, replace_str)
                                with open(csv_filename, 'w', encoding='utf-8') as f:
                                    f.write(new_content)
                        except Exception as e:
                            pass
        else:
            if answer.startswith("AIUse://"):
                pass
            else:
                askstream[streamid]["answer"] = askstream[streamid].get("answer", '') + answer

        return Response('', mimetype='text/plain; charset=utf-8')
    except Exception as e:
        #print(traceback.format_exc())
        return Response("", 
                       status=500, 
                       mimetype='text/plain; charset=utf-8')




# ----------------------
# WebSocket 辅助函数
# ----------------------
def buffer_to_hex(buffer):
    """将 16 字节 Buffer 转换为 32 位十六进制字符串（不带连字符）"""
    return buffer.hex()

async def websocket_handler(websocket):
    """处理 WebSocket 连接"""
    current_api_key = None
    try:
        async for message in websocket:
            if isinstance(message, bytes):
                # 处理二进制消息（文件块）
                if len(message) < 16:
                    print('二进制消息长度不足，无法提取目标 API Key')
                    continue
                # 提取前 16 字节作为目标 API Key
                target_key_buffer = message[:16]
                target_api_key = buffer_to_hex(target_key_buffer)

                target_ws = ws_clients.get(target_api_key)
                if not target_ws:
                    print(f'二进制消息的目标 {target_api_key} 未连接')
                    continue
                # 直接转发整个二进制消息（包含目标 API Key）
                await target_ws.send(message)
                continue

            # 文本消息处理
            try:
                data = json.loads(message)
            except json.JSONDecodeError:
                await websocket.send(json.dumps({'type': 'error', 'message': 'Invalid JSON'}))
                continue

            msg_type = data.get('type')
            if msg_type == 'register':
                api_key = data.get('apiKey')
                if not api_key:
                    await websocket.send(json.dumps({'type': 'error', 'message': 'API_KEY required'}))
                    continue
                # 如果已有相同 apiKey 的连接，关闭旧的
                if api_key in ws_clients:
                    old_ws = ws_clients[api_key]
                    if old_ws != websocket:
                        await old_ws.close()
                ws_clients[api_key] = websocket
                current_api_key = api_key
                await websocket.send(json.dumps({'type': 'register_ack', 'apiKey': api_key}))
                print(f'客户端注册成功: {api_key}')

            elif msg_type == 'message':
                target_api_key = data.get('targetApiKey')
                content = data.get('content')
                message_id = data.get('messageId')

                if content.strip() == '技能表':
                    basename = target_api_key
                    if basename not in skills_csv:
                        skills = scan_skills(basename)
                        skills_csv[basename] = array_to_csv(skills)
                    response_content = skills_csv[basename]
                    await websocket.send(json.dumps({
                        'type': 'response',
                        'targetMessageId': message_id,
                        'content': response_content
                    }))
                    continue
                elif content.startswith('技能信息,'):
                    base_dirs = [s.strip() for s in content[5:].split(',') if s.strip()]
                    if not base_dirs:
                        await websocket.send(json.dumps({
                            'type': 'response',
                            'targetMessageId': message_id,
                            'content': ""
                        }))
                        continue

                    basename = target_api_key
                    skills = []
                    with open(base_app / basename /'skill.json', 'r', encoding='utf-8') as f:
                        skills = json.load(f)

                    results = []
                    for bdir in base_dirs:
                        skill_zip = ''
                        for skill in skills:
                            if (skill['skill_name'] == bdir):
                                skill_zip = skill['skill_zip']
                                break
                        file_path = base_skill / skill_zip
                        if file_path.exists():
                            results.append("技能文件：" + skill_zip)
                        else:
                            try:
                                results.append(get_skill_content(bdir))
                            except:
                                results.append('')
                    final_content = "\n===\n".join(results)
                    if final_content:
                        final_content = "下面是所用到的技能描述以及相关的脚本代码，\n===\n" + final_content
                    await websocket.send(json.dumps({
                        'type': 'response',
                        'targetMessageId': message_id,
                        'content': final_content
                    }))
                    continue
                elif content.startswith('技能文件,'):
                    file_path = base_skill / content[5:]
                    if file_path.exists():
                        try:
                            with open(file_path, 'rb') as f:
                                files = {'file': f} 
                                requests.post('http://127.0.0.1:3131/upload', files=files, timeout=30)
                        except Exception as e:
                            pass

                    await websocket.send(json.dumps({
                        'type': 'response',
                        'targetMessageId': message_id,
                        'content': ""
                    }))
                    continue

                if not target_api_key or not content or not message_id:
                    await websocket.send(json.dumps({'type': 'error', 'message': 'Missing fields in message'}))
                    continue
                target_ws = ws_clients.get(target_api_key)

                if not target_ws:
                    await websocket.send(json.dumps({'type': 'error', 'message': f'Target {target_api_key} not found'}))
                    continue
                # 转发给目标，附上源 apiKey
                await target_ws.send(json.dumps({
                    'type': 'from',
                    'fromApiKey': current_api_key,
                    'content': content,
                    'messageId': message_id
                }))

            elif msg_type == 'response':
                target_api_key = data.get('targetApiKey')
                target_message_id = data.get('targetMessageId')
                content = data.get('content')
                if not target_api_key or not target_message_id or not content:
                    await websocket.send(json.dumps({'type': 'error', 'message': 'Missing fields in response'}))
                    continue
                target_ws = ws_clients.get(target_api_key)
                if not target_ws:
                    await websocket.send(json.dumps({'type': 'error', 'message': f'Response target {target_api_key} not found'}))
                    continue
                await target_ws.send(json.dumps({
                    'type': 'response',
                    'targetMessageId': target_message_id,
                    'content': content
                }))

            elif msg_type == 'file_start':
                target_api_key = data.get('targetApiKey')
                file_id = data.get('fileId')
                file_name = data.get('fileName')
                file_size = data.get('fileSize')
                chunk_size = data.get('chunkSize')
                total_chunks = data.get('totalChunks')
                message_id = data.get('messageId')
                if not all([target_api_key, file_id, file_name, file_size, chunk_size, total_chunks, message_id]):
                    await websocket.send(json.dumps({'type': 'error', 'message': 'Missing fields in file_start'}))
                    continue
                target_ws = ws_clients.get(target_api_key)
                if not target_ws:
                    await websocket.send(json.dumps({'type': 'error', 'message': f'File target {target_api_key} not found'}))
                    continue
                # 添加 fromApiKey 后转发
                await target_ws.send(json.dumps({
                    'type': 'file_start',
                    'fromApiKey': current_api_key,
                    'fileId': file_id,
                    'fileName': file_name,
                    'fileSize': file_size,
                    'chunkSize': chunk_size,
                    'totalChunks': total_chunks,
                    'messageId': message_id
                }))

            else:
                await websocket.send(json.dumps({'type': 'error', 'message': 'Unknown message type'}))
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        # 连接关闭时移除映射
        if current_api_key and ws_clients.get(current_api_key) == websocket:
            del ws_clients[current_api_key]
            print(f'客户端断开: {current_api_key}')

def process_websocket_request(connection, request):
    """握手先于 websocket_handler 执行，在此处理缺失或无效的升级头。"""
    try:
        connection_options = [
            option
            for value in request.headers.get_all('Connection')
            for option in parse_connection(value)
        ]
        if not any(option.lower() == 'upgrade' for option in connection_options):
            raise InvalidUpgrade('Connection', ', '.join(connection_options) or None)

        upgrades = [
            protocol
            for value in request.headers.get_all('Upgrade')
            for protocol in parse_upgrade(value)
        ]
        if len(upgrades) != 1 or upgrades[0].lower() != 'websocket':
            raise InvalidUpgrade('Upgrade', ', '.join(upgrades) or None)
    except InvalidHeader as exc:
        app.logger.info('拒绝 WebSocket 升级请求 (%s): %s', connection.remote_address, exc)
        response = connection.respond(
            HTTPStatus.UPGRADE_REQUIRED,
            'This port requires a WebSocket connection with '
            'Connection: Upgrade and Upgrade: websocket headers.\n',
        )
        response.headers['Upgrade'] = 'websocket'
        return response
    return None


async def start_websocket_server():
    """启动 WebSocket 服务器"""
    async with websockets.serve(
        websocket_handler, '0.0.0.0', 3133,
        process_request=process_websocket_request,
    ):
        print('WebSocket 服务器运行在 ws://0.0.0.0:3133')
        await asyncio.Future()  # 永久运行

def run_websocket_server():
    """在独立线程中运行 WebSocket 服务器"""
    asyncio.run(start_websocket_server())

