"""추천이 생성된 답변 뒤에 남는지 실제 앱 rerun으로 검증한다."""
from pathlib import Path
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[1]


class RecommendationHistoryTests(unittest.TestCase):
    def setUp(self):
        password = patch("common.APP_PASSWORD", None)
        password.start()
        self.addCleanup(password.stop)

    def test_ingredient_cards_keep_snapshots_and_position(self):
        app = AppTest.from_file(str(ROOT / "streamlit_app.py"))

        def send(text, result):
            with patch("streamlit.chat_input", side_effect=[text, None]), patch(
                "common.api", return_value=(event for event in [("result", result)])
            ):
                app.run()
            self.assertFalse(app.exception)

        ingredients = [{"name": "당근", "amount": "1개"}]
        send("재료 확인", {"status": "NEED_MORE_INFO", "step": "INGREDIENT_CONFIRM",
                         "response": "첫 재료 답변", "ingredients": ingredients})
        ingredients[0]["amount"] = "2개"
        send("재료 수정", {"status": "NEED_MORE_INFO", "step": "INGREDIENT_CONFIRM",
                         "response": "수정 답변", "ingredients": ingredients})
        send("재료 모두 삭제", {"status": "NEED_MORE_INFO", "step": "INGREDIENT_CONFIRM",
                            "response": "빈 재료 답변", "ingredients": []})
        send("추천해 줘", {"status": "SUCCESS", "step": "COMPLETED",
                           "response": "추천 답변", "data": {"recipe_sets": []}})
        with patch("streamlit.chat_input", return_value=None):
            app.run()
        self.assertFalse(app.exception)
        values = [getattr(item, "value", None) for item in app.main]
        expected = ["첫 재료 답변", '<span class="chip">당근</span>',
                    "재료 수정", "수정 답변", '<span class="chip">당근</span>',
                    "재료 모두 삭제", "빈 재료 답변", "**냉장고 재료 0개**",
                    "추천해 줘", "추천 답변"]
        positions = [values.index(value) for value in expected]
        self.assertEqual(positions, sorted(positions))
        self.assertEqual([item.value for item in app.markdown].count("**냉장고 재료 1개**"), 2)
        self.assertEqual([item.value for item in app.markdown].count("**냉장고 재료 0개**"), 1)

    def test_recommendations_keep_position_and_original_data(self):
        app = AppTest.from_file(str(ROOT / "streamlit_app.py"))

        def send(text, result):
            with patch("streamlit.chat_input", side_effect=[text, None]), patch(
                "common.api", return_value=(event for event in [("result", result)])
            ):
                app.run()
            self.assertFalse(app.exception)

        data = {"recipe_sets": [{"set_id": "첫 추천", "recipes": []}]}
        send("추천해 줘", {"status": "SUCCESS", "step": "COMPLETED",
                           "response": "첫 답변", "data": data})
        data["recipe_sets"][0]["set_id"] = "변경된 원본"
        send("재료 수정", {"status": "NEED_MORE_INFO", "step": "INGREDIENT_CONFIRM",
                         "response": "재료 확인", "ingredients": []})
        self.assertIn("첫 추천", [item.value for item in app.subheader])
        send("다시 추천", {"status": "SUCCESS", "step": "COMPLETED",
                          "response": "둘째 답변", "data": {
                              "recipe_sets": [{"set_id": "둘째 추천", "recipes": []}]}})
        # 화면의 실제 출력 순서를 검사한다.
        values = [getattr(item, "value", None) for item in app.main]
        expected = ["첫 답변", "첫 추천", "재료 수정", "재료 확인",
                    "다시 추천", "둘째 답변"]
        positions = [values.index(value) for value in expected]
        self.assertEqual(positions, sorted(positions))
        with patch("streamlit.chat_input", return_value=None):
            app.run()
        self.assertFalse(app.exception)
        self.assertEqual([item.value for item in app.subheader].count("첫 추천"), 1)
        self.assertEqual([item.value for item in app.subheader].count("둘째 추천"), 1)
        self.assertEqual(sum("recommendation_data" in msg for msg in app.session_state["messages"]), 2)
        # 새 대화에서는 다시 최초 추천을 표시할 수 있다.
        app.button[0].click()
        with patch("streamlit.chat_input", return_value=None):
            app.run()
        send("새 추천", {"status": "SUCCESS", "step": "COMPLETED",
                        "response": "새 답변", "data": {
                            "recipe_sets": [{"set_id": "새 추천 세트", "recipes": []}]}})
        self.assertIn("새 추천 세트", [item.value for item in app.subheader])
        self.assertNotIn("첫 추천", [item.value for item in app.subheader])

    def test_pdf_ready_response_does_not_repeat_recommendations(self):
        app = AppTest.from_file(str(ROOT / "streamlit_app.py"))

        def send(text, result):
            with patch("streamlit.chat_input", side_effect=[text, None]), patch(
                "common.api", return_value=(event for event in [("result", result)])
            ):
                app.run()
            self.assertFalse(app.exception)

        data = {"recipe_sets": [{"set_id": "첫 추천", "recipes": []}]}
        send("추천해 줘", {"status": "SUCCESS", "step": "COMPLETED",
                           "response": "추천 답변", "data": data,
                           "next_action": "FEEDBACK_OR_SET_SELECTION"})
        send("첫번째 세트", {"status": "SUCCESS", "step": "COMPLETED",
                            "response": "상세 PDF를 생성했습니다.", "data": data,
                            "next_action": "PDF_READY"})

        self.assertEqual([item.value for item in app.subheader].count("첫 추천"), 1)
        self.assertEqual(
            sum("recommendation_data" in msg for msg in app.session_state["messages"]),
            1,
        )

    def test_duplicate_completion_message_does_not_repeat_recommendations(self):
        app = AppTest.from_file(str(ROOT / "streamlit_app.py"))

        def send(text, result):
            with patch("streamlit.chat_input", side_effect=[text, None]), patch(
                "common.api", return_value=(event for event in [("result", result)])
            ):
                app.run()
            self.assertFalse(app.exception)

        data = {"recipe_sets": [{"set_id": "첫 추천", "recipes": []}]}
        result = {
            "status": "SUCCESS",
            "step": "COMPLETED",
            "response": "확정한 재료와 조건에 맞는 메인·반찬 식단을 추천했습니다.",
            "data": data,
            "next_action": "FEEDBACK_OR_SET_SELECTION",
        }
        send("추천해 줘", result)
        send("다시 보여줘", result)

        self.assertEqual([item.value for item in app.subheader].count("첫 추천"), 1)
        self.assertEqual(
            sum("recommendation_data" in msg for msg in app.session_state["messages"]),
            1,
        )


if __name__ == "__main__":
    unittest.main()
