#!/usr/bin/env python3
"""
self-distill 元数据持久化层

唯一允许在 skill 目录的 data/ 下写文件的脚本。
永远不写入 raw message / raw document —— 只存分析结果摘要。

Schema v1 (2026-06-11):
{
  "schema_version": 1,
  "user_id": "user_xxx",
  "user_name": "Demo User",
  "first_run_at": "2026-05-12T10:00:00+08:00",
  "last_run_at": "2026-06-11T11:30:00+08:00",
  "run_count": 3,
  "current_window": {"start": "...", "end": "..."},
  "data_sources": {
    "chat": {"status": "ok", "message_count": 3421, "conversation_count": 87},
    "minutes": {"status": "ok", "meeting_count": 12},
    "doc": {"status": "ok", "doc_count": 8},
    "aitable": {"status": "ok", "base_count": 3}
  },
  "expression_dna": {...},
  "behavior_patterns": {...},
  "personality": {...},
  "slogan_candidates": [...],
  "diff_from_previous": {...}
}
"""

import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List


# CST 时区（+08:00）
CST = timezone(timedelta(hours=8))

SNAPSHOT_PATH = Path(__file__).resolve().parent.parent / "data" / "last_snapshot.json"
SCHEMA_VERSION = 1


def now_iso() -> str:
    """当前时间（CST）ISO 格式"""
    return datetime.now(CST).strftime("%Y-%m-%dT%H:%M:%S%08:00")


def empty_snapshot(user_id: str, user_name: str) -> Dict[str, Any]:
    """生成空 snapshot 模板"""
    return {
        "schema_version": SCHEMA_VERSION,
        "user_id": user_id,
        "user_name": user_name,
        "first_run_at": now_iso(),
        "last_run_at": now_iso(),
        "run_count": 0,
        "current_window": {"start": None, "end": None},
        "data_sources": {
            "chat": {"status": "pending"},
            "minutes": {"status": "pending"},
            "doc": {"status": "pending"},
            "aitable": {"status": "pending"},
        },
        "expression_dna": {},
        "behavior_patterns": {},
        "personality": {},
        "slogan_candidates": [],
        "diff_from_previous": {},
    }


def load_snapshot() -> Optional[Dict[str, Any]]:
    """读 snapshot（不存在返回 None）"""
    if not SNAPSHOT_PATH.exists():
        return None
    try:
        with open(SNAPSHOT_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if data.get("schema_version") != SCHEMA_VERSION:
            print(
                f"⚠️ snapshot schema_version={data.get('schema_version')} "
                f"与当前 ({SCHEMA_VERSION}) 不匹配，建议全量重跑",
                file=__import__("sys").stderr,
            )
        return data
    except (json.JSONDecodeError, OSError) as e:
        print(f"⚠️ snapshot 读取失败：{e}", file=__import__("sys").stderr)
        return None


def save_snapshot(snapshot: Dict[str, Any]) -> None:
    """写 snapshot（覆盖式）"""
    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    snapshot["last_run_at"] = now_iso()
    snapshot["run_count"] = snapshot.get("run_count", 0) + 1
    with open(SNAPSHOT_PATH, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)
    print(f"✓ snapshot 已保存：{SNAPSHOT_PATH}", file=__import__("sys").stderr)


def is_incremental(snapshot: Optional[Dict[str, Any]]) -> bool:
    """判断是否增量模式（有历史 snapshot 即可增量）"""
    if snapshot is None:
        return False
    return snapshot.get("run_count", 0) > 0


def get_incremental_start(snapshot: Optional[Dict[str, Any]]) -> Optional[str]:
    """获取增量起点（上次 last_run_at）"""
    if not is_incremental(snapshot):
        return None
    return snapshot.get("last_run_at")


def verify_user_match(
    snapshot: Optional[Dict[str, Any]], current_user_id: str
) -> bool:
    """校验历史 snapshot 的 userId 与当前 userId 一致"""
    if snapshot is None:
        return True
    return snapshot.get("user_id") == current_user_id


def diff_snapshots(
    old: Optional[Dict[str, Any]], new: Dict[str, Any]
) -> Dict[str, Any]:
    """对比两个 snapshot，输出 diff 摘要（写入 new["diff_from_previous"]）"""
    if old is None or old.get("run_count", 0) == 0:
        return {
            "is_first_run": True,
            "message": "首次运行，无历史对比",
        }

    diff = {
        "is_first_run": False,
        "previous_run_at": old.get("last_run_at"),
        "delta_message_count": 0,
        "new_keywords": [],
        "dropped_keywords": [],
        "new_top_collaborators": [],
        "active_hour_shift": {},
        "mbti_drift": {},
    }

    # 1. 消息数变化
    old_chat = old.get("data_sources", {}).get("chat", {})
    new_chat = new.get("data_sources", {}).get("chat", {})
    old_count = old_chat.get("message_count", 0)
    new_count = new_chat.get("message_count", 0)
    diff["delta_message_count"] = new_count - old_count

    # 2. 关键词变化
    old_kw = dict(old.get("expression_dna", {}).get("top_keywords", []))
    new_kw = dict(new.get("expression_dna", {}).get("top_keywords", []))
    old_top50 = set(list(old_kw.keys())[:50])
    new_top50 = set(list(new_kw.keys())[:50])
    diff["new_keywords"] = sorted(new_top50 - old_top50)
    diff["dropped_keywords"] = sorted(old_top50 - new_top50)

    # 3. 协作变化
    old_collab = dict(old.get("behavior_patterns", {}).get("top_collaborators", []))
    new_collab = dict(new.get("behavior_patterns", {}).get("top_collaborators", []))
    diff["new_top_collaborators"] = [
        name for name in new_collab if name not in old_collab
    ][:5]

    # 4. 活跃时段变化（对比 top 3 高峰小时）
    old_heatmap = old.get("behavior_patterns", {}).get("active_hour_heatmap")
    new_heatmap = new.get("behavior_patterns", {}).get("active_hour_heatmap")
    if old_heatmap and new_heatmap:
        # 简化为 top 3 高峰小时
        old_top = sorted(
            enumerate(sum(row) for row in old_heatmap),
            key=lambda x: -x[1],
        )[:3]
        new_top = sorted(
            enumerate(sum(row) for row in new_heatmap),
            key=lambda x: -x[1],
        )[:3]
        diff["active_hour_shift"] = {
            "previous_top3_hours": [h for h, _ in old_top],
            "current_top3_hours": [h for h, _ in new_top],
        }

    # 5. MBTI 维度漂移（>5 分记一次变化）
    old_mbti = old.get("personality", {}).get("mbti", {})
    new_mbti = new.get("personality", {}).get("mbti", {})
    for dim in ["EI", "SN", "TF", "JP"]:
        old_val = old_mbti.get(dim)
        new_val = new_mbti.get(dim)
        if old_val is not None and new_val is not None:
            # 提取分数
            try:
                old_score = int(old_val.split("(")[1].rstrip(")"))
                new_score = int(new_val.split("(")[1].rstrip(")"))
                if abs(new_score - old_score) >= 5:
                    diff["mbti_drift"][dim] = {
                        "from": old_val,
                        "to": new_val,
                        "delta": new_score - old_score,
                    }
            except (IndexError, ValueError):
                pass

    return diff


def get_window(days: int) -> Dict[str, str]:
    """生成时间窗口（默认 days=30）"""
    end = datetime.now(CST)
    start = end - timedelta(days=days)
    return {
        "start": start.strftime("%Y-%m-%dT00:00:00+08:00"),
        "end": end.strftime("%Y-%m-%dT23:59:59+08:00"),
    }


if __name__ == "__main__":
    # 单元自测
    import sys
    print("snapshot.py 单元测试")
    print(f"  SNAPSHOT_PATH = {SNAPSHOT_PATH}")
    print(f"  schema_version = {SCHEMA_VERSION}")

    # 测试 empty
    s = empty_snapshot("user_test", "TestUser")
    print(f"  empty snapshot keys: {list(s.keys())}")

    # 测试 round-trip
    s["data_sources"]["chat"]["status"] = "ok"
    s["data_sources"]["chat"]["message_count"] = 100
    save_snapshot(s)
    s2 = load_snapshot()
    assert s2["data_sources"]["chat"]["message_count"] == 100
    print(f"  ✓ round-trip 通过")

    # 测试 diff
    s2["data_sources"]["chat"]["message_count"] = 150
    s2["expression_dna"]["top_keywords"] = {"hello": 10, "world": 5}
    s2["behavior_patterns"]["top_collaborators"] = {"alice": 5}
    d = diff_snapshots(s, s2)
    print(f"  diff delta_message_count = {d['delta_message_count']}")
    assert d["delta_message_count"] == 50

    # 清理
    if SNAPSHOT_PATH.exists():
        SNAPSHOT_PATH.unlink()
        print(f"  ✓ 清理测试 snapshot")

    print("✓ 全部通过")
