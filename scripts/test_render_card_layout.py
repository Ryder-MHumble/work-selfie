import re
import unittest

import render_card


def _css_block(selector: str) -> str:
    match = re.search(
        rf"{re.escape(selector)}\s*\{{(?P<body>.*?)\n  \}}",
        render_card.TEMPLATE_4X5,
        flags=re.S,
    )
    assert match, f"missing CSS block for {selector}"
    return match.group("body")


def _base_expression(**overrides):
    data = {
        "length_stats": {"mean": 24, "p90": 48},
        "category": {
            "work_ratio": 0.18,
            "long_msg_ratio": 0.12,
            "single_char_ratio": 0.06,
        },
        "emotion": {"positive": 0.1, "negative": 0.04, "neutral": 0.86},
        "punctuation_density": {"question": 0.02},
        "top_keywords": [],
    }
    data.update(overrides)
    return data


def _base_behavior(**overrides):
    data = {
        "group_vs_p2p": {"group": 0.4, "p2p": 0.6},
        "top_collaborators": [("A", 50), ("B", 20)],
        "active_hour_top3": [14, 10, 13],
        "late_night_ratio": 0.02,
        "weekend_ratio": 0.06,
    }
    data.update(overrides)
    return data


class FigureSelectionTest(unittest.TestCase):
    def test_deep_abstract_work_selects_orange_focus_figure(self):
        figure = render_card.select_figure(
            "架构师",
            _base_expression(
                length_stats={"mean": 96, "p90": 180},
                category={
                    "work_ratio": 0.62,
                    "long_msg_ratio": 0.46,
                    "single_char_ratio": 0.02,
                },
                top_keywords=[("体系", 8), ("架构", 6), ("系统", 5)],
            ),
            _base_behavior(),
        )

        self.assertEqual("toonhub-1.png", figure["image_name"])

    def test_positive_teaching_selects_green_energy_figure(self):
        figure = render_card.select_figure(
            "讲师",
            _base_expression(
                length_stats={"mean": 62, "p90": 120},
                category={
                    "work_ratio": 0.28,
                    "long_msg_ratio": 0.35,
                    "single_char_ratio": 0.01,
                },
                emotion={"positive": 0.42, "negative": 0.01, "neutral": 0.57},
            ),
            _base_behavior(),
        )

        self.assertEqual("toonhub-2.png", figure["image_name"])

    def test_stable_project_push_selects_pink_execution_figure(self):
        figure = render_card.select_figure(
            "指挥官",
            _base_expression(category={
                "work_ratio": 0.3,
                "long_msg_ratio": 0.16,
                "single_char_ratio": 0.04,
            }),
            _base_behavior(
                top_collaborators=[("核心协作", 900), ("B", 100)],
                late_night_ratio=0.01,
                weekend_ratio=0.01,
            ),
        )

        self.assertEqual("toonhub-3.png", figure["image_name"])

    def test_question_driven_short_response_selects_blue_scout_figure(self):
        figure = render_card.select_figure(
            "侦察兵",
            _base_expression(
                length_stats={"mean": 18, "p90": 32},
                category={
                    "work_ratio": 0.12,
                    "long_msg_ratio": 0.03,
                    "single_char_ratio": 0.32,
                },
                punctuation_density={"question": 0.32},
            ),
            _base_behavior(
                group_vs_p2p={"group": 0.75, "p2p": 0.25},
                late_night_ratio=0.14,
            ),
        )

        self.assertEqual("toonhub-4.png", figure["image_name"])


class RenderCardLayoutTest(unittest.TestCase):
    def test_4x5_removes_collaboration_top5_module(self):
        self.assertNotIn("协作 Top 5", render_card.TEMPLATE_4X5)
        self.assertNotIn("collab-section", render_card.TEMPLATE_4X5)

    def test_4x5_css_canvas_matches_png_canvas(self):
        self.assertIn("width: 720px; height: 900px;", render_card.TEMPLATE_4X5)

    def test_4x5_right_panel_moves_right_after_collab_removal(self):
        right_panel = _css_block(".right-panel")

        self.assertIn("left: 41%;", right_panel)
        self.assertIn("width: 59%;", right_panel)

    def test_4x5_left_side_uses_brutalist_collage_instead_of_large_black_block(self):
        sbti_side = _css_block(".sbti-side")

        self.assertNotIn("background: #0A0A0A", sbti_side)
        self.assertIn(".sbti-brutalist-collage", render_card.TEMPLATE_4X5)

    def test_left_side_evidence_does_not_repeat_collaboration(self):
        html = render_card.build_sbti_evidence_html({
            "behavior_patterns": {
                "top_collaborators": [("Demo Lead", 905)],
                "active_hour_top3": [14, 10, 13],
            },
            "expression_dna": {
                "category": {"work_ratio": 0.17, "single_char_ratio": 0.06},
            },
        })

        self.assertNotIn("协作", html)
        self.assertIn("高峰", html)

    def test_4x5_slogan_is_slim_bottom_strip(self):
        slogan = _css_block(".slogan")

        self.assertIn("position: absolute;", slogan)
        self.assertIn("bottom: 18px;", slogan)
        self.assertIn("height: 76px;", slogan)
        self.assertNotIn("height: 100%;", slogan)


if __name__ == "__main__":
    unittest.main()
