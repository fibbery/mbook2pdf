#!/usr/bin/env python3
"""
通用 mdBook 网站爬虫 - 自动爬取并生成 PDF

支持所有 mdBook 构建的文档站点，如:
- https://rustwiki.org/zh-CN/book/
- https://rustwiki.org/zh-CN/rust-by-example/
- https://colobu.com/rust100/
- 以及其他 mdBook 站点

使用方法:
    pip install requests beautifulsoup4 weasyprint
    python mbook2pdf.py <URL>

示例:
    python mbook2pdf.py https://rustwiki.org/zh-CN/book/
    python mbook2pdf.py https://colobu.com/rust100/

macOS 额外依赖:
    brew install pango

Ubuntu 额外依赖:
    sudo apt install libpango-1.0-0 libpangocairo-1.0-0
"""

import argparse
import os
import re
import sys
import time
from collections import OrderedDict
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

# 常量定义
DEFAULT_DELAY = 0.3
DEFAULT_TIMEOUT = 30
DEFAULT_REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
}

# CSS 选择器配置
SIDEBAR_SELECTORS = [
    ('nav', {'class_': 'sidebar'}),
    ('div', {'class_': 'sidebar'}),
    ('div', {'id': 'sidebar'}),
    ('nav', {'class_': 'nav-chapters'}),
    ('ol', {'class_': 'chapter'}),
    ('ul', {'class_': 'chapter'}),
]

MAIN_CONTENT_SELECTORS = [
    ('main', {}),
    ('div', {'class_': 'content'}),
    ('div', {'id': 'content'}),
    ('article', {}),
    ('div', {'class_': 'page-wrapper'}),
]

# 需要移除的元素配置
REMOVE_TAGS = ['nav', 'header', 'footer', 'script', 'style', 'noscript']

REMOVE_CLASSES = [
    'nav-wrapper', 'nav-chapters', 'sidebar', 'menu-bar',
    'nav-wide-wrapper', 'sidetoc', 'pagetoc', 'mobile-nav-chapters',
    'buttons', 'search-wrapper', 'searchresults-outer', 'searchresults-header',
    'theme-popup', 'theme-toggle', 'search-toggle', 'print-button',
    'git-link', 'edit-button', 'back-to-top', 'chapter-nav'
]

REMOVE_IDS = [
    'sidebar', 'menu-bar', 'search-wrapper', 'searchresults-outer',
    'theme-toggle', 'search-toggle', 'searchbar', 'searchresults'
]

# 文件名安全字符正则
FILENAME_UNSAFE_CHARS = r'[<>:"/\\|?*]'


class MdBookCrawler:
    """mdBook 网站爬虫类，用于爬取并生成 PDF"""
    
    def __init__(self, base_url: str, output_dir: Optional[str] = None, delay: float = DEFAULT_DELAY):
        """
        初始化爬虫
        
        Args:
            base_url: mdBook 网站的基础 URL
            output_dir: 输出目录，如果为 None 则自动生成
            delay: 请求间隔秒数
        """
        # 确保 URL 以 / 结尾
        self.base_url = base_url if base_url.endswith('/') else base_url + '/'
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_REQUEST_HEADERS)
        
        # 从 URL 提取站点名称作为输出目录
        self.output_dir = output_dir or self._generate_output_dir(base_url)
        self.book_title: Optional[str] = None
        self.chapters: OrderedDict[str, str] = OrderedDict()
        self.pages: List[Dict[str, str]] = []
    
    @staticmethod
    def _generate_output_dir(base_url: str) -> str:
        """从 URL 生成输出目录名"""
        parsed = urlparse(base_url)
        path_parts = [p for p in parsed.path.split('/') if p]
        site_name = path_parts[-1] if path_parts else parsed.netloc.replace('.', '_')
        return f"./{site_name}_pdf"
    
    def fetch_page(self, url: str) -> Optional[str]:
        """
        获取页面内容
        
        Args:
            url: 要获取的页面 URL
            
        Returns:
            页面 HTML 内容，失败返回 None
        """
        try:
            response = self.session.get(url, timeout=DEFAULT_TIMEOUT)
            response.encoding = 'utf-8'
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            print(f"\n  ⚠️  获取失败 {url}: {e}")
            return None
    
    def _extract_book_title(self, soup: BeautifulSoup) -> str:
        """从 HTML 中提取书籍标题"""
        # 方法1: 从菜单标题或侧边栏 logo 获取
        title_elem = soup.find('h1', class_='menu-title') or soup.find('a', class_='sidebar-logo')
        if title_elem:
            title = title_elem.get_text(strip=True)
            if title:
                return title
        
        # 方法2: 从页面 title 标签获取
        title_tag = soup.find('title')
        if title_tag:
            title = title_tag.get_text(strip=True).split(' - ')[0].strip()
            if title:
                return title
        
        # 默认标题
        return "mdBook 文档"
    
    def _find_sidebar(self, soup: BeautifulSoup):
        """查找侧边栏元素"""
        for tag, attrs in SIDEBAR_SELECTORS:
            sidebar = soup.find(tag, **attrs)
            if sidebar:
                return sidebar
        return None
    
    def _is_valid_chapter_link(self, href: str) -> bool:
        """判断是否为有效的章节链接"""
        # 跳过锚点链接
        if href.startswith('#'):
            return False
        
        # 跳过外部链接
        if href.startswith('http') and self.base_url not in href:
            return False
        
        # 跳过非 HTML 链接（有扩展名的文件）
        if href and not href.endswith('.html') and not href.endswith('/'):
            last_part = href.split('/')[-1]
            if '.' in last_part:
                return False
        
        return True
    
    def _normalize_url(self, href: str) -> str:
        """规范化 URL"""
        if href.startswith('http'):
            full_url = href
        else:
            full_url = urljoin(self.base_url, href)
        
        # 移除锚点
        full_url = full_url.split('#')[0]
        return full_url
    
    def _extract_chapters_from_sidebar(self, sidebar, soup: BeautifulSoup) -> OrderedDict[str, str]:
        """从侧边栏提取章节链接"""
        chapters = OrderedDict()
        
        for a in sidebar.find_all('a', href=True):
            href = a.get('href', '')
            
            if not self._is_valid_chapter_link(href):
                continue
            
            title = a.get_text(strip=True)
            if not title:
                continue
            
            full_url = self._normalize_url(href)
            
            # 确保 URL 属于同一站点
            if urlparse(full_url).netloc == urlparse(self.base_url).netloc:
                if full_url not in chapters:
                    chapters[full_url] = title
        
        return chapters
    
    def _extract_chapters_from_links(self, soup: BeautifulSoup) -> OrderedDict[str, str]:
        """从页面所有链接中提取章节（备用方法）"""
        chapters = OrderedDict()
        
        for a in soup.find_all('a', href=True):
            href = a.get('href', '')
            if href.endswith('.html') and not href.startswith('http'):
                full_url = self._normalize_url(href)
                title = a.get_text(strip=True)
                if title and full_url not in chapters:
                    chapters[full_url] = title
        
        return chapters
    
    def parse_sidebar(self, html: str) -> OrderedDict[str, str]:
        """
        解析侧边栏获取所有章节链接
        
        Args:
            html: 首页 HTML 内容
            
        Returns:
            章节字典，key 为 URL，value 为标题
        """
        soup = BeautifulSoup(html, 'html.parser')
        
        # 提取书籍标题
        self.book_title = self._extract_book_title(soup)
        
        chapters = OrderedDict()
        
        # 方法1: 从侧边栏提取
        sidebar = self._find_sidebar(soup)
        if sidebar:
            chapters = self._extract_chapters_from_sidebar(sidebar, soup)
        
        # 方法2: 如果侧边栏解析失败，从页面链接中提取
        if not chapters:
            chapters = self._extract_chapters_from_links(soup)
        
        # 确保首页在列表中
        if self.base_url not in chapters:
            chapters[self.base_url] = self.book_title
            chapters.move_to_end(self.base_url, last=False)
        
        return chapters
    
    def _find_main_content(self, soup: BeautifulSoup):
        """查找主内容区域"""
        for tag, attrs in MAIN_CONTENT_SELECTORS:
            main = soup.find(tag, **attrs)
            if main:
                return main
        return soup.find('body')
    
    def _remove_unwanted_elements(self, main):
        """移除不需要的元素"""
        # 移除指定标签
        for tag in REMOVE_TAGS:
            for elem in main.find_all(tag):
                elem.decompose()
        
        # 移除指定 class 的元素
        for class_name in REMOVE_CLASSES:
            for elem in main.find_all(class_=class_name):
                elem.decompose()
        
        # 移除指定 id 的元素
        for id_name in REMOVE_IDS:
            elem = main.find(id=id_name)
            if elem:
                elem.decompose()
        
        # 移除 play 按钮等交互元素
        for elem in main.find_all(['button', 'i'], class_=lambda x: x and (
            'play' in x.lower() or 'copy' in x.lower() or 'fa-' in x
        )):
            elem.decompose()
    
    def _process_headings(self, main):
        """处理标题：降级并禁用书签"""
        # 移除页面原有的第一个 h1 标题（我们会在外层添加章节标题）
        first_h1 = main.find('h1')
        if first_h1:
            first_h1.decompose()
        
        # 将内容中的标题降级，避免与章节标题冲突，同时禁用它们的书签
        # h1 -> h2, h2 -> h3, h3 -> h4 等
        for i in range(5, 0, -1):  # 从 h5 到 h1
            for h in main.find_all(f'h{i}'):
                h.name = f'h{min(i+1, 6)}'
                # 添加 class 禁用书签
                existing_classes = h.get('class', [])
                if isinstance(existing_classes, str):
                    existing_classes = [existing_classes]
                h['class'] = existing_classes + ['no-bookmark']
    
    def _fix_media_urls(self, main):
        """修复媒体资源 URL"""
        # 修复图片路径
        for img in main.find_all('img'):
            src = img.get('src', '')
            if src and not src.startswith(('http', 'data:')):
                img['src'] = urljoin(self.base_url, src)
        
        # 修复链接
        for a in main.find_all('a'):
            href = a.get('href', '')
            if href and not href.startswith(('http', '#', 'mailto:', 'javascript:')):
                a['href'] = urljoin(self.base_url, href)
    
    def extract_content(self, html: str) -> str:
        """
        提取页面主要内容
        
        Args:
            html: 页面 HTML 内容
            
        Returns:
            提取后的 HTML 内容
        """
        soup = BeautifulSoup(html, 'html.parser')
        main = self._find_main_content(soup)
        
        if not main:
            return ""
        
        # 清理内容
        self._remove_unwanted_elements(main)
        self._process_headings(main)
        self._fix_media_urls(main)
        
        return str(main)
    
    def _display_progress(self, current: int, total: int, title: str):
        """显示爬取进度"""
        progress_bar_length = 30
        filled = current * progress_bar_length // total
        progress = "█" * filled + "░" * (progress_bar_length - filled)
        display_title = title[:35] if len(title) <= 35 else title[:32] + "..."
        print(f"\r  [{progress}] {current}/{total} {display_title:<35}", end="", flush=True)
    
    def crawl(self) -> bool:
        """
        爬取所有页面
        
        Returns:
            成功返回 True，失败返回 False
        """
        print(f"\n📖 正在获取首页: {self.base_url}")
        
        index_html = self.fetch_page(self.base_url)
        if not index_html:
            print("❌ 无法获取首页")
            return False
        
        print("📋 正在解析目录结构...")
        self.chapters = self.parse_sidebar(index_html)
        
        if not self.chapters:
            print("❌ 无法解析目录结构")
            return False
        
        print(f"✅ 找到 {len(self.chapters)} 个页面")
        print(f"📚 书籍标题: {self.book_title}\n")
        
        pages = []
        total = len(self.chapters)
        
        for i, (url, title) in enumerate(self.chapters.items(), 1):
            self._display_progress(i, total, title)
            
            html = self.fetch_page(url)
            if html:
                content = self.extract_content(html)
                pages.append({
                    'url': url,
                    'title': title,
                    'content': content
                })
            
            time.sleep(self.delay)
        
        print()  # 换行
        print(f"\n✅ 成功爬取 {len(pages)} 个页面")
        
        self.pages = pages
        return True
    
    @staticmethod
    def _get_toc_level(title: str) -> int:
        """
        根据标题判断目录层级
        
        Args:
            title: 章节标题
            
        Returns:
            目录层级 (1-3)
        """
        # 检查是否以数字开头（如 "1. 入门" "1.1 安装" "1.1.1 详细"）
        match = re.match(r'^(\d+(?:\.\d+)*)', title)
        if match:
            num_part = match.group(1)
            dots = num_part.count('.')
            if dots == 0:
                return 1  # 主章节 如 "1. xxx"
            elif dots == 1:
                return 2  # 子章节 如 "1.1 xxx"
            else:
                return 3  # 更深层级
        return 1  # 默认为主章节
    
    @staticmethod
    def _get_css_styles() -> str:
        """获取 CSS 样式"""
        return '''        @page {
            size: A4;
            margin: 2cm 1.5cm;
            @bottom-center {
                content: counter(page);
                font-size: 10pt;
                color: #666;
            }
        }
        
        @page :first {
            @bottom-center { content: none; }
        }
        
        * { box-sizing: border-box; }
        
        body {
            font-family: "PingFang SC", "Microsoft YaHei", "Hiragino Sans GB", 
                         -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            max-width: 100%;
            margin: 0;
            padding: 20px 40px;
            line-height: 1.8;
            color: #2c3e50;
            font-size: 11pt;
            background: white;
        }
        
        /* 封面 */
        .cover {
            page-break-after: always;
            text-align: center;
            padding: 150px 20px 100px;
            min-height: 90vh;
        }
        
        .cover h1 {
            font-size: 36pt;
            color: #c0392b;
            margin-bottom: 20px;
            border: none;
            padding: 0;
        }
        
        .cover .logo {
            font-size: 80pt;
            margin: 40px 0;
        }
        
        .cover .source {
            font-size: 11pt;
            color: #95a5a6;
            margin-top: 60px;
        }
        
        /* 目录 */
        .toc {
            page-break-after: always;
            padding: 20px;
        }
        
        .toc h1 {
            text-align: center;
            color: #2c3e50;
            border: none;
            margin-bottom: 20px;
        }
        
        .toc-table {
            width: 100%;
            border: none;
            border-collapse: collapse;
        }
        
        .toc-table td {
            width: 50%;
            vertical-align: top;
            padding: 0 10px;
            border: none;
        }
        
        .toc-item {
            margin: 3px 0;
            color: #34495e;
            line-height: 1.5;
            font-size: 9pt;
        }
        
        .toc-item.level-1 {
            font-weight: bold;
            margin-top: 10px;
            font-size: 10pt;
            color: #2c3e50;
        }
        
        .toc-item.level-2 {
            padding-left: 12px;
        }
        
        .toc-item.level-3 {
            padding-left: 24px;
            font-size: 8pt;
            color: #7f8c8d;
        }
        
        /* PDF 书签层级设置 */
        .chapter-title {
            string-set: chapter-title content();
        }
        
        h1.bookmark-1, .bookmark-1 {
            bookmark-level: 1;
            bookmark-state: open;
        }
        
        h2.bookmark-2, .bookmark-2 {
            bookmark-level: 2;
            bookmark-state: closed;
        }
        
        h3.bookmark-3, .bookmark-3 {
            bookmark-level: 3;
            bookmark-state: closed;
        }
        
        /* 章节标题样式 */
        h1 {
            color: #c0392b;
            font-size: 22pt;
            border-bottom: 3px solid #e74c3c;
            padding-bottom: 10px;
            margin-top: 0;
            page-break-after: avoid;
            bookmark-level: 1;
        }
        
        h2 {
            color: #2980b9;
            font-size: 16pt;
            border-bottom: 2px solid #3498db;
            padding-bottom: 6px;
            margin-top: 1.5em;
            page-break-after: avoid;
            bookmark-level: 2;
        }
        
        h3 {
            color: #27ae60;
            font-size: 13pt;
            margin-top: 1.2em;
            page-break-after: avoid;
            bookmark-level: 3;
        }
        
        h4, h5, h6 {
            color: #8e44ad;
            margin-top: 1em;
        }
        
        /* 代码样式 */
        code {
            background-color: #f4f4f4;
            padding: 2px 5px;
            border-radius: 3px;
            font-family: "JetBrains Mono", "Fira Code", "SF Mono", Consolas, 
                         "Liberation Mono", Menlo, monospace;
            font-size: 9.5pt;
            color: #c7254e;
        }
        
        pre {
            background-color: #282c34;
            color: #abb2bf;
            padding: 14px;
            border-radius: 6px;
            overflow-x: auto;
            font-size: 9pt;
            line-height: 1.45;
            page-break-inside: avoid;
            white-space: pre-wrap;
            word-wrap: break-word;
            margin: 1em 0;
        }
        
        pre code {
            background-color: transparent;
            padding: 0;
            color: inherit;
            font-size: inherit;
        }
        
        /* 章节分隔 */
        .chapter {
            page-break-before: always;
        }
        
        .chapter:first-of-type {
            page-break-before: avoid;
        }
        
        /* 链接 */
        a {
            color: #3498db;
            text-decoration: none;
        }
        
        /* 引用块 */
        blockquote {
            border-left: 4px solid #f39c12;
            margin: 1em 0;
            padding: 10px 20px;
            background-color: #fef9e7;
            color: #7d6608;
            page-break-inside: avoid;
        }
        
        /* 表格 */
        table {
            border-collapse: collapse;
            width: 100%;
            margin: 1em 0;
            page-break-inside: avoid;
            font-size: 10pt;
        }
        
        th, td {
            border: 1px solid #bdc3c7;
            padding: 8px 10px;
            text-align: left;
        }
        
        th {
            background-color: #3498db;
            color: white;
        }
        
        tr:nth-child(even) {
            background-color: #ecf0f1;
        }
        
        /* 图片 */
        img {
            max-width: 100%;
            height: auto;
            display: block;
            margin: 1em auto;
        }
        
        /* 列表 */
        ul, ol {
            padding-left: 25px;
        }
        
        li {
            margin: 4px 0;
        }
        
        /* 隐藏不需要的元素 */
        .buttons, .fa, .fa-play, .fa-copy,
        button, .play-button, .test-arrow,
        .header, .nav-chapters, .chapter-nav {
            display: none !important;
        }
        
        /* 禁用内容中标题的书签（只保留章节标题的书签） */
        .no-bookmark {
            bookmark-level: none;
        }
        
        /* 封面和目录标题不生成书签 */
        .cover h1, .toc h1 {
            bookmark-level: none;
        }'''
    
    def _generate_toc_html(self) -> str:
        """生成目录 HTML"""
        items = list(self.chapters.items())
        mid = (len(items) + 1) // 2
        
        toc_html = '        <td>\n'
        for url, title in items[:mid]:
            level = self._get_toc_level(title)
            toc_html += f'            <div class="toc-item level-{level}">{title}</div>\n'
        toc_html += '        </td>\n'
        
        toc_html += '        <td>\n'
        for url, title in items[mid:]:
            level = self._get_toc_level(title)
            toc_html += f'            <div class="toc-item level-{level}">{title}</div>\n'
        toc_html += '        </td>\n'
        
        return toc_html
    
    def _generate_chapters_html(self) -> str:
        """生成章节内容 HTML"""
        chapters_html = ''
        for i, page in enumerate(self.pages):
            level = self._get_toc_level(page['title'])
            heading_tag = f'h{min(level, 3)}'
            
            chapters_html += f'''
<div class="chapter" id="chapter-{i}">
<{heading_tag} class="chapter-title bookmark-{level}">{page['title']}</{heading_tag}>
{page['content']}
</div>
'''
        return chapters_html
    
    def generate_html(self) -> str:
        """
        生成合并的 HTML 文件
        
        Returns:
            完整的 HTML 内容
        """
        html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>{self.book_title}</title>
    <style>
{self._get_css_styles()}
    </style>
</head>
<body>

<!-- 封面 -->
<div class="cover">
    <div class="logo">🦀</div>
    <h1>{self.book_title}</h1>
    <p class="source">
        来源：<a href="{self.base_url}">{self.base_url}</a>
    </p>
</div>

<!-- 目录 -->
<div class="toc">
    <h1>目 录</h1>
    <table class="toc-table"><tr>
{self._generate_toc_html()}    </tr></table>
</div>

{self._generate_chapters_html()}
</body>
</html>
'''
        
        return html
    
    @staticmethod
    def _sanitize_filename(title: str) -> str:
        """生成安全的文件名"""
        return re.sub(FILENAME_UNSAFE_CHARS, '_', title)
    
    def save_html(self) -> str:
        """
        保存 HTML 文件
        
        Returns:
            HTML 文件路径
        """
        os.makedirs(self.output_dir, exist_ok=True)
        
        html_content = self.generate_html()
        safe_title = self._sanitize_filename(self.book_title)
        html_file = os.path.join(self.output_dir, f'{safe_title}.html')
        
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"✅ HTML 文件已保存: {html_file}")
        return html_file
    
    def convert_to_pdf(self, html_file: str) -> Optional[str]:
        """
        使用 weasyprint 转换为 PDF
        
        Args:
            html_file: HTML 文件路径
            
        Returns:
            PDF 文件路径，失败返回 None
        """
        try:
            from weasyprint import HTML
            from weasyprint.text.fonts import FontConfiguration
        except ImportError:
            print("\n❌ WeasyPrint 未安装")
            print("   请运行: pip install weasyprint")
            print("   macOS 还需要: brew install pango")
            return None
        
        try:
            print("\n📄 正在使用 WeasyPrint 生成 PDF...")
            print("   (这可能需要几分钟，请耐心等待...)")
            
            font_config = FontConfiguration()
            safe_title = self._sanitize_filename(self.book_title)
            pdf_file = os.path.join(self.output_dir, f'{safe_title}.pdf')
            
            html = HTML(filename=html_file)
            html.write_pdf(pdf_file, font_config=font_config)
            
            # 获取文件大小
            size_mb = os.path.getsize(pdf_file) / (1024 * 1024)
            print("\n✅ PDF 生成成功!")
            print(f"   文件: {pdf_file}")
            print(f"   大小: {size_mb:.1f} MB")
            return pdf_file
            
        except Exception as e:
            print(f"\n❌ PDF 生成失败: {e}")
            return None


def _print_header():
    """打印程序标题"""
    print("=" * 60)
    print("  📚 mdBook 通用爬虫 - PDF 生成器")
    print("=" * 60)


def _print_success():
    """打印成功信息"""
    print("\n" + "=" * 60)
    print("  🎉 完成！")
    print("=" * 60)


def _print_html_only_success():
    """打印仅 HTML 生成成功信息"""
    print("\n" + "=" * 60)
    print("  🎉 HTML 生成完成！")
    print("=" * 60)


def _print_fallback_options(html_file: str):
    """打印备选方案"""
    print("\n" + "-" * 60)
    print("备选方案:")
    print(f"  1. 用浏览器打开 {html_file}")
    print("  2. 按 Ctrl+P (Mac: Cmd+P) 打印为 PDF")
    print("-" * 60)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='通用 mdBook 网站爬虫 - 自动爬取并生成 PDF',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  python mbook2pdf.py https://rustwiki.org/zh-CN/book/
  python mbook2pdf.py https://rustwiki.org/zh-CN/rust-by-example/
  python mbook2pdf.py https://colobu.com/rust100/
  python mbook2pdf.py https://doc.rust-lang.org/book/ -o ./rust_book
        '''
    )
    
    parser.add_argument('url', help='mdBook 网站 URL')
    parser.add_argument('-o', '--output', help='输出目录 (默认: 根据 URL 自动生成)')
    parser.add_argument('-d', '--delay', type=float, default=DEFAULT_DELAY, 
                        help=f'请求间隔秒数 (默认: {DEFAULT_DELAY})')
    parser.add_argument('--html-only', action='store_true',
                        help='只生成 HTML，不转换 PDF')
    
    args = parser.parse_args()
    
    _print_header()
    
    crawler = MdBookCrawler(args.url, args.output, args.delay)
    
    if not crawler.crawl():
        sys.exit(1)
    
    print("\n📝 正在生成 HTML 文件...")
    html_file = crawler.save_html()
    
    if not args.html_only:
        pdf_file = crawler.convert_to_pdf(html_file)
        
        if pdf_file:
            _print_success()
        else:
            _print_fallback_options(html_file)
    else:
        _print_html_only_success()


if __name__ == "__main__":
    main()