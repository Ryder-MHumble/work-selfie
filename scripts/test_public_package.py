import importlib
import os
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_USER_PATH = "/Users/" + "rydersun"
FORBIDDEN_SAMPLE_MARKERS = ("Ryd" + "er 2026", "Ryd" + "er ·", "自查报告 · " + "Ryd" + "er")


class PublicPackageTest(unittest.TestCase):
    def test_package_does_not_contain_user_specific_paths(self):
        checked_suffixes = {".md", ".py"}
        offenders = []
        for path in ROOT.rglob("*"):
            if ".git" in path.parts or not path.is_file():
                continue
            if path.suffix not in checked_suffixes:
                continue
            text = path.read_text(errors="ignore")
            if FORBIDDEN_USER_PATH in text or any(marker in text for marker in FORBIDDEN_SAMPLE_MARKERS):
                offenders.append(path.relative_to(ROOT).as_posix())

        self.assertEqual([], offenders)

    def test_dws_binary_can_be_overridden_by_environment(self):
        os.environ["WORKSELFIE_DWS_BIN"] = "/tmp/example-dws"
        try:
            import collect_self
            import send_report

            importlib.reload(collect_self)
            importlib.reload(send_report)

            self.assertEqual("/tmp/example-dws", collect_self.DWS_BIN)
            self.assertEqual("/tmp/example-dws", send_report.DWS_BIN)
        finally:
            os.environ.pop("WORKSELFIE_DWS_BIN", None)


if __name__ == "__main__":
    unittest.main()
