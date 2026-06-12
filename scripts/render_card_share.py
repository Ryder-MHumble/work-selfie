#!/usr/bin/env python3
"""
self-distill 野兽派×二次元 个人名片 v3 (分享版)

设计目标：3 秒看懂、视觉冲击 > 信息密度，给"分享给别人"用。
和 v2 (render_card.py) 区分：v2 是自查报告封面 (信息密度高)，v3 是社交分享卡片 (冲击优先)。

布局 (1200x1200)：
  ┌──────────────────────────────────┐
  │  ◢ 朱红三角        签 名         │
  │  ▍姓名 RYDER  (巨大野兽派字)      │
  │  ▍INTJ  (黄底爆炸气泡)            │
  │         ┌──────────┐  ◣ 黄方块   │
  │         │  ◉  ◉   │              │
  │         │  短发 锐眉│              │
  │         │  中性表情│              │
  │         └──────────┘              │
  │  slogan 卡片          动物 + 日期 │
  └──────────────────────────────────┘

调色 (严格遵循 card-style-guide.md)：
  bg  #1A2B5E  fg #FFFFFF  accent-red #D62828  accent-yellow #F4C430  ink #0A0A0A
"""

import os
import sys
import time
import subprocess
import tempfile
import argparse
from pathlib import Path
from string import Template
from typing import Optional

CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

CANVAS = 1200  # 1200x1200 方形

# 调色板 (从 card-style-guide.md)
PALETTE = {
    "bg":          "#1A2B5E",  # 深钴蓝
    "fg":          "#FFFFFF",  # 纯白
    "red":         "#D62828",  # 朱红
    "yellow":      "#F4C430",  # 高饱和黄
    "ink":         "#0A0A0A",  # 浓黑
    "skin":        "#F8D7B5",  # 二次元肤色
    "iris":        "#D62828",  # 虹膜朱红
    "iris_dark":   "#7A1818",
}


# ---------- 二次元眼 (精细版，复用 v2 思路但更大更锐) ----------

def anime_eye_svg(size: int = 280, iris_color: str = "#D62828",
                  gaze_x: int = 0, gaze_y: int = -8) -> str:
    """二次元眼：椭圆眼白 + 大虹膜 + 双重高光 + 锐角上眼睑"""
    cx, cy = size // 2, size // 2
    eye_w = int(size * 0.6)
    eye_h = int(size * 0.9)
    cx += gaze_x
    cy += gaze_y

    svg = f'''<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}" xmlns="http://www.w3.org/2000/svg">
      <!-- 眼下淡红阴影 -->
      <ellipse cx="{cx}" cy="{cy + eye_h*0.32}" rx="{eye_w*0.62}" ry="{eye_h*0.14}"
               fill="#E8A98A" opacity="0.55"/>
      <!-- 眼白 -->
      <ellipse cx="{cx}" cy="{cy}" rx="{eye_w/2}" ry="{eye_h/2}"
               fill="#FFFFFF" stroke="#0A0A0A" stroke-width="4"/>
      <!-- 虹膜 (大半圆，被下眼睑遮) -->
      <path d="M {cx - eye_w*0.4} {cy + eye_h*0.05}
               A {eye_h*0.42} {eye_h*0.42} 0 0 1 {cx + eye_w*0.4} {cy + eye_h*0.05}
               L {cx + eye_w*0.4} {cy + eye_h*0.5}
               L {cx - eye_w*0.4} {cy + eye_h*0.5} Z"
            fill="url(#iris-grad-{size})" stroke="#0A0A0A" stroke-width="3"/>
      <!-- 瞳孔 -->
      <ellipse cx="{cx}" cy="{cy + eye_h*0.05}" rx="{eye_h*0.12}" ry="{eye_h*0.18}" fill="#0A0A0A"/>
      <!-- 主高光 -->
      <ellipse cx="{cx - eye_h*0.14}" cy="{cy - eye_h*0.20}" rx="{eye_h*0.13}" ry="{eye_h*0.22}" fill="#FFFFFF"/>
      <!-- 副高光 -->
      <circle cx="{cx + eye_h*0.16}" cy="{cy + eye_h*0.10}" r="{eye_h*0.07}" fill="#FFFFFF"/>
      <!-- 锐利上眼睑 (野兽派粗黑线 + 锐角延长) -->
      <path d="M {cx - eye_w/2 - 6} {cy - eye_h*0.05}
               Q {cx} {cy - eye_h*0.58}, {cx + eye_w/2 + 4} {cy - eye_h*0.12}
               L {cx + eye_w/2 + 22} {cy - eye_h*0.28}
               L {cx + eye_w/2 + 8} {cy - eye_h*0.04}
               Z"
            fill="#0A0A0A" stroke="#0A0A0A" stroke-width="2"/>
      <!-- 下眼睑 -->
      <path d="M {cx - eye_w/2 + 6} {cy + eye_h*0.42}
               Q {cx} {cy + eye_h*0.52}, {cx + eye_w/2 - 6} {cy + eye_h*0.42}"
            fill="none" stroke="#0A0A0A" stroke-width="2" opacity="0.75"/>
      <defs>
        <radialGradient id="iris-grad-{size}" cx="50%" cy="40%" r="60%">
          <stop offset="0%" stop-color="{iris_color}" stop-opacity="0.5"/>
          <stop offset="45%" stop-color="{iris_color}" stop-opacity="1"/>
          <stop offset="100%" stop-color="{PALETTE['iris_dark']}" stop-opacity="1"/>
        </radialGradient>
      </defs>
    </svg>'''
    return svg


def anime_face_svg(size: int = 640, iris_color: str = "#D62828") -> str:
    """完整二次元大头：双眸 + 锐利眉 + 黑色短发 + 短嘴 + 冷白皮肤
    size: 脸部画布尺寸 (输出 SVG 实际宽高)"""
    w = h = size

    # 双眸位置 (脸部中央偏上)
    eye_y = int(h * 0.48)
    eye_l_x = int(w * 0.30)
    eye_r_x = int(w * 0.70)
    eye_size = int(w * 0.30)

    # 眉毛：内高外低 = 严肃/锐利 (中性偏冷)
    brow_y_left_start = eye_y - int(eye_size * 0.42)
    brow_y_left_end   = eye_y - int(eye_size * 0.58)
    brow_y_right_start = eye_y - int(eye_size * 0.58)
    brow_y_right_end   = eye_y - int(eye_size * 0.42)

    eye_l = anime_eye_svg(size=eye_size, iris_color=iris_color, gaze_x=0, gaze_y=-2)
    eye_r = anime_eye_svg(size=eye_size, iris_color=iris_color, gaze_x=0, gaze_y=-2)

    svg = f'''<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" style="overflow: visible;">
      <!-- 脸：下颌略尖的椭圆 -->
      <ellipse cx="{w//2}" cy="{int(h*0.55)}" rx="{int(w*0.40)}" ry="{int(h*0.46)}"
               fill="{PALETTE['skin']}" stroke="#0A0A0A" stroke-width="4"/>
      <!-- 下巴阴影 (野兽派色块) -->
      <path d="M {int(w*0.35)} {int(h*0.78)}
               Q {w//2} {int(h*0.92)}, {int(w*0.65)} {int(h*0.78)}
               L {int(w*0.62)} {int(h*0.80)}
               Q {w//2} {int(h*0.86)}, {int(w*0.38)} {int(h*0.80)} Z"
            fill="#E0AE85" opacity="0.55"/>

      <!-- 黑色短发：覆盖头顶 + 两侧碎发 -->
      <!-- 头顶主体 -->
      <path d="M {int(w*0.10)} {int(h*0.50)}
               Q {int(w*0.20)} {int(h*0.05)}, {w//2} {int(h*0.02)}
               Q {int(w*0.80)} {int(h*0.05)}, {int(w*0.90)} {int(h*0.50)}
               L {int(w*0.86)} {int(h*0.32)}
               Q {w//2} {int(h*0.18)}, {int(w*0.14)} {int(h*0.32)} Z"
            fill="#0A0A0A" stroke="#0A0A0A" stroke-width="2"/>
      <!-- 左侧碎发 -->
      <path d="M {int(w*0.14)} {int(h*0.32)}
               L {int(w*0.10)} {int(h*0.55)}
               L {int(w*0.20)} {int(h*0.50)}
               L {int(w*0.18)} {int(h*0.36)} Z"
            fill="#0A0A0A"/>
      <!-- 右侧碎发 -->
      <path d="M {int(w*0.86)} {int(h*0.32)}
               L {int(w*0.90)} {int(h*0.55)}
               L {int(w*0.80)} {int(h*0.50)}
               L {int(w*0.82)} {int(h*0.36)} Z"
            fill="#0A0A0A"/>
      <!-- 刘海碎发 (略斜) -->
      <path d="M {int(w*0.30)} {int(h*0.32)}
               L {int(w*0.38)} {int(h*0.40)}
               L {int(w*0.50)} {int(h*0.34)}
               L {int(w*0.62)} {int(h*0.40)}
               L {int(w*0.70)} {int(h*0.32)}
               L {int(w*0.70)} {int(h*0.20)}
               L {int(w*0.30)} {int(h*0.20)} Z"
            fill="#0A0A0A"/>

      <!-- 左侧眉 (内高外低 = 严肃) -->
      <line x1="{eye_l_x - 60}" y1="{brow_y_left_end}" x2="{eye_l_x + 60}" y2="{brow_y_left_start}"
            stroke="#0A0A0A" stroke-width="11" stroke-linecap="round"/>
      <!-- 右侧眉 -->
      <line x1="{eye_r_x - 60}" y1="{brow_y_right_start}" x2="{eye_r_x + 60}" y2="{brow_y_right_end}"
            stroke="#0A0A0A" stroke-width="11" stroke-linecap="round"/>

      <!-- 左眼 -->
      <g transform="translate({eye_l_x - eye_size//2}, {eye_y - eye_size//2})">{eye_l}</g>
      <!-- 右眼 -->
      <g transform="translate({eye_r_x - eye_size//2}, {eye_y - eye_size//2})">{eye_r}</g>

      <!-- 鼻子 (极简短线) -->
      <line x1="{w//2 - 4}" y1="{int(h*0.70)}" x2="{w//2 - 4}" y2="{int(h*0.74)}"
            stroke="#0A0A0A" stroke-width="3" stroke-linecap="round"/>

      <!-- 嘴 (短横线，无表情 = 中性冷) -->
      <line x1="{int(w*0.44)}" y1="{int(h*0.80)}" x2="{int(w*0.56)}" y2="{int(h*0.80)}"
            stroke="#0A0A0A" stroke-width="5" stroke-linecap="round"/>

      <!-- 耳朵 (左) -->
      <ellipse cx="{int(w*0.12)}" cy="{int(h*0.55)}" rx="{int(w*0.04)}" ry="{int(h*0.08)}"
               fill="{PALETTE['skin']}" stroke="#0A0A0A" stroke-width="3"/>
      <!-- 耳朵 (右) -->
      <ellipse cx="{int(w*0.88)}" cy="{int(h*0.55)}" rx="{int(w*0.04)}" ry="{int(h*0.08)}"
               fill="{PALETTE['skin']}" stroke="#0A0A0A" stroke-width="3"/>
    </svg>'''
    return svg


# ---------- 噪点 SVG ----------

NOISE_SVG = '''<svg width="240" height="240" xmlns="http://www.w3.org/2000/svg">
  <filter id="n"><feTurbulence type="fractalNoise" baseFrequency="0.92" numOctaves="2" stitchTiles="stitch"/>
  <feColorMatrix values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 0.45 0"/></filter>
  <rect width="240" height="240" filter="url(#n)" opacity="0.5"/>
</svg>'''


# ---------- HTML 模板 (1200x1200 方形，野兽派 × 二次元) ----------

HTML_TEMPLATE = r'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>自查名片 · ${name}</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  html, body {
    width: ${canvas}px; height: ${canvas}px;
    overflow: hidden;
    font-family: 'PingFang HK', 'Hiragino Sans GB', 'STHeiti', 'Noto Sans CJK SC', sans-serif;
  }
  body {
    background: {bg};
    color: white;
    position: relative;
    overflow: hidden;
  }

  /* ============ 野兽派几何拼贴层 ============ */
  .geo {
    position: absolute;
    z-index: 1;
  }
  /* 左上：朱红三角 (跨 460px) */
  .geo-tl {
    top: 0; left: 0;
    width: 0; height: 0;
    border-top: 460px solid {red};
    border-right: 460px solid transparent;
  }
  /* 右下：黄方块 (倾斜 8deg) */
  .geo-br {
    bottom: 0; right: 0;
    width: 380px; height: 380px;
    background: {yellow};
    transform: rotate(8deg) translate(40px, 40px);
    border: 5px solid {ink};
  }
  /* 右上：白色斜方块 (装饰) */
  .geo-tr {
    top: 60px; right: -40px;
    width: 240px; height: 120px;
    background: white;
    transform: skewX(-18deg);
  }
  /* 左下：黑色小三角 */
  .geo-bl {
    bottom: 0; left: 0;
    width: 0; height: 0;
    border-bottom: 200px solid {ink};
    border-right: 200px solid transparent;
  }
  /* 中央装饰：小黄方块 (错位) */
  .geo-mid {
    top: 720px; left: 880px;
    width: 140px; height: 140px;
    background: {red};
    transform: rotate(-6deg);
    border: 4px solid {ink};
  }
  /* 左上放射线 (大三角内) */
  .radiating {
    position: absolute;
    top: 0; left: 0;
    width: 460px; height: 460px;
    z-index: 2;
    pointer-events: none;
  }

  /* ============ 噪点 + 扫描线 (顶层装饰) ============ */
  .noise {
    position: absolute; inset: 0; z-index: 50;
    pointer-events: none; opacity: 0.28;
    background-image: url("data:image/svg+xml;utf8,{noise_svg}");
    background-size: 240px 240px;
  }
  .scanlines {
    position: absolute; inset: 0; z-index: 49;
    pointer-events: none;
    background: repeating-linear-gradient(
      0deg,
      transparent 0px,
      transparent 2px,
      rgba(0,0,0,0.08) 2px,
      rgba(0,0,0,0.08) 3px
    );
  }

  /* ============ 文字与角色 ============ */
  /* 姓名：野兽派巨字 + 错位阴影 */
  .name-block {
    position: absolute;
    top: 70px; left: 80px;
    z-index: 12;
  }
  .name-eyebrow {
    font-size: 20px; font-weight: 700;
    letter-spacing: 0.35em;
    text-transform: uppercase;
    color: {yellow};
    margin-bottom: 10px;
    z-index: 12;
    position: relative;
  }
  .name {
    font-family: 'Impact', 'PingFang HK Heavy', 'Hiragino Sans GB Heavy', sans-serif;
    font-size: 130px; font-weight: 900;
    line-height: 0.9;
    color: white;
    letter-spacing: -0.02em;
    text-shadow:
      -3px 0 0 {ink}, 3px 0 0 {ink},
      0 -3px 0 {ink}, 0 3px 0 {ink},
      -4px 4px 0 {red}, -7px 7px 0 {ink};
    z-index: 12;
    position: relative;
  }
  /* MBTI 爆炸气泡 */
  .mbti-pill {
    display: inline-block;
    font-size: 48px; font-weight: 900;
    color: {ink};
    background: {yellow};
    padding: 8px 22px;
    margin-top: 18px;
    transform: rotate(-3deg);
    border: 5px solid {ink};
    box-shadow: 6px 6px 0 {ink};
    letter-spacing: 0.05em;
  }

  /* 签名 (右上) */
  .signature {
    position: absolute;
    top: 70px; right: 70px;
    z-index: 12;
    text-align: right;
  }
  .signature-tag {
    font-size: 13px; font-weight: 700;
    letter-spacing: 0.25em;
    color: {ink};
    background: white;
    padding: 5px 12px;
    display: inline-block;
    border: 3px solid {ink};
  }
  .signature-date {
    font-size: 28px; font-weight: 900;
    color: white;
    margin-top: 8px;
    font-family: 'SF Mono', 'Menlo', 'Courier New', monospace;
    letter-spacing: 0.1em;
  }

  /* 二次元角色 (占 50% 视觉中心) */
  .face {
    position: absolute;
    top: 50%; left: 50%;
    transform: translate(-58%, -52%);
    z-index: 10;
    width: 700px; height: 700px;
  }

  /* slogan 卡片 (左下) */
  .slogan-card {
    position: absolute;
    bottom: 110px; left: 60px;
    z-index: 14;
    background: {ink};
    border: 5px solid {yellow};
    padding: 18px 26px;
    max-width: 560px;
    transform: rotate(-1.5deg);
    box-shadow: 6px 6px 0 {red};
  }
  .slogan-text {
    font-size: 22px; font-weight: 700;
    color: white;
    font-style: italic;
    line-height: 1.35;
  }
  .slogan-quote-mark {
    font-size: 50px;
    color: {yellow};
    line-height: 0;
    font-family: Georgia, serif;
    margin-right: 4px;
    vertical-align: -8px;
  }
  .slogan-author {
    font-size: 12px; font-weight: 700;
    color: {yellow};
    margin-top: 8px;
    text-align: right;
    letter-spacing: 0.15em;
  }

  /* 动物 (右下角，黄方块上) */
  .animal-card {
    position: absolute;
    bottom: 90px; right: 80px;
    z-index: 14;
    background: white;
    border: 5px solid {ink};
    padding: 12px 22px;
    transform: rotate(4deg);
    text-align: center;
    box-shadow: 5px 5px 0 {ink};
  }
  .animal-label {
    font-size: 11px; font-weight: 700;
    letter-spacing: 0.25em;
    color: {ink};
    text-transform: uppercase;
  }
  .animal-name {
    font-size: 32px; font-weight: 900;
    color: {red};
    line-height: 1.1;
    margin-top: 4px;
  }
  .animal-emoji {
    font-size: 36px;
    line-height: 1;
    margin-top: 2px;
  }
</style>
</head>
<body>
  <!-- 背景几何 -->
  <div class="geo geo-tl"></div>
  <div class="geo geo-br"></div>
  <div class="geo geo-tr"></div>
  <div class="geo geo-bl"></div>
  <div class="geo geo-mid"></div>

  <!-- 放射线 (朱红三角内) -->
  <svg class="radiating" viewBox="0 0 460 460">
    <g stroke="#0A0A0A" stroke-width="2" opacity="0.55">
      <line x1="0" y1="0" x2="460" y2="0"/>
      <line x1="0" y1="0" x2="0" y2="460"/>
      <line x1="0" y1="0" x2="325" y2="325"/>
      <line x1="0" y1="0" x2="460" y2="325"/>
      <line x1="0" y1="0" x2="325" y2="460"/>
      <line x1="0" y1="0" x2="230" y2="460"/>
      <line x1="0" y1="0" x2="120" y2="460"/>
      <line x1="0" y1="0" x2="460" y2="230"/>
      <line x1="0" y1="0" x2="460" y2="120"/>
      <line x1="0" y1="0" x2="200" y2="200"/>
    </g>
  </svg>

  <!-- 姓名 + MBTI -->
  <div class="name-block">
    <div class="name-eyebrow">SELF-DISTILL · 自查名片</div>
    <div class="name">${name}</div>
    <div class="mbti-pill">${mbti}</div>
  </div>

  <!-- 签名 -->
  <div class="signature">
    <div class="signature-tag">自查 · ${date}</div>
    <div class="signature-date">${date_code}</div>
  </div>

  <!-- 二次元大头角色 -->
  <div class="face">{face_svg}</div>

  <!-- slogan 卡片 -->
  <div class="slogan-card">
    <div class="slogan-text"><span class="slogan-quote-mark">"</span>${slogan}</div>
    <div class="slogan-author">— ${mbti} · ${animal}</div>
  </div>

  <!-- 动物卡片 -->
  <div class="animal-card">
    <div class="animal-label">▍最像的动物</div>
    <div class="animal-name">${animal}</div>
    <div class="animal-emoji">${animal_emoji}</div>
  </div>

  <!-- 噪点 + 扫描线 (顶层) -->
  <div class="noise"></div>
  <div class="scanlines"></div>
</body>
</html>'''


# ---------- 渲染入口 ----------

def render_html(template: dict, canvas: int = CANVAS) -> str:
    name = template.get("name", "You")
    mbti = template.get("mbti", "?????")
    slogan = template.get("slogan", "做有判断力的自己")
    animal = template.get("animal", "猫头鹰")
    iris = template.get("iris_color", PALETTE["iris"])

    face_svg = anime_face_svg(size=640, iris_color=iris)

    # emoji 兜底
    ANIMAL_EMOJI = {
        "猫头鹰": "🦉", "蜜蜂": "🐝", "树懒": "🦥", "章鱼": "🐙",
        "狼": "🐺", "孔雀": "🦚", "乌龟": "🐢", "狐狸": "🦊",
        "海狸": "🦫", "海豚": "🐬", "狮子": "🦁", "变色龙": "🦎",
    }
    animal_emoji = ANIMAL_EMOJI.get(animal, "🐾")

    # 日期码 (野兽派常用格式: MM·DD)
    date_str = time.strftime("%Y-%m-%d")
    date_code = time.strftime("%m·%d")

    return Template(HTML_TEMPLATE).substitute(
        name=name,
        mbti=mbti,
        slogan=slogan,
        animal=animal,
        animal_emoji=animal_emoji,
        face_svg=face_svg,
        bg=PALETTE["bg"],
        red=PALETTE["red"],
        yellow=PALETTE["yellow"],
        ink=PALETTE["ink"],
        canvas=canvas,
        date=date_str,
        date_code=date_code,
        noise_svg=NOISE_SVG.replace('\n', '').replace('"', "'"),
    )


def render_html_to_png(html: str, output_path: str,
                       width: int = CANVAS, height: int = CANVAS) -> bool:
    """Chrome headless 截图"""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".html", delete=False, encoding="utf-8"
    ) as f:
        f.write(html)
        html_path = f.name

    try:
        cmd = [
            CHROME_PATH,
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            "--hide-scrollbars",
            "--force-device-scale-factor=1",
            f"--screenshot={output_path}",
            f"--window-size={width},{height}",
            "--virtual-time-budget=5000",
            f"file://{html_path}",
        ]
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=60
        )
        if result.returncode != 0:
            print(f"  Chrome 错误：{result.stderr[:500]}", file=sys.stderr)
            return False
        return os.path.exists(output_path)
    finally:
        try:
            os.unlink(html_path)
        except OSError:
            pass


# ---------- CLI ----------

def main():
    parser = argparse.ArgumentParser(description="野兽派×二次元 个人名片 v3 (分享版)")
    parser.add_argument("--name", default="Demo User")
    parser.add_argument("--mbti", default="INTJ")
    parser.add_argument("--slogan", default="做有判断力的自己")
    parser.add_argument("--animal", default="猫头鹰")
    parser.add_argument("--iris", default=PALETTE["iris"])
    parser.add_argument("--output", default="/tmp/self_distill_card_share.png")
    args = parser.parse_args()

    template = {
        "name": args.name,
        "mbti": args.mbti,
        "slogan": args.slogan,
        "animal": args.animal,
        "iris_color": args.iris,
    }

    print(f"[v3] 渲染 1200x1200 分享名片: {args.name} / {args.mbti} / {args.animal}", file=sys.stderr)
    t0 = time.time()
    html = render_html(template)
    ok = render_html_to_png(html, args.output)
    if ok:
        size = os.path.getsize(args.output)
        print(f"[v3] ✓ {args.output} ({size/1024:.0f}KB, {time.time()-t0:.1f}s)", file=sys.stderr)
    else:
        print(f"[v3] ✗ 渲染失败", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
