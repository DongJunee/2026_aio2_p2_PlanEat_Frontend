"""PlanEat UI """
import base64
import mimetypes
from uuid import uuid4
from html import escape
from io import BytesIO
import streamlit as st
from PIL import Image, UnidentifiedImageError
from common import ApiError, api

st.set_page_config(page_title="PlanEat · 오늘의 식단", page_icon="🥬", layout="wide")
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

for key,value in {"messages":[],"ingredients":[],"confirmed":False,"recommendations":False,"selected":None,"revision":0}.items():
    if key not in st.session_state: st.session_state[key]=value
s=st.session_state

def message(role,text,images=None):
    s.messages.append({"role":role,"text":text,"images":images or []})


def image_data_url(filename: str, data: bytes) -> str:
    """백엔드 Vision API가 허용하는 이미지 Data URL을 만든다."""
    mime_type, _ = mimetypes.guess_type(filename)
    if mime_type not in {"image/jpeg", "image/png", "image/webp"}:
        # 업로드 허용 확장자와 일치하는 안전한 기본값이다.
        mime_type = "image/jpeg"
    encoded = base64.b64encode(data).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"

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
                col.image(img["data"],caption=img["name"],width=160)
if not s.messages:
    st.caption("입력창의 ＋로 사진을 첨부하세요. 전송 전 미리보기에서 삭제할 수 있어요. 최대 5장 · JPG, PNG, WEBP · 장당 10MB")
prompt=st.chat_input("냉장고 사진을 올리거나, 원하는 식단을 이야기해 주세요",accept_file="multiple",file_type=["jpg","jpeg","png","webp"],max_upload_size=5,key="composer")
if prompt:
    files=list(prompt.files)
    text=prompt.text.strip() or ""
    if len(files)>5: st.error("한 번에 최대 5장까지 보낼 수 있어요. 사진을 5장 이하로 다시 선택해 주세요.")
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

            result = api(
                "POST",
                "/chat",
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

            if text or images:
                message("user", text or f"사진 {len(images)}장을 첨부했어요.", images)
                
            if result :
                response_text = result.get("response", "")
                questions = result.get("questions") or []
                if questions:
                    question_text = "\n".join(f"- {question}" for question in questions)
                    response_text = f"{response_text}\n\n{question_text}".strip()
                message("assistant", response_text)
                st.json(result)
                s.last_result = result
                st.rerun()

if "last_result" in s:
    st.json(s.last_result)
