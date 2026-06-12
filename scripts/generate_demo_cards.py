#!/usr/bin/env python3
"""Generate fictional English demo cards for the promotional README."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent))

from render_card import render_html, render_html_to_png, TEMPLATES  # noqa: E402


OUT_DIR = Path(__file__).resolve().parent.parent / "examples" / "cards"


def _analysis(
    *,
    sbti_top3: List[Dict[str, Any]],
    expression: Dict[str, Any],
    behavior: Dict[str, Any],
    decision: Dict[str, Any],
    communication: Dict[str, Any],
    stress: Dict[str, Any],
    value: Dict[str, Any],
    info: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "sbti_top3": sbti_top3,
        "expression_dna": expression,
        "behavior_patterns": behavior,
        "decision_style": decision,
        "communication_style": communication,
        "stress_response": stress,
        "value_tendency": value,
        "info_processing": info,
        "_messages_count": 1200,
    }


def _expression(
    *,
    keywords: List[str],
    mean: int,
    p90: int,
    work: float,
    long_msg: float,
    single_char: float,
    positive: float,
    negative: float,
    question: float,
) -> Dict[str, Any]:
    return {
        "top_keywords": [(word, 10 - i) for i, word in enumerate(keywords)],
        "length_stats": {"mean": mean, "p90": p90},
        "category": {
            "work_ratio": work,
            "long_msg_ratio": long_msg,
            "single_char_ratio": single_char,
        },
        "emotion": {
            "positive": positive,
            "negative": negative,
            "neutral": max(0, 1 - positive - negative),
        },
        "punctuation_density": {"question": question},
    }


def _behavior(
    *,
    group: float,
    collabs: List[int],
    hours: List[int],
    late: float,
    weekend: float,
) -> Dict[str, Any]:
    names = ["Design Ops", "Research Guild", "Launch Room", "Data Studio"]
    return {
        "group_vs_p2p": {"group": group, "p2p": 1 - group},
        "top_collaborators": list(zip(names, collabs)),
        "active_hour_top3": hours,
        "late_night_ratio": late,
        "weekend_ratio": weekend,
    }


def _template(
    *,
    name: str,
    mbti: str,
    sbti_code: str,
    sbti_desc: str,
    animal: str,
    animal_emoji: str,
    motto: str,
) -> Dict[str, Any]:
    return {
        "name": name,
        "date": "2026-06-12",
        "mbti": mbti,
        "mbti_desc": "fictional demo profile",
        "sbti_code": sbti_code,
        "sbti_label": "",
        "sbti_desc": sbti_desc,
        "animal": animal,
        "animal_emoji": animal_emoji,
        "animal_match": 94,
        "sneaky_label": "",
        "slogan_long": motto,
        "personality_traits": [],
        "kpi_happy": [],
        "employee_id": "DEMO42",
        "join_date": "2026-01-01",
    }


CASES = [
    {
        "slug": "orange-focus-architect",
        "template": _template(
            name="Avery North",
            mbti="INTJ",
            sbti_code="架构师",
            sbti_desc="Turns fuzzy strategy into a system map before anyone opens slides.",
            animal="Owl",
            animal_emoji="🦉",
            motto="Think in systems. Ship with intent. Stay focused.",
        ),
        "analysis": _analysis(
            sbti_top3=[
                {"type": "架构师", "score": 96, "evidence": "long messages + systems language"},
                {"type": "深潜者", "score": 88, "evidence": "deep work vocabulary"},
                {"type": "指挥官", "score": 58, "evidence": "clear planning traces"},
            ],
            expression=_expression(
                keywords=["systems", "strategy", "model", "principle", "architecture"],
                mean=96,
                p90=180,
                work=0.62,
                long_msg=0.46,
                single_char=0.02,
                positive=0.08,
                negative=0.02,
                question=0.03,
            ),
            behavior=_behavior(group=0.32, collabs=[120, 28, 18, 12], hours=[9, 11, 15], late=0.01, weekend=0.03),
            decision={"primary": "Systems-first", "primary_score": 98, "secondary": "Evidence-led", "secondary_score": 91},
            communication={"primary": "Precise", "primary_score": 94, "secondary": "Structured", "secondary_score": 88},
            stress={"primary": "Deep-work mode", "primary_score": 92, "secondary": "Quiet reset", "secondary_score": 66},
            value={"primary": "Coherence", "primary_score": 96, "secondary": "Quality", "secondary_score": 82},
            info={"primary": "Long-form synthesis", "primary_score": 97, "secondary": "Framework notes", "secondary_score": 86},
        ),
    },
    {
        "slug": "green-energy-mentor",
        "template": _template(
            name="Mira Vale",
            mbti="ENFP",
            sbti_code="讲师",
            sbti_desc="Explains the messy thing until the room suddenly gets it.",
            animal="Dolphin",
            animal_emoji="🐬",
            motto="Make it clear. Make it warm. Make it memorable.",
        ),
        "analysis": _analysis(
            sbti_top3=[
                {"type": "讲师", "score": 94, "evidence": "long explanations + high positivity"},
                {"type": "记者", "score": 71, "evidence": "collects examples before teaching"},
                {"type": "火警", "score": 50, "evidence": "responds fast when blocked"},
            ],
            expression=_expression(
                keywords=["workshop", "story", "example", "learn", "spark"],
                mean=62,
                p90=120,
                work=0.28,
                long_msg=0.35,
                single_char=0.01,
                positive=0.42,
                negative=0.01,
                question=0.08,
            ),
            behavior=_behavior(group=0.58, collabs=[220, 160, 120, 80], hours=[10, 16, 20], late=0.03, weekend=0.04),
            decision={"primary": "People-first", "primary_score": 96, "secondary": "Story-led", "secondary_score": 89},
            communication={"primary": "Warm explainer", "primary_score": 99, "secondary": "High-context", "secondary_score": 74},
            stress={"primary": "Rallies the room", "primary_score": 87, "secondary": "Asks for signal", "secondary_score": 62},
            value={"primary": "Clarity", "primary_score": 95, "secondary": "Energy", "secondary_score": 91},
            info={"primary": "Examples first", "primary_score": 90, "secondary": "Narrative map", "secondary_score": 84},
        ),
    },
    {
        "slug": "pink-execution-commander",
        "template": _template(
            name="Nova Reed",
            mbti="ESTJ",
            sbti_code="指挥官",
            sbti_desc="Keeps the launch train moving without making it feel like a train.",
            animal="Lion",
            animal_emoji="🦁",
            motto="Align the team. Cut the drift. Move the launch.",
        ),
        "analysis": _analysis(
            sbti_top3=[
                {"type": "指挥官", "score": 100, "evidence": "daytime rhythm + core collaboration"},
                {"type": "记者", "score": 84, "evidence": "high operating signal"},
                {"type": "架构师", "score": 57, "evidence": "planning vocabulary"},
            ],
            expression=_expression(
                keywords=["launch", "owner", "timeline", "risk", "decision"],
                mean=38,
                p90=72,
                work=0.31,
                long_msg=0.16,
                single_char=0.04,
                positive=0.12,
                negative=0.03,
                question=0.04,
            ),
            behavior=_behavior(group=0.45, collabs=[900, 100, 45, 30], hours=[10, 14, 17], late=0.01, weekend=0.01),
            decision={"primary": "Action-biased", "primary_score": 100, "secondary": "Consensus-aware", "secondary_score": 82},
            communication={"primary": "Direct", "primary_score": 97, "secondary": "Status-clear", "secondary_score": 91},
            stress={"primary": "Re-sequences work", "primary_score": 94, "secondary": "Escalates early", "secondary_score": 78},
            value={"primary": "Momentum", "primary_score": 99, "secondary": "Reliability", "secondary_score": 88},
            info={"primary": "Plan board", "primary_score": 93, "secondary": "Decision log", "secondary_score": 70},
        ),
    },
    {
        "slug": "blue-scout-signal",
        "template": _template(
            name="Kai Signal",
            mbti="ENTP",
            sbti_code="侦察兵",
            sbti_desc="Finds the loose thread, pulls it, and turns it into the next move.",
            animal="Fox",
            animal_emoji="🦊",
            motto="Ask sharper. Move faster. Surface the signal.",
        ),
        "analysis": _analysis(
            sbti_top3=[
                {"type": "侦察兵", "score": 92, "evidence": "question-heavy, short-loop probing"},
                {"type": "甩手掌柜", "score": 73, "evidence": "delegates in group channels"},
                {"type": "火警", "score": 61, "evidence": "late incident response"},
            ],
            expression=_expression(
                keywords=["why", "where", "signal", "check", "edge"],
                mean=18,
                p90=32,
                work=0.12,
                long_msg=0.03,
                single_char=0.32,
                positive=0.09,
                negative=0.06,
                question=0.32,
            ),
            behavior=_behavior(group=0.75, collabs=[180, 170, 140, 100], hours=[23, 11, 16], late=0.14, weekend=0.08),
            decision={"primary": "Probe-first", "primary_score": 94, "secondary": "Fast pivot", "secondary_score": 88},
            communication={"primary": "Question-led", "primary_score": 99, "secondary": "Short-loop", "secondary_score": 84},
            stress={"primary": "Rapid triage", "primary_score": 93, "secondary": "Pings experts", "secondary_score": 80},
            value={"primary": "Signal", "primary_score": 96, "secondary": "Speed", "secondary_score": 90},
            info={"primary": "Live scanning", "primary_score": 98, "secondary": "Thread tracing", "secondary_score": 81},
        ),
    },
]


REPLACEMENTS = {
    "01 · 职场 SBTI": "01 · WORK SBTI",
    "02 · 8 候选排行": "02 · STYLE RANKING",
    "03 · 5 维人格": "03 · 5-D PROFILE",
    "04 · 表达 DNA": "04 · EXPRESSION DNA",
    "职场宣言": "WORK MOTTO",
    "匹配度": "MATCH",
    "决策": "Decision",
    "沟通": "Comms",
    "压力": "Stress",
    "价值": "Values",
    "信息": "Info",
    "Top 5 词": "Top words",
    "消息长度": "Length",
    "表达": "Speech",
    "情绪": "Mood",
    "均 ": "Avg ",
    "工作词": "work",
    "长 ": "long ",
    "单字": "short",
    "积极": "pos",
    "中性": "neutral",
    "消极": "neg",
    "高峰": "Peak",
    "作息": "Rhythm",
    "深夜": "late",
    "周末": "weekend",
    "基于 5 维度独立推断 · primary 与 secondary 差距 = 决策漂移空间": "Five independent signals; primary/secondary gap shows drift space",
    "Top 5 词 = 真实话题 · 工作词比 = 干正事的比例": "Top words show live topics; work ratio shows operating focus",
    "Top 3 = 8 候选中分数最高的 3 项 · 其他 5 个分数用 Top 最低 - 5 兜底": "Top 3 are scored directly; remaining styles use a visible fallback baseline",
    "指挥官": "Commander",
    "记者": "Reporter",
    "讲师": "Mentor",
    "深潜者": "Deep Diver",
    "甩手掌柜": "Delegator",
    "火警": "Firefighter",
    "架构师": "Architect",
    "侦察兵": "Scout",
    "人形 Gantt 型": "Human Gantt",
    "数据狂魔型": "Data Hunter",
    "传道授业型": "Explainer",
    "深度内卷型": "Deep Focus",
    "佛系指挥型": "Calm Delegator",
    "红色警戒型": "Fire Watch",
    "PPT 永动机型": "System Builder",
    "信息掮客型": "Signal Scout",
    "均衡型": "Balanced",
}


def english_demo_html(template: Dict[str, Any], analysis: Dict[str, Any]) -> str:
    html = render_html(template, "4x5", analysis=analysis)
    for zh, en in sorted(REPLACEMENTS.items(), key=lambda item: len(item[0]), reverse=True):
        html = html.replace(zh, en)
    return html


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    _, width, height = TEMPLATES["4x5"]
    for case in CASES:
        output = OUT_DIR / f"{case['slug']}.png"
        html = english_demo_html(case["template"], case["analysis"])
        ok = render_html_to_png(html, str(output), width, height)
        if not ok:
            raise RuntimeError(f"Failed to render {case['slug']}")
        print(output)


if __name__ == "__main__":
    main()
