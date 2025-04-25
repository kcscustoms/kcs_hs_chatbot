import streamlit as st
import google.generativeai as genai
import json
import os
import re
from dotenv import load_dotenv
from utils import HSDataManager
from hs_search import lookup_hscode
import requests

# 환경 변수 로드 (.env 파일에서 API 키 등 설정값 로드)
load_dotenv()

# Gemini API 설정
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
genai.configure(api_key=GOOGLE_API_KEY)

# Streamlit 페이지 설정
st.set_page_config(
    page_title="HS 품목분류 챗봇",  # 브라우저 탭 제목
    page_icon="📊",  # 브라우저 탭 아이콘
    layout="wide"  # 페이지 레이아웃을 넓게 설정
)

# 사용자 정의 CSS 스타일 추가
st.markdown("""
<style>
.main > div {
    display: flex;
    flex-direction: column;
    height: 85vh;  # 메인 컨테이너 높이 설정
}
.main > div > div:last-child {
    margin-top: auto;  # 마지막 요소를 하단에 고정
}
.element-container:has(button) {
    background-color: #f0f2f6;  # 버튼 컨테이너 배경색
    padding: 10px;
    border-radius: 10px;
}
.stTextArea textarea {
    border-radius: 20px;  # 입력창 모서리 둥글게
    padding: 10px 15px;
    font-size: 16px;
    min-height: 50px !important;  # 최소 높이
    max-height: 300px !important;  # 최대 높이
    height: auto !important;  # 자동 높이 조절
    resize: vertical !important;  # 수직 방향으로만 크기 조절 가능
    overflow-y: auto !important;  # 내용이 많을 때 스크롤 표시
}
</style>
""", unsafe_allow_html=True)

# HS 데이터 매니저 초기화 (캐싱을 통해 성능 최적화)
@st.cache_resource
def get_hs_manager():
    return HSDataManager()

# HTML 태그 제거 및 텍스트 정제 함수
def clean_text(text):
    # HTML 태그 제거 (더 엄격한 정규식 패턴 사용)
    text = re.sub(r'<[^>]+>', '', text)  # 모든 HTML 태그 제거
    text = re.sub(r'\s*</div>\s*$', '', text)  # 끝에 있는 </div> 태그 제거
    return text.strip()

# 세션 상태 초기화
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []  # 채팅 기록 저장

if 'context' not in st.session_state:
    # 초기 컨텍스트 설정 (카테고리 분류 안내 추가)
    st.session_state.context = """당신은 HS 품목분류 전문가로서 관세청에서 오랜 경력을 가진 전문가입니다. 사용자가 물어보는 품목에 대해 아래 세 가지 유형 중 하나로 질문을 분류하여 답변해주세요.

질문 유형:
1. 웹 검색(Web Search): 물품개요, 용도, 기술개발, 무역동향 등 일반 정보 탐색이 필요한 경우.
2. HS 분류 검색(HS Classification Search): HS 코드, 품목분류, 관세, 세율 등 HS 코드 관련 정보가 필요한 경우.
3. HS 해설서 분석(HS Manual Analysis): HS 해설서, 규정, 판례 등 심층 분석이 필요한 경우.

중요 지침:
1. 사용자가 질문하는 물품에 대해 관련어, 유사품목, 대체품목도 함께 고려하여 가장 적합한 HS 코드를 찾아주세요.
2. 품목의 성분, 용도, 가공상태 등을 고려하여 상세히 설명해주세요.
3. 사용자가 특정 HS code를 언급하며 질문하는 경우, 답변에 해당 HS code 해설서 분석 내용을 포함하여 답변해주세요.
4. 관련 규정이나 판례가 있다면 함께 제시해주세요.
5. 답변은 간결하면서도 전문적으로 제공해주세요.

지금까지의 대화:
"""

import re

# 모듈 상단에서 한 번만 컴파일
HS_PATTERN = re.compile(
    r'\b(?:HS)?\s*\d{4}(?:[.-]\d{2}(?:[.-]\d{2}(?:[.-]\d{2})?)?)?\b',
    flags=re.IGNORECASE
)

def extract_hs_codes(text):
    """여러 HS 코드를 추출하고, 중복 제거 및 숫자만 남겨 표준화"""
    matches = HS_PATTERN.findall(text)
    hs_codes = []
    for raw in matches:
        # 숫자만 남기기
        code = re.sub(r'\D', '', raw)
        if code and code not in hs_codes:
            hs_codes.append(code)
    return hs_codes

import json

def extract_and_store_text(json_file):
    """JSON 파일에서 head1과 text를 추출하여 변수에 저장"""
    try:
        # JSON 파일 읽기
        with open(json_file, 'r', encoding='utf-8') as file:
            data = json.load(file)
        
        # 데이터를 변수에 저장
        extracted_data = []
        for item in data:
            head1 = item.get('head1', '')
            text = item.get('text', '')
            if head1 or text:
                extracted_data.append(f"{head1}\n{text}")
        
        # print("데이터가 변수에 저장되었습니다.")
        return extracted_data
    except Exception as e:
        print(f"오류 발생: {e}")
        return []

# 함수 실행 및 데이터 저장
general_explanation = extract_and_store_text('knowledge/통칙_grouped.json')


def get_hs_explanations(hs_codes):
    """여러 HS 코드에 대한 해설을 취합하는 함수"""
    all_explanations = ""
    for hs_code in hs_codes:
        explanation, type_explanation, number_explanation = lookup_hscode(hs_code, 'knowledge/grouped_11_end.json')

        if explanation and type_explanation and number_explanation:
            all_explanations += f"\n\nHS 코드 {hs_code}에 대한 해설:\n"
            all_explanations += f"해설서 통칙:\n{general_explanation}\n\n"
            all_explanations += f"부 해설:\n{explanation['text']}\n\n"
            all_explanations += f"류 해설:\n{type_explanation['text']}\n\n"
            all_explanations += f"호 해설:\n{number_explanation['text']}\n"
    return all_explanations

# Serper API를 이용한 웹 검색 답변 함수
def web_search_answer(query, num_results=3):
    """
    사용자의 질문에 대해 Serper API를 이용해 웹 검색 결과를 기반으로 답변을 생성합니다.
    (Serper API 키 필요, https://serper.dev)
    """
    SERPER_API_KEY = os.getenv('SERPER_API_KEY')
    if not SERPER_API_KEY:
        return "웹 검색 API 키가 설정되어 있지 않습니다."
    endpoint = "https://google.serper.dev/search"
    headers = {
        "X-API-KEY": SERPER_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "q": query,
        "num": num_results
    }
    try:
        response = requests.post(endpoint, headers=headers, json=payload)
        response.raise_for_status()
        results = response.json().get("organic", [])
        if not results:
            return "웹 검색 결과를 찾을 수 없습니다."
        answer = "웹 검색 결과 요약:\n"
        for idx, item in enumerate(results, 1):
            title = re.sub(r'<.*?>', '', item.get("title", ""))
            snippet = re.sub(r'<.*?>', '', item.get("snippet", ""))
            url = item.get("link", "")
            answer += f"{idx}. [{title}]({url}): {snippet}\n"
        return answer
    except Exception as e:
        return f"웹 검색 중 오류가 발생했습니다: {e}"

# 질문 유형 분류 함수 (LLM 기반)
def classify_question(user_input):
    """
    LLM(Gemini)을 활용하여 사용자의 질문을 아래 세 가지 유형 중 하나로 분류합니다.
    - 'web_search': 물품 개요, 용도, 기술개발, 무역동향, 산업동향 등
    - 'hs_classification': HS 코드, 품목분류, 관세 등
    - 'hs_manual': HS 해설서, 규정, 판례 등 심층 분석
    """
    system_prompt = """
아래는 HS 품목분류 전문가를 위한 질문 유형 분류 기준입니다.

질문 유형:
1. "web_search" : "뉴스", "최근", "동향", "해외", "산업, 기술, 무역동향" 등 일반 정보 탐색이 필요한 경우.
2. "hs_classification": HS 코드, 품목분류, 관세, 세율 등 HS 코드 관련 정보가 필요한 경우.
3. "hs_manual": HS 해설서, 규정, 판례 등 심층 분석이 필요한 경우.

아래 사용자 질문을 읽고, 반드시 위 세 가지 중 하나의 유형만 한글이 아닌 소문자 영문으로 답변하세요.
질문: """ + user_input + """\n답변:"""

    model = genai.GenerativeModel('gemini-2.0-flash')
    response = model.generate_content(system_prompt)
    answer = response.text.strip().lower()
    # 결과가 정확히 세 가지 중 하나인지 확인
    if answer in ["web_search", "hs_classification", "hs_manual"]:
        return answer
    # 예외 처리: 분류 실패 시 기본값
    return "hs_classification"

# 사용자 입력 처리 콜백 함수 (수정)

def handle_web_search(user_input, context, hs_manager):
    relevant = hs_manager.get_relevant_context(user_input)
    search_result = web_search_answer(user_input)
    prompt = f"{context}\n\n관련 데이터:\n{relevant}\n{search_result}\n\n사용자: {user_input}\n"
    model = genai.GenerativeModel('gemini-2.0-flash')
    resp = model.generate_content(prompt)
    return clean_text(resp.text)

def handle_hs_classification_cases(user_input, context, hs_manager):
    relevant = hs_manager.get_relevant_context(user_input)
    # hs_codes = extract_hs_codes(user_input)
    # explanations = get_hs_explanations(hs_codes) if hs_codes else ""
    prompt = f"{context}\n\n관련 데이터:\n{relevant}\n\n사용자: {user_input}\n"
    model = genai.GenerativeModel('gemini-2.0-flash')
    resp = model.generate_content(prompt)
    return clean_text(resp.text)

def handle_hs_manual(user_input, context, hs_manager):
    # 예: HS 해설서 분석 전용 컨텍스트 추가
    manual_context = context + "\n(심층 해설서 분석 모드)"
    # relevant = hs_manager.get_relevant_context(user_input)
    hs_codes = extract_hs_codes(user_input)
    explanations = get_hs_explanations(hs_codes) if hs_codes else ""
    prompt = f"{manual_context}\n\n관련 데이터:\n{explanations}\n\n사용자: {user_input}\n"
    model = genai.GenerativeModel('gemini-2.0-flash')
    resp = model.generate_content(prompt)
    return clean_text(resp.text)

def process_input():
    ui = st.session_state.user_input
    if not ui: 
        return

    st.session_state.chat_history.append({"role": "user", "content": ui})
    hs_manager = get_hs_manager()
    q_type = classify_question(ui)

    # 질문 유형별 분기
    if q_type == "web_search":
        answer = handle_web_search(ui, st.session_state.context, hs_manager)
    elif q_type == "hs_classification":
        answer = handle_hs_classification_cases(ui, st.session_state.context, hs_manager)
    elif q_type == "hs_manual":
        answer = handle_hs_manual(ui, st.session_state.context, hs_manager)
    else:
        # 예외 처리: 기본 HS 분류
        answer = handle_hs_classification_cases(ui, st.session_state.context, hs_manager)

    st.session_state.chat_history.append({"role": "assistant", "content": answer})
    st.session_state.context += f"\n사용자: {ui}\n품목분류 전문가: {answer}\n"
    st.session_state.user_input = ""


# 사이드바 설정
with st.sidebar:
    st.title("HS Chatbot")
    st.markdown("""
    ### 이것은 HS Chatbot입니다.

    이 챗봇은 다음과 같은 방식으로 사용자의 질문에 답변합니다:

    - **웹 검색(Web Search)**: 물품개요, 용도, 뉴스, 무역동향, 산업동향 등 일반 정보 탐색이 필요한 경우 Serper API를 통해 최신 정보를 제공합니다.
    - **HS 분류 검색(HS Classification Search)**: 관세청의 품목분류 사례 약 1000개의 데이터베이스를 활용하여 HS 코드, 품목분류, 관세, 세율 등 정보를 제공합니다.
    - **HS 해설서 분석(HS Manual Analysis)**: HS 해설서, 규정, 판례 등 심층 분석이 필요한 경우 관련 해설서와 규정을 바탕으로 답변합니다.

    사용자는 HS 코드, 품목 분류, 시장 동향, 규정 해설 등 다양한 질문을 할 수 있습니다.
    """)
    
    # 새로운 채팅 시작 버튼
    if st.button("새로운 채팅 시작하기", type="primary"):
        st.session_state.chat_history = []  # 채팅 기록 초기화
        st.session_state.context = """당신은 HS 품목분류 전문가로서 관세청에서 오랜 경력을 가진 전문가입니다. 사용자가 물어보는 품목에 대해 아래 세 가지 유형 중 하나로 질문을 분류하여 답변해주세요.

질문 유형:
1. 웹 검색(Web Search): 물품개요, 용도, 뉴스, 무역동향, 산업동향 등 일반 정보 탐색이 필요한 경우.
2. HS 분류 검색(HS Classification Search): HS 코드, 품목분류, 관세, 세율 등 HS 코드 관련 정보가 필요한 경우.
3. HS 해설서 분석(HS Manual Analysis): HS 해설서, 규정, 판례 등 심층 분석이 필요한 경우.

중요 지침:
1. 사용자가 질문하는 물품에 대해 관련어, 유사품목, 대체품목도 함께 고려하여 가장 적합한 HS 코드를 찾아주세요.
2. 품목의 성분, 용도, 가공상태 등을 고려하여 상세히 설명해주세요.
3. 사용자가 특정 HS code를 언급하며 질문하는 경우, 답변에 해당 HS code 해설서 분석 내용을 포함하여 답변해주세요.
4. 관련 규정이나 판례가 있다면 함께 제시해주세요.
5. 답변은 간결하면서도 전문적으로 제공해주세요.

지금까지의 대화:
"""
        st.rerun()  # 페이지 새로고침

# 메인 페이지 설정
st.title("HS 품목분류 챗봇")
st.write("HS 품목분류에 대해 질문해주세요!")

# 채팅 기록 표시
for message in st.session_state.chat_history:
    if message["role"] == "user":
        st.markdown(f"""<div style='background-color: #e6f7ff; padding: 10px; border-radius: 10px; margin-bottom: 10px;'>
                   <strong>사용자:</strong> {message['content']}
                   </div>""", unsafe_allow_html=True)
    else:
        st.markdown(f"""<div style='background-color: #f0f2f6; padding: 10px; border-radius: 10px; margin-bottom: 10px;'>
                   <strong>품목분류 전문가:</strong> {message['content']}
                   </div>""", unsafe_allow_html=True)


# 하단 입력 영역 (Enter 키로만 전송)
input_container = st.container()
st.markdown("<div style='flex: 1;'></div>", unsafe_allow_html=True)

with input_container:
    # on_change 콜백으로 Enter 누를 때 process_input() 호출
    st.text_input(
        "품목에 대해 질문하세요:", 
        key="user_input", 
        on_change=process_input, 
        placeholder="여기에 입력 후 Enter"
    )
