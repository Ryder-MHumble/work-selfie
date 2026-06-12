#!/usr/bin/env python3
"""
self-distill 名片 v7 — Profile Card 比例

按 真实视觉反馈：
  - ❌ 1050x600（商业名片）不对——他说是 web 比例
  - ✅ 真正要的是 "Profile Card" 比例
  - 3 个变体让他选：1:1 / 3:4 / 9:16

设计风格继承 v6（紧凑 + 非对称 + 野兽派撞色 + 二次元 emoji）
"""

import os
import sys
import time
import json
import subprocess
import tempfile
import hashlib
import re
from pathlib import Path
from typing import Dict, Any, List

CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


# ============== 字体探测 ==============

_CJK_FP = None
try:
    from matplotlib import font_manager as _fm
    for _cand in ["PingFang HK", "Hiragino Sans GB", "STHeiti", "Heiti TC", "Hiragino Sans"]:
        for _af in _fm.fontManager.ttflist:
            if _af.name == _cand:
                _CJK_FP = _fm.FontProperties(fname=_af.fname)
                break
        if _CJK_FP: break
except Exception: pass


# ============== 工具 ==============

def make_barcode_bars(seed: str, bar_count: int = 22) -> str:
    h = hashlib.md5(seed.encode()).hexdigest()
    bars = []
    for i in range(bar_count):
        x = int(h[i % len(h)], 16)
        if x < 5: cls, w = "bar", 3
        elif x < 8: cls, w = "bar", 2
        elif x < 11: cls, w = "empty", 2
        elif x < 14: cls, w = "bar", 2
        else: cls, w = "empty", 1
        bars.append(f'<div class="{cls}" style="width:{w}px;"></div>')
    return ''.join(bars)


def build_traits_html(traits: List[Dict[str, str]]) -> str:
    items = []
    for t in traits[:6]:
        items.append(f'''
        <div class="trait">
          <div class="trait-icon">{t["icon"]}</div>
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
        items.append(f'''
        <div class="kpi-item">
          <span class="kpi-check {'on' if done else 'off'}">{k.get("icon", "✓")}</span>
          <div class="kpi-body">
            <div class="kpi-name">{k["name"]}</div>
            <div class="kpi-evidence">{k["evidence"]}</div>
          </div>
        </div>''')
    return ''.join(items)


# ============== 模板 1:1 (900x900) 正方形 Profile Card ==============

TEMPLATE_1X1 = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  html, body {{
    width: 900px; height: 900px;
    overflow: hidden;
    font-family: 'PingFang HK', 'Hiragino Sans GB', 'STHeiti', 'Noto Sans CJK SC', sans-serif;
  }}
  body {{
    background: #F4EFE3;
    color: #0A0A0A;
    position: relative;
  }}

  /* 背景几何 */
  .bg-1 {{ position: absolute; top: -80px; right: -60px; width: 360px; height: 360px;
          background: #F4C430; transform: rotate(15deg); z-index: 1; }}
  .bg-2 {{ position: absolute; bottom: 200px; left: -30px; width: 180px; height: 180px;
          background: #D62828; transform: rotate(-20deg); z-index: 1; }}
  .bg-3 {{ position: absolute; top: 380px; right: 100px; width: 70px; height: 70px;
          background: #0A0A0A; transform: rotate(45deg); z-index: 1; }}

  .noise {{
    position: absolute; inset: 0; z-index: 50; pointer-events: none; opacity: 0.18;
    background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='200' height='200'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.9'/></filter><rect width='200' height='200' filter='url(%23n)' opacity='0.5'/></svg>");
  }}

  .card {{ position: relative; z-index: 10; width: 900px; height: 900px; padding: 36px 44px; }}

  .top-strip {{
    display: flex; justify-content: space-between; align-items: center;
    font-size: 11px; font-weight: 800;
    letter-spacing: 0.3em; text-transform: uppercase;
    color: #0A0A0A;
    border-bottom: 3px solid #0A0A0A;
    padding-bottom: 8px; margin-bottom: 24px;
  }}
  .mvp {{ background: #0A0A0A; color: #F4C430; padding: 3px 10px; }}

  /* 上半部：姓名 + 动物徽章 */
  .hero {{
    display: grid;
    grid-template-columns: 1fr 130px;
    gap: 20px;
    align-items: end;
    margin-bottom: 20px;
  }}
  .name-eyebrow {{
    font-size: 12px; font-weight: 700;
    letter-spacing: 0.4em; color: #D62828;
    text-transform: uppercase; margin-bottom: 6px;
  }}
  .name {{
    font-size: 110px; font-weight: 900;
    line-height: 0.9; color: #0A0A0A;
    letter-spacing: -0.04em;
  }}
  .animal-badge {{
    width: 130px; height: 130px;
    background: #F4C430;
    border: 4px solid #0A0A0A;
    border-radius: 50%;
    display: flex; flex-direction: column;
    align-items: center; justify-content: center;
    font-size: 60px;
    box-shadow: 5px 5px 0 #0A0A0A;
  }}
  .animal-name {{ font-size: 11px; font-weight: 900; color: #0A0A0A; letter-spacing: 0.1em; }}
  .animal-pct {{ font-size: 12px; font-weight: 700; color: #D62828; }}

  /* 中部：SBTI + MBTI（横向并列） */
  .identity-row {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 14px;
    margin-bottom: 20px;
  }}
  .sbti-block {{
    background: #0A0A0A;
    color: white;
    padding: 12px 16px;
    transform: rotate(-1deg);
  }}
  .sbti-label {{
    font-size: 10px; font-weight: 700;
    color: #F4C430; letter-spacing: 0.3em;
    text-transform: uppercase; margin-bottom: 4px;
  }}
  .sbti-row {{ display: flex; align-items: baseline; gap: 10px; margin-bottom: 4px; }}
  .sbti-tag {{ font-size: 20px; font-weight: 900; color: white; }}
  .sbti-code {{ font-size: 40px; font-weight: 900; color: #F4C430; line-height: 1; }}
  .sbti-desc {{
    font-size: 11px; font-weight: 500; color: white;
    margin-top: 6px; line-height: 1.3;
  }}
  .mbti-block {{
    background: #D62828;
    color: white;
    padding: 12px 16px;
    transform: rotate(1deg);
  }}
  .mbti-label {{
    font-size: 10px; font-weight: 700;
    color: white; letter-spacing: 0.3em;
    text-transform: uppercase; margin-bottom: 4px;
    opacity: 0.8;
  }}
  .mbti-code {{
    font-size: 52px; font-weight: 900; color: white;
    line-height: 0.9; letter-spacing: 0.02em;
  }}
  .mbti-desc {{
    font-size: 11px; font-weight: 600; color: white;
    margin-top: 6px; line-height: 1.3; opacity: 0.95;
  }}

  /* 性格 6 宫格 */
  .traits-title {{
    font-size: 11px; font-weight: 800;
    letter-spacing: 0.3em; text-transform: uppercase;
    color: #0A0A0A; margin-bottom: 8px;
  }}
  .traits-title::before {{ content: "▍"; color: #D62828; margin-right: 4px; }}
  .traits-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 8px 10px;
    margin-bottom: 18px;
  }}
  .trait {{
    display: flex; gap: 6px; align-items: flex-start;
    padding: 6px 8px;
    background: rgba(255,255,255,0.7);
    border-left: 3px solid #0A0A0A;
  }}
  .trait-icon {{ font-size: 18px; flex-shrink: 0; }}
  .trait-body {{ flex: 1; min-width: 0; }}
  .trait-title {{ font-size: 12px; font-weight: 800; color: #0A0A0A; line-height: 1.1; }}
  .trait-desc {{ font-size: 10px; font-weight: 500; color: #555; line-height: 1.2; }}

  /* KPI + 宣言 - 双列 */
  .bottom-row {{
    display: grid;
    grid-template-columns: 1fr 1.2fr;
    gap: 14px;
  }}
  .kpi-section {{
    background: rgba(255,255,255,0.7);
    border: 2px solid #0A0A0A;
    padding: 10px 12px;
  }}
  .kpi-title {{
    font-size: 11px; font-weight: 800;
    letter-spacing: 0.3em; text-transform: uppercase;
    color: #0A0A0A; margin-bottom: 6px;
  }}
  .kpi-title::before {{ content: "▍"; color: #D62828; margin-right: 4px; }}
  .kpi-items {{ display: flex; flex-direction: column; gap: 4px; }}
  .kpi-item {{ display: flex; gap: 6px; align-items: center; font-size: 12px; }}
  .kpi-check {{ font-size: 16px; font-weight: 900; }}
  .kpi-check.on {{ color: #D62828; }}
  .kpi-check.off {{ color: #888; }}
  .kpi-name {{ font-size: 12px; font-weight: 800; color: #0A0A0A; }}
  .kpi-evidence {{ font-size: 10px; color: #666; margin-left: 4px; }}

  .manifesto {{
    background: #0A0A0A;
    color: #F4C430;
    padding: 12px 16px;
    position: relative;
    border-left: 6px solid #D62828;
  }}
  .manifesto::before {{
    content: "👑";
    position: absolute;
    top: -10px; right: 14px;
    font-size: 22px;
  }}
  .manifesto-label {{
    font-size: 10px; font-weight: 700;
    letter-spacing: 0.3em; text-transform: uppercase;
    color: #F4C430; margin-bottom: 4px;
    opacity: 0.7;
  }}
  .manifesto-text {{
    font-size: 15px; font-weight: 900;
    line-height: 1.5; color: white;
    white-space: pre-line;
  }}

  /* 底部条 */
  .bottom-strip {{
    position: absolute;
    bottom: 20px; left: 44px; right: 44px;
    display: flex; justify-content: space-between; align-items: center;
    z-index: 11;
    font-size: 10px; font-weight: 700; color: #0A0A0A;
  }}
  .sneaky-tag {{
    background: #D62828; color: white;
    padding: 4px 12px; font-size: 10px; font-weight: 900;
    border: 2px solid #0A0A0A;
    transform: rotate(-2deg);
  }}
  .barcode-block {{
    background: white; border: 1px solid #0A0A0A; padding: 3px 6px;
  }}
  .barcode {{ display: flex; gap: 1px; height: 20px; }}
  .bar {{ background: #0A0A0A; }}
  .bar.empty {{ background: white; }}
  .barcode-text {{
    font-size: 7px; font-weight: 700; color: #0A0A0A;
    font-family: 'SF Mono', monospace; margin-top: 1px;
  }}
</style>
</head>
<body>
  <div class="bg-1"></div>
  <div class="bg-2"></div>
  <div class="bg-3"></div>

  <div class="card">
    <div class="top-strip">
      <div>SELF-DISTILL · {date}</div>
      <div class="mvp">★ MVP ★</div>
    </div>

    <div class="hero">
      <div>
        <div class="name-eyebrow">▍My Profile Card</div>
        <div class="name">{name}</div>
      </div>
      <div class="animal-badge">
        <div>{animal_emoji}</div>
        <div class="animal-name">{animal}</div>
        <div class="animal-pct">{animal_match}%</div>
      </div>
    </div>

    <div class="identity-row">
      <div class="sbti-block">
        <div class="sbti-label">01 · 职场 SBTI</div>
        <div class="sbti-row">
          <span class="sbti-tag">{sbti_label}</span>
        </div>
        <div class="sbti-code">{sbti_code}</div>
        <div class="sbti-desc">{sbti_desc}</div>
      </div>
      <div class="mbti-block">
        <div class="mbti-label">02 · MBTI</div>
        <div class="mbti-code">{mbti}</div>
        <div class="mbti-desc">{mbti_desc}</div>
      </div>
    </div>

    <div class="traits-title">03 · 性格特征</div>
    <div class="traits-grid">
      {traits_html}
    </div>

    <div class="bottom-row">
      <div class="kpi-section">
        <div class="kpi-title">今日KPI（快乐版）</div>
        <div class="kpi-items">
          {kpi_items}
        </div>
      </div>
      <div class="manifesto">
        <div class="manifesto-label">职场宣言</div>
        <div class="manifesto-text">{slogan_long}</div>
      </div>
    </div>

    <div class="bottom-strip">
      <div class="sneaky-tag">摸鱼伪装大师 · {sneaky_label}</div>
      <div style="display:flex; gap:8px; align-items:center;">
        <span>入职 {join_date} · 工号 {employee_id}</span>
        <div class="barcode-block">
          <div class="barcode">{barcode_bars}</div>
          <div class="barcode-text">SELF-DISTILL</div>
        </div>
      </div>
    </div>
  </div>

  <div class="noise"></div>
</body>
</html>'''


# ============== 模板 4:5 (800x1000) 社交帖子图 ==============

TEMPLATE_4X5 = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  html, body {{
    width: 800px; height: 1000px;
    overflow: hidden;
    font-family: 'PingFang HK', 'Hiragino Sans GB', 'STHeiti', 'Noto Sans CJK SC', sans-serif;
  }}
  body {{ background: #F4EFE3; color: #0A0A0A; position: relative; }}

  /* 4:5 竖向布局调整 */
  .bg-1 {{ position: absolute; top: -60px; right: -40px; width: 280px; height: 280px;
          background: #F4C430; transform: rotate(15deg); z-index: 1; }}
  .bg-2 {{ position: absolute; bottom: 100px; left: -30px; width: 160px; height: 160px;
          background: #D62828; transform: rotate(-20deg); z-index: 1; }}
  .bg-3 {{ position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%) rotate(45deg);
          width: 50px; height: 50px; background: #0A0A0A; z-index: 1; }}

  .noise {{
    position: absolute; inset: 0; z-index: 50; pointer-events: none; opacity: 0.18;
    background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='200' height='200'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.9'/></filter><rect width='200' height='200' filter='url(%23n)' opacity='0.5'/></svg>");
  }}

  .card {{ position: relative; z-index: 10; width: 800px; height: 1000px; padding: 32px 40px; }}

  .top-strip {{
    display: flex; justify-content: space-between; align-items: center;
    font-size: 10px; font-weight: 800; letter-spacing: 0.3em; text-transform: uppercase;
    color: #0A0A0A; border-bottom: 3px solid #0A0A0A;
    padding-bottom: 6px; margin-bottom: 18px;
  }}
  .mvp {{ background: #0A0A0A; color: #F4C430; padding: 3px 10px; }}

  .hero {{
    display: grid; grid-template-columns: 1fr 120px;
    gap: 16px; align-items: center; margin-bottom: 18px;
  }}
  .name-eyebrow {{
    font-size: 11px; font-weight: 700; letter-spacing: 0.4em;
    color: #D62828; text-transform: uppercase; margin-bottom: 4px;
  }}
  .name {{
    font-size: 92px; font-weight: 900; line-height: 0.92;
    color: #0A0A0A; letter-spacing: -0.04em;
  }}
  .animal-badge {{
    width: 120px; height: 120px;
    background: #F4C430; border: 4px solid #0A0A0A;
    border-radius: 50%; display: flex; flex-direction: column;
    align-items: center; justify-content: center;
    font-size: 56px; box-shadow: 5px 5px 0 #0A0A0A;
  }}
  .animal-name {{ font-size: 11px; font-weight: 900; color: #0A0A0A; }}
  .animal-pct {{ font-size: 11px; font-weight: 700; color: #D62828; }}

  .identity-row {{
    display: grid; grid-template-columns: 1fr 1fr; gap: 12px;
    margin-bottom: 16px;
  }}
  .sbti-block {{
    background: #0A0A0A; color: white;
    padding: 10px 14px; transform: rotate(-1deg);
  }}
  .sbti-label {{ font-size: 9px; font-weight: 700; color: #F4C430;
                  letter-spacing: 0.3em; text-transform: uppercase; margin-bottom: 3px; }}
  .sbti-row {{ display: flex; align-items: baseline; gap: 8px; margin-bottom: 3px; }}
  .sbti-tag {{ font-size: 17px; font-weight: 900; color: white; }}
  .sbti-code {{ font-size: 36px; font-weight: 900; color: #F4C430; line-height: 1; }}
  .sbti-desc {{ font-size: 10px; font-weight: 500; color: white; margin-top: 4px; line-height: 1.3; }}
  .mbti-block {{
    background: #D62828; color: white;
    padding: 10px 14px; transform: rotate(1deg);
  }}
  .mbti-label {{ font-size: 9px; font-weight: 700; color: white;
                  letter-spacing: 0.3em; text-transform: uppercase; margin-bottom: 3px; opacity: 0.8; }}
  .mbti-code {{ font-size: 48px; font-weight: 900; color: white; line-height: 0.9; }}
  .mbti-desc {{ font-size: 10px; font-weight: 600; color: white; margin-top: 4px; line-height: 1.3; opacity: 0.95; }}

  .traits-title {{
    font-size: 10px; font-weight: 800; letter-spacing: 0.3em;
    text-transform: uppercase; color: #0A0A0A; margin-bottom: 6px;
  }}
  .traits-title::before {{ content: "▍"; color: #D62828; margin-right: 4px; }}
  .traits-grid {{
    display: grid; grid-template-columns: 1fr 1fr 1fr;
    gap: 6px 8px; margin-bottom: 14px;
  }}
  .trait {{
    display: flex; gap: 5px; align-items: flex-start;
    padding: 5px 6px;
    background: rgba(255,255,255,0.7);
    border-left: 3px solid #0A0A0A;
  }}
  .trait-icon {{ font-size: 16px; flex-shrink: 0; }}
  .trait-body {{ flex: 1; min-width: 0; }}
  .trait-title {{ font-size: 11px; font-weight: 800; color: #0A0A0A; line-height: 1.1; }}
  .trait-desc {{ font-size: 9px; font-weight: 500; color: #555; line-height: 1.2; }}

  /* 4:5 竖向布局：底部区域更大 */
  .bottom-section {{
    display: flex; flex-direction: column; gap: 12px;
    margin-top: 10px;
  }}
  .kpi-section {{
    background: rgba(255,255,255,0.7);
    border: 2px solid #0A0A0A;
    padding: 10px 14px;
  }}
  .kpi-title {{
    font-size: 11px; font-weight: 800;
    letter-spacing: 0.3em; text-transform: uppercase;
    color: #0A0A0A; margin-bottom: 6px;
  }}
  .kpi-title::before {{ content: "▍"; color: #D62828; margin-right: 4px; }}
  .kpi-items {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 6px; }}
  .kpi-item {{ display: flex; gap: 5px; align-items: center; }}
  .kpi-check {{ font-size: 16px; font-weight: 900; }}
  .kpi-check.on {{ color: #D62828; }}
  .kpi-check.off {{ color: #888; }}
  .kpi-name {{ font-size: 11px; font-weight: 800; color: #0A0A0A; }}
  .kpi-evidence {{ font-size: 9px; color: #666; margin-left: 3px; }}

  .manifesto {{
    background: #0A0A0A; color: #F4C430;
    padding: 12px 16px; position: relative;
    border-left: 6px solid #D62828;
  }}
  .manifesto::before {{
    content: "👑"; position: absolute;
    top: -10px; right: 14px; font-size: 22px;
  }}
  .manifesto-label {{
    font-size: 10px; font-weight: 700;
    letter-spacing: 0.3em; text-transform: uppercase;
    color: #F4C430; margin-bottom: 4px; opacity: 0.7;
  }}
  .manifesto-text {{
    font-size: 15px; font-weight: 900;
    line-height: 1.5; color: white;
    white-space: pre-line;
  }}

  .bottom-strip {{
    position: absolute; bottom: 18px; left: 40px; right: 40px;
    display: flex; justify-content: space-between; align-items: center;
    z-index: 11; font-size: 10px; font-weight: 700; color: #0A0A0A;
  }}
  .sneaky-tag {{
    background: #D62828; color: white;
    padding: 4px 12px; font-size: 10px; font-weight: 900;
    border: 2px solid #0A0A0A; transform: rotate(-2deg);
  }}
  .barcode-block {{ background: white; border: 1px solid #0A0A0A; padding: 3px 6px; }}
  .barcode {{ display: flex; gap: 1px; height: 20px; }}
  .bar {{ background: #0A0A0A; }}
  .bar.empty {{ background: white; }}
  .barcode-text {{ font-size: 7px; font-weight: 700; color: #0A0A0A;
                    font-family: 'SF Mono', monospace; margin-top: 1px; }}
</style>
</head>
<body>
  <div class="bg-1"></div>
  <div class="bg-2"></div>
  <div class="bg-3"></div>

  <div class="card">
    <div class="top-strip">
      <div>SELF-DISTILL · {date}</div>
      <div class="mvp">★ MVP ★</div>
    </div>

    <div class="hero">
      <div>
        <div class="name-eyebrow">▍My Profile Card</div>
        <div class="name">{name}</div>
      </div>
      <div class="animal-badge">
        <div>{animal_emoji}</div>
        <div class="animal-name">{animal}</div>
        <div class="animal-pct">{animal_match}%</div>
      </div>
    </div>

    <div class="identity-row">
      <div class="sbti-block">
        <div class="sbti-label">01 · 职场 SBTI</div>
        <div class="sbti-row"><span class="sbti-tag">{sbti_label}</span></div>
        <div class="sbti-code">{sbti_code}</div>
        <div class="sbti-desc">{sbti_desc}</div>
      </div>
      <div class="mbti-block">
        <div class="mbti-label">02 · MBTI</div>
        <div class="mbti-code">{mbti}</div>
        <div class="mbti-desc">{mbti_desc}</div>
      </div>
    </div>

    <div class="traits-title">03 · 性格特征</div>
    <div class="traits-grid">
      {traits_html}
    </div>

    <div class="bottom-section">
      <div class="kpi-section">
        <div class="kpi-title">今日KPI（快乐版）</div>
        <div class="kpi-items">
          {kpi_items}
        </div>
      </div>
      <div class="manifesto">
        <div class="manifesto-label">职场宣言</div>
        <div class="manifesto-text">{slogan_long}</div>
      </div>
    </div>

    <div class="bottom-strip">
      <div class="sneaky-tag">摸鱼伪装大师 · {sneaky_label}</div>
      <div style="display:flex; gap:8px; align-items:center;">
        <span>入职 {join_date} · 工号 {employee_id}</span>
        <div class="barcode-block">
          <div class="barcode">{barcode_bars}</div>
          <div class="barcode-text">SELF-DISTILL</div>
        </div>
      </div>
    </div>
  </div>

  <div class="noise"></div>
</body>
</html>'''


# ============== 模板 9:16 (720x1280) IG/TikTok Profile ==============

TEMPLATE_9X16 = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  html, body {{
    width: 720px; height: 1280px;
    overflow: hidden;
    font-family: 'PingFang HK', 'Hiragino Sans GB', 'STHeiti', 'Noto Sans CJK SC', sans-serif;
  }}
  body {{ background: #F4EFE3; color: #0A0A0A; position: relative; }}

  .bg-1 {{ position: absolute; top: -60px; right: -40px; width: 240px; height: 240px;
          background: #F4C430; transform: rotate(15deg); z-index: 1; }}
  .bg-2 {{ position: absolute; bottom: 250px; left: -30px; width: 140px; height: 140px;
          background: #D62828; transform: rotate(-20deg); z-index: 1; }}
  .bg-3 {{ position: absolute; top: 60%; left: 80%; transform: rotate(45deg);
          width: 50px; height: 50px; background: #0A0A0A; z-index: 1; }}

  .noise {{
    position: absolute; inset: 0; z-index: 50; pointer-events: none; opacity: 0.18;
    background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='200' height='200'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.9'/></filter><rect width='200' height='200' filter='url(%23n)' opacity='0.5'/></svg>");
  }}

  .card {{ position: relative; z-index: 10; width: 720px; height: 1280px; padding: 30px 36px; }}

  .top-strip {{
    display: flex; justify-content: space-between; align-items: center;
    font-size: 10px; font-weight: 800; letter-spacing: 0.3em; text-transform: uppercase;
    color: #0A0A0A; border-bottom: 3px solid #0A0A0A;
    padding-bottom: 6px; margin-bottom: 16px;
  }}
  .mvp {{ background: #0A0A0A; color: #F4C430; padding: 3px 10px; }}

  .hero {{
    text-align: center;
    margin-bottom: 20px;
    position: relative;
  }}
  .name-eyebrow {{
    font-size: 11px; font-weight: 700; letter-spacing: 0.4em;
    color: #D62828; text-transform: uppercase; margin-bottom: 6px;
  }}
  .name {{
    font-size: 100px; font-weight: 900; line-height: 0.92;
    color: #0A0A0A; letter-spacing: -0.04em;
  }}
  .animal-badge {{
    position: absolute;
    top: 10px; right: -10px;
    width: 100px; height: 100px;
    background: #F4C430; border: 4px solid #0A0A0A;
    border-radius: 50%; display: flex; flex-direction: column;
    align-items: center; justify-content: center;
    font-size: 48px; box-shadow: 4px 4px 0 #0A0A0A;
  }}
  .animal-name {{ font-size: 9px; font-weight: 900; color: #0A0A0A; letter-spacing: 0.05em; }}
  .animal-pct {{ font-size: 10px; font-weight: 700; color: #D62828; }}

  /* 9:16 用纵向堆叠：SBTI → MBTI → 性格 → KPI → 宣言 */
  .vertical-stack {{ display: flex; flex-direction: column; gap: 14px; }}

  .sbti-block {{
    background: #0A0A0A; color: white;
    padding: 12px 16px; transform: rotate(-1deg);
  }}
  .sbti-label {{ font-size: 10px; font-weight: 700; color: #F4C430;
                  letter-spacing: 0.3em; text-transform: uppercase; margin-bottom: 4px; }}
  .sbti-row {{ display: flex; align-items: baseline; gap: 10px; margin-bottom: 4px; }}
  .sbti-tag {{ font-size: 18px; font-weight: 900; color: white; }}
  .sbti-code {{ font-size: 40px; font-weight: 900; color: #F4C430; line-height: 1; }}
  .sbti-desc {{ font-size: 11px; font-weight: 500; color: white; margin-top: 4px; line-height: 1.3; }}

  .mbti-block {{
    background: #D62828; color: white;
    padding: 12px 16px; transform: rotate(1deg);
  }}
  .mbti-label {{ font-size: 10px; font-weight: 700; color: white;
                  letter-spacing: 0.3em; text-transform: uppercase; margin-bottom: 4px; opacity: 0.8; }}
  .mbti-code {{ font-size: 50px; font-weight: 900; color: white; line-height: 0.9; }}
  .mbti-desc {{ font-size: 11px; font-weight: 600; color: white; margin-top: 4px; line-height: 1.3; opacity: 0.95; }}

  .traits-title {{
    font-size: 10px; font-weight: 800; letter-spacing: 0.3em;
    text-transform: uppercase; color: #0A0A0A; margin-bottom: 6px;
  }}
  .traits-title::before {{ content: "▍"; color: #D62828; margin-right: 4px; }}
  .traits-grid {{
    display: grid; grid-template-columns: 1fr 1fr;
    gap: 8px 10px;
  }}
  .trait {{
    display: flex; gap: 6px; align-items: flex-start;
    padding: 6px 8px;
    background: rgba(255,255,255,0.7);
    border-left: 3px solid #0A0A0A;
  }}
  .trait-icon {{ font-size: 16px; flex-shrink: 0; }}
  .trait-body {{ flex: 1; min-width: 0; }}
  .trait-title {{ font-size: 12px; font-weight: 800; color: #0A0A0A; line-height: 1.1; }}
  .trait-desc {{ font-size: 10px; font-weight: 500; color: #555; line-height: 1.2; }}

  .kpi-section {{
    background: rgba(255,255,255,0.7);
    border: 2px solid #0A0A0A;
    padding: 10px 14px;
  }}
  .kpi-title {{
    font-size: 11px; font-weight: 800;
    letter-spacing: 0.3em; text-transform: uppercase;
    color: #0A0A0A; margin-bottom: 6px;
  }}
  .kpi-title::before {{ content: "▍"; color: #D62828; margin-right: 4px; }}
  .kpi-items {{ display: flex; flex-direction: column; gap: 4px; }}
  .kpi-item {{ display: flex; gap: 6px; align-items: center; }}
  .kpi-check {{ font-size: 16px; font-weight: 900; }}
  .kpi-check.on {{ color: #D62828; }}
  .kpi-check.off {{ color: #888; }}
  .kpi-name {{ font-size: 12px; font-weight: 800; color: #0A0A0A; }}
  .kpi-evidence {{ font-size: 10px; color: #666; margin-left: 4px; }}

  .manifesto {{
    background: #0A0A0A; color: #F4C430;
    padding: 14px 18px; position: relative;
    border-left: 6px solid #D62828;
  }}
  .manifesto::before {{
    content: "👑"; position: absolute;
    top: -10px; right: 14px; font-size: 22px;
  }}
  .manifesto-label {{
    font-size: 10px; font-weight: 700;
    letter-spacing: 0.3em; text-transform: uppercase;
    color: #F4C430; margin-bottom: 4px; opacity: 0.7;
  }}
  .manifesto-text {{
    font-size: 16px; font-weight: 900;
    line-height: 1.5; color: white;
    white-space: pre-line;
  }}

  .bottom-strip {{
    position: absolute; bottom: 18px; left: 36px; right: 36px;
    display: flex; justify-content: space-between; align-items: center;
    z-index: 11; font-size: 10px; font-weight: 700; color: #0A0A0A;
  }}
  .sneaky-tag {{
    background: #D62828; color: white;
    padding: 4px 12px; font-size: 10px; font-weight: 900;
    border: 2px solid #0A0A0A; transform: rotate(-2deg);
  }}
  .barcode-block {{ background: white; border: 1px solid #0A0A0A; padding: 3px 6px; }}
  .barcode {{ display: flex; gap: 1px; height: 20px; }}
  .bar {{ background: #0A0A0A; }}
  .bar.empty {{ background: white; }}
  .barcode-text {{ font-size: 7px; font-weight: 700; color: #0A0A0A;
                    font-family: 'SF Mono', monospace; margin-top: 1px; }}
</style>
</head>
<body>
  <div class="bg-1"></div>
  <div class="bg-2"></div>
  <div class="bg-3"></div>

  <div class="card">
    <div class="top-strip">
      <div>SELF-DISTILL · {date}</div>
      <div class="mvp">★ MVP ★</div>
    </div>

    <div class="hero">
      <div class="animal-badge">
        <div>{animal_emoji}</div>
        <div class="animal-name">{animal}</div>
        <div class="animal-pct">{animal_match}%</div>
      </div>
      <div class="name-eyebrow">▍My Profile</div>
      <div class="name">{name}</div>
    </div>

    <div class="vertical-stack">
      <div class="sbti-block">
        <div class="sbti-label">01 · 职场 SBTI</div>
        <div class="sbti-row"><span class="sbti-tag">{sbti_label}</span></div>
        <div class="sbti-code">{sbti_code}</div>
        <div class="sbti-desc">{sbti_desc}</div>
      </div>
      <div class="mbti-block">
        <div class="mbti-label">02 · MBTI</div>
        <div class="mbti-code">{mbti}</div>
        <div class="mbti-desc">{mbti_desc}</div>
      </div>
    </div>

    <div class="traits-title" style="margin-top:14px;">03 · 性格特征</div>
    <div class="traits-grid">
      {traits_html}
    </div>

    <div style="margin-top:14px;">
      <div class="kpi-section">
        <div class="kpi-title">今日KPI（快乐版）</div>
        <div class="kpi-items">
          {kpi_items}
        </div>
      </div>
    </div>

    <div style="margin-top:14px;">
      <div class="manifesto">
        <div class="manifesto-label">职场宣言</div>
        <div class="manifesto-text">{slogan_long}</div>
      </div>
    </div>

    <div class="bottom-strip">
      <div class="sneaky-tag">摸鱼伪装大师 · {sneaky_label}</div>
      <div style="display:flex; gap:8px; align-items:center;">
        <span>{join_date} · {employee_id}</span>
        <div class="barcode-block">
          <div class="barcode">{barcode_bars}</div>
          <div class="barcode-text">SELF-DISTILL</div>
        </div>
      </div>
    </div>
  </div>

  <div class="noise"></div>
</body>
</html>'''


TEMPLATES = {
    "1x1": (TEMPLATE_1X1, 900, 900),
    "4x5": (TEMPLATE_4X5, 800, 1000),
    "9x16": (TEMPLATE_9X16, 720, 1280),
}


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


def render_html(t: Dict[str, Any], style: str = "1x1") -> str:
    template_str, w, h = TEMPLATES[style]
    return template_str.format(
        name=t["name"],
        date=t.get("date", ""),
        mbti=t["mbti"],
        mbti_desc=t.get("mbti_desc", ""),
        sbti_code=t.get("sbti_code", "????"),
        sbti_label=t.get("sbti_label", ""),
        sbti_desc=t.get("sbti_desc", ""),
        animal=t.get("animal", "?"),
        animal_emoji=t.get("animal_emoji", "🐾"),
        animal_match=t.get("animal_match", 0),
        sneaky_label=t.get("sneaky_label", ""),
        slogan_long=t.get("slogan_long", ""),
        traits_html=build_traits_html(t.get("personality_traits", [])),
        kpi_items=build_kpi_items(t.get("kpi_happy", [])),
        employee_id=t.get("employee_id", "000000"),
        join_date=t.get("join_date", ""),
        barcode_bars=make_barcode_bars(t.get("employee_id", "0")),
    )


def render_html_to_png(html: str, output: str, w: int, h: int) -> bool:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False, encoding="utf-8") as f:
        f.write(html); html_path = f.name
    try:
        cmd = [CHROME_PATH, "--headless=new", "--disable-gpu", "--no-sandbox",
               "--hide-scrollbars", "--force-device-scale-factor=1",
               f"--screenshot={output}", f"--window-size={w},{h}",
               "--virtual-time-budget=5000", f"file://{html_path}"]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return r.returncode == 0 and os.path.exists(output)
    finally:
        try: os.unlink(html_path)
        except OSError: pass


def render_card(t: Dict[str, Any], output: str, style: str = "1x1") -> bool:
    html = render_html(t, style)
    _, w, h = TEMPLATES[style]
    t0 = time.time()
    ok = render_html_to_png(html, output, w, h)
    if ok:
        print(f"  ✓ {style} ({w}x{h}) → {output} ({os.path.getsize(output)/1024:.0f}KB, {time.time()-t0:.1f}s)",
              file=sys.stderr)
    return ok


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from analyze import analyze_all
    from collect_self import collect_all
    from snapshot import load_snapshot
    from datetime import datetime, timezone, timedelta
    import argparse

    parser = argparse.ArgumentParser(description="名片 v7（3 个 Profile Card 比例）")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--output-dir", default="/tmp/self-distill-cards")
    parser.add_argument("--style", choices=["1x1", "4x5", "9x16", "all"], default="all")
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
    join_date = result.messages[-1].create_time[:10] if result.messages else end.strftime("%Y-%m-%d")
    if old_snap and old_snap.get("first_run_at"):
        join_date = old_snap["first_run_at"][:10]

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
        "personality_traits": analysis["personality_traits"],
        "slogan_long": analysis["slogan_long"],
        "kpi_happy": analysis["kpi_happy"],
        "animal": analysis["personality"]["animal"]["primary"],
        "animal_emoji": ANIMAL_EMOJI.get(analysis["personality"]["animal"]["primary"], "🐾"),
        "animal_match": int(analysis["personality"]["animal"]["primary_match"] * 100),
        "employee_id": result.user_id[-6:] if result.user_id else "000000",
        "join_date": join_date,
        "date": time.strftime("%Y-%m-%d"),
    }

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    styles = ["1x1", "4x5", "9x16"] if args.style == "all" else [args.style]
    for s in styles:
        out = output_dir / f"card_v7_{s}_{result.user_name}_{args.days}d.png"
        render_card(template, str(out), style=s)
    print(f"\n✓ 完成 {len(styles)} 张", file=sys.stderr)
