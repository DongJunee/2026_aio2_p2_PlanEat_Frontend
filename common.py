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

def api(method: str, path: str, **kwargs):
    """백엔드를 호출하고 JSON 을 돌려준다. 실패하면 ApiError 를 던진다."""
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
