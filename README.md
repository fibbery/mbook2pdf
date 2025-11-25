# mdBook 网站爬虫 - PDF 生成器

一个通用的 mdBook 网站爬虫工具，可以自动爬取 mdBook 构建的文档网站并生成精美的 PDF 文件。

## ✨ 特性

- 🚀 **通用支持**：支持所有 mdBook 构建的文档站点
- 📚 **自动爬取**：自动解析目录结构，爬取所有章节
- 📄 **PDF 生成**：生成格式精美的 PDF 文件，包含目录和书签
- 🎨 **样式优化**：自动清理页面元素，优化 PDF 显示效果
- 📖 **目录生成**：自动生成目录页，支持多级目录结构
- 🔖 **PDF 书签**：自动生成 PDF 书签，方便导航
- 🌐 **HTML 输出**：支持仅生成 HTML 文件，可用浏览器打印为 PDF

## 📋 系统要求

- Python 3.6+
- 操作系统：macOS、Linux、Windows

## 🔧 安装

### 1. 安装 Python 依赖

```bash
pip install requests beautifulsoup4 weasyprint
```

### 2. 安装系统依赖

#### macOS

```bash
brew install pango
```

#### Ubuntu/Debian

```bash
sudo apt install libpango-1.0-0 libpangocairo-1.0-0
```

#### Windows

Windows 用户通常不需要额外安装系统依赖，WeasyPrint 会自动处理。

## 🚀 使用方法

### 基本用法

```bash
python mbook2pdf.py <URL>
```

### 命令行参数

- `url`：mdBook 网站 URL（必需）
- `-o, --output`：输出目录（可选，默认根据 URL 自动生成）
- `-d, --delay`：请求间隔秒数（可选，默认 0.3 秒）
- `--html-only`：只生成 HTML，不转换 PDF（可选）

### 使用示例

```bash
# 基本用法 - 爬取 Rust 官方文档
python mbook2pdf.py https://rustwiki.org/zh-CN/book/

# 指定输出目录
python mbook2pdf.py https://rustwiki.org/zh-CN/book/ -o ./rust_book

# 自定义请求间隔（避免请求过快）
python mbook2pdf.py https://colobu.com/rust100/ -d 0.5

# 只生成 HTML 文件
python mbook2pdf.py https://rustwiki.org/zh-CN/rust-by-example/ --html-only
```

## 📖 支持的网站示例

- [Rust 程序设计语言（中文版）](https://rustwiki.org/zh-CN/book/)
- [Rust By Example（中文版）](https://rustwiki.org/zh-CN/rust-by-example/)
- [Rust 100 例](https://colobu.com/rust100/)
- [Rust 官方文档](https://doc.rust-lang.org/book/)
- 以及其他所有 mdBook 构建的文档站点

## 📁 输出文件

程序会在输出目录中生成以下文件：

- `{书名}.html`：完整的 HTML 文件，包含所有章节
- `{书名}.pdf`：生成的 PDF 文件（如果未使用 `--html-only` 选项）

## 🎯 功能说明

### 自动目录解析

程序会自动解析网站的侧边栏，提取所有章节链接，并按照原始顺序组织。

### 内容清理

程序会自动清理页面中的以下元素：
- 导航栏和侧边栏
- 搜索框和按钮
- 代码运行按钮
- 其他交互元素

### PDF 样式

生成的 PDF 包含：
- 封面页（包含书名和来源链接）
- 目录页（两列布局，支持多级目录）
- 章节内容（自动分页，优化排版）
- PDF 书签（自动生成，方便导航）

### 标题处理

- 自动将页面中的标题降级（h1 → h2，h2 → h3 等）
- 为每个章节添加统一的章节标题
- 禁用内容中标题的 PDF 书签，只保留章节标题的书签

## ⚙️ 配置说明

### 请求间隔

默认请求间隔为 0.3 秒，可以通过 `-d` 参数调整：

```bash
# 更慢的请求间隔（更安全，避免被封）
python mbook2pdf.py <URL> -d 1.0

# 更快的请求间隔（可能被限制）
python mbook2pdf.py <URL> -d 0.1
```

### 输出目录

如果不指定输出目录，程序会根据 URL 自动生成目录名：

- URL: `https://rustwiki.org/zh-CN/book/` → 目录: `./book_pdf`
- URL: `https://colobu.com/rust100/` → 目录: `./rust100_pdf`

## 🔍 常见问题

### Q: WeasyPrint 安装失败怎么办？

**A:** 请确保已安装系统依赖：
- macOS: `brew install pango`
- Ubuntu: `sudo apt install libpango-1.0-0 libpangocairo-1.0-0`

### Q: PDF 生成失败怎么办？

**A:** 如果 PDF 生成失败，程序会提示备选方案：
1. 用浏览器打开生成的 HTML 文件
2. 使用浏览器的打印功能（Ctrl+P / Cmd+P）打印为 PDF

### Q: 爬取速度太慢怎么办？

**A:** 可以通过 `-d` 参数调整请求间隔，但请注意：
- 间隔太短可能被网站限制
- 建议保持默认值 0.3 秒或更长

### Q: 支持哪些网站？

**A:** 支持所有使用 mdBook 构建的文档网站。如果遇到问题，可以：
1. 使用 `--html-only` 选项只生成 HTML
2. 检查网站是否使用了特殊的 mdBook 主题或自定义样式

### Q: 如何只生成 HTML？

**A:** 使用 `--html-only` 选项：

```bash
python mbook2pdf.py <URL> --html-only
```

然后可以用浏览器打开 HTML 文件，使用打印功能生成 PDF。

## 📝 代码结构

```
mbook2pdf.py
├── MdBookCrawler 类
│   ├── __init__()          # 初始化爬虫
│   ├── fetch_page()        # 获取页面内容
│   ├── parse_sidebar()     # 解析侧边栏
│   ├── extract_content()   # 提取主要内容
│   ├── crawl()             # 爬取所有页面
│   ├── generate_html()     # 生成 HTML
│   ├── save_html()         # 保存 HTML 文件
│   └── convert_to_pdf()    # 转换为 PDF
└── main()                  # 主函数
```

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

本项目采用 MIT 许可证。

## 🙏 致谢

- [mdBook](https://github.com/rust-lang/mdBook) - Rust 官方文档工具
- [WeasyPrint](https://weasyprint.org/) - HTML/CSS 转 PDF 工具
- [BeautifulSoup](https://www.crummy.com/software/BeautifulSoup/) - HTML 解析库

## 📧 联系方式

如有问题或建议，欢迎提交 Issue。

---

**注意**：请遵守目标网站的 robots.txt 和使用条款，合理使用爬虫工具。

