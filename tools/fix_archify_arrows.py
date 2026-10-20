# -*- coding: utf-8 -*-
"""修复 archify 交付 HTML 中箭头朝向异常的小工具。

背景：archify 渲染器给部分边输出的路径带有零长度末段
（形如 M x y L x y L x2 y2 L x2 y2，首尾点各重复一次）。
SVG 的 marker-end 用 orient=auto 按末段方向旋转箭头，
末段长度为零时方向未定义，浏览器把箭头画成歪斜的小折线，
肉眼看不到正常箭头（2026-09-14 实测确认）。

修复：把 path 的 d 属性和 data-composition-points 属性里的
连续重复坐标点折叠掉，末段恢复真实方向，箭头即正常。

用法：
    .venv/Scripts/python tools/fix_archify_arrows.py "docs/4_多媒体信息抽取_全链路综合图.html"

注意：该修复作用在交付产物上。每次用 archify 重新 deliver 之后
都需要重新跑一遍本脚本（渲染器问题未在上游修复前）。
"""

import re
import sys
from pathlib import Path


def 折叠重复点(坐标串: str, 分隔符: str) -> str:
    """把连续重复的坐标点折叠为单点，返回折叠后的字符串。"""
    if 分隔符 == ";":
        点列 = 坐标串.split(";")
        结果 = [p for i, p in enumerate(点列) if i == 0 or p != 点列[i - 1]]
        return ";".join(结果)
    # d 属性：archify 边路径固定是 M x y L x y ... 的空格分隔格式
    词元 = 坐标串.split()
    点列 = []
    for t in 词元:
        if t in ("M", "L"):
            continue
        点列.append(t)
    对 = [(点列[i], 点列[i + 1]) for i in range(0, len(点列), 2)]
    折叠 = [p for i, p in enumerate(对) if i == 0 or p != 对[i - 1]]
    片段 = []
    for i, (x, y) in enumerate(折叠):
        片段.append("M" if i == 0 else "L")
        片段.extend([x, y])
    return " ".join(片段)


def 修复(html路径: Path) -> None:
    文本 = html路径.read_text(encoding="utf-8")
    改动d = 0
    改动点 = 0

    def 处理标签(m: re.Match) -> str:
        nonlocal 改动d, 改动点
        标签 = m.group(0)

        def 换d(mm: re.Match) -> str:
            nonlocal 改动d
            原值 = mm.group(1)
            新值 = 折叠重复点(原值, " ")
            if 新值 != 原值:
                改动d += 1
            return 'd="' + 新值 + '"'

        def 换点(mm: re.Match) -> str:
            nonlocal 改动点
            原值 = mm.group(1)
            新值 = 折叠重复点(原值, ";")
            if 新值 != 原值:
                改动点 += 1
            return 'data-composition-points="' + 新值 + '"'

        标签 = re.sub(r'\bd="([^"]+)"', 换d, 标签)
        标签 = re.sub(r'data-composition-points="([^"]+)"', 换点, 标签)
        return 标签

    # 只处理带 data-edge-from 的边 path，其余 SVG 元素（图标等）不动
    文本 = re.sub(r'<path\b[^>]*data-edge-from=[^>]*>', 处理标签, 文本)
    html路径.write_text(文本, encoding="utf-8")
    print(f"完成：折叠了 {改动d} 条路径 d 属性、{改动点} 条 composition-points。")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) != 2:
        sys.exit("用法：python tools/fix_archify_arrows.py <archify导出的html>")
    目标 = Path(sys.argv[1])
    if not 目标.exists():
        sys.exit(f"错误：找不到文件 {目标}")
    修复(目标)


if __name__ == "__main__":
    main()
