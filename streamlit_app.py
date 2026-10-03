"""PlanEat UI prototype: no backend requests."""
from html import escape
from io import BytesIO
import streamlit as st
from PIL import Image, UnidentifiedImageError

st.set_page_config(page_title="PlanEat · 오늘의 한 끼", page_icon="🥬", layout="wide")
SAMPLE = [{"재료": n, "수량": q, "확인 근거": "데모 예시"} for n,q in [("양배추","반 통"),("두부","1모"),("계란","3개"),("당근","1개"),("양파","2개"),("밥","1공기"),("닭가슴살","1팩")]]
# TODO: Replace fixtures with recipe records returned by the backend's internal DB.
SETS = [
    ("🥬","가볍게, 든든하게","양배추 달걀볶음","두부 샐러드",20,420,["양배추","계란","두부"],("참깨","1작은술","생략 가능","생략하면 고소한 풍미가 줄어들어요.")),
    ("🍗","단백질 가득 한 끼","닭가슴살 채소덮밥","당근 달걀볶음",25,610,["닭가슴살","밥","당근","계란"],("간장","1큰술","필수","덮밥의 기본 간에 사용해요.")),
    ("🍲","따뜻한 집밥 한 상","두부 채소국","양배추 달걀전",30,460,["두부","양파","양배추","계란"],("대파","반 대","구매 권장","국물에 향과 감칠맛을 더해요.")),
    ("🍚","남은 재료도 알뜰하게","채소 달걀볶음밥","구운 두부",15,540,["밥","계란","당근","양파","두부"],("참기름","1작은술","생략 가능","생략하면 볶음밥의 고소함이 줄어들어요.")),
    ("🥗","산뜻하게 즐기는 저녁","닭가슴살 양배추 샐러드","달걀 채소찜",20,390,["닭가슴살","양배추","계란","당근"],("레몬즙","1큰술","대체 가능","식초를 조금씩 넣어 신맛을 조절할 수 있어요.")),
]
st.markdown('''<style>
.stApp{background:#fafbf8;}[data-testid="stSidebar"]{background:#f0f3eb;border-right:1px solid #e0e6d9;}
.block-container{max-width:1080px;padding-top:2rem;padding-bottom:5rem;}
h1,h2,h3{color:#243d2c;letter-spacing:-.045em;}h1{font-size:2.6rem!important;}
[data-testid="stChatMessage"]{background:transparent;}[data-testid="stChatInput"]{border-radius:22px;border-color:#cbd6c4;}
[data-testid="stBottom"]{background:#fafbf8;}div.stButton>button{border-radius:12px;min-height:42px;}
div.stButton>button[kind="primary"]{background:#355d40;border-color:#355d40;}
.brand{font-size:27px;font-weight:800;color:#2c5036;letter-spacing:-1px;}.muted{color:#74806e;font-size:13px;}
.eyebrow{color:#6c805f;font-size:12px;font-weight:700;letter-spacing:2px;margin:24px 0 12px;}
.hero{padding:24px 0 20px;}.hero p{color:#75806f;line-height:1.9;}
.chip{display:inline-block;background:#eef3e8;color:#4d6744;padding:5px 11px;border-radius:20px;font-size:12px;margin:3px;}
.food{font-size:42px;background:linear-gradient(120deg,#edf2e4,#f8f3e8);padding:20px;border-radius:13px;}
@media(max-width:640px){.block-container{padding-top:1rem;}h1{font-size:2rem!important;}}
</style>''', unsafe_allow_html=True)

for key,value in {"messages":[],"ingredients":[],"confirmed":False,"recommendations":False,"selected":None,"revision":0}.items():
    if key not in st.session_state: st.session_state[key]=value
s=st.session_state

def message(role,text,images=None):
    s.messages.append({"role":role,"text":text,"images":images or []})

def sample():
    s.ingredients=[dict(r) for r in SAMPLE]
    s.confirmed=False
    s.recommendations=False
    s.selected=None
    s.revision+=1

def missing(recipe):
    owned={r["재료"] for r in s.ingredients}
    result=[(n,"1인분","필수","메뉴의 주재료로 필요해요.") for n in recipe[6] if n not in owned]
    if recipe[7][0] not in owned: result.append(recipe[7])
    return result

with st.sidebar:
    st.markdown('<div class="brand">🥬 PlanEat</div><div class="muted">내 냉장고에서 시작하는 한 끼</div>',unsafe_allow_html=True)
    st.write("")
    if st.button("＋ 새로운 대화",width="stretch"):
        s.clear()
        st.rerun()
    st.divider()
    st.caption("오늘의 식사 준비")
    for label,done in [("01  사진 올리기",bool(s.ingredients)),("02  재료 확인하기",s.confirmed),("03  한 끼 고르기",s.recommendations)]:
        st.write(("●  " if done else "○  ")+label)
    st.divider()
    st.markdown("**나의 식사 조건**")
    purpose=st.selectbox("식사 목적",["균형식","다이어트","벌크업","일반식"])
    minutes=st.select_slider("조리 시간",options=[15,20,30,45,60],value=30,format_func=lambda x:f"{x}분 이내")
    cuisine=st.selectbox("선호 식단",["한식","양식","혼합"])
    exclusions=st.text_input("알레르기 · 비선호 재료",placeholder="예: 땅콩, 우유")
    vegetarian=st.checkbox("채식 식단")
    spicy=st.checkbox("매운 음식도 좋아요")
    st.divider()
    st.caption("프론트엔드 데모 · API 미연결\n\n사진 분석과 추천은 예시 데이터로 표시됩니다.")
st.markdown("**오늘의 한 끼**")
st.divider()
if not s.messages:
    st.markdown('<div class="hero"><div class="eyebrow">A LITTLE LESS WASTE, A BETTER MEAL</div><h1>냉장고에 있는 재료로,<br>오늘은 뭘 먹을까요?</h1><p>냉장고와 영수증 사진을 올려주세요.<br>재료를 함께 확인하고, 나에게 맞는 한 끼를 찾아봐요.</p></div>',unsafe_allow_html=True)
    for col,icon,title,desc in zip(st.columns(3),["📷","🥕","🍽️"],["사진으로 간편하게","재료는 꼼꼼하게","선택은 여유롭게"],["냉장고 · 영수증 사진 최대 5장","수량 수정부터 빠진 재료 추가까지","메인과 곁들임, 2개씩 5세트"]):
        with col,st.container(border=True):
            st.write(icon)
            st.markdown(f"**{title}**")
            st.caption(desc)
    st.write("")
    if st.button("✦ 예시 냉장고로 시작하기",type="primary"):
        sample()
        message("user","예시 냉장고로 오늘의 한 끼를 찾아볼게요.")
        message("assistant","예시 재료 7개를 준비했어요. 실제 사진 분석 결과가 아닙니다. 재료와 수량을 확인해 주세요.")
        st.rerun()
for msg in s.messages:
    with st.chat_message(msg["role"],avatar="🥬" if msg["role"]=="assistant" else "🙂"):
        st.write(msg["text"])
        if msg["images"]:
            for col,img in zip(st.columns(len(msg["images"])),msg["images"]):
                col.image(img["data"],caption=img["name"],width=160)
if s.ingredients and not s.confirmed:
    with st.container(border=True):
        st.subheader("냉장고 재료를 확인해 주세요",anchor=False)
        st.caption("예시 데이터 · 셀을 눌러 수정하고, 행 선택으로 삭제하거나 마지막 행에 재료를 추가하세요.")
        edited=st.data_editor(s.ingredients,num_rows="dynamic",hide_index=True,key=f"ingredients_{s.revision}",width="stretch",column_config={"재료":st.column_config.TextColumn(required=True),"수량":st.column_config.TextColumn(required=True),"확인 근거":st.column_config.TextColumn(disabled=True)})
        if st.button("이 재료로 확정하기 →",type="primary"):
            valid=[{"재료":str(r.get("재료") or "").strip(),"수량":str(r.get("수량") or "").strip(),"확인 근거":r.get("확인 근거") or "직접 추가"} for r in edited]
            if not valid or any(not r["재료"] or not r["수량"] for r in valid): st.error("재료를 하나 이상 입력하고 이름과 수량을 채워주세요.")
            elif len({r["재료"] for r in valid})!=len(valid): st.error("같은 재료는 한 행으로 합쳐 수량을 확인해 주세요.")
            else:
                s.ingredients=valid
                s.confirmed=True
                message("assistant","재료를 확정했어요. 왼쪽에서 식사 조건을 선택하거나 원하는 식사를 메시지로 남겨주세요.")
                st.rerun()
if s.confirmed:
    with st.expander(f"확정한 재료 {len(s.ingredients)}개"):
        st.markdown(''.join(f'<span class="chip">{escape(r["재료"])} · {escape(r["수량"])}</span>' for r in s.ingredients),unsafe_allow_html=True)
        if st.button("재료 다시 수정"):
            s.confirmed=False
            s.recommendations=False
            s.selected=None
            s.revision+=1
            st.rerun()
    if st.button("내 한 끼 5세트 보기",type="primary"):
        # TODO: POST confirmed ingredients, purpose, minutes, cuisine, exclusions,
        # vegetarian, spicy and conversation to the backend recommendation API.
        s.recommendations=True
        st.rerun()
if s.recommendations:
    st.markdown('<div class="eyebrow">YOUR MEAL IDEAS</div>',unsafe_allow_html=True)
    st.subheader("오늘, 마음이 가는 한 끼를 골라보세요",anchor=False)
    st.caption(f"선택 조건: {purpose} · {minutes}분 이내 · {cuisine}"+(" · 채식" if vegetarian else "")+(" · 매운 음식 허용" if spicy else "")+(f" · 제외: {exclusions}" if exclusions else ""))
    st.info("5세트는 고정 예시입니다. 목적·시간·알레르기·채식 조건은 아직 추천에 적용되지 않습니다. 영양 정보와 조리 안내도 예시입니다.")
    for idx,recipe in enumerate(SETS):
        emoji,title,main,side,duration,calories,required,extra=recipe
        with st.container(border=True):
            art,body,action=st.columns([1,4,1.4])
            art.markdown(f'<div class="food">{emoji}</div>',unsafe_allow_html=True)
            with body:
                st.caption(f"SET {idx+1:02d} · {title}")
                st.markdown(f"### {main} + {side}")
                st.caption(f"◷ {duration}분 · 약 {calories} kcal / 세트 · 레시피 2개")
                owned=[n for n in required if n in {r["재료"] for r in s.ingredients}]
                st.write("보유 재료: "+(", ".join(owned) or "없음"))
                st.caption("부족 재료: "+(", ".join(x[0] for x in missing(recipe)) or "추가 구매 없음"))
            with action:
                if st.button("선택됨 ✓" if s.selected==idx else "세트 살펴보기",key=f"select_{idx}",width="stretch"):
                    s.selected=idx
                    st.rerun()
            if s.selected==idx:
                detail,shopping=st.tabs(["레시피 상세","장보기 목록"])
                with detail:
                    st.caption("원본 DB 연결 전 · 분량과 조리 순서는 UI 예시이며 공식 레시피가 아닙니다.")
                    for dish in [main,side]:
                        with st.expander(dish):
                            st.write("**세트 재료 · 분량 예시**")
                            st.write(" / ".join(f"{n} 1인분" for n in required))
                            st.write("**조리 순서 예시**")
                            st.write("1. 재료를 씻고 먹기 좋은 크기로 준비합니다.\n2. 메뉴에 맞게 재료를 익힙니다.\n3. 간을 조절하고 그릇에 담습니다.")
                            # TODO: Render per-recipe original quantities, steps,
                            # image URL, nutrition and source from backend response.
                    st.caption("세트 선택으로 다른 세트의 재료가 차감되지 않아요.")
                with shopping:
                    items=missing(recipe)
                    if not items: st.success("추가 구매할 재료가 없어요.")
                    for n,q,importance,note in items:
                        st.checkbox(f"{n} · {q} · {importance}",key=f"buy_{s.revision}_{idx}_{n}")
                        st.caption(note)
                    content="\n".join(f"- {n} {q} ({i}): {note}" for n,q,i,note in items) or "추가 구매 없음"
                    st.download_button("장보기 목록 저장 ↓",content,file_name=f"planeat-set-{idx+1}.txt",mime="text/plain",key=f"download_{idx}")
st.caption("입력창의 ＋로 사진을 첨부하세요. 전송 전 미리보기에서 삭제할 수 있어요. 최대 5장 · JPG, PNG, WEBP · 장당 10MB")
prompt=st.chat_input("냉장고 사진을 올리거나, 원하는 한 끼를 이야기해 주세요",accept_file="multiple",file_type=["jpg","jpeg","png","webp"],max_upload_size=10,key="composer")
if prompt:
    files=list(prompt.files)
    text=prompt.text.strip()
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
            if text or images:
                message("user",text or "이 사진 속 재료로 한 끼를 찾아주세요.",images)
                if images:
                    # TODO: Send image bytes to backend extraction endpoint;
                    # replace samples with merged candidates and image evidence.
                    sample()
                    message("assistant",f"사진 {len(images)}장을 받았어요. 현재는 사진을 분석하지 않는 데모로 예시 재료를 표시합니다. 아래 목록을 확인하고 수정해 주세요.")
                elif s.confirmed:
                    # TODO: Send natural language and confirmed ingredients to API.
                    # Add loading, error and retry states around that request.
                    s.recommendations=True
                    message("assistant","요청을 기록했어요. 지금은 자연어 조건을 해석하지 않는 데모입니다. 화면 확인용 5세트를 보여드릴게요.")
                else: message("assistant","먼저 ＋로 사진을 첨부하거나 예시 재료를 불러온 뒤 재료를 확정해 주세요.")
                st.rerun()
if s.messages and not s.ingredients:
    if st.button("예시 재료 불러오기"):
        sample()
        st.rerun()


