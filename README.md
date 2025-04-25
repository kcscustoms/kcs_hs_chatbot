# HS 품목분류 챗봇

관세청 전문가의 지식을 바탕으로 HS 품목분류에 대한 정확한 답변을 제공하는 AI 챗봇입니다. Streamlit과 Google Gemini API를 활용하여 사용자의 질문을 전문적이고 정확하게 처리합니다.

## 주요 기능

1. **정확한 품목분류 정보 제공**  
   - 관세청 품목분류 사례 데이터베이스 활용  
   - HS 위원회 및 협의회 결정사항 참조  
   - 정확한 HS 코드와 분류 근거 제시  

2. **스마트 검색 기능**  
   - 키워드 기반 인덱싱으로 빠른 검색  
   - 관련어 및 유사 품목 자동 검색  
   - 가중치 기반 검색 결과 정렬  

3. **대화형 인터페이스**  
   - 멀티턴 대화 지원 및 이전 대화 컨텍스트 유지  
   - Enter 키로 질문 전송, Shift + Enter로 줄바꿈 가능  
   - 모바일 친화적 UI 및 하단 고정 입력창  

4. **최적화된 성능**  
   - `st.cache_resource`를 이용한 HS 데이터 매니저 캐싱  
   - 효율적인 메모리 사용과 선택적 컨텍스트 로딩  
   - 데이터 로딩 초기화 후 빠른 응답 보장  

## 추가된 주요 기능

5. **질문 유형 분류 및 처리**  
   - Google Gemini API를 활용해 질문을 세 가지 유형으로 분류:  
     - **웹 검색(Web Search)**: 물품 개요, 기술 개발, 무역·산업 동향 등  
     - **HS 분류 검색(HS Classification Search)**: HS 코드, 품목분류, 관세 등  
     - **HS 해설서 분석(HS Manual Analysis)**: HS 해설서, 규정, 판례 등 심층 분석  
   - 분류에 따라 각기 다른 핸들러로 적합한 답변 생성  

6. **웹 검색 통합**  
   - Serper API를 사용해 최신 웹 검색 결과 제공  
   - 결과를 요약하여 제목·링크와 함께 출력  
   - API 키 미설정 또는 에러 시 사용자 안내 메시지 제공  

7. **HS 코드 추출 및 해설**  
   - 정규식 패턴으로 사용자 입력 내 HS 코드 자동 추출  
   - `knowledge/통칙_grouped.json` 및 `knowledge/grouped_11_end.json` 기반 해설 통합  
   - 해설서 통칙, 부류·류·호별 상세 설명 일괄 제공  

8. **사용자 정의 CSS 스타일**  
   - Flex 레이아웃과 둥근 모서리, 패딩 등 커스텀 스타일 적용  
   - 버튼, 입력창, 메시지 컨테이너 등 UI 요소 개선  

9. **세션 상태 관리**  
   - `st.session_state`로 채팅 기록 및 대화 컨텍스트 유지  
   - “새로운 채팅 시작하기” 버튼으로 세션 초기화  


## 설치 방법

1. 저장소 클론
```bash
git clone https://github.com/YSCHOI-github/kcs_hs_chatbot
cd kcs_hs_chatbot
```

2. 가상환경 생성 및 활성화
```bash
# Windows
python -m venv venv
.\venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

3. 필요한 패키지 설치
```bash
pip install -r requirements.txt
```

4. 환경 변수 설정
- `.env` 파일 생성
- api key 추가
GOOGLE_API_KEY='your-google-gemini-key'
SERPER_API_KEY='your-serper-api-key'

## 업데이트된 실행 방법

1. 애플리케이션 실행
```bash
streamlit run main.py
```

2. 웹 브라우저에서 접속
- http://localhost:8501 으로 접속

## 프로젝트 구조

```
├── main.py                 # Streamlit 애플리케이션 메인
├── utils.py                # HSDataManager 및 유틸리티 함수
├── hs_search.py            # HS 코드 검색 및 해설 제공 로직
├── knowledge/              # HS 해설서 및 관련 JSON 데이터
│   ├── 통칙_grouped.json
│   ├── grouped_11_end.json
│   ├── HS위원회.json            # HS 위원회 결정사항
│   ├── HS협의회.json            # HS 협의회 결정사항
│   └── HS분류사례_part*.json
├── requirements.txt        # 프로젝트 의존성 목록
└── .env                    # 환경 변수 파일 (gitignore 처리)
```

## 데이터 소스

- **HS 분류사례**: 실제 품목분류 사례 데이터 (10개 파트로 분할)
- **HS 위원회 결정사항**: 품목분류 관련 위원회 결정사항
- **HS 협의회 결정사항**: 협의회의 주요 결정 및 해석
- **HS 해설서 데이터**: grouped_11_end.json 및 통칙_grouped.json 파일 활용