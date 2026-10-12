"""Run with: python -m unittest discover -s tests"""
import importlib.util
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

import httpx


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("stream_common", ROOT / "common.py")
common = importlib.util.module_from_spec(spec)
with patch.dict(sys.modules, {"streamlit": types.SimpleNamespace(secrets={})}):
    spec.loader.exec_module(common)


class ChatStreamTests(unittest.TestCase):
    result = {"status": "SUCCESS", "step": "COMPLETED", "response": "안녕!"}

    def consume(self, body, content_type="text/event-stream", status=200):
        response = httpx.Response(
            status, text=body, headers={"Content-Type": content_type},
            request=httpx.Request("POST", "http://test/chat"),
        )
        result = {}
        with patch.object(common.httpx, "stream") as request:
            request.return_value.__enter__.return_value = response
            events = common.api("POST", "/chat", accept="text/event-stream", json={})
            chunks = list(common.chat_chunks(events, result))
            self.assertEqual(request.call_args.kwargs["headers"]["Accept"], "text/event-stream")
            request.return_value.__exit__.assert_called_once()
        return chunks, result

    def test_delta_and_multiline_result(self):
        body = ': heartbeat\r\n\r\nevent: delta\r\ndata: {"text":"안녕"}\r\n\r\n'
        body += 'event: delta\ndata: {"text":"!"}\n\n'
        body += 'event: result\n' + ''.join(
            f'data: {line}\n' for line in json.dumps(self.result, indent=2).splitlines()
        ) + '\n'
        chunks, result = self.consume(body)
        self.assertEqual(chunks, ["안녕", "!"])
        self.assertEqual(result, self.result)

    def test_final_only_sse(self):
        self.assertEqual(self.consume(f'data: {json.dumps(self.result)}\n\n'),
                         (["안녕!"], self.result))

    def test_backend_complete_payload(self):
        payload = {**self.result, "data": {"recipe_sets": []}, "next_action": "FEEDBACK_OR_SET_SELECTION"}
        events = [
            ("start", {"phase": "accepted"}),
            ("progress", {"phase": "processing"}),
            ("delta", {"index": 0, "text": "안녕"}),
            ("delta", {"index": 1, "text": "!"}),
            ("complete", {"http_status": 200, "payload": payload}),
            ("done", {"reason": "complete"}),
        ]
        body = ''.join(f'event: {event}\ndata: {json.dumps(data)}\n\n' for event, data in events)
        self.assertEqual(self.consume(body), (["안녕", "!"], payload))

    def test_backend_complete_without_delta(self):
        data = {"http_status": 200, "payload": self.result}
        self.assertEqual(self.consume(f'event: complete\ndata: {json.dumps(data)}\n\n'),
                         (["안녕!"], self.result))

    def test_backend_error_payload(self):
        data = {"http_status": 500, "payload": {"status": "ERROR", "response": "서버 처리 실패"}}
        with self.assertRaisesRegex(common.ApiError, "서버 처리 실패"):
            self.consume(f'event: error\ndata: {json.dumps(data)}\n\n')

    def test_backend_done_without_complete_is_incomplete(self):
        with self.assertRaisesRegex(common.ApiError, "최종 결과"):
            self.consume('event: done\ndata: {"reason":"complete"}\n\n')

    def test_backend_malformed_complete(self):
        with self.assertRaisesRegex(common.ApiError, "payload"):
            self.consume('event: complete\ndata: {"http_status":200}\n\n')

    def test_json_fallback(self):
        self.assertEqual(self.consume(json.dumps(self.result), "application/json"),
                         (["안녕!"], self.result))

    def test_bad_or_incomplete_streams(self):
        for body in ['data: invalid\n\n', 'data: [DONE]\n\n',
                     'event: delta\ndata: {"text":"partial"}\n\n',
                     'event: error\ndata: {"message":"failed"}\n\n',
                     'event: delta\ndata: {"text":42}\n\n']:
            with self.subTest(body=body), self.assertRaises(common.ApiError):
                self.consume(body)

    def test_http_error_shows_backend_detail(self):
        with self.assertRaisesRegex(common.ApiError, "재료 사진을 다시 올려 주세요"):
            self.consume(
                json.dumps({"detail": "재료 사진을 다시 올려 주세요"}),
                "application/json",
                status=422,
            )

    def test_gateway_error_shows_recovery_guidance(self):
        with self.assertRaisesRegex(common.ApiError, "Render 배포·재시작 상태"):
            self.consume("<html>Bad Gateway</html>", "text/html", status=502)

    def test_normal_api_still_returns_json(self):
        response = httpx.Response(200, json=self.result)
        with patch.object(common.httpx, "request", return_value=response):
            self.assertEqual(common.api("POST", "/chat", json={}), self.result)

    def test_adapter_closes_stream_on_error(self):
        closed = []
        def events():
            try:
                yield "error", {"message": "failed"}
            finally:
                closed.append(True)
        with self.assertRaises(common.ApiError):
            list(common.chat_chunks(events(), {}))
        self.assertEqual(closed, [True])


if __name__ == "__main__":
    unittest.main()
