"""PlanEat UI """
import base64
import mimetypes
from contextlib import closing
from copy import deepcopy
from itertools import chain
from random import choice
from urllib.parse import urljoin
from uuid import uuid4
from html import escape
from io import BytesIO
import streamlit as st
from attachment_limits import MAX_SESSION_IMAGES, remaining_image_slots
import httpx
from PIL import Image, UnidentifiedImageError
from common import ApiError, BACKEND_URL, HTTP_TIMEOUT, api, chat_chunks, require_auth

LOADING_MESSAGES = (
    "셰프가 냉장고 안에서 재료들과 파티 중이에요.",
    "양파가 눈물 닦으며 메뉴 회의에 참석했어요.",
    "냉장고 속 달걀이 오늘의 주인공 자리를 노리고 있어요.",
    "파프리카가 알록달록한 의견을 내고 있어요.",
    "냄비가 벌써부터 보글보글 연습 중이에요.",
    "두부가 어떤 요리로 변신할지 고민하고 있어요.",
    "재료들이 서로 ‘나랑 잘 어울려!’ 하고 손들고 있어요.",
    "프라이팬이 오늘의 메뉴를 기다리며 몸을 풀고 있어요.",
    "장바구니가 재료를 출석체크 하고 있어요.",
    "셰프가 냉장고 탐험을 마치고 메뉴를 들고 오는 중이에요.",
)

st.set_page_config(page_title="PlanEat · 오늘의 식단", page_icon="🥬", layout="wide")
require_auth()
st.markdown('''<style>
/* 상단 Deploy 버튼 숨기기 */
.stAppDeployButton { display: none; }
.stApp{background:#fafbf8;}[data-testid="stSidebar"]{background:#f0f3eb;border-right:1px solid #e0e6d9;}
.block-container{max-width:1080px;padding-top:4.5rem;padding-bottom:5rem;}
h1,h2,h3{color:#243d2c;letter-spacing:-.045em;}h1{font-size:2.6rem!important;}
[data-testid="stChatMessage"]{background:transparent;}[data-testid="stChatInput"]{border-radius:22px;border-color:#cbd6c4;}
[data-testid="stBottom"]{background:#fafbf8;}div.stButton>button{border-radius:12px;min-height:42px;}
div.stButton>button[kind="primary"]{background:#355d40;border-color:#355d40;}
.brand{font-size:27px;font-weight:800;color:#2c5036;letter-spacing:-1px;}.muted{color:#74806e;font-size:13px;}
.eyebrow{color:#6c805f;font-size:12px;font-weight:700;letter-spacing:2px;margin:24px 0 12px;}
.hero{padding:24px 0 20px;}.hero p{color:#75806f;line-height:1.9;}
.chip{display:inline-block;background:#eef3e8;color:#4d6744;padding:5px 11px;border-radius:20px;font-size:12px;margin:3px;}
.food{font-size:42px;background:linear-gradient(120deg,#edf2e4,#f8f3e8);padding:20px;border-radius:13px;}
@media(max-width:640px){.block-container{padding-top:4.5rem;}h1{font-size:2rem!important;}}
</style>''', unsafe_allow_html=True)

for key,value in {"messages":[],"ingredients":[],"confirmed":False,"recommendations":False,"recommendation_data":{},"revision":0}.items():
    if key not in st.session_state: st.session_state[key]=value
s=st.session_state

def message(role,text,images=None,recommendation_data=None,ingredients=None):
    entry = {"role":role,"text":text,"images":images or []}
    if recommendation_data is not None:
        # 각 답변의 추천 결과를 보존하여 이후 추천으로 덮어쓰지 않는다.
        entry["recommendation_data"] = deepcopy(recommendation_data)
    if ingredients is not None:
        entry["ingredients"] = deepcopy(ingredients)
    s.messages.append(entry)


def image_data_url(filename: str, data: bytes) -> str:
    """백엔드 Vision API가 허용하는 이미지 Data URL을 만든다."""
    mime_type, _ = mimetypes.guess_type(filename)
    if mime_type not in {"image/jpeg", "image/png", "image/webp"}:
        # 업로드 허용 확장자와 일치하는 안전한 기본값이다.
        mime_type = "image/jpeg"
    encoded = base64.b64encode(data).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"

def render_recommendations(data):
    st.markdown('<div class="eyebrow">YOUR MEAL IDEAS</div>',unsafe_allow_html=True)
    st.subheader("오늘, 마음이 가는 식단을 골라보세요",anchor=False)
    recipe_sets = data.get("recipe_sets") or []
    if not recipe_sets:
        st.info("추천된 식단이 없습니다. 원하는 식단을 다시 요청해 주세요.")
    for set_index in range(0, len(recipe_sets), 2):
        for set_column, meal_set in zip(st.columns(2, gap="large"), recipe_sets[set_index:set_index + 2]):
            set_id = meal_set["set_id"]
            recipes = meal_set.get("recipes") or []
            with set_column.container(border=True):
                st.subheader(set_id, anchor=False)
                st.caption(f"레시피 {len(recipes)}개")
                for number, recipe in enumerate(recipes, start=1):
                    thumbnail, description = st.columns([1, 2], gap="medium", vertical_alignment="top")
                    with thumbnail:
                        if recipe.get("image"):
                            st.image(recipe["image"], caption=recipe["title"], width="stretch")
                        else:
                            st.markdown('<div class="food">🍽️</div>', unsafe_allow_html=True)
                    with description:
                        st.markdown(f"**{number}. {recipe['title']}(출처:{recipe.get('recipe_id', '정보 없음')})**")
                        st.caption(f"조리 시간: {recipe['cook_time']}분")
                        st.caption("보유 재료: " + (", ".join(recipe.get("owned_ingredients") or []) or "없음"))
                        st.caption("부족 재료: " + (", ".join(item["name"] for item in recipe.get("missing_ingredients") or []) or "추가 구매 없음"))

with st.sidebar:
    st.markdown('<div class="brand">🥬 PlanEat</div><div class="muted">내 냉장고에서 시작하는 식단</div>',unsafe_allow_html=True)
    st.write("")
    if st.button("＋ 새로운 대화",width="stretch"):
        s.clear()
        st.rerun()
    st.divider()
    st.caption("오늘의 식사 준비")
    for label,done in [("01  사진 올리기",bool(s.ingredients)),("02  재료 확인하기",s.confirmed),("03  식단 고르기",s.recommendations)]:
        st.write(("●  " if done else "○  ")+label)
st.markdown("**오늘의 식단**")
st.divider()
if not s.messages:
    st.markdown('<div class="hero"><div class="eyebrow">A LITTLE LESS WASTE, A BETTER MEAL</div><h1>냉장고에 있는 재료로,<br>오늘은 뭘 먹을까요?</h1><p>냉장고와 영수증 사진을 올려주세요.<br>재료를 함께 확인하고, 나에게 맞는 식단을 찾아봐요.</p></div>',unsafe_allow_html=True)
    for col,icon,title,desc in zip(st.columns(3),["📷","🥕","🍽️"],["사진으로 간편하게","재료는 꼼꼼하게","선택은 여유롭게"],["냉장고 · 영수증 사진 최대 5장","수량 수정부터 빠진 재료 추가까지","SET A · B, 각 5개 메뉴"]):
        with col,st.container(border=True):
            st.write(icon)
            st.markdown(f"**{title}**")
            st.caption(desc)
    st.write("")
for msg in s.messages:
    with st.chat_message(msg["role"],avatar="🥬" if msg["role"]=="assistant" else "🙂"):
        st.write(msg["text"])
        if msg["images"]:
            for col,img in zip(st.columns(len(msg["images"])),msg["images"]):
                # Data URL은 원본을 유지하고 표시 너비만 줄여 확대 시에도 선명하다.
                col.image(image_data_url(img["name"], img["data"]),caption=img["name"],width=160)
    if "recommendation_data" in msg:
        render_recommendations(msg["recommendation_data"])

    if "ingredients" in msg:
        with st.container(border=True):
            st.markdown(f"**냉장고 재료 {len(msg['ingredients'])}개**")
            st.markdown(''.join(f'<span class="chip">{escape(r["name"])} · {escape(r["amount"])}</span>' for r in msg["ingredients"]),unsafe_allow_html=True)

if not s.messages:
    st.caption("입력창의 ＋로 사진을 첨부하세요. 전송 전 미리보기에서 삭제할 수 있어요. 최대 5장 · JPG, PNG, WEBP · 장당 10MB")
remaining_images = remaining_image_slots(s.messages)
attachment_mode = "multiple" if remaining_images > 1 else bool(remaining_images)
prompt=st.chat_input("냉장고 사진을 올리거나, 원하는 식단을 이야기해 주세요",accept_file=attachment_mode,file_type=["jpg","jpeg","png","webp"],max_upload_size=5,key="composer")
if prompt:
    files=[] if isinstance(prompt, str) else list(prompt.files)
    text=(prompt if isinstance(prompt, str) else prompt.text).strip()
    if len(files) > remaining_images:
        st.error(f"대화당 사진은 최대 {MAX_SESSION_IMAGES}장까지 첨부할 수 있어요. 현재 추가 가능한 사진은 {remaining_images}장입니다. 사진 수를 줄여 다시 보내 주세요.")
    else:
        images=[]
        try:
            for file in files:
                data=file.getvalue()
                with Image.open(BytesIO(data)) as img: img.verify()
                images.append({"name":file.name,"data":data})
        except (UnidentifiedImageError,OSError,ValueError,Image.DecompressionBombError):
            st.error("읽을 수 없는 이미지가 있어요. JPG, PNG 또는 WEBP 사진을 다시 첨부해 주세요.")
        else:
            # 같은 대화에서는 동일한 session_id 유지
            if "session_id" not in s:
                s.session_id = str(uuid4())

            # ChatRequest.message는 빈 문자열을 허용하지 않는다. 사진만 첨부한
            # 경우에도 사진 분석 의도를 명시해 API 계약을 만족시킨다.
            request_message = text or "첨부한 냉장고 사진 속 재료를 확인해주세요."

            events = api(
                "POST",
                "/chat",
                accept="text/event-stream",
                json={
                    "session_id": s.session_id,
                    "message": request_message,
                    "attachments": [
                        {
                            "type": "image",
                            "data": image_data_url(image["name"], image["data"]),
                        }
                        for image in images
                    ],
                },
            )

            user_text = text or f"사진 {len(images)}장을 첨부했어요."
            message("user", user_text, images)
            with st.chat_message("user", avatar="🙂"):
                st.write(user_text)
                for img in images:
                    st.image(image_data_url(img["name"], img["data"]), caption=img["name"], width=160)

            result = {}
            chunks = []

            def response_chunks():
                stream = chat_chunks(events, result)
                try:
                    for chunk in stream:
                        chunks.append(chunk)
                        yield chunk
                finally:
                    stream.close()

            try:
                with st.chat_message("assistant", avatar="🥬"):
                    with closing(response_chunks()) as stream:
                        # 진행 이벤트만 오는 동안 표시하고 첫 텍스트 수신 시 숨긴다.
                        with st.spinner(choice(LOADING_MESSAGES), show_time=True):
                            first_chunk = next(stream, "")
                        streamed_text = st.write_stream(chain((first_chunk,), stream))
            except ApiError as exc:
                # 중단된 응답도 기록하여 다음 rerun에서 사라지지 않게 한다.
                failure_text = f"응답을 완료하지 못했습니다: {exc}"
                partial_text = "".join(chunks)
                message("assistant", f"{partial_text}\n\n{failure_text}".strip())
                st.error(failure_text)
            else:
                ingredients = None
                if (
                    result.get("status") == "NEED_MORE_INFO"
                    and result.get("step") == "INGREDIENT_CONFIRM"
                ):
                    s.ingredients = result.get("ingredients") or []
                    ingredients = s.ingredients
                    s.confirmed = False
                    s.recommendations = False
                    s.recommendation_data = {}
                    s.revision += 1
                elif (
                    result.get("status") == "SUCCESS"
                    and result.get("step") == "COMPLETED"
                ):
                    s.recommendation_data = result.get("data") or {}
                    s.recommendations = True
                    s.confirmed = True
                    s.revision += 1
                    if result.get("next_action") == "PDF_READY":
                        s.pending_pdf_url = result.get("pdf_url") or ""
                
                response_text = result.get("response") or streamed_text or ""
                questions = result.get("questions") or []
                if questions:
                    question_text = "\n".join(f"- {question}" for question in questions)
                    response_text = f"{response_text}\n\n{question_text}".strip()
                recommendation_data = None
                if (
                    result.get("status") == "SUCCESS"
                    and result.get("step") == "COMPLETED"
                    and "recipe_sets" in (result.get("data") or {})
                    # 최초 추천은 기록에 고정하고 후속 완료 응답에는 추가하지 않는다.
                    and not any("recommendation_data" in msg for msg in s.messages)
                ):
                    recommendation_data = result["data"]
                message("assistant", response_text, recommendation_data=recommendation_data,
                        ingredients=ingredients)
                s.last_result = result
                st.rerun()

if "pending_pdf_url" in s:
    pdf_url = s.pop("pending_pdf_url")
    if not pdf_url:
        st.error("PDF 다운로드 주소가 응답에 없습니다.")
    else:
        try:
            pdf_response = httpx.get(
                urljoin(BACKEND_URL.rstrip("/") + "/", pdf_url),
                timeout=HTTP_TIMEOUT,
                follow_redirects=True,
            )
            pdf_response.raise_for_status()
            if not pdf_response.content.startswith(b"%PDF-"):
                raise ValueError("PDF가 아닌 응답")
        except (httpx.HTTPError, ValueError):
            st.error("PDF를 가져오지 못했습니다. 채팅으로 PDF를 다시 요청해 주세요.")
        else:
            # rerun 후 한 번만 실행하여 다른 입력으로 인한 중복 다운로드를 막는다.
            encoded_pdf = base64.b64encode(pdf_response.content).decode("ascii")
            st.html(f"""
                <script>
                (() => {{
                    const bytes = Uint8Array.from(atob("{encoded_pdf}"), c => c.charCodeAt(0));
                    const url = URL.createObjectURL(new Blob([bytes], {{type: "application/pdf"}}));
                    const link = document.createElement("a");
                    link.href = url;
                    link.download = "planeat-recipes.pdf";
                    document.body.appendChild(link);
                    link.click();
                    link.remove();
                    setTimeout(() => URL.revokeObjectURL(url), 60000);
                }})();
                </script>
            """, unsafe_allow_javascript=True)

# if "last_result" in s:
#     st.json(s.last_result) # 테스트용
