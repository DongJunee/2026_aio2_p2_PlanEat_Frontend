import unittest
import os
import runpy
import tempfile
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[1]


class AuthTests(unittest.TestCase):
    def test_dotenv_password_loaded_and_environment_takes_precedence(self):
        source = (ROOT / "common.py").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "common.py").write_text(source, encoding="utf-8")
            (root / ".env").write_text('APP_PASSWORD="dotenv-test"\n', encoding="utf-8")
            with patch.dict(os.environ, {}, clear=True), patch("streamlit.secrets", {}):
                config = runpy.run_path(str(root / "common.py"))
                self.assertEqual(config["APP_PASSWORD"], "dotenv-test")
                os.environ["APP_PASSWORD"] = "environment-test"
                config = runpy.run_path(str(root / "common.py"))
                self.assertEqual(config["APP_PASSWORD"], "environment-test")

    def test_pages_require_password_for_each_new_session(self):
        for page in ("streamlit_app.py", "streamlit_app_proto.py"):
            with self.subTest(page=page), patch("common.APP_PASSWORD", "접속-test"):
                app = AppTest.from_file(str(ROOT / page)).run()
                self.assertFalse(app.exception)
                self.assertEqual(app.text_input[0].label, "접속 비밀번호")
                self.assertEqual(len(app.chat_input), 0)

                app.button[0].click().run()
                self.assertEqual(app.error[0].value, "비밀번호를 입력해 주세요.")
                app.text_input[0].set_value("wrong")
                app.button[0].click().run()
                self.assertEqual(app.error[0].value, "비밀번호가 올바르지 않습니다.")
                self.assertEqual(len(app.chat_input), 0)

                app.text_input[0].set_value("접속-test")
                app.button[0].click().run()
                self.assertFalse(app.exception)
                self.assertTrue(app.session_state.authed)
                self.assertEqual(len(app.chat_input), 1)
                app.run()
                self.assertEqual(len(app.chat_input), 1)

                app.session_state.messages = [{"role": "user", "text": "이전 대화", "images": []}]
                next(button for button in app.button if button.label == "＋ 새로운 대화").click().run()
                self.assertFalse(app.exception)
                self.assertTrue(app.session_state.authed)
                self.assertEqual(app.session_state.messages, [])
                self.assertEqual(len(app.chat_input), 1)
                self.assertFalse(any(field.label == "접속 비밀번호" for field in app.text_input))

                fresh = AppTest.from_file(str(ROOT / page)).run()
                self.assertEqual(len(fresh.chat_input), 0)
                self.assertEqual(fresh.text_input[0].label, "접속 비밀번호")

    def test_unconfigured_password_allows_access(self):
        with patch("common.APP_PASSWORD", None):
            app = AppTest.from_file(str(ROOT / "streamlit_app.py")).run()
            self.assertFalse(app.exception)
            self.assertEqual(len(app.chat_input), 1)


if __name__ == "__main__":
    unittest.main()
