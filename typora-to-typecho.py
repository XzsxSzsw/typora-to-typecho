import os
import re
import time
import sys
import random
import shutil
import yaml
import requests
import urllib3
import brotli
from ftplib import FTP, error_perm, error_temp
from urllib.parse import urljoin, urlparse
from pathlib import Path


# ========== YAML 配置读取 + 插值解析（最终修复版） ==========
def load_yaml_config(config_path="config.yaml"):
    """读取YAML配置并解析多层嵌套插值，确保返回字典"""
    # 1. 检查配置文件是否存在
    if not os.path.exists(config_path):
        print(f"❌ 配置文件 {config_path} 不存在！")
        sys.exit(1)

    # 2. 读取原始YAML配置
    try:
        with open(config_path, encoding="utf-8") as f:
            raw_config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        print(f"❌ YAML配置文件解析错误：{e}")
        sys.exit(1)

    # 3. 校验原始配置类型
    if not isinstance(raw_config, dict):
        print(f"❌ 配置文件格式错误！应为字典类型，实际：{type(raw_config)}")
        sys.exit(1)
    print(f"✅ 原始配置读取成功，类型：{type(raw_config)}")

    # 4. 定义递归+循环解析插值的函数（核心修复：缩进+逻辑完整）
    def resolve_interpolations(item, config):
        """
        递归解析所有插值，支持多层嵌套
        :param item: 当前要解析的元素（字符串/字典/列表）
        :param config: 完整配置字典（用于插值查找）
        :return: 解析后的元素
        """
        # 处理字符串类型：循环解析直到无${}占位符
        if isinstance(item, str):
            current_str = item
            # 循环解析，确保多层嵌套插值被完全替换
            while "${" in current_str:
                # 匹配所有${xxx.xxx}格式的插值
                pattern = r"\$\{([\w.]+)\}"
                matches = re.findall(pattern, current_str)
                if not matches:
                    break  # 无插值，退出循环

                for match in matches:
                    # 拆分插值路径（如 global.domain → ["global", "domain"]）
                    keys = match.split(".")
                    val = config
                    try:
                        # 逐层查找插值变量
                        for key in keys:
                            val = val[key]
                        # 替换插值（确保值为字符串类型）
                        current_str = current_str.replace(f"${{{match}}}", str(val))
                    except KeyError:
                        print(f"❌ 插值变量 '{match}' 不存在于配置中！")
                        sys.exit(1)
            return current_str

        # 处理字典类型：递归解析每个键值对
        elif isinstance(item, dict):
            new_dict = {}
            for k, v in item.items():
                new_dict[k] = resolve_interpolations(v, config)
            return new_dict

        # 处理列表类型：递归解析每个元素
        elif isinstance(item, list):
            new_list = []
            for elem in item:
                new_list.append(resolve_interpolations(elem, config))
            return new_list

        # 其他类型（数字/布尔/None）直接返回
        else:
            return item

    # 5. 解析所有配置
    resolved_config = resolve_interpolations(raw_config, raw_config)

    # 6. 最终校验+调试打印
    if not isinstance(resolved_config, dict):
        print(f"❌ 插值解析后配置类型错误！应为字典，实际：{type(resolved_config)}")
        sys.exit(1)

    # 调试打印关键插值结果
    print("\n📌 插值结果验证：")
    print(f"   - 站点域名：{resolved_config['global']['domain']}")
    print(f"   - 首页URL：{resolved_config['site']['home_url']}")
    print(f"   - 登录页URL：{resolved_config['site']['login_page']}")
    print(f"   - 图片服务器URL：{resolved_config['image']['server_img_url']}")

    return resolved_config


# 加载并解析配置
config = load_yaml_config()

# ========== 配置参数提取（与原逻辑一致） ==========
# 站点配置
SITE_DOMAIN = config["global"]["domain"]
SITE_HOME = config["site"]["home_url"]
TYPECHO_LOGIN_PAGE = config["site"]["login_page"]
TYPECHO_ADMIN_URL = config["site"]["admin_url"]
TYPECHO_WRITE_URL = config["site"]["write_post_url"]
TYPECHO_MANAGE_POSTS_URL = config["site"]["manage_posts_url"]
TYPECHO_MANAGE_CATEGORIES_URL = config["site"]["manage_categories_url"]
TYPECHO_DELETE_POST_URL = config["site"]["delete_post_url"]
TIMEZONE = config["global"]["timezone"]

# 登录配置
USERNAME = config["login"]["username"]
PASSWORD = config["login"]["password"]
COOKIE_PREFIX = config["login"]["cookie_prefix"]

# 图片配置
IMG_ROOT_DIR = config["image"]["processed_img_root"]
IMG_SERVER_URL = config["image"]["server_img_url"]
SPACE_REPLACE_CHAR = config["image"]["space_replace_char"]

# FTP配置
FTP_HOST = config["ftp"]["host"]
FTP_PORT = config["ftp"]["port"]
FTP_USER = config["ftp"]["user"]
FTP_PWD = config["ftp"]["password"]
FTP_IMG_BASE_PATH = config["ftp"]["base_path"]
FTP_TIMEOUT = config["ftp"]["timeout"]
FTP_PASSIVE = config["ftp"]["passive"]

# 请求配置
USER_AGENT = config["request"]["user_agent"]
MIN_DELAY = config["request"]["min_delay"]
MAX_DELAY = config["request"]["max_delay"]
BATCH_DELAY = config["request"]["batch_delay"]

# 分类配置
DEFAULT_CATEGORY_ID = config["category"]["default_category_id"]

# ========== 以下代码完全保留（无需修改） ==========
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

CHROME_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Ch-Ua": '"Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Priority": "u=0, i",
    "Cache-Control": "max-age=0",
}

ADMIN_KEYWORDS = ["网站概要", "管理面板", "文章管理", "退出登录", "Typecho"]

# 全局变量
img_mapping = {}
article_id = None
ftp_conn = None
note_img_local_dir = ""
temp_content = ""
category_map = {}
batch_stats = {"total": 0, "success": 0, "failed": 0, "failed_files": []}


# ========== 核心工具函数（完全保留） ==========
def decode_response(resp: requests.Response) -> str:
    try:
        resp.encoding = "utf-8"
        ce = resp.headers.get("Content-Encoding", "").lower()
        if ce == "br":
            return brotli.decompress(resp.content).decode("utf-8", errors="ignore")
        elif ce in ["gzip", "deflate"]:
            return resp.text
        return resp.content.decode("utf-8", errors="ignore")
    except:
        return resp.content.decode("utf-8", errors="ignore")


def print_step(title: str, step_num: int):
    print("\n" + "=" * 80)
    print(f"📌 执行步骤 [{step_num}/7]：{title}")
    print("=" * 80)


def human_delay(min_seconds: float = None, max_seconds: float = None):
    min_s = min_seconds if min_seconds else MIN_DELAY
    max_s = max_seconds if max_seconds else MAX_DELAY
    delay = random.uniform(min_s, max_s)
    print(f"⏳ 模拟人类操作延迟：{delay:.2f}秒")
    time.sleep(delay)


def check_cookie(session: requests.Session, cookie_name: str) -> tuple[bool, str]:
    cookie_value = session.cookies.get(cookie_name, domain=SITE_DOMAIN)
    if not cookie_value:
        cookie_value = session.cookies.get(cookie_name, domain=f".{SITE_DOMAIN}")
    return (True, cookie_value) if cookie_value else (False, "")


def check_admin_keyword(admin_html: str) -> tuple[bool, str]:
    if "网站概要" in admin_html:
        return True, "网站概要"
    for keyword in ADMIN_KEYWORDS[1:]:
        if keyword in admin_html:
            return True, keyword
    return False, ""


def update_referer_headers(session: requests.Session, referer_url: str):
    session.headers["Referer"] = referer_url
    if referer_url == "":
        session.headers["Sec-Fetch-Site"] = "none"
    elif urlparse(referer_url).netloc == SITE_DOMAIN:
        session.headers["Sec-Fetch-Site"] = "same-origin"
    else:
        session.headers["Sec-Fetch-Site"] = "cross-site"


def clean_local_img_dir(dir_path: str):
    if os.path.exists(dir_path):
        try:
            shutil.rmtree(dir_path)
            print(f"✅ 已清理本地图片目录：{dir_path}")
        except Exception as e:
            print(f"⚠️ 清理本地目录失败：{e}")


def reset_global_vars():
    global img_mapping, article_id, note_img_local_dir, temp_content
    img_mapping = {}
    article_id = None
    note_img_local_dir = ""
    temp_content = ""


def replace_space_char(text: str) -> str:
    return text.replace(" ", SPACE_REPLACE_CHAR).strip()


def parse_user_selection(input_str: str, max_num: int) -> list[int]:
    selected = []
    parts = input_str.strip().split()
    for part in parts:
        if "-" in part:
            try:
                start, end = part.split("-")
                start = int(start)
                end = int(end)
                if 1 <= start <= end <= max_num:
                    selected.extend(range(start, end + 1))
                else:
                    print(f"⚠️ 无效范围：{part}，请确保在1-{max_num}之间")
            except ValueError:
                print(f"⚠️ 无效输入：{part}，请输入数字或范围如1-3")
        else:
            try:
                num = int(part)
                if 1 <= num <= max_num:
                    selected.append(num)
                else:
                    print(f"⚠️ 无效编号：{num}，请确保在1-{max_num}之间")
            except ValueError:
                print(f"⚠️ 无效输入：{part}，请输入数字")
    return sorted(list(set(selected)))


def rollback_article(session: requests.Session, article_id: str):
    if not article_id:
        return
    print(f"\n🔄 开始回滚：删除文章ID {article_id}")
    try:
        edit_url = f"{SITE_HOME}/admin/write-post.php?cid={article_id}"
        update_referer_headers(session, TYPECHO_MANAGE_POSTS_URL)
        edit_resp = session.get(edit_url, timeout=10)
        edit_html = decode_response(edit_resp)

        publish_token = re.search(r"_=([0-9a-f]{32})", edit_html)
        publish_token = (
            publish_token.group(1)
            if publish_token
            else "4bc337a9bb2079e48605260b98bcc6d8"
        )
        csrf_token = re.search(r'name="__typecho_csrf_token" value="(.*?)"', edit_html)
        csrf_token = csrf_token.group(1) if csrf_token else ""

        delete_api = (
            f"{SITE_HOME}/index.php/action/contents-post-edit?_={publish_token}"
        )
        delete_data = {
            "cid": article_id,
            "do": "delete",
            "__typecho_csrf_token": csrf_token,
        }
        delete_headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": edit_url,
            **CHROME_HEADERS,
        }
        delete_resp = session.post(
            delete_api, data=delete_data, headers=delete_headers, timeout=10
        )
        if delete_resp.status_code in [200, 302]:
            print(f"✅ 回滚成功：已删除文章ID {article_id}")
        else:
            print(f"❌ 回滚失败：删除文章ID {article_id} 失败")
    except Exception as e:
        print(f"❌ 回滚异常：{e}")


def rollback_ftp_files(remote_dir: str):
    if not ftp_conn or not remote_dir:
        return
    print(f"\n🔄 开始回滚：删除FTP目录 {remote_dir} 下的图片")
    try:
        original_dir = ftp_conn.pwd()
        ftp_conn.cwd(remote_dir)
        file_list = ftp_conn.nlst()
        for file in file_list:
            ftp_conn.delete(file)
            print(f"✅ 删除FTP文件：{file}")
        ftp_conn.cwd(original_dir)
        ftp_conn.rmd(remote_dir)
        print(f"✅ 删除FTP空目录：{remote_dir}")
    except Exception as e:
        print(f"❌ FTP回滚失败：{e}")


# ========== 1. 登录验证（完全保留原逻辑） ==========
def simulate_browser_login() -> tuple[bool, requests.Session]:
    print_step("登录验证", 1)
    session = requests.Session()
    session.headers.update(CHROME_HEADERS)
    session.headers["Referer"] = ""
    session.adapters.DEFAULT_POOLSIZE = 1
    session.verify = False
    session.timeout = 60

    print("✅ Session初始化完成")
    human_delay()

    try:
        home_resp = session.get(SITE_HOME, allow_redirects=True, timeout=10)
        print(f"📈 首页响应码：{home_resp.status_code}")
    except Exception as e:
        print(f"⚠️ 首页访问警告：{e}")
    human_delay(1.5, 2.5)

    update_referer_headers(session, SITE_HOME)
    try:
        login_resp = session.get(TYPECHO_LOGIN_PAGE, allow_redirects=True, timeout=10)
        login_html = decode_response(login_resp)

        action_patterns = [
            r'<form.*?action="(.*?index.php/action/login\?_=.*?)".*?>',
            r'action="(.*?/action/login\?_=.*?)"',
            r'<form[^>]*?action="([^"]+)"',
        ]
        real_login_url = None
        for pattern in action_patterns:
            match = re.search(pattern, login_html, re.DOTALL | re.IGNORECASE)
            if match:
                real_login_url = match.group(1)
                break

        if not real_login_url:
            print("❌ 未找到登录接口")
            return False, session
        if not real_login_url.startswith("http"):
            real_login_url = urljoin(TYPECHO_LOGIN_PAGE, real_login_url)
        print(f"✅ 找到登录接口：{real_login_url}")
    except Exception as e:
        print(f"❌ 登录页访问失败：{e}")
        return False, session
    human_delay(2.0, 3.0)

    update_referer_headers(session, TYPECHO_LOGIN_PAGE)
    login_data = {
        "name": USERNAME,
        "password": PASSWORD,
        "referer": TYPECHO_ADMIN_URL,
        "login": "登录",
    }

    try:
        login_resp = session.post(
            real_login_url,
            data=login_data,
            allow_redirects=True,
            timeout=10,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        auth_exists = check_cookie(session, f"{COOKIE_PREFIX}__typecho_authCode")[0]
        uid_exists = check_cookie(session, f"{COOKIE_PREFIX}__typecho_uid")[0]
        php_exists = check_cookie(session, "PHPSESSID")[0]

        print(f"\n📌 登录验证结果：")
        print(f"   AuthCode：{'✅ 存在' if auth_exists else '❌ 缺失'}")
        print(f"   UID：{'✅ 存在' if uid_exists else '❌ 缺失'}")
        print(f"   PHPSESSID：{'✅ 存在' if php_exists else '❌ 缺失'}")

        if not (auth_exists and uid_exists and php_exists):
            print("❌ 登录失败：核心Cookie缺失")
            return False, session
    except Exception as e:
        print(f"❌ 登录提交失败：{e}")
        return False, session
    human_delay(1.0, 2.0)

    update_referer_headers(session, TYPECHO_LOGIN_PAGE)
    try:
        admin_resp = session.get(TYPECHO_ADMIN_URL, allow_redirects=False, timeout=10)
        admin_html = decode_response(admin_resp)

        if check_admin_keyword(admin_html)[0]:
            print("✅ 后台访问成功，登录验证通过")
            return True, session
        else:
            print("❌ 后台验证失败：未找到关键标识")
            return False, session
    except Exception as e:
        print(f"❌ 后台访问失败：{e}")
        return False, session


# ========== 2. 抓取文章分类（完全保留） ==========
def crawl_categories(session: requests.Session) -> bool:
    print_step("抓取文章分类", 2)
    global category_map
    category_map.clear()

    try:
        update_referer_headers(session, TYPECHO_ADMIN_URL)
        cate_resp = session.get(TYPECHO_MANAGE_CATEGORIES_URL, timeout=10)
        if cate_resp.status_code != 200:
            print(f"❌ 分类页访问失败：状态码 {cate_resp.status_code}")
            category_map[DEFAULT_CATEGORY_ID] = "默认分类"
            print(f"⚠️ 使用默认分类：[{DEFAULT_CATEGORY_ID}] 默认分类")
            return True
        cate_html = decode_response(cate_resp)

        cate_pattern = r'<a href="[^"]*category\.php\?mid=(\d+)"[^>]*>([^<]+)</a>'
        matches = re.findall(cate_pattern, cate_html)
        if not matches:
            print("❌ 未抓取到任何分类，使用默认分类")
            category_map[DEFAULT_CATEGORY_ID] = "默认分类"
            return True

        for mid, cate_name in matches:
            mid = int(mid)
            cate_name = cate_name.strip()
            category_map[mid] = cate_name

        print(f"✅ 成功抓取 {len(category_map)} 个分类：")
        for idx, (mid, name) in enumerate(category_map.items(), 1):
            print(f"   {idx}. [{mid}] {name}")
        return True
    except Exception as e:
        print(f"❌ 抓取分类失败：{e}")
        category_map[DEFAULT_CATEGORY_ID] = "默认分类"
        print(f"⚠️ 使用默认分类：[{DEFAULT_CATEGORY_ID}] 默认分类")
        return True


def select_categories() -> list[int]:
    if not category_map:
        print(f"❌ 无可用分类，使用默认分类ID {DEFAULT_CATEGORY_ID}")
        return [DEFAULT_CATEGORY_ID]

    print("\n" + "=" * 50)
    print("📋 可选分类列表（基于后台抓取）")
    print("=" * 50)
    sorted_cates = sorted(category_map.items(), key=lambda x: x[0])
    cate_idx_map = {}
    for idx, (mid, name) in enumerate(sorted_cates, 1):
        cate_idx_map[idx] = mid
        print(f"   {idx}. [{mid}] {name}")
    print("=" * 50)
    print("提示：输入分类编号，支持单个(如1)、多个(如1 3)、范围(如1-2)")
    print("直接回车使用第一个分类")

    while True:
        user_input = input("请输入分类选择：").strip()
        if not user_input:
            default_mid = sorted_cates[0][0]
            print(f"✅ 选择默认分类：[{default_mid}] {category_map[default_mid]}")
            return [default_mid]

        selected_idxs = parse_user_selection(user_input, len(sorted_cates))
        if selected_idxs:
            selected_mids = [cate_idx_map[idx] for idx in selected_idxs]
            print(f"✅ 已选择分类：")
            for mid in selected_mids:
                print(f"   - [{mid}] {category_map[mid]}")
            return selected_mids
        else:
            print("❌ 无效选择，请重新输入！")


# ========== 3. Markdown格式清洗 + 动态图片路径处理（完全保留） ==========
def process_markdown_images(
    raw_content: str, md_file_path: str
) -> tuple[str, dict, bool]:
    global img_mapping, note_img_local_dir, temp_content
    img_mapping = {}
    content = raw_content
    img_counter = 1
    process_success = True

    md_basename = os.path.splitext(os.path.basename(md_file_path))[0]
    md_basename = replace_space_char(md_basename)
    md_dir = os.path.dirname(md_file_path)

    note_img_local_dir = os.path.join(IMG_ROOT_DIR, md_basename)

    try:
        Path(note_img_local_dir).mkdir(parents=True, exist_ok=True)
        print(f"✅ 创建处理后图片目录：{note_img_local_dir}")
    except Exception as e:
        print(f"❌ 创建本地目录失败：{e}")
        return content, img_mapping, False

    img_pattern = r"!\[(.*?)\]\((.*?\.(png|jpg|jpeg|gif|webp))\)"
    img_pattern = re.compile(img_pattern, re.IGNORECASE | re.DOTALL)

    def replace_img_path(match):
        nonlocal img_counter, process_success
        alt_text = match.group(1)
        img_path = match.group(2).strip()
        img_ext = match.group(3).lower()

        if os.path.isabs(img_path):
            raw_img_path = img_path
        else:
            raw_img_path = os.path.join(md_dir, img_path)
        raw_img_path = os.path.abspath(raw_img_path)
        raw_img_path = raw_img_path.replace("/", "\\")

        new_filename = f"{md_basename}_{int(time.time())}_{img_counter}.{img_ext}"
        new_filename = replace_space_char(new_filename)
        img_counter += 1
        local_save_path = os.path.join(note_img_local_dir, new_filename)

        if os.path.exists(raw_img_path):
            try:
                shutil.copy2(raw_img_path, local_save_path)
                temp_tag = f"__IMG_TAG_{new_filename}__"
                img_mapping[local_save_path] = {
                    "new_filename": new_filename,
                    "temp_tag": temp_tag,
                    "original_path": raw_img_path,
                }
                print(f"✅ 处理图片：{raw_img_path} → {local_save_path}")
                return f"![{alt_text}]({temp_tag})"
            except Exception as e:
                print(f"❌ 复制图片失败：{raw_img_path} → {e}")
                process_success = False
                return match.group(0)
        else:
            print(f"❌ 图片不存在：{raw_img_path}")
            process_success = False
            return match.group(0)

    content = img_pattern.sub(replace_img_path, content)

    html_img_pattern = r'<img.*?src=["\'](.*?\.(png|jpg|jpeg|gif|webp))["\'].*?>'
    html_img_pattern = re.compile(html_img_pattern, re.IGNORECASE | re.DOTALL)

    def replace_html_img(match):
        nonlocal img_counter, process_success
        img_path = match.group(1).strip()
        img_ext = match.group(2).lower()

        if os.path.isabs(img_path):
            raw_img_path = img_path
        else:
            raw_img_path = os.path.join(md_dir, img_path)
        raw_img_path = os.path.abspath(raw_img_path)
        raw_img_path = raw_img_path.replace("/", "\\")

        new_filename = f"{md_basename}_{int(time.time())}_{img_counter}.{img_ext}"
        new_filename = replace_space_char(new_filename)
        img_counter += 1
        local_save_path = os.path.join(note_img_local_dir, new_filename)

        if os.path.exists(raw_img_path):
            try:
                shutil.copy2(raw_img_path, local_save_path)
                temp_tag = f"__IMG_TAG_{new_filename}__"
                img_mapping[local_save_path] = {
                    "new_filename": new_filename,
                    "temp_tag": temp_tag,
                    "original_path": raw_img_path,
                }
                print(f"✅ 处理HTML图片：{raw_img_path} → {local_save_path}")
                return f'<img src="{temp_tag}" alt="image" title="image">'
            except Exception as e:
                print(f"❌ 复制HTML图片失败：{raw_img_path} → {e}")
                process_success = False
                return match.group(0)
        else:
            print(f"❌ HTML图片不存在：{raw_img_path}")
            process_success = False
            return match.group(0)

    content = html_img_pattern.sub(replace_html_img, content)
    temp_content = content

    print(f"\n📊 图片处理统计：共处理 {len(img_mapping)} 张图片（原始路径分布不同）")
    return content, img_mapping, process_success


def clean_markdown_for_theme(raw_content: str, md_file_path: str) -> tuple[str, bool]:
    print_step("Markdown格式清洗 + 动态图片路径处理", 3)

    content = raw_content
    original_length = len(content)

    content, _, process_success = process_markdown_images(content, md_file_path)
    if not process_success:
        print("❌ 图片处理失败")
        return content, False

    content = re.sub(r"<[^>]+>", "", content)
    print("✅ 移除多余HTML标签")

    def full_to_half(s):
        result = []
        for char in s:
            code = ord(char)
            if code == 12288:
                result.append(" ")
            elif 65281 <= code <= 65374:
                result.append(chr(code - 65248))
            else:
                result.append(char)
        return "".join(result)

    content = full_to_half(content)

    content = re.sub(r"^(#+)(\S)", r"\1 \2", content, flags=re.MULTILINE)
    content = re.sub(r"^(#+)\s+(.+?)\s+#+$", r"\1 \2", content, flags=re.MULTILINE)
    content = re.sub(r"^#{7,}", "######", content, flags=re.MULTILINE)
    content = re.sub(
        r'(#{1,6}\s+)(.+?)["&<>/\\:*\?|]+', r"\1\2", content, flags=re.MULTILINE
    )

    content = re.sub(r"\n{3,}", "\n\n", content)
    content = re.sub(r" {2,}", " ", content)
    content = re.sub(r"^\s+$", "", content, flags=re.MULTILINE)
    content = content.replace("\r\n", "\n").replace("\r", "\n")

    print(
        f"\n📊 格式清洗统计：原始 {original_length} 字符 → 清洗后 {len(content)} 字符"
    )
    print("✅ 格式清洗完成")
    return content, True


# ========== FTP函数（完全保留） ==========
def ftp_init_connection() -> tuple[bool, FTP]:
    global ftp_conn
    try:
        ftp = FTP()
        ftp.set_pasv(FTP_PASSIVE)
        ftp.connect(FTP_HOST, FTP_PORT, timeout=FTP_TIMEOUT)
        ftp.login(FTP_USER, FTP_PWD)
        ftp.encoding = "utf-8"

        current_dir = ftp.pwd()
        print(f"✅ FTP登录成功！当前根目录：{current_dir}")

        ftp_conn = ftp
        return True, ftp
    except error_temp as e:
        print(f"❌ FTP连接超时：{e}")
        return False, None
    except error_perm as e:
        print(f"❌ FTP登录失败：{e}")
        return False, None
    except Exception as e:
        print(f"❌ FTP初始化失败：{e}")
        return False, None


def ftp_verify_file_exists(remote_dir: str, filename: str) -> bool:
    if not ftp_conn:
        print(f"❌ FTP未连接，无法验证文件：{remote_dir}{filename}")
        return False

    try:
        original_dir = ftp_conn.pwd()
        ftp_conn.cwd(remote_dir)
        file_list = ftp_conn.nlst()
        exists = filename in file_list
        ftp_conn.cwd(original_dir)

        if exists:
            print(f"✅ FTP验证成功：文件 {remote_dir}{filename} 存在")
        else:
            print(f"❌ FTP验证失败：文件 {remote_dir}{filename} 不存在")
        return exists
    except Exception as e:
        print(f"⚠️ FTP验证异常：{e}")
        return False


def ftp_upload_file_with_verify(
    local_file_path: str, remote_dir: str, new_filename: str
) -> bool:
    if not ftp_conn:
        print(f"❌ FTP未连接，跳过上传：{local_file_path}")
        return False

    try:
        dirs = remote_dir.strip("/").split("/")
        current_dir = ""
        for dir_name in dirs:
            if dir_name:
                current_dir += f"/{dir_name}"
                try:
                    ftp_conn.cwd(current_dir)
                except error_perm:
                    ftp_conn.mkd(current_dir)
                    ftp_conn.cwd(current_dir)

        with open(local_file_path, "rb") as f:
            ftp_conn.storbinary(f"STOR {new_filename}", f, blocksize=8192)

        return ftp_verify_file_exists(remote_dir, new_filename)
    except Exception as e:
        print(f"❌ FTP上传失败：{local_file_path} → {e}")
        return False


def ftp_batch_verify_files(remote_dir: str, img_mapping: dict) -> tuple[bool, list]:
    print(f"\n🔍 批量FTP验证文件（目录：{remote_dir}）...")
    success_count = 0
    fail_files = []
    total_files = len(img_mapping)

    for local_path, img_info in img_mapping.items():
        filename = img_info["new_filename"]
        if ftp_verify_file_exists(remote_dir, filename):
            success_count += 1
        else:
            fail_files.append(filename)

    print(f"📊 FTP验证统计：成功 {success_count}/{total_files}，失败 {len(fail_files)}")
    if fail_files:
        print(f"❌ 验证失败的文件：{fail_files}")
    return success_count > 0 and success_count >= total_files * 0.9, fail_files


def ftp_close_connection():
    global ftp_conn
    if ftp_conn:
        try:
            ftp_conn.quit()
            print("✅ FTP连接已关闭")
        except:
            ftp_conn.close()
        ftp_conn = None


# ========== 4. 发布文章并验证（完全保留） ==========
def extract_article_id(
    session: requests.Session, publish_resp: requests.Response, article_title: str
) -> str:
    global article_id
    all_matched_ids = []
    title_escaped = re.escape(article_title)

    try:
        redirect_url = publish_resp.headers.get("Location", "")
        if redirect_url:
            id_match1 = re.search(r"/archives/(\d+)/?", redirect_url)
            id_match2 = re.search(r"cid=(\d+)", redirect_url)
            if id_match1:
                all_matched_ids.append(id_match1.group(1))
            if id_match2:
                all_matched_ids.append(id_match2.group(1))

        print(f"🔍 提取文章ID：{article_title}")
        manage_resp = session.get(TYPECHO_MANAGE_POSTS_URL, timeout=10)
        manage_html = decode_response(manage_resp)

        precise_pattern = (
            rf'<a href="[^"]*write-post\.php\?cid=(\d+)"[^>]*>{title_escaped}</a>'
        )
        precise_matches = re.findall(precise_pattern, manage_html, re.IGNORECASE)
        if precise_matches:
            all_matched_ids.extend(precise_matches)

        cid_matches = re.findall(r"write-post\.php\?cid=(\d+)", manage_html)
        archive_matches = re.findall(r"/index\.php/archives/(\d+)/", manage_html)
        all_matched_ids.extend(cid_matches)
        all_matched_ids.extend(archive_matches)

        if all_matched_ids:
            unique_ids = list(
                set([id_str for id_str in all_matched_ids if id_str.isdigit()])
            )
            if unique_ids:
                article_id = str(max([int(id_str) for id_str in unique_ids]))
                print(f"✅ 提取文章ID：{article_id}")
                return article_id

        print("❌ 未能提取文章ID")
        return None
    except Exception as e:
        print(f"❌ 提取ID失败：{e}")
        return None


def verify_article_published(session: requests.Session, title: str) -> bool:
    print(f"\n🔍 验证文章发布状态：{title}")
    title_escaped = re.escape(title)

    for page in range(1, 5):
        manage_url = f"{TYPECHO_MANAGE_POSTS_URL}?page={page}"
        try:
            resp = session.get(manage_url, timeout=10)
            if resp.status_code == 200 and re.search(
                rf"<a[^>]*>{title_escaped}</a>", decode_response(resp)
            ):
                print(f"✅ 文章发布验证通过！")
                return True
        except Exception as e:
            print(f"⚠️ 检查第{page}页失败：{e}")

    print(f"❌ 文章发布验证失败")
    return False


def publish_article(
    session: requests.Session, title: str, cleaned_content: str, category_ids: list[int]
) -> bool:
    print_step("发布文章并验证", 4)
    global article_id
    article_id = None

    try:
        update_referer_headers(session, TYPECHO_ADMIN_URL)
        write_resp = session.get(TYPECHO_WRITE_URL, timeout=10)
        if write_resp.status_code != 200:
            raise Exception(f"发布页访问失败：{write_resp.status_code}")
        write_html = decode_response(write_resp)

        publish_token = re.search(r"_=([0-9a-f]{32})", write_html)
        publish_token = (
            publish_token.group(1)
            if publish_token
            else "4bc337a9bb2079e48605260b98bcc6d8"
        )
        csrf_token = re.search(r'name="__typecho_csrf_token" value="(.*?)"', write_html)
        csrf_token = csrf_token.group(1) if csrf_token else ""

        publish_api = (
            f"{SITE_HOME}/index.php/action/contents-post-edit?_={publish_token}"
        )
        publish_data = {
            "title": title,
            "text": cleaned_content,
            "markdown": "1",
            "visibility": "publish",
            "do": "publish",
            "timezone": TIMEZONE,
            "__typecho_csrf_token": csrf_token,
            "submit": "发布",
        }
        for cid in category_ids:
            publish_data[f"category[]"] = str(cid)

        publish_headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": SITE_HOME,
            "Referer": TYPECHO_WRITE_URL,
            **CHROME_HEADERS,
        }
        publish_resp = session.post(
            publish_api,
            data=publish_data,
            headers=publish_headers,
            allow_redirects=False,
            timeout=30,
            verify=False,
        )
        print(f"📈 发布响应码：{publish_resp.status_code}")

        article_id = extract_article_id(session, publish_resp, title)
        if not article_id:
            print("❌ 提取文章ID失败，发布验证无法进行")
            return False

        if verify_article_published(session, title):
            return True
        else:
            rollback_article(session, article_id)
            return False
    except Exception as e:
        print(f"❌ 发布文章失败：{e}")
        import traceback

        traceback.print_exc()
        if article_id:
            rollback_article(session, article_id)
        return False


# ========== 5. 上传图片并验证（完全保留） ==========
def update_article_img_links(
    session: requests.Session, article_id: str, article_title: str
) -> bool:
    global temp_content, img_mapping
    if not img_mapping or not article_id:
        print("ℹ️ 无图片需要更新链接")
        return True

    try:
        updated_content = temp_content
        remote_dir = f"/{article_id}/"
        for local_path, img_info in img_mapping.items():
            temp_tag = img_info["temp_tag"]
            new_filename = img_info["new_filename"]
            final_url = f"{IMG_SERVER_URL}{article_id}/{new_filename}"
            updated_content = updated_content.replace(temp_tag, final_url)

        edit_url = f"{SITE_HOME}/admin/write-post.php?cid={article_id}"
        update_referer_headers(session, TYPECHO_MANAGE_POSTS_URL)
        edit_resp = session.get(edit_url, timeout=10)
        edit_html = decode_response(edit_resp)

        if article_title not in edit_html:
            print(f"⚠️ 编辑页无标题：{article_title}")
            return False

        publish_token = re.search(r"_=([0-9a-f]{32})", edit_html)
        publish_token = (
            publish_token.group(1)
            if publish_token
            else "4bc337a9bb2079e48605260b98bcc6d8"
        )
        csrf_token = re.search(r'name="__typecho_csrf_token" value="(.*?)"', edit_html)
        csrf_token = csrf_token.group(1) if csrf_token else ""

        update_api = (
            f"{SITE_HOME}/index.php/action/contents-post-edit?_={publish_token}"
        )
        update_data = {
            "cid": article_id,
            "title": article_title,
            "text": updated_content,
            "markdown": "1",
            "visibility": "publish",
            "do": "publish",
            "timezone": TIMEZONE,
            "__typecho_csrf_token": csrf_token,
            "submit": "保存",
        }
        for cid in category_map.keys():
            update_data[f"category[]"] = str(cid)

        update_headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": SITE_HOME,
            "Referer": edit_url,
            **CHROME_HEADERS,
        }
        update_resp = session.post(
            update_api,
            data=update_data,
            headers=update_headers,
            allow_redirects=False,
            timeout=30,
            verify=False,
        )

        if update_resp.status_code in [200, 302]:
            print(f"✅ 文章链接更新成功（状态码：{update_resp.status_code}）")
            return True
        else:
            print(f"❌ 链接更新失败（状态码：{update_resp.status_code}）")
            return False
    except Exception as e:
        print(f"❌ 更新链接失败：{e}")
        import traceback

        traceback.print_exc()
        return False


def upload_and_verify_images(
    session: requests.Session, article_id: str, article_title: str
) -> bool:
    print_step("上传图片并验证", 5)
    if not img_mapping or not article_id:
        print("ℹ️ 无图片需要上传")
        return True

    ftp_success, _ = ftp_init_connection()
    if not ftp_success:
        print("❌ FTP连接失败，图片上传终止")
        rollback_article(session, article_id)
        return False

    try:
        remote_dir = f"/{article_id}/"
        print(f"\n📤 开始上传图片到 /{article_id}/ 目录（共{len(img_mapping)}张）...")

        all_upload_success = True
        for local_path, img_info in img_mapping.items():
            if not ftp_upload_file_with_verify(
                local_path, remote_dir, img_info["new_filename"]
            ):
                all_upload_success = False

        batch_verify_success, fail_files = ftp_batch_verify_files(
            remote_dir, img_mapping
        )
        if not batch_verify_success:
            print(f"❌ 图片批量验证失败：{fail_files}")
            rollback_ftp_files(remote_dir)
            rollback_article(session, article_id)
            return False

        if not update_article_img_links(session, article_id, article_title):
            print(f"⚠️ 链接更新失败，可手动编辑修正")

        print("✅ 图片上传并验证成功")
        return True
    except Exception as e:
        print(f"❌ 图片上传失败：{e}")
        import traceback

        traceback.print_exc()
        if article_id:
            rollback_ftp_files(f"/{article_id}/")
            rollback_article(session, article_id)
        return False
    finally:
        ftp_close_connection()


# ========== 6. 关闭并释放Session（完全保留） ==========
def release_resources(session: requests.Session):
    print_step("关闭并释放Session", 6)
    try:
        session.close()
        print("✅ Session已释放")
    except Exception as e:
        print(f"⚠️ 释放Session异常：{e}")
    ftp_close_connection()


# ========== 批量文件处理（完全保留） ==========
def select_files_to_publish(folder_path: str) -> list[str]:
    md_files = []
    for file in os.listdir(folder_path):
        if file.lower().endswith(".md"):
            md_files.append(os.path.join(folder_path, file))
    md_files.sort()

    if not md_files:
        print(f"❌ 文件夹 {folder_path} 下无MD文件")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("📋 文件夹下的MD文件列表（按名称排序）")
    print("=" * 60)
    for idx, file in enumerate(md_files, 1):
        file_name = os.path.basename(file)
        print(f"   {idx}. {file_name}")
    print("=" * 60)
    print("提示：输入要发布的文件编号，支持格式：")
    print("   单个选择：1 3 5")
    print("   范围选择：1-3")
    print("   全部选择：all")

    while True:
        user_input = input("请输入选择（直接回车退出）：").strip()
        if not user_input:
            sys.exit(0)
        if user_input.lower() == "all":
            print(f"✅ 选择全部 {len(md_files)} 个文件")
            return md_files

        selected_nums = parse_user_selection(user_input, len(md_files))
        if selected_nums:
            selected_files = [md_files[num - 1] for num in selected_nums]
            print(f"\n✅ 已选择 {len(selected_files)} 个文件：")
            for file in selected_files:
                print(f"   - {os.path.basename(file)}")
            return selected_files
        else:
            print("❌ 无效选择，请重新输入！")


def process_selected_files(session: requests.Session, selected_files: list[str]):
    category_ids = select_categories()

    batch_stats["total"] = len(selected_files)
    print(f"\n✅ 开始发布 {len(selected_files)} 个文件...")
    for idx, file in enumerate(selected_files, 1):
        print(f"\n{'='*100}")
        print(f"📄 处理进度：{idx}/{len(selected_files)}")
        print(f"{'='*100}")
        if publish_single_file(session, file, category_ids):
            batch_stats["success"] += 1
        else:
            batch_stats["failed"] += 1
            batch_stats["failed_files"].append(file)
        human_delay(BATCH_DELAY, BATCH_DELAY)

    print("\n" + "=" * 100)
    print("📊 批量发布结果汇总")
    print("=" * 100)
    print(f"📝 总文件数：{batch_stats['total']}")
    print(f"✅ 成功数：{batch_stats['success']}")
    print(f"❌ 失败数：{batch_stats['failed']}")
    if batch_stats["failed_files"]:
        print(f"\n❌ 失败文件列表：")
        for file in batch_stats["failed_files"]:
            print(f"   - {os.path.basename(file)}")


def publish_single_file(
    session: requests.Session, md_file_path: str, category_ids: list[int]
) -> bool:
    reset_global_vars()
    try:
        with open(md_file_path, "r", encoding="utf-8") as f:
            raw_content = f.read()

        title = os.path.splitext(os.path.basename(md_file_path))[0]
        title = replace_space_char(title)
        print(f"✅ 文章标题：{title}")

        cleaned_content, process_success = clean_markdown_for_theme(
            raw_content, md_file_path
        )
        if not process_success:
            print(f"❌ 步骤3失败：格式清洗/图片处理失败")
            return False

        if not publish_article(session, title, cleaned_content, category_ids):
            print(f"❌ 步骤4失败：文章发布/验证失败")
            clean_local_img_dir(note_img_local_dir)
            return False

        if not upload_and_verify_images(session, article_id, title):
            print(f"❌ 步骤5失败：图片上传/验证失败")
            clean_local_img_dir(note_img_local_dir)
            return False

        clean_local_img_dir(note_img_local_dir)
        print(f"\n✅ 文件 {md_file_path} 全部步骤执行成功！")
        return True

    except Exception as e:
        print(f"❌ 文件处理异常：{e}")
        import traceback

        traceback.print_exc()
        if article_id:
            rollback_article(session, article_id)
            rollback_ftp_files(f"/{article_id}/")
        clean_local_img_dir(note_img_local_dir)
        return False


# ========== 主函数（完全保留） ==========
def main():
    print("=" * 80)
    print("🎯 Typecho 批量发布工具（YAML配置版）")
    print("✅ 特性：YAML多层插值 + 动态图片路径解析 + 仅批量选择文件")
    print("=" * 80)

    if len(sys.argv) != 2:
        print("❌ 使用方法：python script.py <MD文件夹路径>")
        print("   示例：python script.py 'D:/笔记/待发布'")
        sys.exit(1)

    target_path = sys.argv[1].strip("'\"")

    if not os.path.isdir(target_path):
        print(f"❌ 无效路径：{target_path}（必须是文件夹路径）")
        sys.exit(1)

    login_success, session = simulate_browser_login()
    if not login_success:
        print("\n❌ 登录验证失败，程序终止")
        sys.exit(1)

    crawl_categories(session)

    selected_files = select_files_to_publish(target_path)
    if not selected_files:
        release_resources(session)
        sys.exit(0)

    process_selected_files(session, selected_files)

    release_resources(session)
    print("\n🔌 所有连接已释放，批量处理完成！")


if __name__ == "__main__":
    main()
