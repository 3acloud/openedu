import json
import re
import uuid
import shutil
from pathlib import Path
import speech_recognition as sr
import pypdf
import mammoth
import openpyxl
import zipfile
import pathspec
import pandas as pd
from pptx import Presentation
import xmindparser
from lxml import etree
import pytesseract
#from pyzbar.pyzbar import decode
from PIL import Image


CODEC_TEST_LIST = [
    "utf-8-sig",
    "utf-8",
    "gbk",
    "gb2312",
    "utf-16",
    "utf-16-le",
    "utf-16-be",
    "utf-32",
    "utf-32-le",
    "utf-32-be",
]


def try_load_json_file(file_path: str, default=dict):
    if Path(file_path).exists():
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            pass
#            mprint_error(f"Failed to load json file: {file_path}, {e}")
    return default()


def rename_path(path: str | Path):
    path = Path(path)

    for item in path.iterdir():
        if item.is_file() or item.is_dir():
            try:
                new_name = item.name.encode("cp437").decode("gbk")
            except Exception:
                new_name = item.name

            new_path = item.with_name(new_name)
            item.rename(new_path)

            if new_path.is_dir():
                rename_path(new_path)


def read_gitignore(folder_path, extra_ignore_patterns=None):
    gitignore_path = folder_path / ".gitignore"
    ignore_lines = []

    if gitignore_path.exists():
        with gitignore_path.open("r", encoding="utf-8") as file:
            ignore_lines.extend(line.strip() for line in file)

    if extra_ignore_patterns:
        ignore_lines.extend(extra_ignore_patterns)

    spec = pathspec.PathSpec.from_lines("gitwildmatch", ignore_lines)
    return spec


def is_ignored(path, spec, folder_path):
    relative_path = path.relative_to(folder_path)
    # Use pathspec to check if the file should be ignored
    return spec.match_file(relative_path.as_posix())


def read_folder(folder_path, ignore_list):
    contents = []
    for path in sorted(folder_path.rglob("*")):
        if path.is_file() and not is_ignored(path, ignore_list, folder_path):
            try:
                file_content = read_file_content(local_file=path, read_zip=False)
                rel_path = path.relative_to(folder_path)
                contents.append(f"# {rel_path}\n```\n{file_content}\n```\n")
            except Exception as e:
                print(f"Could not read file {path}: {e}")
    return contents


def read_zip_contents(zip_file_path: str | Path, extract_path: str | Path = "SERVERFILES/tmp") -> Path:
    if not zipfile.is_zipfile(zip_file_path):
        raise FileNotFoundError(f"The file at {zip_file_path} is not a valid zip file.")

    zip_path = Path(zip_file_path)
    extract_path += "/{" + str(uuid.uuid4()) + "}" 
    extract_to_path = Path(extract_path)

    extract_to_path.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_file_path, "r") as zip_ref:
        zip_ref.extractall(extract_to_path)

    rename_path(extract_to_path)

    folder_path = Path(extract_to_path)
    extra_ignore_list = [".git", ".gitignore", ".gitattributes"]
    ignore_list = read_gitignore(folder_path, extra_ignore_list)

    contents = read_folder(folder_path, ignore_list)

    try:
        shutil.rmtree(extract_path)
    except Exception:
        pass

    return "\n".join(contents)


def read_file_content(local_file: str | Path, read_zip: bool = False):
    filename = Path(local_file).name
    if filename.endswith(".docx") or filename.endswith(".doc"):
        with open(local_file, "rb") as docx_file:
            docx_data = mammoth.convert_to_markdown(docx_file)
            markdown_text = docx_data.value
            return markdown_text
    elif filename.endswith(".pdf"):
        with open(local_file, "rb") as pdf_file_obj:
            pdf_reader = pypdf.PdfReader(pdf_file_obj)
            pdf_contents = [page.extract_text() for page in pdf_reader.pages]
            return "\n\n".join(pdf_contents)
    elif filename.endswith(".pptx"):
        ppt = Presentation(local_file)
        ppt_contents = []
        for slide in ppt.slides:
            for shape in slide.shapes:
                if hasattr(shape, "text") and shape.text:
                    ppt_contents.append(shape.text.strip())
        return "\n\n".join(ppt_contents)
    elif filename.endswith(".xlsx"):
        try:
            df = pd.read_excel(local_file, engine="openpyxl")
            return df.to_csv(index=False)
        except Exception as e:
            #mprint_error(e)
            wb = openpyxl.load_workbook(local_file, data_only=True)
            ws = wb.active
            csv_contents = []
            for row in ws.rows:
                csv_contents.append(",".join([str(cell.value) if cell.value else "" for cell in row]))
            return "\n\n".join(csv_contents)
    elif filename.endswith((".txt", ".md", ".html", ".json", ".csv", ".srt")):
        for codec in CODEC_TEST_LIST:
            try:
                with open(local_file, "r", encoding=codec) as txt_file:
                    txt_contents = txt_file.read()
                    return txt_contents
            except Exception as e:
                pass
                #mprint_error(e)
        else:
            #mprint_error("Failed to decode file")
            return ""
    elif filename.endswith(".zip") and read_zip:
        content = read_zip_contents(local_file)
        return content
    else:
        for codec in CODEC_TEST_LIST:
            try:
                with open(local_file, "r", encoding=codec) as txt_file:
                    txt_contents = txt_file.read()
                    return txt_contents
            except Exception as e:
                pass
                #mprint_error(e)
        else:
            #mprint_error("Failed to decode file")
            return txt_contents



def generate_md(data, level=1):
    md = ''
    for topic in data['topics']:
        title = topic['title']
        md += f"{'#' * level} {title}\n\n"

        if 'topics' in topic:
            md += generate_md(topic, level + 1)

    return md


def convert_to_markdown(elem, level=1):
    markdown = ""
    
    # 创建标题
    title = elem.get('TEXT')
    if title == None:
        title = ""
        level = 0
    else:
        markdown += "#" * level + " " + title + "\n\n"

    # 遍历子元素
    for child_elem in elem.getchildren():
        # 检查子元素类型
        if child_elem.tag == 'node':
            # 递归转换子元素
            markdown += convert_to_markdown(child_elem, level + 1)
        elif child_elem.tag == 'richcontent':
            # 处理文本内容
            markdown += child_elem.text + "\n\n"

    return markdown



def get_file_content(file):
        result = ""
        file = file.replace('Image://', 'SERVERFILES/', 1) if file.startswith('Image://') else file
        file = file.replace('File://', 'SERVERFILES/', 1) if file.startswith('File://') else file
        if file.find("SERVERFILES") == -1:
            file = "SERVERFILES/" + file
        if file.lower().endswith(".docx"):
            with open(file, "rb") as docx_file:
                docx_data = mammoth.convert_to_markdown(docx_file)
                markdown_text = docx_data.value
                result = markdown_text
        elif file.lower().endswith(".pdf"):
            with open(file, "rb") as pdf_file_obj:
                pdf_reader = pypdf.PdfReader(pdf_file_obj)
                pdf_contents = [page.extract_text() for page in pdf_reader.pages]
                result = "\n\n".join(pdf_contents)
        elif file.lower().endswith(".pptx"):
            ppt = Presentation(file)
            ppt_contents = []
            for slide in ppt.slides:
                for shape in slide.shapes:
                    if hasattr(shape, "text") and shape.text:
                        ppt_contents.append(shape.text.strip())
            result = "\n\n".join(ppt_contents)
        elif file.lower().endswith(".xlsx"):
            try:
                df = pd.read_excel(file, engine="openpyxl")
                result = df.to_csv(index=False)
            except Exception:
                wb = openpyxl.load_workbook(file, data_only=True)
                ws = wb.active
                csv_contents = []
                for row in ws.rows:
                    csv_contents.append(",".join([str(cell.value) if cell.value else "" for cell in row]))
                result = "\n\n".join(csv_contents)
        elif file.lower().endswith(".xmind"):
            content = xmindparser.xmind_to_dict(file)
            result = generate_md(content[0]['topic'])
        elif file.lower().endswith(".mm"):
            tree = etree.parse(file)
            root = tree.getroot()
            result = convert_to_markdown(root)
        elif file.lower().endswith((".txt", ".md", ".html", ".json", ".csv", ".srt")):
            for codec in CODEC_TEST_LIST:
                try:
                    with open(file, "r", encoding=codec) as txt_file:
                        txt_contents = txt_file.read()
                        result = txt_contents
                        break
                except Exception:
                    pass
            else:
                result = ""
        #elif file.lower().endswith((".jpg",".jpeg",".png",".gif",".bmp",".tif")):
        #    image = Image.open(file)
        #    txt_contents = ""
        #    data = decode(image)
        #    for obj in data:
        #        txt_contents += obj.data.decode("utf-8")
        #    if txt_contents == "":
        #        txt_contents = pytesseract.image_to_string(image, lang='eng+chi_sim+chi_tra')
        #    result = txt_contents
        elif file.lower().endswith(".zip"):
            txt_contents = read_zip_contents(file)
            result = txt_contents
        else:
            for codec in CODEC_TEST_LIST:
                try:
                    with open(file, "r", encoding="utf-8-sig") as txt_file:
                        txt_contents = txt_file.read()
                        result = txt_contents
                        break
                except Exception:
                    pass
            else:
                result = ""

        return result

def replace_filenames_with_content(text, file_extensions=None):
    """
    将文本中的所有文件名替换为对应的文件内容
    
    Args:
        text: 输入文本
        file_extensions: 允许的文件扩展名列表，如 ['.md', '.json', '.txt']
    
    Returns:
        替换后的文本
    """
    # 定义文件扩展名的模式
    if file_extensions:
        # 转义扩展名中的点号
        ext_pattern = '|'.join(re.escape(ext) for ext in file_extensions)
    else:
        # 如果没有指定扩展名，匹配常见的扩展名
        ext_pattern = r'\.(?:docx|pdf|pptx|xlsx|xmind|mm|txt|md|html|json|csv|srt|mp3|wav|ogg|flac|aac|wma|m4a|mpeg|amr|ac3|aiff|jpg|jpeg|png|gif|bmp|tif|webp|zip|py|js|xml|yml)'
    
    # GUID 正则表达式，匹配 {xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx}.扩展名
    guid_pattern = r'\{[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}\}'
    
    # 完整文件名模式
    filename_pattern = f'({guid_pattern}{ext_pattern})'
    
    # 查找所有文件名
    filenames = re.findall(filename_pattern, text)
    
    # 缓存已读取的文件内容，避免重复读取
    file_cache = {}
    
    def replace_match(match):
        filename = match.group(1)
        
        # 如果已经在缓存中，直接返回缓存的内容
        if filename in file_cache:
            return file_cache[filename]
        
        # 获取文件内容
        try:
            content = get_file_content(filename)
        except Exception:
            content = filename
        file_cache[filename] = content
        
        return content
    
    # 使用 re.sub 进行替换
    result = re.sub(filename_pattern, replace_match, text)
    
    return result


def copy_file(src, dst):
    if Path(src).exists():
        Path(dst).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(src, dst)
        return True
    return False
