"""화면 여러 곳에서 같이 쓰는 설정과 백엔드 호출 함수.

오류 메시지를 여기 한 곳에서만 만든다. 화면마다 제각각 문구를 쓰면
같은 상황인데 다르게 보이고, 나중에 고칠 때 빠뜨리는 곳이 생긴다.
"""

import os
import hmac
import json
from pathlib import Path
from dotenv import load_dotenv
import httpx
import streamlit as st

# 실행 디렉터리와 관계없이 프로젝트 루트의 .env를 읽는다.
# 이미 지정된 환경 변수는 덮어쓰지 않는다.
load_dotenv(Path(__file__).resolve().parent / ".env", override=False)

def setting(name, default=None):
    """Streamlit secrets를 우선하고, 없으면 환경 변수를 읽는다."""
    try:
        value = st.secrets.get(name)
    except FileNotFoundError:
        value = None
    return value or os.environ.get(name, default)

BACKEND_URL = setting("BACKEND_URL", "http://127.0.0.1:8000")
APP_PASSWORD = setting("APP_PASSWORD")


def require_auth():
    """페이지를 실행할 때마다 현재 세션의 접속 인증을 확인한다."""
    if APP_PASSWORD and not st.session_state.get("authed"):
        st.markdown("""
        <style>
        .stApp { background: radial-gradient(ellipse at top, #eaf1e4, #fafbf8 65%); }
        [data-testid="stMainBlockContainer"] {
            width: 100%; max-width: 640px; box-sizing: border-box;
            padding: clamp(3rem, 12vh, 8rem) 24px 3rem;
        }
        .auth-brand { text-align: center; color: #355d40; font-size: 24px;
            font-weight: 800; letter-spacing: -1px; margin-bottom: 28px; }
        [data-testid="stForm"] { background: #fff; border: 1px solid #e0e8da;
            border-radius: 24px; padding: 32px;
            box-shadow: 0 16px 48px #2c503610; }
        .auth-icon { display: flex; align-items: center; justify-content: center;
            width: 56px; height: 56px; border-radius: 18px; background: #eef3e8;
            font-size: 28px; margin-bottom: 20px; }
        .auth-title { color: #243d2c; font-size: 27px; font-weight: 750;
            letter-spacing: -1px; margin: 0 0 10px; line-height: 1.35;
            word-break: keep-all; overflow-wrap: break-word; }
        .auth-description { color: #6b7866; font-size: 14px; line-height: 1.8;
            margin: 0 0 20px; word-break: keep-all; }
        [data-testid="stTextInput"] label { color: #344730; }
        [data-testid="stTextInputRootElement"] { background: #fafbf8;
            color: #243d2c; border-radius: 12px; }
        [data-testid="stTextInputRootElement"]:focus-within {
            border-color: #355d40; box-shadow: 0 0 0 3px #355d4015; }
        [data-testid="stFormSubmitButton"] button {
            min-height: 48px; border-radius: 12px; background: #355d40;
            border: 1px solid #355d40; color: white; font-weight: 600; }
        [data-testid="stFormSubmitButton"] button:hover {
            background: #294b32; border-color: #294b32; color: white; }
        [data-testid="stFormSubmitButton"] button:focus-visible {
            outline: 3px solid #92b581; outline-offset: 3px; }
        .auth-footer { text-align: center; color: #74806e; font-size: 12px;
            margin-top: 18px; }
        @media (max-width: 480px) {
            [data-testid="stMainBlockContainer"] { padding-left: 20px; padding-right: 20px; }
            [data-testid="stForm"] { padding: 24px; }
            .auth-title { font-size: 24px; }
        }
        </style>
        <div class="auth-brand">🥬 PlanEat</div>
        """, unsafe_allow_html=True)
        with st.form("access_password"):
            st.markdown("""
            <div class="auth-icon" aria-hidden="true">🌱</div>
            <h1 class="auth-title">오늘의 식단을 시작해 볼까요?</h1>
            <p class="auth-description">내 냉장고에서 시작하는 가벼운 식사 계획.<br>
            전달받은 비밀번호로 PlanEat에 입장해 주세요.</p>
            """, unsafe_allow_html=True)
            pw = st.text_input("접속 비밀번호", type="password", placeholder="비밀번호를 입력해 주세요")
            submitted = st.form_submit_button("PlanEat 시작하기", type="primary", use_container_width=True)
            if submitted:
                if pw and hmac.compare_digest(pw.encode("utf-8"), APP_PASSWORD.encode("utf-8")):
                    st.session_state.authed = True
                    st.rerun()
                st.error("비밀번호가 올바르지 않습니다." if pw else "비밀번호를 입력해 주세요.")
        st.markdown('<p class="auth-footer">인증 후 나만의 식단을 계획할 수 있어요.</p>', unsafe_allow_html=True)
        st.stop()

HTTP_TIMEOUT = 180

_HTTP_STATUS_GUIDANCE = {
    400: "요청 형식이 올바르지 않습니다. 입력 내용을 확인해 주세요.",
    401: "백엔드 인증에 실패했습니다. 서비스 설정을 확인해 주세요.",
    403: "이 요청을 처리할 권한이 없습니다.",
    404: "요청한 백엔드 API 주소를 찾을 수 없습니다. BACKEND_URL과 API 경로를 확인해 주세요.",
    408: "서버가 요청을 제때 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.",
    413: "첨부한 데이터가 너무 큽니다. 사진 용량이나 개수를 줄여 주세요.",
    422: "입력값을 처리할 수 없습니다. 누락되거나 잘못된 항목을 확인해 주세요.",
    429: "요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.",
    500: "백엔드에서 처리 중 오류가 발생했습니다. Render 로그를 확인해 주세요.",
    502: "백엔드 서비스가 응답하지 않습니다. Render 배포·재시작 상태를 확인한 뒤 다시 시도해 주세요.",
    503: "백엔드 서비스가 일시적으로 사용할 수 없습니다. 잠시 후 다시 시도해 주세요.",
    504: "백엔드 응답 시간이 초과되었습니다. 잠시 후 다시 시도해 주세요.",
}

class ApiError(Exception):
    """화면에 그대로 보여줄 수 있는 오류 메시지를 담는다.

    httpx 가 던지는 예외 이름(ConnectError 등)이 아니라 무엇을 하면 되는지가 담긴 문장으로 바꿔서 돌려준다.
    """


def _format_error_detail(value) -> str | None:
    """백엔드가 공개한 안전한 오류 문구를 화면용 텍스트로 정리한다."""

    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, dict):
        for key in ("response", "detail", "message", "error"):
            detail = _format_error_detail(value.get(key))
            if detail:
                return detail
        return None
    if isinstance(value, list):
        messages: list[str] = []
        for item in value[:3]:
            if isinstance(item, dict):
                message = item.get("msg") or item.get("message")
                location = item.get("loc")
                if isinstance(message, str):
                    field = ".".join(str(part) for part in location) if isinstance(location, list) else "입력값"
                    messages.append(f"{field}: {message}")
                    continue
            detail = _format_error_detail(item)
            if detail:
                messages.append(detail)
        return " / ".join(messages) or None
    return None


def _api_error_from_response(response: httpx.Response) -> ApiError:
    """HTTP 상태 코드와 JSON 오류 본문을 함께 사용자에게 전달한다."""

    detail = None
    try:
        detail = _format_error_detail(response.json())
    except (ValueError, json.JSONDecodeError):
        # HTML 오류 페이지는 그대로 노출하지 않는다. 오류 코드별 안내가 더 안전하고 유용하다.
        pass

    status_code = response.status_code
    message = detail or _HTTP_STATUS_GUIDANCE.get(
        status_code,
        "서버 요청 처리에 실패했습니다. 잠시 후 다시 시도해 주세요.",
    )
    return ApiError(f"{message} (상태 코드 {status_code})")

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
        raise _api_error_from_response(res)

    return res.json() if res.content else None


def api_stream(method: str, path: str, **kwargs):
    """SSE의 빈 줄 경계와 여러 data 줄을 처리하며 연결을 유지한다."""
    try:
        with httpx.stream(
            method, f"{BACKEND_URL}{path}", timeout=HTTP_TIMEOUT, **kwargs
        ) as res:
            if res.status_code >= 400:
                # raise_for_status()만 호출하면 4xx/5xx 본문을 버려 백엔드의 구체적인
                # 오류 메시지를 화면에 보여줄 수 없다.
                res.read()
                raise _api_error_from_response(res)
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
    except httpx.ConnectError as exc:
        raise ApiError(
            "백엔드 서버에 연결할 수 없습니다. Render 서비스 주소와 배포 상태를 확인해 주세요."
        ) from exc
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
