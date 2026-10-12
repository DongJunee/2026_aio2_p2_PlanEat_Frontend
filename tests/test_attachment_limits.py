"""세션 누적 첨부 제한과 실제 앱의 전송 차단을 검증한다."""
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PIL import Image
from streamlit.testing.v1 import AppTest

from attachment_limits import remaining_image_slots


ROOT = Path(__file__).resolve().parents[1]


class AttachmentLimitTests(unittest.TestCase):
    def setUp(self):
        password = patch("common.APP_PASSWORD", None)
        password.start()
        self.addCleanup(password.stop)
        data = BytesIO()
        Image.new("RGB", (1, 1)).save(data, format="PNG")
        self.image = {"name": "food.png", "data": data.getvalue()}

    def app(self, count):
        app = AppTest.from_file(str(ROOT / "streamlit_app.py"))
        app.session_state["messages"] = [
            {"role": "user", "text": "사진", "images": [self.image] * count}
        ]
        return app

    def prompt(self, count):
        return SimpleNamespace(text="재료 확인", files=[
            SimpleNamespace(name="food.png", getvalue=lambda: self.image["data"])
            for _ in range(count)
        ])

    def test_counts_images_across_messages_and_resets(self):
        messages = [{"role": "user", "images": [self.image] * 3},
                    {"role": "assistant", "images": []},
                    {"role": "user", "images": [self.image] * 2}]
        self.assertEqual(remaining_image_slots(messages), 0)
        self.assertEqual(remaining_image_slots([]), 5)

    def test_excess_attachments_never_reach_api_or_history(self):
        for existing, incoming in [(0, 6), (3, 3), (4, 2), (5, 1)]:
            with self.subTest(existing=existing, incoming=incoming):
                app = self.app(existing)
                with patch("streamlit.chat_input", return_value=self.prompt(incoming)), patch("common.api") as api:
                    app.run()
                self.assertFalse(app.exception)
                self.assertTrue(app.error)
                api.assert_not_called()
                self.assertEqual(len(app.session_state["messages"]), 1)

    def test_exact_limit_and_text_after_limit(self):
        for existing, prompt, expected in [(3, self.prompt(2), 2), (4, self.prompt(1), 1), (5, "계속 추천해 주세요", 0)]:
            with self.subTest(existing=existing):
                app = self.app(existing)
                def events():
                    yield "result", {"status": "NEED_MORE_INFO", "step": "INGREDIENT_CONFIRM", "response": "확인", "ingredients": []}
                with patch("streamlit.chat_input", side_effect=[prompt, None]), patch("common.api", return_value=events()) as api:
                    app.run()
                self.assertFalse(app.exception)
                self.assertEqual(len(api.call_args.kwargs["json"]["attachments"]), expected)
                self.assertEqual(remaining_image_slots(app.session_state["messages"]), 0)

    def test_full_session_disables_attachment_control(self):
        app = self.app(5)
        with patch("streamlit.chat_input", return_value=None) as composer:
            app.run()
        self.assertFalse(app.exception)
        self.assertIs(composer.call_args.kwargs["accept_file"], False)

    def test_four_images_only_allows_single_attachment_in_both_apps(self):
        for filename in ("streamlit_app.py", "streamlit_app_proto.py"):
            with self.subTest(filename=filename):
                app = AppTest.from_file(str(ROOT / filename))
                app.session_state["messages"] = [
                    {"role": "user", "text": "사진", "images": [self.image] * 4}
                ]
                with patch("streamlit.chat_input", return_value=None) as composer:
                    app.run()
                self.assertFalse(app.exception)
                self.assertIs(composer.call_args.kwargs["accept_file"], True)


if __name__ == "__main__":
    unittest.main()
