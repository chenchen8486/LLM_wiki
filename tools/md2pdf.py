# -*- coding: utf-8 -*-
"""Markdown 转 PDF 小工具。

路线：markdown 库（纯 Python）转带样式 HTML，再调本机 Edge / Chrome
无头模式打印成 PDF。Windows 自带浏览器渲染，中文无需额外装字体。

用法：
    python tools/md2pdf.py "3_领域归属评估与开源工程参考.md"
    python tools/md2pdf.py 输入.md -o 输出.pdf
"""

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import markdown

# 浏览器候选路径，按优先级探测
浏览器候选 = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
]

# 打印样式：A4 页面、中文字体栈、表格边框、代码块底色
CSS = """
@page { size: A4; margin: 18mm 16mm; }
* { box-sizing: border-box; }
body { font-family: "Microsoft YaHei", "PingFang SC", "SimSun", sans-serif;
       font-size: 11pt; line-height: 1.8; color: #222; margin: 0; }
h1 { font-size: 19pt; border-bottom: 2px solid #333; padding-bottom: 6px; }
h2 { font-size: 15pt; margin-top: 1.6em; border-bottom: 1px solid #ccc; padding-bottom: 4px; }
h3 { font-size: 12.5pt; margin-top: 1.4em; }
h4 { font-size: 11.5pt; }
p { margin: 0.6em 0; }
ul, ol { padding-left: 1.6em; margin: 0.6em 0; }
li { margin: 0.25em 0; }
table { border-collapse: collapse; width: 100%; margin: 0.8em 0; font-size: 9.5pt; }
th, td { border: 1px solid #999; padding: 5px 8px; text-align: left; vertical-align: top; }
th { background: #f0f0f0; }
code { font-family: Consolas, "Courier New", monospace; font-size: 9.5pt;
       background: #f4f4f4; padding: 1px 4px; border-radius: 3px; }
pre { background: #f6f6f6; border: 1px solid #ddd; padding: 10px;
      border-radius: 4px; white-space: pre-wrap; word-wrap: break-word; }
pre code { background: none; padding: 0; }
blockquote { border-left: 3px solid #bbb; margin: 0.8em 0; padding: 2px 12px; color: #555; }
a { color: #1a5fb4; text-decoration: none; }
hr { border: none; border-top: 1px solid #ccc; margin: 1.2em 0; }
.mermaid { text-align: center; margin: 0.8em 0; }
.mermaid svg { max-width: 100%; height: auto; }
"""

HTML模板 = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<base href="{基址}">
<title>{标题}</title>
<style>{样式}</style>
</head>
<body>
{正文}
</body>
</html>
"""


def 找浏览器() -> str:
    for 路径 in 浏览器候选:
        if Path(路径).exists():
            return 路径
    sys.exit("错误：未找到 Edge 或 Chrome，无法打印 PDF。")


def 转pdf(md路径: Path, pdf路径: Path) -> None:
    文本 = md路径.read_text(encoding="utf-8")
    # ELK 布局引擎不在 mermaid 单文件构建内，打印时去掉该指令回退默认布局
    文本 = re.sub(r"^%%\{init:.*defaultRenderer.*elk.*\}%%\s*$", "", 文本, flags=re.M)
    正文 = markdown.markdown(
        文本,
        extensions=["tables", "fenced_code", "sane_lists", "toc", "attr_list"],
    )
    # mermaid 代码块改成 div.mermaid，交给浏览器端 mermaid.js 渲染成 SVG
    正文 = re.sub(
        r'<pre><code class="language-mermaid">(.*?)</code></pre>',
        r'<div class="mermaid">\1</div>',
        正文,
        flags=re.S,
    )
    # base 指向 md 所在目录，保证临时 HTML 里的相对路径图片能加载
    基址 = md路径.parent.resolve().as_uri() + "/"
    html = HTML模板.format(标题=md路径.stem, 基址=基址, 样式=CSS, 正文=正文)

    # mermaid.js 内联进 HTML（离线可用），在打印前执行渲染
    mermaid脚本 = (Path(__file__).parent / "mermaid.min.js").read_text(encoding="utf-8")
    注入 = (
        "<script>" + mermaid脚本 + "</script>"
        "<script>mermaid.initialize({startOnLoad: false});"
        "mermaid.run({querySelector: '.mermaid'});</script>"
    )
    html = html.replace("</body>", 注入 + "</body>")

    # 临时 HTML 落盘，浏览器以 file:// 方式打开打印
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", suffix=".html", delete=False
    ) as f:
        f.write(html)
        临时html = Path(f.name)

    try:
        命令 = [
            找浏览器(),
            "--headless=new",
            "--disable-gpu",
            "--no-pdf-header-footer",
            # 等 mermaid.js 异步渲染完 SVG 再打印
            "--virtual-time-budget=20000",
            f"--print-to-pdf={pdf路径.resolve()}",
            临时html.resolve().as_uri(),
        ]
        subprocess.run(命令, check=True, timeout=180,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    finally:
        临时html.unlink(missing_ok=True)

    if not pdf路径.exists() or pdf路径.stat().st_size == 0:
        sys.exit("错误：浏览器未产出 PDF，请检查浏览器版本是否支持无头打印。")
    print(f"完成：{pdf路径}（{pdf路径.stat().st_size / 1024:.0f} KB）")


def main() -> None:
    # Windows 中文控制台默认 GBK，显式切 UTF-8 防止输出乱码
    sys.stdout.reconfigure(encoding="utf-8")
    解析 = argparse.ArgumentParser(description="Markdown 转 PDF")
    解析.add_argument("输入", help="Markdown 文件路径")
    解析.add_argument("-o", "--输出", help="输出 PDF 路径，默认同目录同名 .pdf")
    参数 = 解析.parse_args()

    md路径 = Path(参数.输入)
    if not md路径.exists():
        sys.exit(f"错误：找不到文件 {md路径}")
    pdf路径 = Path(参数.输出) if 参数.输出 else md路径.with_suffix(".pdf")
    转pdf(md路径, pdf路径)


if __name__ == "__main__":
    main()
