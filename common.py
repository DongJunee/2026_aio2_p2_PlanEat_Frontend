"""화면 여러 곳에서 같이 쓰는 설정과 백엔드 호출 함수.

오류 메시지를 여기 한 곳에서만 만든다. 화면마다 제각각 문구를 쓰면
같은 상황인데 다르게 보이고, 나중에 고칠 때 빠뜨리는 곳이 생긴다.
"""

import os
import json
import httpx
import streamlit as st

try:
    _backend_url_secret = st.secrets.get("BACKEND_URL")
except Exception:
    _backend_url_secret = None

BACKEND_URL = _backend_url_secret or os.environ.get(
    "BACKEND_URL", "http://127.0.0.1:8000"
)

HTTP_TIMEOUT = 60

class ApiError(Exception):
    """화면에 그대로 보여줄 수 있는 오류 메시지를 담는다.

    httpx 가 던지는 예외 이름(ConnectError 등)이 아니라 무엇을 하면 되는지가 담긴 문장으로 바꿔서 돌려준다.
    """

def api(method: str, path: str, *, accept=None, **kwargs):
    """JSON 또는 (event, data) SSE iterator를 반환한다."""
    if accept is not None:
        headers = httpx.Headers(kwargs.pop("headers", None))
        headers["Accept"] = accept
        kwargs["headers"] = headers
    if accept == "text/event-stream":
        return api_stream(method, path, **kwargs)
    try:
        res = httpx.request(
                method, f"{BACKEND_URL}{path}", timeout=HTTP_TIMEOUT, **kwargs
            )
    except httpx.ConnectError:
        raise ApiError(
            "백엔드 서버에 연결할 수 없습니다."
            "backend 폴더에서 `uv run uvicorn app.main:app --reload` 가 떠 있는지 확인하세요."
        )
    except httpx.TimeoutException:
        raise ApiError(
            "서버가 제때 응답하지 않았습니다. 잠시 후 다시 시도하세요."
        )

    if res.status_code >= 400:
        # FastAPI가 계약 오류의 원인을 JSON으로 내려주므로, 사용자가 다음 행동을
        # 알 수 있도록 안전한 서버 메시지만 보여준다.
        try:
            detail = res.json().get("response")
        except (ValueError, AttributeError):
            detail = None
        if isinstance(detail, str) and detail.strip():
            raise ApiError(detail.strip())
        raise ApiError(f"요청이 실패했습니다 (상태 코드 {res.status_code}).")

    return res.json() if res.content else None


def api_stream(method: str, path: str, **kwargs):
    """SSE의 빈 줄 경계와 여러 data 줄을 처리하며 연결을 유지한다."""
    try:
        with httpx.stream(
            method, f"{BACKEND_URL}{path}", timeout=HTTP_TIMEOUT, **kwargs
        ) as res:
            res.raise_for_status()
            content_type = res.headers.get("content-type", "").split(";", 1)[0].strip()
            if content_type == "application/json":
                # SSE 협상이 적용되지 않은 서버의 기존 JSON 응답도 지원한다.
                res.read()
                yield "result", res.json()
                return
            if content_type != "text/event-stream":
                raise ApiError("서버가 지원하지 않는 응답 형식을 반환했습니다.")
            res.encoding = "utf-8"
            event, data_lines = "message", []
            for line in res.iter_lines():
                if not line:
                    if data_lines:
                        data = "\n".join(data_lines)
                        if data == "[DONE]":
                            return
                        yield event, json.loads(data)
                    event, data_lines = "message", []
                elif not line.startswith(":"):
                    field, _, value = line.partition(":")
                    if value.startswith(" "):
                        value = value[1:]
                    if field == "event":
                        event = value or "message"
                    elif field == "data":
                        data_lines.append(value)
    except httpx.HTTPStatusError as exc:
        raise ApiError(f"요청이 실패했습니다 (상태 코드 {exc.response.status_code}).") from exc
    except httpx.TimeoutException as exc:
        raise ApiError("응답 수신 시간이 초과되었습니다. 다시 시도해 주세요.") from exc
    except httpx.HTTPError as exc:
        raise ApiError("서버와 통신 중 연결 오류가 발생했습니다.") from exc
    except ValueError as exc:
        raise ApiError("서버 응답이 올바른 JSON이 아닙니다.") from exc


def chat_chunks(events, result):
    """delta.text를 출력하고 complete.payload의 ChatResponse를 저장한다."""
    has_text = False
    try:
        for event, data in events:
            if not isinstance(data, dict):
                raise ApiError("채팅 이벤트 데이터는 JSON 객체여야 합니다.")
            if event in {"start", "progress"}:
                continue
            if event == "done":
                break
            if event in {"complete", "error"}:
                payload = data.get("payload")
                if isinstance(payload, dict):
                    data = payload
                elif event == "complete":
                    raise ApiError("채팅 complete 이벤트에 최종 payload가 없습니다.")
            if event == "error" or data.get("status") == "ERROR":
                raise ApiError(str(data.get("response") or data.get("message") or "응답 생성에 실패했습니다."))
            if event in {"complete", "result"} or ("status" in data and "step" in data):
                if not all(key in data for key in ("status", "step", "response")):
                    raise ApiError("채팅 최종 결과에 필수 항목이 없습니다.")
                if not isinstance(data["response"], str):
                    raise ApiError("채팅 응답 텍스트 형식이 올바르지 않습니다.")
                result.update(data)
                if not has_text and data["response"]:
                    yield data["response"]
                return
            if event == "delta":
                chunk = data.get("text")
                if not isinstance(chunk, str):
                    raise ApiError("채팅 delta 이벤트의 text가 문자열이 아닙니다.")
                if chunk:
                    has_text = True
                    yield chunk
        raise ApiError("최종 결과를 받기 전에 응답이 종료되었습니다. 다시 시도해 주세요.")
    finally:
        events.close()
