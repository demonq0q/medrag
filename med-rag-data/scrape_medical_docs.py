#!/usr/bin/env python3
"""
MedRAG 医学知识库数据采集脚本
==============================
功能：
  1. 下载 PDF 格式的临床指南和药品说明书
  2. 爬取网页内容（默沙东诊疗手册、Mayo Clinic、NMPA 等）并转为 Markdown
  3. 自动保存到 raw/ 对应子目录

使用方法：
  pip install requests beautifulsoup4 html2text pdfplumber markdownify
  python scrape_medical_docs.py

注意：
  - 本脚本仅供教学科研使用，请遵守相关网站的 robots.txt 和使用条款
  - 脚本内置了请求间隔（2-5秒），避免给目标服务器造成负担
  - 部分网站可能需要代理才能访问
"""

import os
import re
import time
import json
import logging
import hashlib
from pathlib import Path
from urllib.parse import urlparse, urljoin
from datetime import datetime

import requests
from bs4 import BeautifulSoup

# ============================================================
# 配置区
# ============================================================

BASE_DIR = Path(__file__).parent  # med-rag-data/
RAW_DIR = BASE_DIR / "raw"

# 请求配置
REQUEST_TIMEOUT = 30          # 请求超时（秒）
REQUEST_DELAY_MIN = 2         # 请求间隔下限（秒）
REQUEST_DELAY_MAX = 5         # 请求间隔上限（秒）
MAX_RETRIES = 3               # 最大重试次数

# 请求头（模拟浏览器）
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
}

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(BASE_DIR / "scrape_log.txt", encoding="utf-8"),
    ]
)
logger = logging.getLogger(__name__)


# ============================================================
# 工具函数
# ============================================================

def ensure_dir(path: Path):
    """确保目录存在"""
    path.mkdir(parents=True, exist_ok=True)


def delay():
    """请求间隔，避免过快请求"""
    import random
    t = random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX)
    time.sleep(t)


def safe_filename(name: str, max_len: int = 80) -> str:
    """生成安全的文件名"""
    # 移除不安全字符
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', name)
    name = name.strip('. ')
    if len(name) > max_len:
        name = name[:max_len]
    return name or hashlib.md5(name.encode()).hexdigest()[:12]


def fetch_url(url: str, stream: bool = False) -> requests.Response:
    """带重试的 URL 请求"""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(
                url,
                headers=HEADERS,
                timeout=REQUEST_TIMEOUT,
                stream=stream,
                allow_redirects=True,
            )
            resp.raise_for_status()
            return resp
        except requests.RequestException as e:
            logger.warning(f"  请求失败 (第{attempt}次): {url} -> {e}")
            if attempt < MAX_RETRIES:
                delay()
            else:
                logger.error(f"  放弃请求: {url}")
                raise


def html_to_markdown(html_content: str) -> str:
    """将 HTML 转为 Markdown"""
    try:
        from markdownify import markdownify
        return markdownify(html_content, heading_style="ATX", strip=['img', 'script', 'style'])
    except ImportError:
        pass

    try:
        import html2text
        h = html2text.HTML2Text()
        h.ignore_links = False
        h.ignore_images = True
        h.ignore_emphasis = False
        h.body_width = 0
        return h.handle(html_content)
    except ImportError:
        pass

    # 最终回退：用 BeautifulSoup 提取纯文本
    soup = BeautifulSoup(html_content, 'html.parser')
    for tag in soup(['script', 'style', 'nav', 'footer', 'header']):
        tag.decompose()
    return soup.get_text(separator='\n', strip=True)


def clean_markdown(md: str) -> str:
    """清理 Markdown 内容"""
    # 移除多余空行
    md = re.sub(r'\n{4,}', '\n\n\n', md)
    # 移除行尾空白
    md = '\n'.join(line.rstrip() for line in md.splitlines())
    return md.strip()


# ============================================================
# PDF 下载
# ============================================================

def download_pdf(url: str, save_path: Path):
    """下载 PDF 文件"""
    if save_path.exists():
        logger.info(f"  已存在，跳过: {save_path.name}")
        return True

    ensure_dir(save_path.parent)
    logger.info(f"  下载 PDF: {save_path.name}")

    try:
        resp = fetch_url(url, stream=True)
        content_type = resp.headers.get('Content-Type', '')

        # 检查是否为 PDF
        first_bytes = resp.content[:5]
        if first_bytes != b'%PDF-' and 'pdf' not in content_type.lower():
            logger.warning(f"  非 PDF 内容，跳过: {url}")
            return False

        with open(save_path, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

        file_size = save_path.stat().st_size
        logger.info(f"  ✅ 保存成功: {save_path.name} ({file_size/1024:.1f} KB)")
        return True

    except Exception as e:
        logger.error(f"  ❌ 下载失败: {url} -> {e}")
        return False


# ============================================================
# 网页爬取
# ============================================================

def scrape_page(url: str, save_path: Path, title: str = None,
                content_selector: str = None,
                extra_metadata: dict = None):
    """
    爬取单个网页并保存为 Markdown

    参数:
        url: 目标 URL
        save_path: 保存路径
        title: 文档标题（为空则从页面提取）
        content_selector: CSS 选择器，定位正文区域（为空则自动检测）
        extra_metadata: 额外元数据
    """
    if save_path.exists():
        logger.info(f"  已存在，跳过: {save_path.name}")
        return True

    ensure_dir(save_path.parent)
    logger.info(f"  爬取网页: {url}")

    try:
        resp = fetch_url(url)
        resp.encoding = resp.apparent_encoding or 'utf-8'
        html = resp.text

        soup = BeautifulSoup(html, 'html.parser')

        # 提取标题
        if not title:
            title_tag = soup.find('title')
            title = title_tag.get_text(strip=True) if title_tag else urlparse(url).path.split('/')[-1]
            title = title.split('|')[0].split('-')[0].strip()

        # 提取正文
        if content_selector:
            # 尝试多个选择器，取内容最多的
            candidates = []
            for sel in content_selector.split(','):
                sel = sel.strip()
                try:
                    el = soup.select_one(sel)
                    if el:
                        candidates.append(el)
                except Exception:
                    pass
            if candidates:
                content_el = max(candidates, key=lambda el: len(el.get_text(strip=True)))
            else:
                content_el = soup.body or soup
        else:
            # 自动检测正文区域（兼容多种网站结构）
            content_el = (
                soup.find('article') or
                soup.find('main') or
                soup.find('div', class_=re.compile(r'layoutContainer')) or
                soup.find('div', class_=re.compile(r'(content|article|main|body|text)', re.I)) or
                soup.find('div', id=re.compile(r'(content|article|main)', re.I)) or
                soup.body or
                soup
            )

        # 移除无关元素
        for tag in content_el.find_all(['script', 'style', 'nav', 'footer',
                                         'aside', 'iframe', 'noscript']):
            tag.decompose()
        # 保守地移除广告/评论等div（仅匹配明确的无关class）
        for tag in content_el.find_all('div', class_=re.compile(
                r'^(comment|sidebar|advertisement|share-buttons|breadcrumb)', re.I)):
            tag.decompose()

        # 转为 Markdown
        md_content = html_to_markdown(str(content_el))
        md_content = clean_markdown(md_content)

        # 添加元数据头
        metadata_lines = [
            f"---",
            f"source_url: {url}",
            f"title: \"{title}\"",
            f"scrape_date: {datetime.now().strftime('%Y-%m-%d')}",
        ]
        if extra_metadata:
            for k, v in extra_metadata.items():
                metadata_lines.append(f"{k}: \"{v}\"")
        metadata_lines.append(f"---\n")

        final_content = '\n'.join(metadata_lines) + f"# {title}\n\n{md_content}"

        with open(save_path, 'w', encoding='utf-8') as f:
            f.write(final_content)

        logger.info(f"  ✅ 保存成功: {save_path.name} ({len(md_content)} 字符)")
        return True

    except Exception as e:
        logger.error(f"  ❌ 爬取失败: {url} -> {e}")
        return False


# ============================================================
# 任务定义：所有要采集的目标
# ============================================================

def get_pdf_tasks():
    """PDF 下载任务列表"""
    return [
        # === 临床指南 ===
        {
            "url": "https://www.huasan.net/wp-content/uploads/2025/10/%E4%B8%AD%E5%9B%BD%E7%B3%96%E5%B0%BF%E7%97%85%E9%98%B2%E6%B2%BB%E6%8C%87%E5%8D%97%EF%BC%882024%E7%89%88%EF%BC%89.pdf",
            "save_dir": RAW_DIR / "guidelines" / "endocrinology",
            "filename": "中国糖尿病防治指南2024版_华山医院.pdf",
        },
        {
            "url": "https://www.scdc.sh.cn/shjk/shjk/upload/202303/0306_165758_510.pdf",
            "save_dir": RAW_DIR / "guidelines" / "endocrinology",
            "filename": "中国2型糖尿病防治指南2020年版.pdf",
        },
        {
            "url": "https://cjournal.hep.com.cn/0253-3626/CN/PDF/10.13406/j.cnki.cyxb.003749",
            "save_dir": RAW_DIR / "guidelines" / "endocrinology",
            "filename": "中国糖尿病防治指南2024版_解读.pdf",
        },
        {
            "url": "https://99homecare.com/files/22024.pdf",
            "save_dir": RAW_DIR / "guidelines" / "endocrinology",
            "filename": "中国2型糖尿病运动治疗指南2024版.pdf",
        },
        {
            # 糖尿病指南 PDF（中华医学会）
            "url": "https://diab.cma.org.cn/uploadfile/chinaguideline.pdf",
            "save_dir": RAW_DIR / "guidelines" / "endocrinology",
            "filename": "中国2型糖尿病防治指南_CMA.pdf",
        },
    ]


def get_webpage_tasks():
    """网页爬取任务列表"""
    tasks = []

    # ========================================
    # 1. 默沙东诊疗手册 - 内分泌科
    # ========================================
    msd_base = RAW_DIR / "disease_entries" / "msd_manual"
    ensure_dir(msd_base)

    msd_pages = [
        ("2型糖尿病_大众版",
         "https://www.msdmanuals.cn/home/hormonal-and-metabolic-disorders/diabetes-mellitus-and-low-blood-sugar-hypoglycemia/type-2-diabetes-mellitus",
         {"doc_type": "disease_entry", "source": "默沙东诊疗手册_大众版", "department": "内分泌科"}),

        ("2型糖尿病_专业版",
         "https://www.msdmanuals.cn/professional/endocrine-and-metabolic-disorders/diabetes-mellitus-and-hypoglycemia/type-2-diabetes-mellitus",
         {"doc_type": "disease_entry", "source": "默沙东诊疗手册_专业版", "department": "内分泌科"}),

        ("1型糖尿病_大众版",
         "https://www.msdmanuals.cn/home/hormonal-and-metabolic-disorders/diabetes-mellitus-and-low-blood-sugar-hypoglycemia/type-1-diabetes-mellitus-dm",
         {"doc_type": "disease_entry", "source": "默沙东诊疗手册_大众版", "department": "内分泌科"}),

        ("1型糖尿病_专业版",
         "https://www.msdmanuals.cn/professional/endocrine-and-metabolic-disorders/diabetes-mellitus-and-hypoglycemia/type-1-diabetes-mellitus",
         {"doc_type": "disease_entry", "source": "默沙东诊疗手册_专业版", "department": "内分泌科"}),

        ("糖尿病概述",
         "https://www.msdmanuals.cn/home/hormonal-and-metabolic-disorders/diabetes-mellitus-and-low-blood-sugar-hypoglycemia/overview-of-diabetes-mellitus",
         {"doc_type": "disease_entry", "source": "默沙东诊疗手册", "department": "内分泌科"}),

        ("糖尿病的药物治疗",
         "https://www.msdmanuals.cn/home/hormonal-and-metabolic-disorders/diabetes-mellitus-and-low-blood-sugar-hypoglycemia/medication-treatment-of-diabetes-mellitus",
         {"doc_type": "drug_overview", "source": "默沙东诊疗手册", "department": "内分泌科"}),

        ("糖尿病的长期并发症",
         "https://www.msdmanuals.cn/home/hormonal-and-metabolic-disorders/diabetes-mellitus-and-low-blood-sugar-hypoglycemia/long-term-complications-of-diabetes-mellitus",
         {"doc_type": "complications", "source": "默沙东诊疗手册", "department": "内分泌科"}),

        ("糖尿病的急性并发症",
         "https://www.msdmanuals.cn/home/hormonal-and-metabolic-disorders/diabetes-mellitus-and-low-blood-sugar-hypoglycemia/acute-complications-of-diabetes-mellitus",
         {"doc_type": "complications", "source": "默沙东诊疗手册", "department": "内分泌科"}),

        ("低血糖_专业版",
         "https://www.msdmanuals.cn/professional/endocrine-and-metabolic-disorders/diabetes-mellitus-and-hypoglycemia/hypoglycemia",
         {"doc_type": "disease_entry", "source": "默沙东诊疗手册_专业版", "department": "内分泌科"}),
    ]

    for title, url, meta in msd_pages:
        tasks.append({
            "url": url,
            "save_path": msd_base / f"{safe_filename(title)}.md",
            "title": title,
            "content_selector": ".layoutContainer, main, article, .content, #content",
            "extra_metadata": meta,
        })

    # ========================================
    # 2. 默沙东诊疗手册 - 心血管科
    # ========================================
    msd_cardio = RAW_DIR / "disease_entries" / "msd_manual"

    msd_cardio_pages = [
        ("高血压_专业版",
         "https://www.msdmanuals.cn/professional/cardiovascular-disorders/hypertension/hypertension",
         {"doc_type": "disease_entry", "source": "默沙东诊疗手册_专业版", "department": "心内科"}),

        ("高脂血症_专业版",
         "https://www.msdmanuals.cn/professional/endocrine-and-metabolic-disorders/lipid-disorders/hyperlipidemia",
         {"doc_type": "disease_entry", "source": "默沙东诊疗手册_专业版", "department": "心内科"}),

        ("心力衰竭_专业版",
         "https://www.msdmanuals.cn/professional/cardiovascular-disorders/heart-failure/heart-failure-hf",
         {"doc_type": "disease_entry", "source": "默沙东诊疗手册_专业版", "department": "心内科"}),

        ("心房颤动_专业版",
         "https://www.msdmanuals.cn/professional/cardiovascular-disorders/arrhythmias/atrial-fibrillation-af",
         {"doc_type": "disease_entry", "source": "默沙东诊疗手册_专业版", "department": "心内科"}),
    ]

    for title, url, meta in msd_cardio_pages:
        tasks.append({
            "url": url,
            "save_path": msd_cardio / f"{safe_filename(title)}.md",
            "title": title,
            "content_selector": ".layoutContainer, main, article, .content, #content",
            "extra_metadata": meta,
        })

    # ========================================
    # 3. 默沙东诊疗手册 - 呼吸科/消化科
    # ========================================
    msd_other_pages = [
        ("支气管哮喘_专业版",
         "https://www.msdmanuals.cn/professional/pulmonary-disorders/asthma-and-related-disorders/asthma",
         {"doc_type": "disease_entry", "source": "默沙东诊疗手册_专业版", "department": "呼吸科"},
         "respiratory"),

        ("COPD_专业版",
         "https://www.msdmanuals.cn/professional/pulmonary-disorders/chronic-obstructive-pulmonary-disease-and-related-disorders/chronic-obstructive-pulmonary-disease-copd",
         {"doc_type": "disease_entry", "source": "默沙东诊疗手册_专业版", "department": "呼吸科"},
         "respiratory"),

        ("胃炎_专业版",
         "https://www.msdmanuals.cn/professional/gastrointestinal-disorders/gastritis-and-peptic-ulcer-disease/gastritis",
         {"doc_type": "disease_entry", "source": "默沙东诊疗手册_专业版", "department": "消化科"},
         "gastroenterology"),

        ("胃食管反流病_专业版",
         "https://www.msdmanuals.cn/professional/gastrointestinal-disorders/esophageal-and-swallowing-disorders/gastroesophageal-reflux-disease-gerd",
         {"doc_type": "disease_entry", "source": "默沙东诊疗手册_专业版", "department": "消化科"},
         "gastroenterology"),
    ]

    for title, url, meta, subdir in msd_other_pages:
        tasks.append({
            "url": url,
            "save_path": msd_base / f"{safe_filename(title)}.md",
            "title": title,
            "content_selector": ".layoutContainer, main, article, .content, #content",
            "extra_metadata": meta,
        })

    # ========================================
    # 4. Mayo Clinic 中文版
    # ========================================
    mayo_base = RAW_DIR / "disease_entries" / "mayo_clinic"
    ensure_dir(mayo_base)

    mayo_pages = [
        ("2型糖尿病_Mayo",
         "https://www.mayoclinic.org/zh-hans/diseases-conditions/type-2-diabetes/symptoms-causes/syc-20351193",
         {"doc_type": "disease_entry", "source": "Mayo Clinic", "department": "内分泌科"}),

        ("高血压_Mayo",
         "https://www.mayoclinic.org/zh-hans/diseases-conditions/high-blood-pressure/symptoms-causes/syc-20373410",
         {"doc_type": "disease_entry", "source": "Mayo Clinic", "department": "心内科"}),

        ("高血压诊断与治疗_Mayo",
         "https://www.mayoclinic.org/zh-hans/diseases-conditions/high-blood-pressure/diagnosis-treatment/drc-20373417",
         {"doc_type": "disease_entry", "source": "Mayo Clinic", "department": "心内科"}),

        ("阿司匹林疗法_Mayo",
         "https://www.mayoclinic.org/zh-hans/diseases-conditions/heart-disease/in-depth/daily-aspirin-therapy/art-20046797",
         {"doc_type": "drug_overview", "source": "Mayo Clinic", "department": "心内科"}),

        ("华法林副作用_Mayo",
         "https://www.mayoclinic.org/zh-hans/diseases-conditions/deep-vein-thrombosis/in-depth/warfarin-side-effects/art-20047592",
         {"doc_type": "drug_safety", "source": "Mayo Clinic", "department": "心内科"}),

        ("他汀类药物副作用_Mayo",
         "https://www.mayoclinic.org/zh-hans/diseases-conditions/high-blood-cholesterol/in-depth/statin-side-effects/art-20046013",
         {"doc_type": "drug_safety", "source": "Mayo Clinic", "department": "心内科"}),

        ("高血压危害_Mayo",
         "https://www.mayoclinic.org/zh-hans/diseases-conditions/high-blood-pressure/in-depth/high-blood-pressure/art-20045868",
         {"doc_type": "disease_entry", "source": "Mayo Clinic", "department": "心内科"}),

        ("控制高血压非药物方法_Mayo",
         "https://www.mayoclinic.org/zh-hans/diseases-conditions/high-blood-pressure/in-depth/high-blood-pressure/art-20046974",
         {"doc_type": "lifestyle", "source": "Mayo Clinic", "department": "心内科"}),

        ("继发性高血压_Mayo",
         "https://www.mayoclinic.org/zh-hans/diseases-conditions/secondary-hypertension/symptoms-causes/syc-20350679",
         {"doc_type": "disease_entry", "source": "Mayo Clinic", "department": "心内科"}),
    ]

    for title, url, meta in mayo_pages:
        tasks.append({
            "url": url,
            "save_path": mayo_base / f"{safe_filename(title)}.md",
            "title": title,
            "content_selector": "main, article, #main-content, .main-content",
            "extra_metadata": meta,
        })

    # ========================================
    # 5. NMPA 药品说明书
    # ========================================
    drug_base = RAW_DIR / "drug_labels"
    ensure_dir(drug_base)

    nmpa_drugs = [
        ("盐酸二甲双胍肠溶胶囊说明书_NMPA",
         "https://www.nmpa.gov.cn/wwwroot/hysms3/075.htm",
         {"doc_type": "drug_label", "source": "NMPA", "drug_name": "盐酸二甲双胍"}),
    ]

    for title, url, meta in nmpa_drugs:
        tasks.append({
            "url": url,
            "save_path": drug_base / f"{safe_filename(title)}.md",
            "title": title,
            "content_selector": "main, article, .content, #content, body",
            "extra_metadata": meta,
        })

    # ========================================
    # 6. 清华大学医院药品说明书
    # ========================================
    thu_drugs = [
        ("盐酸二甲双胍片_清华医院",
         "https://xyy.tsinghua.edu.cn/info/1055/6604.htm",
         {"doc_type": "drug_label", "source": "清华大学医院", "drug_name": "二甲双胍"}),

        ("达格列净片_清华医院",
         "https://xyy.tsinghua.edu.cn/info/1055/6602.htm",
         {"doc_type": "drug_label", "source": "清华大学医院", "drug_name": "达格列净"}),

        ("德谷胰岛素利拉鲁肽注射液_清华医院",
         "https://xyy.tsinghua.edu.cn/info/1055/6603.htm",
         {"doc_type": "drug_label", "source": "清华大学医院", "drug_name": "德谷胰岛素利拉鲁肽"}),
    ]

    for title, url, meta in thu_drugs:
        tasks.append({
            "url": url,
            "save_path": drug_base / f"{safe_filename(title)}.md",
            "title": title,
            "content_selector": "main, article, .v_news_content, .wp_articlecontent, #vsb_content, body",
            "extra_metadata": meta,
        })

    return tasks


# ============================================================
# 额外爬取：自动发现默沙东诊疗手册更多疾病页面
# ============================================================

def discover_msd_pages():
    """
    从默沙东诊疗手册首页自动发现更多疾病页面
    返回爬取任务列表
    """
    tasks = []
    msd_home = "https://www.msdmanuals.cn/professional"
    msd_base = RAW_DIR / "disease_entries" / "msd_manual"

    # 预定义要爬取的科室和关键词
    target_sections = [
        # 内分泌科
        ("endocrine-and-metabolic-disorders", "内分泌科"),
        # 心血管科
        ("cardiovascular-disorders", "心内科"),
        # 呼吸科
        ("pulmonary-disorders", "呼吸科"),
        # 消化科
        ("gastrointestinal-disorders", "消化科"),
        # 神经内科
        ("neurologic-disorders", "神经内科"),
        # 血液科
        ("hematology-oncology", "血液科"),
        # 肾内科
        ("genitourinary-disorders", "肾内科"),
        # 精神科
        ("psychiatric-disorders", "精神科"),
        # 肌肉骨骼
        ("musculoskeletal-and-connective-tissue-disorders", "骨科"),
        # 感染
        ("infections", "感染科"),
    ]

    logger.info("🔍 正在从默沙东诊疗手册发现更多疾病页面...")

    for section_path, department in target_sections:
        section_url = f"{msd_home}/{section_path}"
        try:
            resp = fetch_url(section_url)
            resp.encoding = resp.apparent_encoding or 'utf-8'
            soup = BeautifulSoup(resp.text, 'html.parser')

            # 查找该科室下的所有疾病链接
            links = soup.find_all('a', href=re.compile(rf'/{section_path}/[^/]+/[^/]+'))
            seen_urls = set()

            for link in links[:15]:  # 每个科室最多取15个
                href = link.get('href', '')
                full_url = urljoin(section_url, href)

                # 去除锚点/fragment (#xxx), 避免重复爬取同一页面的子章节
                url_no_fragment = full_url.split('#')[0]

                if url_no_fragment in seen_urls:
                    continue
                seen_urls.add(url_no_fragment)

                link_text = link.get_text(strip=True)
                if not link_text or len(link_text) < 2:
                    continue

                title = f"{link_text}_专业版"
                save_name = safe_filename(f"{link_text}_MSD专业版_{department}")

                tasks.append({
                    "url": url_no_fragment,
                    "save_path": msd_base / f"{save_name}.md",
                    "title": title,
                    "content_selector": ".layoutContainer, main, article, .content, #content",
                    "extra_metadata": {
                        "doc_type": "disease_entry",
                        "source": "默沙东诊疗手册_专业版",
                        "department": department,
                        "auto_discovered": "true",
                    },
                })

            logger.info(f"  {department}: 发现 {len(seen_urls)} 个页面")
            delay()

        except Exception as e:
            logger.warning(f"  {department}: 发现失败 -> {e}")

    return tasks


# ============================================================
# 主执行逻辑
# ============================================================

def run_pdf_downloads():
    """执行 PDF 下载"""
    logger.info("=" * 60)
    logger.info("📥 开始 PDF 下载任务")
    logger.info("=" * 60)

    tasks = get_pdf_tasks()
    success = 0
    fail = 0

    for i, task in enumerate(tasks, 1):
        url = task["url"]
        save_path = task["save_dir"] / task["filename"]
        logger.info(f"\n[{i}/{len(tasks)}] {task['filename']}")

        try:
            if download_pdf(url, save_path):
                success += 1
            else:
                fail += 1
        except Exception as e:
            logger.error(f"  ❌ 异常: {e}")
            fail += 1

        delay()

    logger.info(f"\n📥 PDF 下载完成: 成功 {success}, 失败 {fail}")
    return success, fail


def run_webpage_scraping():
    """执行网页爬取"""
    logger.info("=" * 60)
    logger.info("🌐 开始网页爬取任务")
    logger.info("=" * 60)

    tasks = get_webpage_tasks()
    success = 0
    fail = 0
    skip = 0

    for i, task in enumerate(tasks, 1):
        url = task["url"]
        save_path = task["save_path"]
        title = task.get("title", "")

        if save_path.exists():
            logger.info(f"[{i}/{len(tasks)}] 已存在，跳过: {save_path.name}")
            skip += 1
            continue

        logger.info(f"\n[{i}/{len(tasks)}] {title}")

        try:
            if scrape_page(
                url=url,
                save_path=save_path,
                title=title,
                content_selector=task.get("content_selector"),
                extra_metadata=task.get("extra_metadata"),
            ):
                success += 1
            else:
                fail += 1
        except Exception as e:
            logger.error(f"  ❌ 异常: {e}")
            fail += 1

        delay()

    logger.info(f"\n🌐 网页爬取完成: 成功 {success}, 失败 {fail}, 跳过 {skip}")
    return success, fail


def run_auto_discovery():
    """自动发现并爬取默沙东更多页面"""
    logger.info("=" * 60)
    logger.info("🔍 开始自动发现任务（默沙东诊疗手册）")
    logger.info("=" * 60)

    tasks = discover_msd_pages()
    success = 0
    fail = 0
    skip = 0

    for i, task in enumerate(tasks, 1):
        save_path = task["save_path"]

        if save_path.exists():
            skip += 1
            continue

        logger.info(f"\n[{i}/{len(tasks)}] {task.get('title', '')}")

        try:
            if scrape_page(
                url=task["url"],
                save_path=save_path,
                title=task.get("title"),
                content_selector=task.get("content_selector"),
                extra_metadata=task.get("extra_metadata"),
            ):
                success += 1
            else:
                fail += 1
        except Exception as e:
            logger.error(f"  ❌ 异常: {e}")
            fail += 1

        delay()

    logger.info(f"\n🔍 自动发现完成: 成功 {success}, 失败 {fail}, 跳过 {skip}")
    return success, fail


def generate_report(pdf_result, web_result, discover_result):
    """生成采集报告"""
    report_path = BASE_DIR / "scrape_report.json"

    # 统计所有已保存的文件
    all_files = []
    for root, dirs, files in os.walk(RAW_DIR):
        for f in files:
            fpath = Path(root) / f
            all_files.append({
                "path": str(fpath.relative_to(BASE_DIR)),
                "size_kb": round(fpath.stat().st_size / 1024, 1),
                "type": f.suffix.lstrip('.'),
            })

    report = {
        "scrape_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "summary": {
            "pdf_downloads": {"success": pdf_result[0], "fail": pdf_result[1]},
            "webpage_scraping": {"success": web_result[0], "fail": web_result[1]},
            "auto_discovery": {"success": discover_result[0], "fail": discover_result[1]},
        },
        "total_files_collected": len(all_files),
        "files": sorted(all_files, key=lambda x: x["path"]),
    }

    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    logger.info(f"\n📊 采集报告已保存: {report_path}")
    logger.info(f"📊 共采集 {len(all_files)} 个文件")


# ============================================================
# 入口
# ============================================================

def main():
    logger.info("🚀 MedRAG 医学知识库数据采集脚本启动")
    logger.info(f"📁 数据保存目录: {RAW_DIR}")
    logger.info(f"⏱️  请求间隔: {REQUEST_DELAY_MIN}-{REQUEST_DELAY_MAX} 秒")
    logger.info("")

    # 确保目录结构存在
    ensure_dir(RAW_DIR)

    # Phase 1: PDF 下载
    pdf_result = run_pdf_downloads()

    # Phase 2: 网页爬取（预定义URL）
    web_result = run_webpage_scraping()

    # Phase 3: 自动发现默沙东更多页面
    discover_result = run_auto_discovery()

    # 生成报告
    generate_report(pdf_result, web_result, discover_result)

    logger.info("\n" + "=" * 60)
    logger.info("🎉 全部采集任务完成！")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
