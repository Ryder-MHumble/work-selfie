#!/usr/bin/env python3
"""
self-distill 新野兽派+二次元 名片 v5

按 真实视觉反馈：
  - ❌ 不用 SVG 人物（之前的二次元男程序员太糙）
  - ✅ 全新风格："新时代新野兽派+二次元"
  - ✅ 重点：排版 + UI 优化

设计原则：
  - 不做精细插画
  - 野兽派：高对比 / 几何块 / 粗黑边 / 留白张力
  - 二次元：用 emoji + 抽象符号表达（👨‍💻🦊🐺☕🏆）
  - 排版：字号对比、字重对比、字间距
"""

import os
import sys
import time
import json
import subprocess
import tempfile
import hashlib
from pathlib import Path
from typing import Dict, Any, List

CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


# ============== 字体探测 ==============

_CJK_FONT_CANDIDATES = [
    "PingFang HK", "Hiragino Sans GB", "STHeiti", "Heiti TC",
    "Hiragino Sans", "Songti SC", "Kaiti SC", "PingFang SC", "Arial Unicode MS",
]
_CJK_FP = None
try:
    from matplotlib import font_manager as _fm
    for _f in _CJK_FONT_CANDIDATES:
        for _af in _fm.fontManager.ttflist:
            if _af.name == _f:
                _CJK_FP = _fm.FontProperties(fname=_af.fname)
                break
        if _CJK_FP:
            break
except Exception as e:
    print(f"  font 探测失败: {e}", file=sys.stderr)


# ============== 工具函数 ==============

def make_barcode_bars(employee_id: str, bar_count: int = 24) -> str:
    h = hashlib.md5(employee_id.encode()).hexdigest()
    bars = []
    for i in range(bar_count):
        hex_idx = int(h[i % len(h)], 16)
        if hex_idx < 5:
            cls, width = "bar", 4
        elif hex_idx < 8:
            cls, width = "bar", 2
        elif hex_idx < 11:
            cls, width = "empty", 3
        elif hex_idx < 14:
            cls, width = "bar", 3
        else:
            cls, width = "empty", 2
        bars.append(f'<div class="{cls}" style="width: {width}px;"></div>')
    return ''.join(bars)


def build_traits_html(traits: List[Dict[str, str]]) -> str:
    items = []
    for t in traits[:6]:
        items.append(f'''
        <div class="trait">
          <span class="trait-icon">{t["icon"]}</span>
          <div class="trait-body">
            <div class="trait-title">{t["title"]}</div>
            <div class="trait-desc">{t["desc"]}</div>
          </div>
        </div>''')
    return ''.join(items)


def build_kpi_items(kpis: List[Dict[str, str]]) -> str:
    items = []
    for k in kpis:
        done = k.get("icon") == "✓"
        cls = "done" if done else "todo"
        items.append(f'''
        <div class="kpi-item">
          <span class="kpi-check {cls}">{k.get("icon", "✓")}</span>
          <span class="kpi-name">{k["name"]}</span>
          <span class="kpi-evidence">{k["evidence"]}</span>
        </div>''')
    return ''.join(items)


# ============== 模板：风格 A — 野兽派极简（黑+深红+米白） ==============

TEMPLATE_A = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>职场人设卡 A · {name}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  html, body {{ width: 1200px; height: 900px; overflow: hidden;
                font-family: 'PingFang HK', 'Hiragino Sans GB', 'STHeiti', 'Noto Sans CJK SC', sans-serif; }}

  body {{
    background: #F2EFE9;
    color: #0A0A0A;
    position: relative;
  }}

  /* 主色：深红 #C8102E + 浓黑 #0A0A0A + 米白 #F2EFE9 + 警示黄 #F4C430 */

  /* 几何块：右上大圆 */
  .geo-circle {{
    position: absolute; top: -150px; right: -150px;
    width: 600px; height: 600px;
    border-radius: 50%;
    background: #C8102E;
    z-index: 1;
  }}
  /* 几何块：左下三角形 */
  .geo-triangle {{
    position: absolute; bottom: -100px; left: -50px;
    width: 0; height: 0;
    border-left: 250px solid transparent;
    border-right: 0 solid transparent;
    border-bottom: 350px solid #0A0A0A;
    z-index: 1;
    transform: rotate(20deg);
  }}

  /* 噪点 */
  .noise {{
    position: absolute; inset: 0; z-index: 50; pointer-events: none; opacity: 0.15;
    background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='200' height='200'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.9'/></filter><rect width='200' height='200' filter='url(%23n)' opacity='0.4'/></svg>");
  }}

  /* 主体内容 */
  .content {{ position: relative; z-index: 10; padding: 50px 60px; }}

  /* 顶部 eyebrow */
  .eyebrow {{
    display: inline-block;
    font-size: 14px; font-weight: 700;
    letter-spacing: 0.4em;
    text-transform: uppercase;
    color: #0A0A0A;
    border-bottom: 3px solid #C8102E;
    padding-bottom: 4px;
    margin-bottom: 16px;
  }}

  /* 姓名（巨大野兽派字体） */
  .name {{
    font-size: 140px; font-weight: 900;
    line-height: 0.95;
    color: #0A0A0A;
    letter-spacing: -0.04em;
    margin-bottom: 6px;
  }}

  /* Slogan 副标题 */
  .slogan {{
    font-size: 28px; font-weight: 600;
    color: #C8102E;
    font-style: italic;
    margin-bottom: 36px;
  }}

  /* 主网格：3 列 */
  .grid {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 30px; margin-top: 24px; }}

  /* 模块卡（无边框野兽派） */
  .module {{ position: relative; }}

  .module-num {{
    font-size: 64px; font-weight: 900;
    color: #F4C430;
    line-height: 1;
    margin-bottom: 4px;
    text-shadow: 3px 3px 0 #0A0A0A;
  }}
  .module-num-label {{
    font-size: 12px; font-weight: 700;
    letter-spacing: 0.3em;
    text-transform: uppercase;
    color: #0A0A0A;
    margin-bottom: 12px;
  }}

  /* SBTI 模块 */
  .sbti-label {{
    font-size: 18px; font-weight: 800;
    color: #0A0A0A;
    margin-bottom: 4px;
  }}
  .sbti-code {{
    font-size: 48px; font-weight: 900;
    color: #C8102E;
    line-height: 1;
    margin-bottom: 8px;
  }}
  .sbti-desc {{
    font-size: 13px; font-weight: 500;
    color: #0A0A0A;
    line-height: 1.4;
  }}

  /* MBTI 模块 */
  .mbti-code {{
    font-size: 56px; font-weight: 900;
    color: #0A0A0A;
    line-height: 1;
    margin-bottom: 8px;
    letter-spacing: 0.02em;
  }}
  .mbti-desc {{
    font-size: 13px; font-weight: 500;
    color: #0A0A0A;
    line-height: 1.4;
  }}

  /* 性格特征 */
  .traits {{ display: flex; flex-direction: column; gap: 6px; margin-top: 6px; }}
  .trait {{
    display: flex; gap: 8px; align-items: flex-start;
    padding: 4px 0;
    border-bottom: 1px solid rgba(0,0,0,0.1);
  }}
  .trait:last-child {{ border-bottom: none; }}
  .trait-icon {{ font-size: 18px; flex-shrink: 0; margin-top: 1px; }}
  .trait-body {{ flex: 1; }}
  .trait-title {{ font-size: 13px; font-weight: 800; color: #0A0A0A; line-height: 1.2; }}
  .trait-desc {{ font-size: 11px; color: #555; line-height: 1.3; }}

  /* 底部三栏：Sneaky + KPI + Manifesto */
  .footer {{ display: grid; grid-template-columns: 1fr 1.4fr 1fr; gap: 24px; margin-top: 36px; }}

  /* Sneaky 标签（旋转小贴士） */
  .sneaky {{
    background: #F4C430;
    border: 3px solid #0A0A0A;
    padding: 12px 16px;
    transform: rotate(-3deg);
    box-shadow: 4px 4px 0 #0A0A0A;
  }}
  .sneaky-title {{
    font-size: 18px; font-weight: 900;
    color: #0A0A0A;
    margin-bottom: 4px;
  }}
  .sneaky-evidence {{
    font-size: 11px; font-weight: 600;
    color: #0A0A0A;
    line-height: 1.3;
  }}

  /* KPI 列表 */
  .kpi {{ }}
  .kpi-title {{
    font-size: 14px; font-weight: 800;
    color: #0A0A0A;
    margin-bottom: 8px;
    border-bottom: 2px solid #C8102E;
    padding-bottom: 4px;
  }}
  .kpi-item {{
    display: flex; align-items: center; gap: 8px;
    font-size: 13px;
    margin: 5px 0;
  }}
  .kpi-check {{ font-size: 16px; font-weight: 900; }}
  .kpi-check.done {{ color: #C8102E; }}
  .kpi-check.todo {{ color: #888; }}
  .kpi-name {{ font-weight: 700; color: #0A0A0A; }}
  .kpi-evidence {{ color: #777; font-size: 11px; }}

  /* Manifesto */
  .manifesto {{
    background: #0A0A0A;
    color: white;
    padding: 14px 18px;
    transform: rotate(2deg);
    box-shadow: 4px 4px 0 #C8102E;
    position: relative;
  }}
  .manifesto::before {{
    content: "👑";
    position: absolute;
    top: -16px; right: 12px;
    font-size: 24px;
  }}
  .manifesto-title {{
    font-size: 13px; font-weight: 800;
    color: #F4C430;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    margin-bottom: 6px;
  }}
  .manifesto-text {{
    font-size: 14px; font-weight: 800;
    line-height: 1.5;
    color: white;
    white-space: pre-line;
  }}

  /* 底部：员工号 + 入职 + 动物 + 二维感 */
  .bottom {{
    position: absolute;
    bottom: 30px; left: 60px; right: 60px;
    display: flex; justify-content: space-between; align-items: flex-end;
    z-index: 10;
  }}
  .bottom-left {{
    display: flex; align-items: flex-end; gap: 16px;
  }}
  .animal-stamp {{
    font-size: 56px;
    line-height: 1;
  }}
  .animal-meta {{
    font-size: 11px; font-weight: 700;
    color: #0A0A0A;
    line-height: 1.4;
  }}
  .animal-meta-label {{ color: #999; }}

  .bottom-right {{
    display: flex; gap: 12px; align-items: flex-end;
  }}
  .barcode-block {{
    background: white;
    border: 2px solid #0A0A0A;
    padding: 6px 10px;
  }}
  .barcode {{ display: flex; gap: 1px; height: 32px; }}
  .bar {{ background: #0A0A0A; }}
  .bar.empty {{ background: white; }}
  .barcode-text {{
    font-size: 10px; font-weight: 700;
    color: #0A0A0A;
    margin-top: 2px;
    font-family: 'SF Mono', monospace;
  }}
  .motto {{
    font-size: 12px; font-weight: 700;
    color: #0A0A0A;
    line-height: 1.4;
    max-width: 280px;
    text-align: right;
  }}
  .motto-label {{ color: #C8102E; }}

  /* 副标题行 */
  .subtitle-row {{
    display: flex; align-items: center; gap: 16px;
    margin-top: -16px;
    margin-bottom: 24px;
  }}
  .subtitle-text {{
    font-size: 14px; font-weight: 700;
    color: #0A0A0A;
  }}
  .subtitle-emoji {{
    font-size: 32px;
    line-height: 1;
  }}
</style>
</head>
<body>
  <div class="geo-circle"></div>
  <div class="geo-triangle"></div>

  <div class="content">
    <div class="eyebrow">SELF-DISTILL · 自查 / {date}</div>
    <div class="name">{name}</div>
    <div class="slogan">"{motto}"</div>

    <div class="subtitle-row">
      <span class="subtitle-emoji">👨‍💻</span>
      <span class="subtitle-text">SBTI <strong>{sbti_code}</strong> · MBTI <strong>{mbti}</strong> · 动物 <strong>{animal_emoji} {animal}</strong></span>
    </div>

    <div class="grid">
      <!-- 01 SBTI -->
      <div class="module">
        <div class="module-num">01</div>
        <div class="module-num-label">SBTI</div>
        <div class="sbti-label">{sbti_label}</div>
        <div class="sbti-code">{sbti_code}</div>
        <div class="sbti-desc">{sbti_desc}</div>
      </div>

      <!-- 02 MBTI -->
      <div class="module">
        <div class="module-num">02</div>
        <div class="module-num-label">MBTI</div>
        <div class="mbti-code">{mbti}</div>
        <div class="mbti-desc">{mbti_desc}</div>
      </div>

      <!-- 03 性格特征 -->
      <div class="module">
        <div class="module-num">03</div>
        <div class="module-num-label">性格特征</div>
        <div class="traits">
          {traits_html}
        </div>
      </div>
    </div>

    <div class="footer">
      <!-- Sneaky -->
      <div class="sneaky">
        <div class="sneaky-title">{sneaky_label}</div>
        <div class="sneaky-evidence">{sneaky_evidence}</div>
      </div>

      <!-- KPI -->
      <div class="kpi">
        <div class="kpi-title">▍今日KPI（快乐版）</div>
        {kpi_items}
      </div>

      <!-- Manifesto -->
      <div class="manifesto">
        <div class="manifesto-title">▍职场宣言</div>
        <div class="manifesto-text">{slogan_long}</div>
      </div>
    </div>
  </div>

  <!-- 底部：动物 + 工号 + 座右铭 -->
  <div class="bottom">
    <div class="bottom-left">
      <div class="animal-stamp">{animal_emoji}</div>
      <div class="animal-meta">
        <div><span class="animal-meta-label">动物原型：</span><strong>{animal}</strong>（吻合 {animal_match}%）</div>
        <div><span class="animal-meta-label">入职时间：</span>{join_date}</div>
        <div><span class="animal-meta-label">工号：</span>{employee_id}</div>
      </div>
    </div>
    <div class="bottom-right">
      <div class="barcode-block">
        <div class="barcode">{barcode_bars}</div>
        <div class="barcode-text">SELF-DISTILL · {date_short}</div>
      </div>
    </div>
  </div>

  <div class="noise"></div>
</body>
</html>'''


# ============== 模板：风格 B — 野兽派杂志（大字 + 排版美感） ==============

TEMPLATE_B = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>职场人设卡 B · {name}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  html, body {{ width: 1200px; height: 900px; overflow: hidden;
                font-family: 'PingFang HK', 'Hiragino Sans GB', 'STHeiti', 'Noto Sans CJK SC', sans-serif; }}

  body {{
    background: #FFFFFF;
    color: #0A0A0A;
    position: relative;
  }}

  /* 主色：荧光黄 #FFD400 + 浓黑 #0A0A0A + 纯白 #FFFFFF + 警示红 #FF3B30 */

  /* 顶部黄条 */
  .top-bar {{
    position: absolute; top: 0; left: 0; right: 0;
    height: 60px;
    background: #FFD400;
    border-bottom: 4px solid #0A0A0A;
    z-index: 10;
    display: flex; align-items: center; padding: 0 40px;
    justify-content: space-between;
  }}
  .top-bar-left {{
    font-size: 18px; font-weight: 900;
    color: #0A0A0A;
    letter-spacing: 0.15em;
    text-transform: uppercase;
  }}
  .top-bar-right {{
    font-size: 14px; font-weight: 800;
    color: #0A0A0A;
    letter-spacing: 0.2em;
  }}

  /* 大标题 */
  .huge-title {{
    position: absolute;
    top: 90px; left: 40px;
    z-index: 5;
  }}
  .huge {{
    font-size: 180px; font-weight: 900;
    line-height: 0.85;
    color: #0A0A0A;
    letter-spacing: -0.05em;
  }}
  .huge-name {{
    color: #FF3B30;
  }}

  /* 副标题（破折号+职位描述） */
  .job-desc {{
    margin-top: 8px;
    display: flex; align-items: center; gap: 12px;
  }}
  .job-desc-line {{
    width: 80px; height: 4px;
    background: #0A0A0A;
  }}
  .job-desc-text {{
    font-size: 20px; font-weight: 700;
    color: #0A0A0A;
  }}
  .job-desc-emoji {{
    font-size: 28px;
  }}

  /* 右侧巨大动物 emoji */
  .animal-huge {{
    position: absolute;
    top: 100px; right: 50px;
    z-index: 4;
    font-size: 240px;
    line-height: 1;
    transform: rotate(-8deg);
    filter: drop-shadow(8px 8px 0 #FFD400);
  }}

  /* MBTI 大字 */
  .mbti-block {{
    position: absolute;
    top: 380px; right: 60px;
    z-index: 5;
    text-align: right;
  }}
  .mbti-label {{
    font-size: 14px; font-weight: 700;
    letter-spacing: 0.3em;
    text-transform: uppercase;
    color: #FF3B30;
    margin-bottom: 4px;
  }}
  .mbti-value {{
    font-size: 110px; font-weight: 900;
    color: #0A0A0A;
    line-height: 0.9;
    letter-spacing: -0.03em;
  }}
  .mbti-desc {{
    font-size: 14px; font-weight: 600;
    color: #555;
    margin-top: 4px;
    max-width: 380px;
  }}

  /* SBTI 横条 */
  .sbti-block {{
    position: absolute;
    top: 340px; left: 40px;
    z-index: 5;
    max-width: 500px;
  }}
  .sbti-label {{
    font-size: 14px; font-weight: 700;
    letter-spacing: 0.3em;
    text-transform: uppercase;
    color: #0A0A0A;
    margin-bottom: 6px;
  }}
  .sbti-tag {{
    display: inline-block;
    background: #0A0A0A;
    color: #FFD400;
    font-size: 22px; font-weight: 900;
    padding: 4px 14px;
    margin-bottom: 6px;
  }}
  .sbti-code {{
    font-size: 56px; font-weight: 900;
    color: #FF3B30;
    line-height: 1;
  }}
  .sbti-desc {{
    font-size: 13px; font-weight: 500;
    color: #0A0A0A;
    margin-top: 6px;
    line-height: 1.4;
  }}

  /* 性格特征 - 横向单行 */
  .traits-row {{
    position: absolute;
    top: 550px; left: 40px; right: 40px;
    z-index: 5;
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
  }}
  .trait {{
    background: #0A0A0A;
    color: white;
    padding: 12px 14px;
    border-left: 6px solid #FFD400;
  }}
  .trait-icon {{
    font-size: 24px;
    margin-bottom: 2px;
  }}
  .trait-title {{
    font-size: 16px; font-weight: 900;
    color: #FFD400;
    line-height: 1.2;
  }}
  .trait-desc {{
    font-size: 11px; font-weight: 500;
    color: white;
    margin-top: 2px;
    line-height: 1.3;
  }}

  /* 底部三栏：sneaky / kpi / manifesto */
  .bottom-strip {{
    position: absolute;
    bottom: 0; left: 0; right: 0;
    height: 200px;
    background: #FFD400;
    border-top: 4px solid #0A0A0A;
    z-index: 5;
    display: grid;
    grid-template-columns: 1.2fr 1.4fr 1fr;
    padding: 20px 40px;
    gap: 24px;
  }}

  .sneaky {{ color: #0A0A0A; }}
  .sneaky-label {{
    font-size: 11px; font-weight: 700;
    letter-spacing: 0.3em;
    text-transform: uppercase;
    color: #0A0A0A;
    margin-bottom: 4px;
  }}
  .sneaky-title {{
    font-size: 24px; font-weight: 900;
    color: #0A0A0A;
    line-height: 1.1;
    margin-bottom: 4px;
  }}
  .sneaky-evidence {{
    font-size: 12px; font-weight: 600;
    color: #0A0A0A;
    line-height: 1.3;
  }}

  .kpi {{ }}
  .kpi-label {{
    font-size: 11px; font-weight: 700;
    letter-spacing: 0.3em;
    text-transform: uppercase;
    color: #0A0A0A;
    margin-bottom: 4px;
  }}
  .kpi-item {{
    display: flex; align-items: center; gap: 8px;
    font-size: 13px;
    margin: 3px 0;
  }}
  .kpi-check {{ font-size: 16px; font-weight: 900; }}
  .kpi-check.done {{ color: #0A0A0A; }}
  .kpi-check.todo {{ color: #FF3B30; }}
  .kpi-name {{ font-weight: 800; color: #0A0A0A; }}
  .kpi-evidence {{ color: #444; font-size: 11px; }}

  .manifesto {{
    background: #0A0A0A;
    color: white;
    padding: 12px 16px;
    position: relative;
  }}
  .manifesto-label {{
    font-size: 11px; font-weight: 700;
    letter-spacing: 0.3em;
    text-transform: uppercase;
    color: #FFD400;
    margin-bottom: 4px;
  }}
  .manifesto-text {{
    font-size: 14px; font-weight: 800;
    line-height: 1.4;
    color: white;
    white-space: pre-line;
  }}

  /* 条形码 - 右下角独立 */
  .barcode-mini {{
    position: absolute;
    bottom: 210px; right: 40px;
    z-index: 5;
    background: white;
    border: 2px solid #0A0A0A;
    padding: 4px 8px;
  }}
  .barcode {{ display: flex; gap: 1px; height: 24px; }}
  .bar {{ background: #0A0A0A; }}
  .bar.empty {{ background: white; }}
  .barcode-text {{
    font-size: 9px; font-weight: 700;
    color: #0A0A0A;
    margin-top: 1px;
    font-family: 'SF Mono', monospace;
  }}
</style>
</head>
<body>
  <div class="top-bar">
    <div class="top-bar-left">SELF-DISTILL</div>
    <div class="top-bar-right">★ 今日工位 MVP ★</div>
  </div>

  <div class="huge-title">
    <div class="huge"><span class="huge-name">{name}</span><br>的职场人设</div>
    <div class="job-desc">
      <div class="job-desc-line"></div>
      <div class="job-desc-emoji">👨‍💻</div>
      <div class="job-desc-text">{slogan}</div>
    </div>
  </div>

  <div class="animal-huge">{animal_emoji}</div>

  <div class="sbti-block">
    <div class="sbti-label">▍01 职场SBTI</div>
    <div class="sbti-tag">{sbti_label}</div>
    <div class="sbti-code">{sbti_code}</div>
    <div class="sbti-desc">{sbti_desc}</div>
  </div>

  <div class="mbti-block">
    <div class="mbti-label">▍02 MBTI</div>
    <div class="mbti-value">{mbti}</div>
    <div class="mbti-desc">{mbti_desc}</div>
  </div>

  <div class="traits-row">
    {traits_html}
  </div>

  <div class="barcode-mini">
    <div class="barcode">{barcode_bars}</div>
    <div class="barcode-text">工号 {employee_id} · {join_date}</div>
  </div>

  <div class="bottom-strip">
    <div class="sneaky">
      <div class="sneaky-label">▍摸鱼伪装</div>
      <div class="sneaky-title">{sneaky_label}</div>
      <div class="sneaky-evidence">{sneaky_evidence}</div>
    </div>
    <div class="kpi">
      <div class="kpi-label">▍今日KPI（快乐版）</div>
      {kpi_items}
    </div>
    <div class="manifesto">
      <div class="manifesto-label">▍职场宣言 👑</div>
      <div class="manifesto-text">{slogan_long}</div>
    </div>
  </div>
</body>
</html>'''


# ============== 入口 ==============

MBTI_DESC = {
    "INTJ": "开会像主持人，执行靠最后一晚爆发",
    "INTP": "逻辑永动机，嘴比手先到",
    "ENTJ": "目标导向，所有事都能拆解成三步",
    "ENTP": "有一百个想法，走通一个就够了不起",
    "INFJ": "安静的洞察者，懂你没说的那半句",
    "INFP": "保持真诚，保持好奇，保持温柔",
    "ENFJ": "把人放第一位，把事做到极致",
    "ENFP": "全场的快乐源泉，灵感不断",
    "ISTJ": "把事做对，把人做好，把日子过稳",
    "ISFJ": "先照顾好你，再照顾好世界",
    "ESTJ": "执行大于讨论，结果大于过程",
    "ESFJ": "气氛是协作的燃料，人是主角",
    "ISTP": "工具用得熟，问题就少",
    "ISFP": "慢工出细活，细活出好活",
    "ESTP": "先动起来，再优化，再迭代",
    "ESFP": "现场是唯一的真相",
}

ANIMAL_EMOJI = {
    "猫头鹰": "🦉", "蜜蜂": "🐝", "树懒": "🦥", "章鱼": "🐙",
    "狼": "🐺", "孔雀": "🦚", "乌龟": "🐢", "狐狸": "🦊",
    "海狸": "🦫", "海豚": "🐬", "狮子": "🦁", "变色龙": "🦎",
}


def render_html_a(template: Dict[str, Any]) -> str:
    return TEMPLATE_A.format(
        name=template["name"],
        date=template.get("date", ""),
        date_short=template.get("date_short", ""),
        motto=template.get("motto", ""),
        mbti=template["mbti"],
        mbti_desc=template.get("mbti_desc", ""),
        sbti_code=template.get("sbti_code", "????"),
        sbti_label=template.get("sbti_label", ""),
        sbti_desc=template.get("sbti_desc", ""),
        animal=template.get("animal", "?"),
        animal_emoji=template.get("animal_emoji", "🐾"),
        animal_match=template.get("animal_match", 0),
        sneaky_label=template.get("sneaky_label", ""),
        sneaky_evidence=template.get("sneaky_evidence", ""),
        slogan=template.get("slogan", ""),
        slogan_long=template.get("slogan_long", ""),
        traits_html=build_traits_html(template.get("personality_traits", [])),
        kpi_items=build_kpi_items(template.get("kpi_happy", [])),
        employee_id=template.get("employee_id", "000000"),
        join_date=template.get("join_date", ""),
        barcode_bars=make_barcode_bars(template.get("employee_id", "0")),
    )


def render_html_b(template: Dict[str, Any]) -> str:
    return TEMPLATE_B.format(
        name=template["name"],
        mbti=template["mbti"],
        mbti_desc=template.get("mbti_desc", ""),
        sbti_code=template.get("sbti_code", "????"),
        sbti_label=template.get("sbti_label", ""),
        sbti_desc=template.get("sbti_desc", ""),
        animal=template.get("animal", "?"),
        animal_emoji=template.get("animal_emoji", "🐾"),
        animal_match=template.get("animal_match", 0),
        sneaky_label=template.get("sneaky_label", ""),
        sneaky_evidence=template.get("sneaky_evidence", ""),
        slogan=template.get("slogan", ""),
        slogan_long=template.get("slogan_long", ""),
        traits_html=build_traits_html(template.get("personality_traits", [])),
        kpi_items=build_kpi_items(template.get("kpi_happy", [])),
        employee_id=template.get("employee_id", "000000"),
        join_date=template.get("join_date", ""),
        barcode_bars=make_barcode_bars(template.get("employee_id", "0")),
    )


def render_html_to_png(html_content: str, output_path: str,
                       width: int = 1200, height: int = 900) -> bool:
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".html", delete=False, encoding="utf-8"
    ) as f:
        f.write(html_content)
        html_path = f.name
    try:
        cmd = [
            CHROME_PATH, "--headless=new", "--disable-gpu", "--no-sandbox",
            "--hide-scrollbars", "--force-device-scale-factor=1",
            f"--screenshot={output_path}", f"--window-size={width},{height}",
            "--virtual-time-budget=5000", f"file://{html_path}",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            print(f"  Chrome 错误：{result.stderr[:500]}", file=sys.stderr)
            return False
        return os.path.exists(output_path)
    finally:
        try: os.unlink(html_path)
        except OSError: pass


def render_card(template: Dict[str, Any], output_path: str, style: str = "A") -> bool:
    if style == "A":
        html = render_html_a(template)
    else:
        html = render_html_b(template)
    t0 = time.time()
    success = render_html_to_png(html, output_path)
    if success:
        size = os.path.getsize(output_path)
        print(f"  ✓ 风格 {style} 已保存：{output_path} ({size/1024:.0f}KB, {time.time()-t0:.1f}s)",
              file=sys.stderr)
    return success


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from analyze import analyze_all
    from collect_self import collect_all
    from snapshot import load_snapshot, CST
    from datetime import datetime, timezone, timedelta
    import argparse

    parser = argparse.ArgumentParser(description="职场人设卡 v5（两种野兽派风格）")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--output-dir", default="/tmp/self-distill-cards")
    parser.add_argument("--style", choices=["A", "B", "both"], default="both")
    args = parser.parse_args()

    CST = timezone(timedelta(hours=8))
    end = datetime.now(CST)
    start = end - timedelta(days=args.days)
    result = collect_all(
        start_iso=start.strftime("%Y-%m-%dT00:00:00+08:00"),
        end_iso=end.strftime("%Y-%m-%dT23:59:59+08:00"),
    )
    analysis = analyze_all(result.messages)

    old_snap = load_snapshot()
    join_date = "2026-06-11"
    if old_snap and old_snap.get("first_run_at"):
        join_date = old_snap["first_run_at"][:10]
    elif result.messages:
        join_date = result.messages[-1].create_time[:10]

    motto = analysis["slogan_candidates"][0] if analysis["slogan_candidates"] else "做有判断力的产品"
    mbti_code = "".join(d[0] for d in analysis["personality"]["mbti"].values())

    template = {
        "name": result.user_name,
        "mbti": mbti_code,
        "mbti_desc": MBTI_DESC.get(mbti_code, "多场景切换"),
        "sbti_code": analysis["sbti_style"]["code"],
        "sbti_label": analysis["sbti_style"]["label"],
        "sbti_desc": analysis["sbti_style"]["desc"],
        "sneaky_label": analysis["sneaky_label"]["label"],
        "sneaky_evidence": analysis["sneaky_label"]["evidence"],
        "personality_traits": analysis["personality_traits"],
        "slogan": motto,
        "slogan_long": analysis["slogan_long"],
        "kpi_happy": analysis["kpi_happy"],
        "animal": analysis["personality"]["animal"]["primary"],
        "animal_emoji": ANIMAL_EMOJI.get(analysis["personality"]["animal"]["primary"], "🐾"),
        "animal_match": int(analysis["personality"]["animal"]["primary_match"] * 100),
        "employee_id": result.user_id[-6:] if result.user_id else "000000",
        "join_date": join_date,
        "motto": motto,
        "date": time.strftime("%Y-%m-%d"),
        "date_short": time.strftime("%m/%d"),
    }

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.style in ["A", "both"]:
        out_a = output_dir / f"card_v5_A_{result.user_name}_{args.days}d.png"
        render_card(template, str(out_a), style="A")
    if args.style in ["B", "both"]:
        out_b = output_dir / f"card_v5_B_{result.user_name}_{args.days}d.png"
        render_card(template, str(out_b), style="B")

    print(f"\n✓ 完成", file=sys.stderr)
