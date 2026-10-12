# PlanEat Frontend

Streamlit 기반 챗봇 UI

## 준비
```powershell
uv sync
```

## 실행
```powershell
uv run streamlit run streamlit_app.py
```

## 실행 (프로토타입)
```powershell
uv run streamlit run streamlit_app_proto.py
```

## 접속 비밀번호

프로젝트 루트의 `.env` 파일에 아래와 같이 설정할 수 있습니다.

```dotenv
APP_PASSWORD="원하는 비밀번호"
```

설정을 추가하거나 변경한 뒤에는 Streamlit 서버를 재시작하세요.
Streamlit secrets에 `APP_PASSWORD = "원하는 비밀번호"`를 설정하거나,
실행 전에 PowerShell에서 환경 변수로 지정합니다.

```powershell
$env:APP_PASSWORD = "원하는 비밀번호"
uv run streamlit run streamlit_app.py
```

설정하면 기본 페이지와 프로토타입 모두 비밀번호 인증 후 이용할 수 있습니다.
인증은 세션 동안 유지되며, 비밀번호를 설정하지 않으면 바로 진입합니다.
설정 우선순위는 secrets → 기존 환경 변수 → `.env`입니다.

## 채팅 스트리밍

`streamlit_app.py`는 `/chat` 요청에 `Accept: text/event-stream` 헤더를 보내고,
`common.py`의 `httpx.stream()`으로 SSE 응답을 읽습니다.

- `start`, `progress`: 서버의 요청 수락 및 처리 진행 이벤트입니다.
- `delta`: `data.text`를 `st.write_stream()`으로 순서대로 표시합니다.
- `complete`: `data.payload`의 최종 JSON으로 대화 기록과 재료·추천·PDF 상태를 갱신합니다.
- `error`: `data.payload.response`에 담긴 서버 오류 문구를 표시합니다.
- `done`: 종료 이벤트입니다. 최종 결과 없이 종료되면 미완료 응답으로 처리합니다.

첫 텍스트를 기다리는 동안 채팅 영역에 “답변을 준비하고 있어요…” 로딩 애니메이션과
경과 시간을 표시합니다. 첫 텍스트가 도착하거나 오류가 발생하면 로딩을 종료합니다.
서버가 기존 `application/json` 응답을 반환하는 경우도 지원합니다.

## 전체 테스트

프로젝트 루트에서 `tests` 폴더의 모든 테스트를 일괄 실행합니다.

```powershell
uv run python -m unittest discover -s tests -v
```

각 테스트 결과가 표시되며, 마지막에 `OK`가 출력되면 전체 통과입니다.

## 스트리밍 테스트

`tests/test_chat_stream.py`는 실제 백엔드 대신 모의 HTTP/SSE 응답을 사용해
`common.py`의 스트리밍 처리를 검사합니다. 백엔드 실행이나 외부 API 호출은 필요하지 않습니다.

프로젝트 루트(`C:\PlanEat\FrontEnd`)에서 실행합니다.

```powershell
uv run python -m unittest discover -s tests -p "test_chat_stream.py" -v
```

다음 동작을 확인합니다.

- 텍스트 조각 수신과 여러 `data` 줄로 구성된 SSE 이벤트 파싱
- `complete.payload`의 최종 결과 저장 및 텍스트 조각 없는 최종 응답 처리
- 서버 오류, 잘못된 데이터, 최종 결과 없는 스트림 종료 감지
- 기존 JSON API 호출과 JSON 응답 호환성
- 정상 완료 또는 오류 발생 시 스트림 정리

성공하면 각 테스트에 `ok`가 표시되고 마지막에 `OK`가 출력됩니다.

```text
Ran 12 tests in ...

OK
```

### 실제 화면 확인

자동 테스트는 실제 백엔드 연결이나 Streamlit 화면을 검증하지 않습니다.
백엔드와 Streamlit 앱을 실행한 뒤 다음 항목을 직접 확인합니다.

1. 메시지를 보내고 응답이 지연될 때 채팅 영역의 로딩 애니메이션과 경과 시간이 보이는지 확인합니다.
2. 첫 텍스트가 도착하면 로딩이 사라지고 답변이 이어서 표시되는지 확인합니다.
3. 응답 완료 후 재료 확인 또는 추천 화면이 갱신되고, 다음 메시지를 보내도 이전 답변이 유지되는지 확인합니다.
4. 백엔드를 중지한 상태에서 메시지를 보내면 로딩이 종료되고 오류 안내가 표시되는지 확인합니다.
