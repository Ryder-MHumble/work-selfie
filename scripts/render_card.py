#!/usr/bin/env python3
"""
self-distill 名片 v7 — Profile Card 比例

按最终视觉方向选定：4:5 竖向（小红书帖图比例）= 默认
1:1 / 9:16 保留为可选变体

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

# 让 render_card 能 import analyze 的常量
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from analyze import ABSTRACT_KEYWORDS  # noqa: E402
except ImportError:
    # fallback：独立运行 render_card.py 时
    ABSTRACT_KEYWORDS = set("""
        体系系统架构模式框架本质核心底层顶层方法论思维范式原则逻辑
        抽象宏观全局端到端整体战略方向趋势意义价值
    """.split())

CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


# ============== 人物库（8 SBTI 风格各自独立分类）==============
# 设计：SBTI 风格负责"人设标签"，FIGURE_LIBRARY 负责"3D 小人视觉选择"。
# 选图不再固定 SBTI→图片，而是按小人的视觉特征对表达/行为信号打分。

PERSONA_DIR = Path(__file__).parent.parent / "assets"

FIGURE_LIBRARY = {
    "orange_focus": {
        "image": str(PERSONA_DIR / "toonhub-1.png"),
        "image_name": "toonhub-1.png",
        "color": "#D96B1F",
        "label": "专注橙 · 深潜研究员",
        "visual": "橙色眼镜小人，衣服写着 STAY FOCUSED，表情认真、稳定、抗干扰",
    },
    "green_energy": {
        "image": str(PERSONA_DIR / "toonhub-2.png"),
        "image_name": "toonhub-2.png",
        "color": "#27AE60",
        "label": "元气绿 · 讲解气氛组",
        "visual": "绿色小人双手比 V，表情外放，适合积极、表达、带动氛围",
    },
    "pink_execution": {
        "image": str(PERSONA_DIR / "toonhub-3.png"),
        "image_name": "toonhub-3.png",
        "color": "#E78CAD",
        "label": "推进粉 · 项目推进官",
        "visual": "粉色小人双拳举起，像完成冲刺后的庆祝，适合推进、协调、Gantt 感",
    },
    "blue_scout": {
        "image": str(PERSONA_DIR / "toonhub-4.png"),
        "image_name": "toonhub-4.png",
        "color": "#1A63B8",
        "label": "侦察蓝 · 快速响应兵",
        "visual": "蓝色小人指向前方，衣服写着 FOCUS，适合问询、侦察、快速响应",
    },
}


def _safe_ratio(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value or 0)))
    except (TypeError, ValueError):
        return 0.0


def _top_collab_share(behavior: Dict[str, Any]) -> float:
    collabs = behavior.get("top_collaborators", []) or []
    if not collabs:
        return 0.0
    counts = [
        c[1] if isinstance(c, (list, tuple)) else c.get("count", 0)
        for c in collabs
    ]
    total = sum(max(0, int(c or 0)) for c in counts) or 1
    return max(0.0, min(1.0, max(counts or [0]) / total))


def select_figure(sbti_code: str, expression: Dict, behavior: Dict) -> Dict[str, Any]:
    """按小人自身视觉特征选图，而不是只按 SBTI 标签硬映射。"""
    expression = expression or {}
    behavior = behavior or {}
    length = expression.get("length_stats", {}) or {}
    category = expression.get("category", {}) or {}
    emotion = expression.get("emotion", {}) or {}
    punct = expression.get("punctuation_density", {}) or {}
    gv = behavior.get("group_vs_p2p", {}) or {}

    mean_len = float(length.get("mean", 0) or 0)
    work = _safe_ratio(category.get("work_ratio"))
    long_msg = _safe_ratio(category.get("long_msg_ratio"))
    single_char = _safe_ratio(category.get("single_char_ratio"))
    positive = _safe_ratio(emotion.get("positive"))
    question = _safe_ratio(punct.get("question"))
    group = _safe_ratio(gv.get("group"))
    late = _safe_ratio(behavior.get("late_night_ratio"))
    weekend = _safe_ratio(behavior.get("weekend_ratio"))
    collab_share = _top_collab_share(behavior)

    abstract_hits = sum(
        count for word, count in expression.get("top_keywords", [])
        if word in ABSTRACT_KEYWORDS
    )

    scores = {
        "orange_focus": (
            (35 if sbti_code in {"深潜者", "架构师"} else 0)
            + min(25, mean_len / 4)
            + long_msg * 35
            + work * 20
            + min(20, abstract_hits * 3)
        ),
        "green_energy": (
            (35 if sbti_code == "讲师" else 0)
            + positive * 55
            + long_msg * 25
            + min(15, mean_len / 5)
            + (1 - single_char) * 8
        ),
        "pink_execution": (
            (35 if sbti_code in {"指挥官", "记者"} else 0)
            + collab_share * 25
            + (1 - min(1, late + weekend)) * 15
            + work * 20
            + (10 if 8 <= (behavior.get("active_hour_top3", [12]) or [12])[0] <= 19 else 0)
        ),
        "blue_scout": (
            (35 if sbti_code in {"侦察兵", "甩手掌柜", "火警"} else 0)
            + question * 60
            + single_char * 25
            + group * 15
            + late * 20
        ),
    }
    key = max(scores, key=scores.get)
    figure = FIGURE_LIBRARY[key]
    return {
        **figure,
        "key": key,
        "score": int(scores[key]),
        "scores": {k: int(v) for k, v in scores.items()},
    }


PERSONA_LIBRARY = {
    "深潜者": {
        "image": str(PERSONA_DIR / "toonhub-1.png"),   # legacy fallback; 4x5 实际选图走 select_figure()
        "color": "#1A2B5E",
        "classify_func": lambda e, b: min(1.0, (
            max(0, (e["length_stats"]["mean"] - 30) / 80) * 0.4
            + e["category"]["work_ratio"] * 1.0
            + e["category"]["long_msg_ratio"] * 0.6
        )),
    },
    "甩手掌柜": {
        "image": str(PERSONA_DIR / "toonhub-4.png"),   # legacy fallback; 4x5 实际选图走 select_figure()
        "color": "#E74C3C",
        "classify_func": lambda e, b: min(1.0, (
            b["group_vs_p2p"]["group"] * 0.5
            + e["category"]["single_char_ratio"] * 1.2
            + (1 - e["category"]["long_msg_ratio"]) * 0.3
        )),
    },
    "火警": {
        "image": str(PERSONA_DIR / "toonhub-2.png"),   # legacy fallback; 4x5 实际选图走 select_figure()
        "color": "#9B59B6",
        "classify_func": lambda e, b: min(1.0, (
            e["emotion"]["negative"] * 8
            + (b.get("active_hour_top3", [12])[0] >= 22 or b.get("active_hour_top3", [12])[0] <= 5) * 0.3
            + b["late_night_ratio"] * 2
        )),
    },
    "架构师": {
        "image": str(PERSONA_DIR / "toonhub-1.png"),   # legacy fallback; 4x5 实际选图走 select_figure()
        "color": "#1A2B5E",
        "classify_func": lambda e, b: min(1.0, (
            sum(c for w, c in e["top_keywords"] if w in ABSTRACT_KEYWORDS) / max(1, b.get("_n", 1)) * 4
            + max(0, (e["length_stats"]["mean"] - 25) / 60) * 0.4
            + (1 - e["punctuation_density"]["question"]) * 0.2
        )),
    },
    "侦察兵": {
        "image": str(PERSONA_DIR / "toonhub-4.png"),   # legacy fallback; 4x5 实际选图走 select_figure()
        "color": "#E74C3C",
        "classify_func": lambda e, b: min(1.0, (
            e["punctuation_density"]["question"] * 8
            + (e["length_stats"]["mean"] < 30) * 0.3
            + b["late_night_ratio"] * 1.5
            + e["category"]["single_char_ratio"] * 1.0
        )),
    },
    "记者": {
        "image": str(PERSONA_DIR / "toonhub-3.png"),   # legacy fallback; 4x5 实际选图走 select_figure()
        "color": "#27AE60",
        "classify_func": lambda e, b: min(1.0, (
            sum(c for w, c in e["top_keywords"] if w in {"数据", "截图", "记录", "统计", "看", "查", "调研", "数"}) / max(1, b.get("_n", 1)) * 4
            + b["top_collaborators"][0][1] / max(1, b.get("_n", 1)) * 2 if b["top_collaborators"] else 0
            + (1 - b["weekend_ratio"]) * 0.2
        )),
    },
    "指挥官": {
        "image": str(PERSONA_DIR / "toonhub-3.png"),   # legacy fallback; 4x5 实际选图走 select_figure()
        "color": "#27AE60",
        "classify_func": lambda e, b: min(1.0, (
            (1 - b["late_night_ratio"]) * 0.3
            + (1 - b["weekend_ratio"]) * 0.3
            + b["top_collaborators"][0][1] / max(1, b.get("_n", 1)) * 2 if b["top_collaborators"] else 0
            + len(b["top_collaborators"]) / 50 if b["top_collaborators"] else 0
        )),
    },
    "讲师": {
        "image": str(PERSONA_DIR / "toonhub-2.png"),   # legacy fallback; 4x5 实际选图走 select_figure()
        "color": "#9B59B6",
        "classify_func": lambda e, b: min(1.0, (
            e["length_stats"]["mean"] / 50 * 0.4
            + e["category"]["long_msg_ratio"] * 0.6
            + (1 - e["category"]["single_char_ratio"]) * 0.2
        )),
    },
    # 兜底：SBTI Top1 缺失 / 异常 → 均衡型
    "均衡型": {
        "image": str(PERSONA_DIR / "toonhub-3.png"),
        "color": "#7F7F7F",
        "classify_func": lambda e, b: 0.5,
    },
}


def select_persona(
    sbti_code: str,
    expression: Dict,
    behavior: Dict,
    messages_count: int = 0,
) -> Dict:
    """根据 SBTI Top1 选 persona，并根据数据信号选择 3D 小人

    人设标签 = 按 SBTI 风格名查 PERSONA_LIBRARY（不再用 MBTI 间接选）
    3D 小人 = select_figure() 按图像特征评分选择
    每个 SBTI 风格都有自己独立的 classify_func（基于 expression + behavior）
    behavior 里注入 _n = messages_count（替代原 messages_global）

    返回：{"code", "image", "color", "tag", "score"}
    """
    # 注入 messages_count 到 behavior（供 classify_func 使用）
    b = {**behavior, "_n": messages_count}
    persona = PERSONA_LIBRARY.get(sbti_code, PERSONA_LIBRARY["均衡型"])
    code = sbti_code if sbti_code in PERSONA_LIBRARY else "均衡型"
    figure = select_figure(code, expression, b)
    try:
        score = int(persona["classify_func"](expression, b) * 100)
    except Exception:
        score = 50
    return {
        "code": code,
        "image": figure["image"],
        "color": figure["color"],
        "tag": SBTI_STYLE_MAP_TAG.get(code, code),
        "score": score,
        "figure_key": figure["key"],
        "figure_label": figure["label"],
        "figure_reason": figure["visual"],
    }


# SBTI 风格 → 简短中文标签（用于人物图旁边的 tag）
SBTI_STYLE_MAP_TAG = {
    "深潜者": "深度内卷型",
    "甩手掌柜": "佛系指挥型",
    "火警": "红色警戒型",
    "架构师": "PPT 永动机型",
    "侦察兵": "信息掮客型",
    "记者": "数据狂魔型",
    "指挥官": "人形 Gantt 型",
    "讲师": "传道授业型",
    "均衡型": "均衡型",
}


def encode_image_as_data_uri(path: str) -> str:
    """把图片编码成 base64 data URI（嵌到 HTML 里用）"""
    import base64
    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode("ascii")
    return f"data:image/png;base64,{data}"


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
    width: 720px; height: 900px;
    overflow: hidden;
    font-family: 'PingFang HK', 'Hiragino Sans GB', 'STHeiti', 'Noto Sans CJK SC', sans-serif;
  }}
  body {{
    background: #F2EFE9;
    color: #0A0A0A;
    position: relative;
  }}

  /* ===== 左侧 41%：释放更多人像 + 新野兽派方块，避免大面积黑块 ===== */
  .toonhub-bg {{
    position: absolute;
    top: 0; left: 0;
    width: 41%;
    height: 59%;
    overflow: hidden;
    z-index: 1;
    border-right: 3px solid #0A0A0A;
    border-bottom: 3px solid #0A0A0A;
  }}
  .toonhub-bg img {{
    width: 100%; height: 100%;
    object-fit: cover;
    object-position: center 18%;
    filter: contrast(1.05) saturate(1.1);
  }}
  .toonhub-bg::after {{
    content: "";
    position: absolute;
    inset: 0;
    background: linear-gradient(180deg,
      rgba(242, 239, 233, 0) 30%,
      rgba(242, 239, 233, 0.82) 100%);
  }}

  .sbti-brutalist-collage {{
    position: absolute;
    left: 18px; top: 46%;
    width: 33%;
    height: 44%;
    z-index: 3;
    pointer-events: none;
  }}
  .neo-block {{
    position: absolute;
    border: 3px solid #0A0A0A;
    box-shadow: 5px 5px 0 rgba(10,10,10,0.18);
  }}
  .neo-yellow {{ left: 12px; top: 0; width: 72px; height: 112px; background: #F4C430; transform: rotate(-7deg); }}
  .neo-red {{ left: 96px; top: 38px; width: 92px; height: 62px; background: #D62828; transform: rotate(4deg); }}
  .neo-green {{ left: 36px; top: 132px; width: 134px; height: 74px; background: #27AE60; transform: rotate(2deg); }}
  .neo-cream {{ left: 116px; top: 228px; width: 76px; height: 118px; background: #F2EFE9; transform: rotate(-4deg); }}

  /* 左下 SBTI 内容卡：小块信息，不再整块黑底压画面 */
  .sbti-side {{
    position: absolute;
    top: 51%; left: 18px;
    width: 32%;
    min-height: 255px;
    background: rgba(242, 239, 233, 0.94);
    color: #0A0A0A;
    padding: 14px 12px 12px 12px;
    z-index: 5;
    display: flex; flex-direction: column;
    justify-content: flex-start;
    border: 3px solid #0A0A0A;
    box-shadow: 8px 8px 0 #D62828;
    transform: rotate(-0.6deg);
  }}
  .sbti-side::before {{
    content: "01";
    position: absolute;
    top: -16px; right: 10px;
    background: #0A0A0A;
    color: #F4C430;
    padding: 2px 7px;
    font-size: 13px; font-weight: 900;
    letter-spacing: 0.08em;
  }}
  .sbti-side-label {{
    font-size: 8px; font-weight: 800;
    color: #D62828;
    letter-spacing: 0.3em; text-transform: uppercase;
    margin-bottom: 4px;
  }}
  .sbti-side-code {{
    display: inline-block;
    background: #0A0A0A;
    color: white;
    font-size: 10px; font-weight: 900;
    padding: 2px 8px;
    margin-bottom: 6px;
    align-self: flex-start;
  }}
  .sbti-side-title {{
    font-size: 23px; font-weight: 900;
    color: #0A0A0A;
    line-height: 1.05;
    margin-bottom: 6px;
    letter-spacing: -0.01em;
  }}
  .sbti-side-tag {{
    font-size: 11px; font-weight: 700;
    color: #D62828;
    margin-bottom: 8px;
  }}
  .sbti-side-desc {{
    font-size: 10px; font-weight: 500;
    color: #333;
    line-height: 1.4;
    margin-bottom: 8px;
  }}
  .sbti-side-score {{
    font-size: 9px; font-weight: 800;
    color: #D62828;
    letter-spacing: 0.1em;
  }}
  .sbti-side-divider {{
    border-top: 1px dashed rgba(10, 10, 10, 0.28);
    margin: 6px 0 4px 0;
  }}
  .sbti-side-stat {{
    display: flex; align-items: baseline; gap: 4px;
    font-size: 9px; line-height: 1.25;
    margin: 1px 0;
    padding: 2px 3px;
    background: rgba(255,255,255,0.6);
  }}
  .sss-k {{
    width: 38px; flex-shrink: 0;
    font-weight: 800; color: #D62828;
    letter-spacing: 0.1em;
  }}
  .sss-v {{
    flex: 1; color: #0A0A0A; font-weight: 700;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }}

  /* ===== 右侧 59%：内容整体右移，底部宣言独立成横条 ===== */
  .right-panel {{
    position: absolute;
    top: 0; left: 41%; right: 0; bottom: 0;
    width: 59%;
    padding: 18px 20px 18px 22px;
    z-index: 10;
    display: grid;
    grid-template-rows: 24px 72px 34px 208px 172px 132px;
    gap: 7px;
  }}

  /* 顶部行：日期 + MVP 标记 */
  .top-strip {{
    flex: 0 0 auto;
    display: flex; justify-content: space-between; align-items: center;
    font-size: 9px; font-weight: 800;
    letter-spacing: 0.3em; text-transform: uppercase;
    color: #0A0A0A;
    border-bottom: 2px solid #0A0A0A;
    padding-bottom: 4px;
    margin-bottom: 6px;
  }}
  .mvp {{
    background: #0A0A0A; color: #F4C430;
    padding: 2px 8px;
    font-size: 9px; font-weight: 900;
    letter-spacing: 0.2em;
  }}

  /* 主姓名 */
  .name-block {{
    flex: 0 0 auto;
    margin-bottom: 4px;
  }}
  .name-eyebrow {{
    font-size: 9px; font-weight: 800;
    letter-spacing: 0.4em;
    color: #D62828;
    text-transform: uppercase;
  }}
  .name {{
    font-size: 52px; font-weight: 900;
    line-height: 0.95;
    color: #0A0A0A;
    letter-spacing: -0.04em;
    margin: 2px 0;
  }}

  /* 核心身份条（3 个标签横排） */
  .identity-strip {{
    flex: 0 0 auto;
    display: flex; gap: 6px; flex-wrap: wrap;
    margin: 2px 0 6px 0;
  }}
  .identity-chip {{
    display: inline-block;
    background: #0A0A0A;
    color: white;
    font-size: 10px; font-weight: 800;
    padding: 3px 8px;
    letter-spacing: 0.05em;
  }}
  .identity-chip.keirsey {{
    background: {persona_color};
    color: white;
  }}
  .identity-chip.animal {{
    background: #F4C430;
    color: #0A0A0A;
    border: 2px solid #0A0A0A;
  }}

  /* 主 SBTI 块 */
  .sbti-main {{
    background: #0A0A0A;
    color: white;
    padding: 8px 10px;
    margin: 6px 0;
    position: relative;
    transform: rotate(-0.5deg);
  }}
  .sbti-label {{
    font-size: 8px; font-weight: 700;
    color: #F4C430;
    letter-spacing: 0.3em; text-transform: uppercase;
    margin-bottom: 3px;
  }}
  .sbti-title {{
    font-size: 16px; font-weight: 900;
    color: white;
    line-height: 1.1;
    margin-bottom: 2px;
  }}
  .sbti-desc {{
    font-size: 10px; font-weight: 500;
    color: white;
    line-height: 1.3;
    opacity: 0.95;
  }}

  /* 5 维推断条（横排 5 个图标） */
  .traits-5d {{
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 4px;
    margin: 6px 0;
    background: rgba(255,255,255,0.7);
    border: 1px solid #0A0A0A;
    padding: 4px;
  }}
  .trait-5d {{
    text-align: center;
    font-size: 9px;
  }}
  .trait-5d-icon {{
    font-size: 18px;
    line-height: 1;
  }}
  .trait-5d-label {{
    font-size: 8px; font-weight: 800;
    color: #0A0A0A;
    margin-top: 1px;
    line-height: 1.1;
  }}
  .trait-5d-score {{
    font-size: 7px; font-weight: 700;
    color: #D62828;
  }}

  /* ===== 新模块 1: SBTI 8 候选排行条（精简：top 3 + 其他 5 候选 1 行汇总） ===== */
  .sbti8-section {{
    flex: 0 0 auto;
    margin: 0;
    overflow: hidden;
    min-height: 0;
  }}
  .sbti8-title {{
    font-size: 11px; font-weight: 800;
    letter-spacing: 0.3em; text-transform: uppercase;
    color: #0A0A0A; margin-bottom: 4px;
  }}
  .sbti8-title::before {{ content: "▍"; color: #D62828; margin-right: 3px; }}
  .sbti8-item {{
    display: flex; align-items: center; gap: 4px;
    font-size: 11px; font-weight: 700;
    color: #999;
    line-height: 1.5;
    margin: 2px 0;
  }}
  .sbti8-item.top3 {{ color: #0A0A0A; font-weight: 800; }}
  .sbti8-name {{
    width: 38px; flex-shrink: 0;
  }}
  .sbti8-bar {{
    flex: 1; height: 5px;
    background: rgba(0,0,0,0.08);
    position: relative;
  }}
  .sbti8-bar-fill {{
    position: absolute; left: 0; top: 0; bottom: 0;
    background: #D62828;
  }}
  .sbti8-item.top3 .sbti8-bar-fill {{
    background: #0A0A0A;
  }}
  .sbti8-score {{
    width: 32px; text-align: right;
    font-size: 11px; font-weight: 800;
    color: #0A0A0A;
  }}
  .sbti8-summary {{
    font-size: 9px; color: #999; font-weight: 600;
    margin-top: 2px; padding-top: 2px;
    border-top: 1px dashed rgba(0,0,0,0.15);
  }}
  .sbti8-footer {{
    font-size: 9px; color: #D62828; font-weight: 600;
    margin-top: 4px; padding-top: 4px;
    border-top: 1px dashed rgba(0,0,0,0.15);
    letter-spacing: 0.02em;
  }}

  /* ===== 新模块 2: 5 维推断详表（紧凑：primary+secondary 同行） ===== */
  .t5d-section {{
    flex: 0 0 auto;
    margin: 0;
    overflow: hidden;
    min-height: 0;
  }}
  .t5d-title {{
    font-size: 11px; font-weight: 800;
    letter-spacing: 0.3em; text-transform: uppercase;
    color: #0A0A0A; margin-bottom: 4px;
  }}
  .t5d-title::before {{ content: "▍"; color: #D62828; margin-right: 3px; }}
  .t5d-row {{
    display: flex; align-items: baseline; gap: 4px;
    font-size: 11px; line-height: 1.5;
    margin: 1px 0;
    padding: 2px 4px;
    background: rgba(255,255,255,0.5);
    border-left: 2px solid #0A0A0A;
  }}
  .t5d-label {{
    width: 28px; font-weight: 900; color: #0A0A0A;
    flex-shrink: 0;
  }}
  .t5d-primary {{
    color: #0A0A0A; font-weight: 800;
    white-space: nowrap;
  }}
  .t5d-primary b {{ color: #D62828; font-weight: 900; }}
  .t5d-sub {{
    font-size: 9px; color: #888; font-weight: 600;
    white-space: nowrap;
  }}
  .t5d-footer {{
    font-size: 9px; color: #D62828; font-weight: 600;
    margin-top: 4px; padding-top: 4px;
    border-top: 1px dashed rgba(0,0,0,0.15);
    letter-spacing: 0.02em;
  }}

  /* ===== 新模块 3: 表达 DNA 关键数据 ===== */
  .dna-section {{
    flex: 0 0 auto;
    margin: 0;
    overflow: hidden;
    min-height: 0;
  }}
  .dna-title {{
    font-size: 11px; font-weight: 800;
    letter-spacing: 0.3em; text-transform: uppercase;
    color: #0A0A0A; margin-bottom: 4px;
  }}
  .dna-title::before {{ content: "▍"; color: #D62828; margin-right: 3px; }}
  .dna-row {{
    display: flex; gap: 4px; align-items: baseline;
    font-size: 11px; line-height: 1.5;
    margin: 1px 0;
    padding: 2px 4px;
    background: rgba(255,255,255,0.5);
  }}
  .dna-k {{
    width: 50px; flex-shrink: 0;
    font-weight: 900; color: #0A0A0A;
  }}
  .dna-v {{
    flex: 1; color: #555; font-weight: 600;
  }}
  .dna-footer {{
    font-size: 9px; color: #D62828; font-weight: 600;
    margin-top: 4px; padding-top: 4px;
    border-top: 1px dashed rgba(0,0,0,0.15);
    letter-spacing: 0.02em;
  }}

  /* 底部 Slogan 黑底黄字 */
  .slogan {{
    flex: 0 0 auto;
    background: #0A0A0A;
    color: #F4C430;
    position: absolute;
    left: 22px; right: 20px; bottom: 18px;
    height: 76px;
    padding: 10px 14px;
    border-left: 5px solid #D62828;
    display: flex;
    align-items: center;
    gap: 12px;
  }}
  .slogan::before {{
    content: "👑";
    position: absolute;
    top: -8px; right: 12px;
    font-size: 18px;
  }}
  .slogan-label {{
    flex: 0 0 auto;
    font-size: 8px; font-weight: 700;
    letter-spacing: 0.3em; text-transform: uppercase;
    color: #F4C430;
    opacity: 0.7;
    writing-mode: vertical-rl;
    line-height: 1;
  }}
  .slogan-text {{
    flex: 1;
    font-size: 16px; font-weight: 900;
    line-height: 1.18;
    color: white;
    white-space: normal;
  }}

  /* 装饰：野兽派几何 + 噪点 */
  .bg-deco-1 {{
    position: absolute;
    top: 80px; right: 50%;
    width: 80px; height: 80px;
    background: #F4C430;
    transform: rotate(20deg);
    z-index: 2;
  }}
  .bg-deco-2 {{
    position: absolute;
    bottom: 100px; right: 0;
    width: 50px; height: 50px;
    background: #D62828;
    transform: rotate(15deg);
    z-index: 2;
  }}
  .noise {{
    position: absolute; inset: 0; z-index: 50; pointer-events: none; opacity: 0.12;
    background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='200' height='200'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.9'/></filter><rect width='200' height='200' filter='url(%23n)' opacity='0.5'/></svg>");
  }}
</style>
</head>
<body>
  <!-- 左侧上半 3D 人物图背景 -->
  <div class="toonhub-bg">
    <img src="{toonhub_image}" alt="3D portrait">
  </div>

  <!-- 装饰几何块 -->
  <div class="bg-deco-1"></div>
  <div class="bg-deco-2"></div>

  <!-- 新野兽派几何拼贴：替代旧版左侧大面积黑块 -->
  <div class="sbti-brutalist-collage" aria-hidden="true">
    <div class="neo-block neo-yellow"></div>
    <div class="neo-block neo-red"></div>
    <div class="neo-block neo-green"></div>
    <div class="neo-block neo-cream"></div>
  </div>

  <!-- 左侧 SBTI 风格小信息卡 -->
  <div class="sbti-side">
    <div class="sbti-side-label">01 · 职场 SBTI</div>
    <div class="sbti-side-code">{persona_code}</div>
    <div class="sbti-side-title">{sbti_label}</div>
    <div class="sbti-side-tag">{persona_tag}</div>
    <div class="sbti-side-desc">{sbti_desc}</div>
    <div class="sbti-side-score">匹配度 {persona_score}%</div>
    <div class="sbti-side-divider"></div>
    {sbti_evidence_html}
  </div>

  <!-- 右侧信息面板 -->
  <div class="right-panel">
    <div class="top-strip">
      <div>SELF-DISTILL · {date}</div>
      <div class="mvp">★ MVP ★</div>
    </div>

    <div class="name-block">
      <div class="name-eyebrow">▍My Profile</div>
      <div class="name">{name}</div>
    </div>

    <div class="identity-strip">
      <span class="identity-chip keirsey">{persona_code} · {persona_tag}</span>
      <span class="identity-chip animal">{animal_emoji} {animal}</span>
      <span class="identity-chip">{mbti}</span>
    </div>

    <!-- SBTI 8 候选排行条（信息密度模块 1；左侧 SBTI 块已显示主风格，此处是数据化全排行） -->
    <div class="sbti8-section">
      <div class="sbti8-title">02 · 8 候选排行</div>
      {sbti_8_html}
    </div>

    <!-- 5 维推断详表（信息密度模块 2） -->
    <div class="t5d-section">
      <div class="t5d-title">03 · 5 维人格</div>
      {traits_5d_html}
    </div>

    <!-- 表达 DNA 关键数据（信息密度模块 3） -->
    <div class="dna-section">
      <div class="dna-title">04 · 表达 DNA</div>
      {expression_dna_html}
    </div>

    <!-- Slogan -->
    <div class="slogan">
      <div class="slogan-label">职场宣言</div>
      <div class="slogan-text">{slogan_long}</div>
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
    "4x5": (TEMPLATE_4X5, 720, 900),
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


def render_html(t: Dict[str, Any], style: str = "4x5", analysis: Dict[str, Any] = None) -> str:
    """渲染 HTML

    新版：人设按 SBTI Top1 查 PERSONA_LIBRARY，3D 小人按 FIGURE_LIBRARY 的视觉特征评分选择
    analysis 含 expression_dna + behavior_patterns + sbti_top3 + 5 维推断
    """
    template_str, w, h = TEMPLATES[style]

    # 默认空 analysis（兼容旧调用——传 t 里的 _expression_dna / _behavior_patterns）
    if analysis is None:
        analysis = {
            "expression_dna": t.get("_expression_dna", {}),
            "behavior_patterns": t.get("_behavior_patterns", {}),
            "sbti_top3": t.get("_sbti_top3", []),
        }
    expression = analysis.get("expression_dna", {}) or {}
    behavior = analysis.get("behavior_patterns", {}) or {}
    messages_count = analysis.get("_messages_count", 0)

    # 选 persona（SBTI 人设 + 3D 小人视觉特征评分）
    sbti_code = t.get("sbti_code", "均衡型")
    persona = select_persona(sbti_code, expression, behavior, messages_count)

    # 压缩图到 800px 宽后转 base64
    import subprocess
    import tempfile as _tf
    _thumb = _tf.NamedTemporaryFile(suffix=".png", delete=False)
    subprocess.run(["sips", "-Z", "800", persona["image"], "--out", _thumb.name],
                   capture_output=True)
    toonhub_data_uri = encode_image_as_data_uri(_thumb.name)
    os.unlink(_thumb.name)

    return template_str.format(
        name=t["name"],
        date=t.get("date", ""),
        mbti=t.get("mbti", "????"),
        mbti_desc=t.get("mbti_desc", ""),
        sbti_code=persona["code"],
        sbti_label=persona["tag"],
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
        # 新版：persona_*（替换原 keirsey_*）
        persona_code=persona["code"],
        persona_tag=persona["tag"],
        persona_color=persona["color"],
        persona_score=persona["score"],
        toonhub_image=toonhub_data_uri,
        # 新模块（信息密度）
        sbti_8_html=build_sbti_8_html(analysis.get("sbti_top3", [])),
        traits_5d_html=build_traits_5d_html(analysis),
        expression_dna_html=build_expression_dna_html(expression),
        sbti_evidence_html=build_sbti_evidence_html(analysis),
    )


# ============== 新模块 HTML builders ==============

def build_sbti_8_html(sbti_top3: List[Dict[str, Any]]) -> str:
    """SBTI 8 候选排行条 HTML

    设计：完整显示 8 个 SBTI 风格
    Top 3 行（真实数据）黑色突出，其他 5 个用 max(1, min-5) 兜底分数灰色显示
    信息密度高，让卡片右侧填满
    """
    if not sbti_top3:
        return ""

    ALL_SBTI = [
        "深潜者", "甩手掌柜", "火警", "架构师",
        "侦察兵", "记者", "指挥官", "讲师",
    ]

    score_map = {s["type"]: s["score"] for s in sbti_top3}
    top3_set = set(score_map.keys())

    items = []
    # Top 3 行（黑色突出）—— 来自真实数据
    for s in sbti_top3:
        name = s["type"]
        sc = s["score"]
        bar_w = int(sc * 70 / 100)
        items.append(
            f'<div class="sbti8-item top3">'
            f'<span class="sbti8-name">{name}</span>'
            f'<span class="sbti8-bar"><span class="sbti8-bar-fill" style="width:{bar_w}px;"></span></span>'
            f'<span class="sbti8-score">{sc}%</span>'
            f'</div>'
        )

    # Top 3 之外的 5 个 SBTI（按 ALL_SBTI 顺序展示，用 max(1, min-5) 兜底分数）
    if score_map:
        min_score = min(score_map.values())
        fill = max(1, min_score - 5)
    else:
        fill = 1
    for name in ALL_SBTI:
        if name in top3_set:
            continue
        sc = score_map.get(name, fill)
        bar_w = int(sc * 70 / 100)
        items.append(
            f'<div class="sbti8-item">'
            f'<span class="sbti8-name">{name}</span>'
            f'<span class="sbti8-bar"><span class="sbti8-bar-fill" style="width:{bar_w}px;"></span></span>'
            f'<span class="sbti8-score">{sc}%</span>'
            f'</div>'
        )

    # 末尾加 1 行汇总注脚
    items.append(
        f'<div class="sbti8-footer">▎Top 3 = 8 候选中分数最高的 3 项 · 其他 5 个分数用 Top 最低 - 5 兜底</div>'
    )

    return "".join(items)


def build_traits_5d_html(analysis: Dict[str, Any]) -> str:
    """5 维推断详表 HTML

    显示 5 维（决策/沟通/压力/价值观/信息处理），每维 primary + secondary + 分数
    """
    if not analysis:
        return ""

    dims = [
        ("决策", analysis.get("decision_style")),
        ("沟通", analysis.get("communication_style")),
        ("压力", analysis.get("stress_response")),
        ("价值", analysis.get("value_tendency")),
        ("信息", analysis.get("info_processing")),
    ]

    items = []
    for label, dim in dims:
        if not dim:
            continue
        primary = dim.get("primary", "?")
        primary_score = dim.get("primary_score", 0)
        secondary = dim.get("secondary")
        secondary_score = dim.get("secondary_score", 0)
        if secondary:
            line2 = f'<span class="t5d-sub">{secondary} {secondary_score}%</span>'
        else:
            line2 = ""
        items.append(
            f'<div class="t5d-row">'
            f'<span class="t5d-label">{label}</span>'
            f'<span class="t5d-primary">{primary} <b>{primary_score}%</b></span>'
            f'{line2}'
            f'</div>'
        )

    # 末尾加 1 行汇总注脚（视觉上"段填满"）
    items.append(
        f'<div class="t5d-footer">▎基于 5 维度独立推断 · primary 与 secondary 差距 = 决策漂移空间</div>'
    )
    return "".join(items)


def build_expression_dna_html(expression_dna: Dict[str, Any]) -> str:
    """表达 DNA 关键数据 HTML

    显示：Top 5 关键词 + 长度分布（mean/p90）+ 工作词比 + 情绪倾向
    """
    if not expression_dna:
        return ""

    top_kw = [w for w, _ in expression_dna.get("top_keywords", [])[:5]]
    ls = expression_dna.get("length_stats", {})
    cat = expression_dna.get("category", {})
    emo = expression_dna.get("emotion", {})

    lines = []
    if top_kw:
        kw_html = " · ".join(top_kw)
        lines.append(f'<div class="dna-row"><span class="dna-k">Top 5 词</span><span class="dna-v">{kw_html}</span></div>')
    if ls:
        mean = ls.get("mean", 0)
        p90 = ls.get("p90", 0)
        lines.append(f'<div class="dna-row"><span class="dna-k">消息长度</span><span class="dna-v">均 {mean:.0f} / P90 {p90:.0f}</span></div>')
    if cat:
        work = cat.get("work_ratio", 0) * 100
        long_msg = cat.get("long_msg_ratio", 0) * 100
        sc = cat.get("single_char_ratio", 0) * 100
        lines.append(f'<div class="dna-row"><span class="dna-k">表达</span><span class="dna-v">工作词 {work:.0f}% · 长 {long_msg:.0f}% · 单字 {sc:.0f}%</span></div>')
    if emo:
        pos = emo.get("positive", 0) * 100
        neg = emo.get("negative", 0) * 100
        neu = emo.get("neutral", 0) * 100
        lines.append(f'<div class="dna-row"><span class="dna-k">情绪</span><span class="dna-v">积极 {pos:.0f}% · 中性 {neu:.0f}% · 消极 {neg:.0f}%</span></div>')

    # 末尾加 1 行汇总注脚
    lines.append(
        f'<div class="dna-footer">▎Top 5 词 = 真实话题 · 工作词比 = 干正事的比例</div>'
    )

    return "".join(lines)


def build_sbti_evidence_html(analysis: Dict[str, Any]) -> str:
    """SBTI 块底部数据速览 HTML（左侧黑色块下方用）

    显示 3 行紧凑统计，避免重复协作榜：
    1. 高峰时段（top 3 hours）
    2. 深夜消息 + 周末活跃比例
    3. 工作词比 + 单字比

    数据缺失时优雅降级（用 "—" 占位）
    """
    if not analysis:
        return ""

    behavior = analysis.get("behavior_patterns", {}) or {}
    expression = analysis.get("expression_dna", {}) or {}

    rows = []

    # 1. 高峰时段
    active_hours = behavior.get("active_hour_top3", []) or []
    if active_hours:
        # 转成 02d 格式（如果元素是 int）
        try:
            hours_str = " · ".join(f"{int(h):02d}:00" for h in active_hours[:3])
        except (TypeError, ValueError):
            hours_str = " · ".join(str(h) for h in active_hours[:3])
        rows.append(
            f'<div class="sbti-side-stat">'
            f'<span class="sss-k">高峰</span>'
            f'<span class="sss-v">{hours_str}</span>'
            f'</div>'
        )

    # 3. 深夜 + 周末占比
    late = behavior.get("late_night_ratio", 0) or 0
    weekend = behavior.get("weekend_ratio", 0) or 0
    if late or weekend:
        rows.append(
            f'<div class="sbti-side-stat">'
            f'<span class="sss-k">作息</span>'
            f'<span class="sss-v">深夜 {late*100:.0f}% · 周末 {weekend*100:.0f}%</span>'
            f'</div>'
        )

    # 4. 工作词比 + 单字比
    cat = expression.get("category", {}) or {}
    if cat:
        work = cat.get("work_ratio", 0) * 100
        sc = cat.get("single_char_ratio", 0) * 100
        rows.append(
            f'<div class="sbti-side-stat">'
            f'<span class="sss-k">表达</span>'
            f'<span class="sss-v">工作词 {work:.0f}% · 单字 {sc:.0f}%</span>'
            f'</div>'
        )

    return "".join(rows)


def build_collab_html(top_collaborators: List) -> str:
    """协作 Top 5 数据条 HTML（接受多种输入格式）"""
    if not top_collaborators:
        return ""

    max_count = max(
        (c[1] if isinstance(c, (list, tuple)) else c.get("count", 0))
        for c in top_collaborators[:5]
    ) or 1

    items = []
    for i, c in enumerate(top_collaborators[:5], 1):
        name = c[0] if isinstance(c, (list, tuple)) else c.get("name", "?")
        count = c[1] if isinstance(c, (list, tuple)) else c.get("count", 0)
        bar_w = int(count * 60 / max_count)
        items.append(
            f'<div class="collab-item">'
            f'<span class="collab-rank">#{i}</span>'
            f'<span class="collab-name">{name}</span>'
            f'<span class="collab-bar"><span class="collab-bar-fill" style="width:{bar_w}px;"></span></span>'
            f'<span class="collab-count">{count}</span>'
            f'</div>'
        )

    # 末尾加 1 行汇总注脚
    total = sum(
        (c[1] if isinstance(c, (list, tuple)) else c.get("count", 0))
        for c in top_collaborators[:5]
    )
    items.append(
        f'<div class="collab-footer">▎Top 5 累计 {total} 次 · 占 Top {len(top_collaborators[:5])} 总消息 {total/max_count*100/100:.0f}%</div>'
    )
    return "".join(items)


def render_html_to_png(html: str, output: str, w: int, h: int) -> bool:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False, encoding="utf-8") as f:
        f.write(html); html_path = f.name
    try:
        cmd = [CHROME_PATH, "--headless=new", "--disable-gpu", "--no-sandbox",
               "--hide-scrollbars", "--force-device-scale-factor=1",
               f"--screenshot={output}", f"--window-size={w},{h}",
               "--virtual-time-budget=5000", f"file://{html_path}"]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            print(f"  ⚠️ Chrome exit={r.returncode}, stderr={r.stderr[:300]}",
                  file=sys.stderr)
        return r.returncode == 0 and os.path.exists(output)
    except subprocess.TimeoutExpired:
        print(f"  ⚠️ Chrome 渲染超时（120s），html 大小={os.path.getsize(html_path)/1024:.0f}KB",
              file=sys.stderr)
        return False
    finally:
        try: os.unlink(html_path)
        except OSError: pass


def render_card(t: Dict[str, Any], output: str, style: str = "4x5", analysis: Dict[str, Any] = None) -> bool:
    html = render_html(t, style, analysis=analysis)
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
        # 把 messages_count 注入到 analysis
        analysis["_messages_count"] = len(result.messages)
        render_card(template, str(out), style=s, analysis=analysis)
    print(f"\n✓ 完成 {len(styles)} 张", file=sys.stderr)
