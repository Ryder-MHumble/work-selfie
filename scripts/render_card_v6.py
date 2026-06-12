#!/usr/bin/env python3
"""
self-distill 名片 v6 — 完全重新设计

按 真实视觉反馈：
  - 比例 = 商业个人名片 1050x600 (1.75:1)
  - 排版紧凑 / 信息密度高
  - 不能对称/平铺 / 必有设计感
  - 野兽派×二次元 自由发挥

设计概念（v6 全新）：
  - 主体：左侧巨大姓名（垂直锚点）+ 右侧分层信息
  - 不对称：左 1/3 是姓名/SBTI/MBTI 主标识区；右 2/3 是性格+KPI+宣言 分层排版
  - 多层次：4 层视觉信息叠加（背景几何 / 主姓名 / 数据条 / 标签群）
  - 撞色：黑 + 荧光黄 + 警示红 + 1 个二次元点缀色（钴蓝）
  - 野兽派特征：粗黑边 / 几何拼贴 / 高对比 / 噪点
  - 二次元特征：emoji 徽章 / 大字手写感 / 二次元元素符号
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

# 商业名片标准 1.75:1 = 1050x600


# ============== 字体探测 ==============

_CJK_FP = None
try:
    from matplotlib import font_manager as _fm
    for _cand in ["PingFang HK", "Hiragino Sans GB", "STHeiti", "Heiti TC", "Hiragino Sans"]:
        for _af in _fm.fontManager.ttflist:
            if _af.name == _cand:
                _CJK_FP = _fm.FontProperties(fname=_af.fname)
                break
        if _CJK_FP:
            break
except Exception:
    pass


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


def build_traits_grid(traits: List[Dict[str, str]], cols: int = 3) -> str:
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


# ============== 模板 v6 ==============

TEMPLATE = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>名片 · {name}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  html, body {{
    width: 1050px; height: 600px;
    overflow: hidden;
    font-family: 'PingFang HK', 'Hiragino Sans GB', 'STHeiti', 'Noto Sans CJK SC', sans-serif;
  }}

  body {{
    background: #F4EFE3;  /* 米白卡纸感 */
    color: #0A0A0A;
    position: relative;
  }}

  /* ===== 背景几何（非对称）===== */
  .bg-shape-1 {{
    position: absolute;
    top: -50px; right: -30px;
    width: 280px; height: 280px;
    background: #F4C430;
    transform: rotate(15deg);
    z-index: 1;
  }}
  .bg-shape-2 {{
    position: absolute;
    bottom: -20px; left: 30%;
    width: 140px; height: 140px;
    background: #D62828;
    transform: rotate(-20deg);
    z-index: 1;
  }}
  .bg-shape-3 {{
    position: absolute;
    top: 50%; left: 35%;
    transform: translate(-50%, -50%) rotate(45deg);
    width: 60px; height: 60px;
    background: #0A0A0A;
    z-index: 1;
  }}

  /* 噪点（野兽派细节） */
  .noise {{
    position: absolute; inset: 0; z-index: 50; pointer-events: none; opacity: 0.18;
    background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='200' height='200'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.9'/></filter><rect width='200' height='200' filter='url(%23n)' opacity='0.5'/></svg>");
  }}

  /* ===== 主内容 ===== */
  .card {{
    position: relative;
    z-index: 10;
    width: 1050px; height: 600px;
    padding: 28px 36px;
  }}

  /* ===== 顶部一行：左 eyebrow + 右 日期 + MVP ===== */
  .top-strip {{
    display: flex; justify-content: space-between; align-items: center;
    font-size: 10px; font-weight: 800;
    letter-spacing: 0.3em;
    text-transform: uppercase;
    color: #0A0A0A;
    border-bottom: 2px solid #0A0A0A;
    padding-bottom: 6px;
    margin-bottom: 14px;
  }}
  .mvp-stamp {{
    background: #0A0A0A;
    color: #F4C430;
    padding: 2px 8px;
    font-size: 10px; font-weight: 900;
    letter-spacing: 0.2em;
  }}

  /* ===== 主体网格：不对称 35% + 65% ===== */
  .main-grid {{
    display: grid;
    grid-template-columns: 320px 1fr;
    gap: 22px;
    height: 470px;
  }}

  /* ===== 左栏：姓名 + SBTI + MBTI（垂直叠加）===== */
  .left-col {{ position: relative; }}

  /* 姓名 - 巨大文字 */
  .name-block {{
    margin-bottom: 14px;
  }}
  .name-eyebrow {{
    font-size: 10px; font-weight: 700;
    letter-spacing: 0.4em;
    color: #D62828;
    text-transform: uppercase;
    margin-bottom: 4px;
  }}
  .name {{
    font-size: 80px; font-weight: 900;
    line-height: 0.92;
    color: #0A0A0A;
    letter-spacing: -0.04em;
  }}
  .name-zh {{
    font-size: 50px; font-weight: 900;
    color: #0A0A0A;
    margin-top: 2px;
    line-height: 1;
  }}
  .name-zh .red {{ color: #D62828; }}

  /* SBTI - 横长条 */
  .sbti-block {{
    background: #0A0A0A;
    color: white;
    padding: 8px 12px;
    margin: 10px 0 8px 0;
    position: relative;
    transform: rotate(-1deg);
  }}
  .sbti-label {{
    font-size: 9px; font-weight: 700;
    color: #F4C430;
    letter-spacing: 0.3em;
    text-transform: uppercase;
    margin-bottom: 2px;
  }}
  .sbti-row {{
    display: flex; align-items: baseline; gap: 8px;
  }}
  .sbti-tag {{
    font-size: 16px; font-weight: 900;
    color: white;
  }}
  .sbti-code {{
    font-size: 28px; font-weight: 900;
    color: #F4C430;
    line-height: 1;
  }}
  .sbti-desc {{
    font-size: 10px; font-weight: 500;
    color: white;
    margin-top: 4px;
    line-height: 1.3;
  }}

  /* MBTI - 大方块 */
  .mbti-block {{
    background: #D62828;
    color: white;
    padding: 10px 14px;
    transform: rotate(1deg);
    margin: 10px 0 0 16px;
    position: relative;
  }}
  .mbti-label {{
    font-size: 9px; font-weight: 700;
    color: white;
    letter-spacing: 0.3em;
    text-transform: uppercase;
    margin-bottom: 2px;
    opacity: 0.8;
  }}
  .mbti-code {{
    font-size: 48px; font-weight: 900;
    color: white;
    line-height: 0.9;
    letter-spacing: 0.02em;
  }}
  .mbti-desc {{
    font-size: 10px; font-weight: 600;
    color: white;
    margin-top: 4px;
    line-height: 1.3;
    opacity: 0.95;
  }}

  /* 动物 emoji 徽章（圆形） */
  .animal-badge {{
    position: absolute;
    top: 12px; right: -8px;
    width: 80px; height: 80px;
    background: #F4C430;
    border: 3px solid #0A0A0A;
    border-radius: 50%;
    display: flex; flex-direction: column;
    align-items: center; justify-content: center;
    font-size: 36px;
    box-shadow: 3px 3px 0 #0A0A0A;
    z-index: 12;
  }}
  .animal-badge-name {{
    font-size: 8px; font-weight: 900;
    color: #0A0A0A;
    letter-spacing: 0.1em;
    margin-top: -2px;
  }}
  .animal-badge-pct {{
    font-size: 9px; font-weight: 700;
    color: #D62828;
  }}

  /* ===== 右栏：性格 + KPI + 宣言 + 工号 ===== */
  .right-col {{ position: relative; }}

  /* 性格特征 - 3x2 网格 */
  .traits-title {{
    font-size: 10px; font-weight: 800;
    letter-spacing: 0.3em;
    text-transform: uppercase;
    color: #0A0A0A;
    margin-bottom: 6px;
  }}
  .traits-title::before {{
    content: "▍";
    color: #D62828;
    margin-right: 2px;
  }}
  .traits-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 6px 8px;
    margin-bottom: 10px;
  }}
  .trait {{
    display: flex; gap: 6px; align-items: flex-start;
    padding: 5px 6px;
    background: rgba(255,255,255,0.7);
    border-left: 3px solid #0A0A0A;
  }}
  .trait-icon {{ font-size: 16px; flex-shrink: 0; }}
  .trait-body {{ flex: 1; min-width: 0; }}
  .trait-title {{
    font-size: 11px; font-weight: 800;
    color: #0A0A0A;
    line-height: 1.1;
  }}
  .trait-desc {{
    font-size: 9px; font-weight: 500;
    color: #555;
    line-height: 1.2;
  }}

  /* KPI - 横向 */
  .kpi-section {{
    background: rgba(255,255,255,0.7);
    border: 2px solid #0A0A0A;
    padding: 7px 10px;
    margin-bottom: 8px;
  }}
  .kpi-header {{
    display: flex; align-items: center; gap: 8px;
    margin-bottom: 4px;
  }}
  .kpi-title {{
    font-size: 10px; font-weight: 800;
    letter-spacing: 0.3em;
    text-transform: uppercase;
    color: #0A0A0A;
  }}
  .kpi-items {{
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 4px;
  }}
  .kpi-item {{
    display: flex; gap: 4px; align-items: center;
    font-size: 10px;
  }}
  .kpi-check {{
    font-size: 14px; font-weight: 900;
  }}
  .kpi-check.on {{ color: #D62828; }}
  .kpi-check.off {{ color: #888; }}
  .kpi-body {{ line-height: 1.1; }}
  .kpi-name {{
    font-size: 11px; font-weight: 800;
    color: #0A0A0A;
  }}
  .kpi-evidence {{
    font-size: 8px; color: #666;
  }}

  /* 宣言 - 黑底黄字 */
  .manifesto {{
    background: #0A0A0A;
    color: #F4C430;
    padding: 8px 12px;
    position: relative;
    margin-bottom: 8px;
    border-left: 6px solid #D62828;
  }}
  .manifesto::before {{
    content: "👑";
    position: absolute;
    top: -8px; right: 10px;
    font-size: 20px;
  }}
  .manifesto-label {{
    font-size: 9px; font-weight: 700;
    letter-spacing: 0.3em;
    text-transform: uppercase;
    color: #F4C430;
    margin-bottom: 2px;
    opacity: 0.7;
  }}
  .manifesto-text {{
    font-size: 13px; font-weight: 900;
    line-height: 1.4;
    color: white;
    white-space: pre-line;
  }}

  /* Sneaky + 工号 - 底部紧凑行 */
  .bottom-strip {{
    display: flex; justify-content: space-between; align-items: center;
    gap: 12px;
  }}
  .sneaky-tag {{
    background: #D62828;
    color: white;
    padding: 4px 10px;
    font-size: 10px; font-weight: 900;
    letter-spacing: 0.05em;
    border: 2px solid #0A0A0A;
    transform: rotate(-2deg);
    display: inline-block;
  }}
  .bottom-meta {{
    display: flex; gap: 10px; align-items: center;
    font-size: 9px; font-weight: 700;
    color: #0A0A0A;
  }}
  .barcode-block {{
    background: white;
    border: 1px solid #0A0A0A;
    padding: 3px 6px;
  }}
  .barcode {{ display: flex; gap: 1px; height: 20px; }}
  .bar {{ background: #0A0A0A; }}
  .bar.empty {{ background: white; }}
  .barcode-text {{
    font-size: 7px; font-weight: 700;
    color: #0A0A0A;
    font-family: 'SF Mono', monospace;
    margin-top: 1px;
  }}
</style>
</head>
<body>
  <div class="bg-shape-1"></div>
  <div class="bg-shape-2"></div>
  <div class="bg-shape-3"></div>

  <div class="card">
    <!-- 顶行 -->
    <div class="top-strip">
      <div>SELF-DISTILL · 自查名片 · {date}</div>
      <div class="mvp-stamp">★ MVP ★</div>
    </div>

    <!-- 主体 -->
    <div class="main-grid">

      <!-- 左栏：姓名 + SBTI + MBTI -->
      <div class="left-col">
        <div class="animal-badge">
          <div>{animal_emoji}</div>
          <div class="animal-badge-name">{animal}</div>
          <div class="animal-badge-pct">{animal_match}%</div>
        </div>

        <div class="name-block">
          <div class="name-eyebrow">▍My ID Card</div>
          <div class="name">{name}</div>
        </div>

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

      <!-- 右栏：性格 + KPI + 宣言 + 工号 -->
      <div class="right-col">
        <div class="traits-title">03 · 性格特征</div>
        <div class="traits-grid">
          {traits_html}
        </div>

        <div class="kpi-section">
          <div class="kpi-header">
            <div class="kpi-title">▍今日KPI（快乐版）</div>
          </div>
          <div class="kpi-items">
            {kpi_items}
          </div>
        </div>

        <div class="manifesto">
          <div class="manifesto-label">▍职场宣言</div>
          <div class="manifesto-text">{slogan_long}</div>
        </div>

        <div class="bottom-strip">
          <div class="sneaky-tag">摸鱼伪装大师 · {sneaky_label}</div>
          <div class="bottom-meta">
            <span>入职 {join_date}</span>
            <div class="barcode-block">
              <div class="barcode">{barcode_bars}</div>
              <div class="barcode-text">工号 {employee_id}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <div class="noise"></div>
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


def render_html(t: Dict[str, Any]) -> str:
    return TEMPLATE.format(
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
        traits_html=build_traits_grid(t.get("personality_traits", [])),
        kpi_items=build_kpi_items(t.get("kpi_happy", [])),
        employee_id=t.get("employee_id", "000000"),
        join_date=t.get("join_date", ""),
        barcode_bars=make_barcode_bars(t.get("employee_id", "0")),
    )


def render_html_to_png(html: str, output: str, w=1050, h=600) -> bool:
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


def render_card(t: Dict[str, Any], output: str) -> bool:
    html = render_html(t)
    t0 = time.time()
    ok = render_html_to_png(html, output)
    if ok:
        print(f"  ✓ {output} ({os.path.getsize(output)/1024:.0f}KB, {time.time()-t0:.1f}s)",
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

    parser = argparse.ArgumentParser(description="名片 v6（商业名片比例）")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--output-dir", default="/tmp/self-distill-cards")
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
    out = output_dir / f"card_v6_{result.user_name}_{args.days}d.png"
    render_card(template, str(out))
    print(f"\n✓ 完成：{out}", file=sys.stderr)
