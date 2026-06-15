import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

import monthly_export
from collect_self import ChatMessage


ROOT = Path(__file__).resolve().parents[1]


class MonthlyExportTest(unittest.TestCase):
    def test_iter_month_windows_preserves_partial_first_and_last_month(self):
        windows = monthly_export.iter_month_windows(
            "2026-01-15T09:30:00+08:00",
            "2026-03-02T18:15:00+08:00",
        )

        self.assertEqual(["2026-01", "2026-02", "2026-03"], [w.month for w in windows])
        self.assertEqual("2026-01-15 09:30:00", windows[0].start_dws)
        self.assertEqual("2026-01-31 23:59:59", windows[0].end_dws)
        self.assertEqual("2026-02-01 00:00:00", windows[1].start_dws)
        self.assertEqual("2026-02-28 23:59:59", windows[1].end_dws)
        self.assertEqual("2026-03-01 00:00:00", windows[2].start_dws)
        self.assertEqual("2026-03-02 18:15:00", windows[2].end_dws)

    def test_export_uses_dws_list_all_and_writes_month_files(self):
        page = {
            "result": {
                "hasMore": False,
                "nextCursor": "",
                "conversationMessagesList": [
                    {
                        "openConversationId": "cid-1",
                        "title": "Launch Room",
                        "singleChat": False,
                        "messages": [
                            {
                                "content": "推进 README 发布计划",
                                "createTime": "2026-01-20 10:01:00",
                                "sender": "Alex",
                            }
                        ],
                    }
                ],
            }
        }
        run_dws = Mock(return_value=page)

        with tempfile.TemporaryDirectory() as tmp:
            result = monthly_export.export_monthly_chats(
                "2026-01-01T00:00:00+08:00",
                "2026-01-31T23:59:59+08:00",
                output_dir=tmp,
                run_dws_func=run_dws,
                sleep_seconds=0,
            )

            args = run_dws.call_args.args[0]
            self.assertEqual(["chat", "message", "list-all"], args[:3])
            self.assertIn("--start", args)
            self.assertIn("--end", args)
            self.assertIn("--cursor", args)

            month_dir = Path(tmp) / "2026-01"
            self.assertTrue((month_dir / "messages.jsonl").exists())
            self.assertTrue((month_dir / "monthly-analysis.md").exists())
            self.assertFalse((Path(tmp) / "data").exists())
            raw_line = json.loads((month_dir / "messages.jsonl").read_text().strip())
            self.assertEqual("推进 README 发布计划", raw_line["content"])
            self.assertEqual(1, result["months"][0]["message_count"])
            self.assertEqual(1, len(result["messages"]))

    def test_monthly_analysis_contains_core_work_progress_and_behavior_sections(self):
        messages = [
            ChatMessage("完成 Demo 卡片并推进 README", "2026-02-03 11:00:00", "c1", "产品发布", False, "Alex"),
            ChatMessage("同步用户反馈和下一步计划", "2026-02-04 15:00:00", "c2", "用户访谈", True, "Alex"),
        ]

        text = monthly_export.build_monthly_analysis_markdown(
            month="2026-02",
            messages=messages,
            metadata={
                "pages": 1,
                "possibly_truncated": False,
                "window_start": "2026-02-01 00:00:00",
                "window_end": "2026-02-28 23:59:59",
            },
        )

        self.assertIn("重点工作", text)
        self.assertIn("进展", text)
        self.assertIn("用户行为特性", text)
        self.assertIn("message_count: 2", text)
        self.assertIn("active_hours", text)
        self.assertIn("top_keywords", text)
        self.assertIn("collaborators", text)

    def test_export_marks_month_possibly_truncated_when_page_cap_hits(self):
        page = {
            "result": {
                "hasMore": True,
                "nextCursor": "next-1",
                "conversationMessagesList": [
                    {
                        "openConversationId": "cid-1",
                        "title": "Busy Room",
                        "messages": [
                            {"content": "继续推进", "createTime": "2026-03-01 09:00:00"}
                        ],
                    }
                ],
            }
        }

        with tempfile.TemporaryDirectory() as tmp:
            result = monthly_export.export_monthly_chats(
                "2026-03-01T00:00:00+08:00",
                "2026-03-31T23:59:59+08:00",
                output_dir=tmp,
                max_pages_per_month=1,
                run_dws_func=Mock(return_value=page),
                sleep_seconds=0,
            )

        self.assertTrue(result["months"][0]["possibly_truncated"])
        self.assertEqual("next-1", result["months"][0]["next_cursor"])

    def test_export_summary_omits_raw_messages_for_json_output(self):
        summary = monthly_export.summarize_export_result({
            "output_dir": "/tmp/monthly",
            "manifest_path": "/tmp/monthly/manifest.json",
            "months": [{"month": "2026-04", "message_count": 1}],
            "messages": [
                ChatMessage("raw content", "2026-04-01 09:00:00", "c1", "Room", False, "Alex")
            ],
        })

        json.dumps(summary, ensure_ascii=False)
        self.assertNotIn("messages", summary)
        self.assertEqual(1, summary["message_count"])

    def test_monthly_export_rejects_skill_data_directory(self):
        with self.assertRaisesRegex(ValueError, "skill data"):
            monthly_export.export_monthly_chats(
                "2026-05-01T00:00:00+08:00",
                "2026-05-01T23:59:59+08:00",
                output_dir=str(ROOT / "data"),
                run_dws_func=Mock(),
                sleep_seconds=0,
            )

    def test_docs_describe_monthly_export_flow(self):
        readme = (ROOT / "README.md").read_text()
        skill = (ROOT / "SKILL.md").read_text()

        self.assertIn("--monthly-export", readme)
        self.assertIn("按月份", readme)
        self.assertIn("dws chat message list-all", skill)
        self.assertIn("monthly-analysis.md", skill)


if __name__ == "__main__":
    unittest.main()
