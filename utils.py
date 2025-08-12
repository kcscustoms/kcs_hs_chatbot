import json
import re
import os
import requests
import time
from typing import Dict, List, Any
from collections import defaultdict
from difflib import SequenceMatcher
from google import genai
from google.genai import types
from dotenv import load_dotenv



# 환경 변수 로드 (.env 파일에서 API 키 등 설정값 로드)
load_dotenv()
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
client = genai.Client(api_key=GOOGLE_API_KEY)

class HSDataManager:
    """
    HS 코드 관련 데이터를 관리하는 클래스
    - HS 분류 사례, 위원회 결정, 협의회 결정 등의 데이터를 로드하고 관리
    - 키워드 기반 검색 기능 제공
    - 관련 컨텍스트 생성 기능 제공
    """
    
    def __init__(self):
        """HSDataManager 초기화"""
        self.data = {}  # 모든 HS 관련 데이터를 저장하는 딕셔너리
        self.search_index = defaultdict(list)  # 키워드 기반 검색을 위한 인덱스
        self.load_all_data()  # 모든 데이터 파일 로드
        self.build_search_index()  # 검색 인덱스 구축
    
    def load_all_data(self):
        """
        모든 HS 데이터 파일을 로드하는 메서드
        - HS분류사례_part1~10.json 파일 로드
        - HS위원회.json, HS협의회.json 파일 로드
        - hs_classification_data_us.json 파일 로드 (미국 관세청 품목분류 사례)
        - hs_classification_data_eu.json 파일 로드 (EU 관세청 품목분류 사례)
        """
        # HS분류사례 파트 로드 (1~10)
        for i in range(1, 11):
            try:
                with open(f'knowledge/HS분류사례_part{i}.json', 'r', encoding='utf-8') as f:
                    self.data[f'HS분류사례_part{i}'] = json.load(f)
            except FileNotFoundError:
                print(f'Warning: HS분류사례_part{i}.json not found')
        
        # 기타 JSON 파일 로드 (위원회, 협의회 결정)
        other_files = ['knowledge/HS위원회.json', 'knowledge/HS협의회.json']
        for file in other_files:
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    self.data[file.replace('.json', '')] = json.load(f)
            except FileNotFoundError:
                print(f'Warning: {file} not found')
        
        # 미국 관세청 품목분류 사례 로드
        try:
            with open('knowledge/hs_classification_data_us.json', 'r', encoding='utf-8') as f:
                self.data['hs_classification_data_us'] = json.load(f)
        except FileNotFoundError:
            print('Warning: hs_classification_data_us.json not found')
        
        # EU 관세청 품목분류 사례 로드
        try:
            with open('knowledge/hs_classification_data_eu.json', 'r', encoding='utf-8') as f:
                self.data['hs_classification_data_eu'] = json.load(f)
        except FileNotFoundError:
            print('Warning: hs_classification_data_eu.json not found')
    
    def build_search_index(self):
        """
        검색 인덱스 구축 메서드
        - 각 데이터 항목에서 키워드를 추출
        - 추출된 키워드를 인덱스에 저장하여 빠른 검색 가능
        """
        for source, items in self.data.items():
            for item in items:
                # 품목명에서 키워드 추출
                keywords = self._extract_keywords(str(item))
                # 각 키워드에 대해 해당 아이템 참조 저장
                for keyword in keywords:
                    self.search_index[keyword].append((source, item))
    
    def _extract_keywords(self, text: str) -> List[str]:
        """
        텍스트에서 의미있는 키워드를 추출하는 내부 메서드
        Args:
            text: 키워드를 추출할 텍스트
        Returns:
            추출된 키워드 리스트
        """
        # 특수문자 제거 및 공백 기준 분리
        words = re.sub(r'[^\w\s]', ' ', text).split()
        # 중복 제거 및 길이 2 이상인 단어만 선택
        return list(set(word for word in words if len(word) >= 2))
    
    def search(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """
        쿼리와 관련된 가장 연관성 높은 항목들을 검색하는 메서드
        Args:
            query: 검색할 쿼리 문자열
            max_results: 반환할 최대 결과 수 (기본값: 5)
        Returns:
            검색 결과 리스트 (출처와 항목 정보 포함)
        """
        query_keywords = self._extract_keywords(query)
        results = defaultdict(int)
        
        # 각 키워드에 대해 매칭되는 항목 찾기
        for keyword in query_keywords:
            for source, item in self.search_index.get(keyword, []):
                # 가중치 계산 (키워드 매칭 횟수 기반)
                results[(source, str(item))] += 1
        
        # 가중치 기준 정렬
        sorted_results = sorted(results.items(), key=lambda x: x[1], reverse=True)
        
        # 상위 결과만 반환
        return [
            {'source': source, 'item': eval(item_str)}
            for (source, item_str), _ in sorted_results[:max_results]
        ]
    
    def search_domestic_group(self, query: str, group_idx: int, max_results: int = 3) -> List[Dict[str, Any]]:
        """국내 HS 분류 데이터 그룹별 검색 메서드"""
        query_keywords = self._extract_keywords(query)
        results = defaultdict(int)

        # 그룹별 데이터 소스 정의 (5개 그룹)
        group_sources = [
            ['HS분류사례_part1', 'HS분류사례_part2'],  # 그룹1
            ['HS분류사례_part3', 'HS분류사례_part4'],  # 그룹2
            ['HS분류사례_part5', 'HS분류사례_part6'],  # 그룹3
            ['HS분류사례_part7', 'HS분류사례_part8'],  # 그룹4
            ['HS분류사례_part9', 'HS분류사례_part10', 'knowledge/HS위원회', 'knowledge/HS협의회']  # 그룹5
        ]
        sources = group_sources[group_idx]

        for keyword in query_keywords:
            for source, item in self.search_index.get(keyword, []):
                if source in sources:
                    results[(source, str(item))] += 1

        sorted_results = sorted(results.items(), key=lambda x: x[1], reverse=True)
        return [
            {'source': source, 'item': eval(item_str)}
            for (source, item_str), _ in sorted_results[:max_results]
        ]

    def get_domestic_context_group(self, query: str, group_idx: int) -> str:
        """국내 HS 분류 관련 컨텍스트(그룹별)를 생성하는 메서드"""
        results = self.search_domestic_group(query, group_idx)
        context = []
        for result in results:
            context.append(f"출처: {result['source']} (국내 관세청)\n항목: {json.dumps(result['item'], ensure_ascii=False)}")
        return "\n\n".join(context)

    def search_overseas_group(self, query: str, group_idx: int, max_results: int = 3) -> List[Dict[str, Any]]:
        """해외 HS 분류 데이터 그룹별 검색 메서드"""
        query_keywords = self._extract_keywords(query)
        results = defaultdict(int)
        
        # 해외 데이터를 그룹별로 분할 처리
        if group_idx < 3:  # 그룹 0,1,2는 미국 데이터
            target_source = 'hs_classification_data_us'
            # 미국 데이터를 3등분
            us_data = self.data.get(target_source, [])
            chunk_size = len(us_data) // 3
            start_idx = group_idx * chunk_size
            end_idx = start_idx + chunk_size if group_idx < 2 else len(us_data)
            target_items = us_data[start_idx:end_idx]
        else:  # 그룹 3,4는 EU 데이터
            target_source = 'hs_classification_data_eu'
            # EU 데이터를 2등분
            eu_data = self.data.get(target_source, [])
            chunk_size = len(eu_data) // 2
            eu_group_idx = group_idx - 3  # 0 or 1
            start_idx = eu_group_idx * chunk_size
            end_idx = start_idx + chunk_size if eu_group_idx < 1 else len(eu_data)
            target_items = eu_data[start_idx:end_idx]
        
        # 해당 그룹 데이터에서만 검색
        for keyword in query_keywords:
            for source, item in self.search_index.get(keyword, []):
                if source == target_source and item in target_items:
                    results[(source, str(item))] += 1
        
        sorted_results = sorted(results.items(), key=lambda x: x[1], reverse=True)
        return [
            {'source': source, 'item': eval(item_str)}
            for (source, item_str), _ in sorted_results[:max_results]
        ]

    def get_overseas_context_group(self, query: str, group_idx: int) -> str:
        """해외 HS 분류 관련 컨텍스트(그룹별)를 생성하는 메서드"""
        results = self.search_overseas_group(query, group_idx)
        context = []
        
        for result in results:
            # 출처에 따라 국가 구분
            if result['source'] == 'hs_classification_data_us':
                country = "미국 관세청"
            elif result['source'] == 'hs_classification_data_eu':
                country = "EU 관세청"
            else:
                country = "해외 관세청"
                
            context.append(f"출처: {result['source']} ({country})\n항목: {json.dumps(result['item'], ensure_ascii=False)}")
        
        return "\n\n".join(context)
    
    def search_domestic(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """국내 HS 분류 데이터에서만 검색하는 메서드"""
        query_keywords = self._extract_keywords(query)
        results = defaultdict(int)
        
        # 국내 데이터 소스만 필터링
        domestic_sources = [
            'HS분류사례_part1', 'HS분류사례_part2', 'HS분류사례_part3', 'HS분류사례_part4', 'HS분류사례_part5',
            'HS분류사례_part6', 'HS분류사례_part7', 'HS분류사례_part8', 'HS분류사례_part9', 'HS분류사례_part10',
            'knowledge/HS위원회', 'knowledge/HS협의회'
        ]
        
        for keyword in query_keywords:
            for source, item in self.search_index.get(keyword, []):
                # 국내 데이터 소스만 포함
                if source in domestic_sources:
                    results[(source, str(item))] += 1
        
        sorted_results = sorted(results.items(), key=lambda x: x[1], reverse=True)
        
        return [
            {'source': source, 'item': eval(item_str)}
            for (source, item_str), _ in sorted_results[:max_results]
        ]
    
    def get_domestic_context(self, query: str) -> str:
        """국내 HS 분류 관련 컨텍스트를 생성하는 메서드"""
        results = self.search_domestic(query)
        context = []
        
        for result in results:
            context.append(f"출처: {result['source']} (국내 관세청)\n항목: {json.dumps(result['item'], ensure_ascii=False)}")
        
        return "\n\n".join(context)
    
    def search_overseas_improved(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """해외 HS 분류 데이터에서만 검색하는 개선된 메서드 (search_index 활용)"""
        query_keywords = self._extract_keywords(query)
        results = defaultdict(int)
        
        # 해외 데이터 소스만 필터링
        overseas_sources = ['hs_classification_data_us', 'hs_classification_data_eu']
        
        for keyword in query_keywords:
            for source, item in self.search_index.get(keyword, []):
                # 해외 데이터 소스만 포함
                if source in overseas_sources:
                    results[(source, str(item))] += 1
        
        sorted_results = sorted(results.items(), key=lambda x: x[1], reverse=True)
        
        return [
            {'source': source, 'item': eval(item_str)}
            for (source, item_str), _ in sorted_results[:max_results]
        ]
    
    def get_domestic_context(self, query: str) -> str:
        """국내 HS 분류 관련 컨텍스트를 생성하는 메서드"""
        results = self.search_domestic(query)
        context = []
        
        for result in results:
            context.append(f"출처: {result['source']} (국내 관세청)\n항목: {json.dumps(result['item'], ensure_ascii=False)}")
        
        return "\n\n".join(context)


    def get_relevant_context(self, query: str) -> str:
        """
        쿼리에 관련된 컨텍스트를 생성하는 메서드
        Args:
            query: 컨텍스트를 생성할 쿼리 문자열
        Returns:
            관련 컨텍스트 문자열 (출처와 항목 정보 포함)
        """
        results = self.search(query)
        context = []
        
        for result in results:
            context.append(f"출처: {result['source']}\n항목: {json.dumps(result['item'], ensure_ascii=False)}")
        
        return "\n\n".join(context)
    
    def get_overseas_context_improved(self, query: str) -> str:
        """해외 HS 분류 관련 컨텍스트를 생성하는 개선된 메서드"""
        results = self.search_overseas_improved(query)
        context = []
        
        for result in results:
            # 출처에 따라 국가 구분
            if result['source'] == 'hs_classification_data_us':
                country = "미국 관세청"
            elif result['source'] == 'hs_classification_data_eu':
                country = "EU 관세청"
            else:
                country = "해외 관세청"
                
            context.append(f"출처: {result['source']} ({country})\n항목: {json.dumps(result['item'], ensure_ascii=False)}")
        
        return "\n\n".join(context)

# HTML 태그 제거 및 텍스트 정제 함수
def clean_text(text):
    # HTML 태그 제거 (더 엄격한 정규식 패턴 사용)
    text = re.sub(r'<[^>]+>', '', text)  # 모든 HTML 태그 제거
    text = re.sub(r'\s*</div>\s*$', '', text)  # 끝에 있는 </div> 태그 제거
    return text.strip()

# HS 코드 추출 패턴 정의 및 함수
# 더 유연한 HS 코드 추출 패턴
HS_PATTERN = re.compile(
    r'(?:HS\s*)?(\d{4}(?:[.-]?\d{2}(?:[.-]?\d{2}(?:[.-]?\d{2})?)?)?)',
    flags=re.IGNORECASE
)

def extract_hs_codes(text):
    """
    여러 HS 코드를 추출하고, 중복 제거 및 숫자만 남겨 표준화
    개선사항:
    - 단어 경계(\b) 제거로 더 유연한 매칭
    - 숫자만 있는 경우도 처리 가능
    - 최소 4자리 숫자 체크 추가
    """
    matches = HS_PATTERN.findall(text)
    hs_codes = []
    
    for raw in matches:
        # 숫자만 남기기
        code = re.sub(r'\D', '', raw)
        # 최소 4자리이고 중복이 아닌 경우만 추가
        if len(code) >= 4 and code not in hs_codes:
            hs_codes.append(code)
    
    # 만약 위 패턴으로 찾지 못하고, 입력이 4자리 이상의 숫자로만 구성된 경우
    if not hs_codes:
        # 순수 숫자만 있는 경우 체크
        numbers_only = re.findall(r'\d{4,}', text)
        for num in numbers_only:
            if num not in hs_codes:
                hs_codes.append(num)
    
    return hs_codes

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
        
        return extracted_data
    except Exception as e:
        print(f"오류 발생: {e}")
        return []

# 통칙 데이터 로드 (재사용을 위한 전역 변수)
general_explanation = extract_and_store_text('knowledge/통칙_grouped.json')

def lookup_hscode(hs_code, json_file):
    """HS 코드에 대한 해설 정보를 조회하는 함수"""
    try:
        with open(json_file, 'r', encoding='utf-8') as file:
            data = json.load(file)
        
        # 각 설명 유형별 초기값 설정
        part_explanation = {"text": "해당 부에 대한 설명을 찾을 수 없습니다."}
        chapter_explanation = {"text": "해당 류에 대한 설명을 찾을 수 없습니다."}
        sub_explanation = {"text": "해당 호에 대한 설명을 찾을 수 없습니다."}

        # 1) 류(類) key: "제00류"
        chapter_key = f"제{int(hs_code[:2])}류"
        chapter_explanation = next((g for g in data if g.get('header2') == chapter_key), chapter_explanation)

        # 2) 호 key: "00.00"
        sub_key = f"{hs_code[:2]}.{hs_code[2:]}"
        sub_explanation = next((g for g in data if g.get('header2') == sub_key), sub_explanation)

        # 3) 부(部) key: "제00부"
        part_key = chapter_explanation.get('header1') if chapter_explanation else None
        part_explanation = next((g for g in data if (g.get('header1') == part_key)&(re.sub(r'제\s*(\d+)\s*부', r'제\1부', g.get('header1')) == part_key)), None)
        
        return part_explanation, chapter_explanation, sub_explanation
    
    except Exception as e:
        print(f"HS 코드 조회 오류: {e}")
        return ({"text": "오류가 발생했습니다."}, {"text": "오류가 발생했습니다."}, {"text": "오류가 발생했습니다."})

def get_hs_explanations(hs_codes):
    """여러 HS 코드에 대한 해설을 취합하는 함수 (마크다운 형식)"""
    all_explanations = ""
    for hs_code in hs_codes:
        explanation, type_explanation, number_explanation = lookup_hscode(hs_code, 'knowledge/grouped_11_end.json')

        if explanation and type_explanation and number_explanation:
            all_explanations += f"\n\n# HS 코드 {hs_code} 해설\n\n"
            all_explanations += f"## 📋 해설서 통칙\n\n"
            
            # 통칙 내용을 리스트 형태로 정리
            if general_explanation:
                for i, rule in enumerate(general_explanation[:5], 1):  # 처음 5개만 표시
                    all_explanations += f"### 통칙 {i}\n{rule}\n\n"
            
            all_explanations += f"## 📂 부(部) 해설\n\n{explanation['text']}\n\n"
            all_explanations += f"## 📚 류(類) 해설\n\n{type_explanation['text']}\n\n"
            all_explanations += f"## 📝 호(號) 해설\n\n{number_explanation['text']}\n\n"
            all_explanations += "---\n"  # 구분선 추가
    
    return all_explanations

class TariffTableSearcher:
    def __init__(self):
        self.tariff_data = []
        self.load_tariff_table()
    
    def load_tariff_table(self):
        """관세율표 데이터 로드"""
        try:
            with open('knowledge/hstable.json', 'r', encoding='utf-8') as f:
                self.tariff_data = json.load(f)
        except FileNotFoundError:
            print("Warning: hstable.json not found")
            self.tariff_data = []
    
    def calculate_similarity(self, query, text):
        """텍스트 유사도 계산"""
        if not query or not text:
            return 0.0
        return SequenceMatcher(None, query.lower(), text.lower()).ratio()
    
    def search_by_tariff_table(self, query, top_n=10):
        """관세율표에서 유사도 기반 HS코드 후보 검색"""
        candidates = []
        
        for item in self.tariff_data:
            hs_code = item.get('품목번호', '')
            korean_name = item.get('한글품명', '')
            english_name = item.get('영문품명', '')
            
            # 한글품명과 영문품명에서 유사도 계산
            korean_sim = self.calculate_similarity(query, korean_name)
            english_sim = self.calculate_similarity(query, english_name)
            
            # 최고 유사도 사용
            max_similarity = max(korean_sim, english_sim)
            
            if max_similarity > 0.1:  # 최소 임계값
                candidates.append({
                    'hs_code': hs_code,
                    'korean_name': korean_name,
                    'english_name': english_name,
                    'similarity': max_similarity,
                    'matched_field': 'korean' if korean_sim > english_sim else 'english'
                })
        
        # 유사도 순으로 정렬하여 상위 N개 반환
        candidates.sort(key=lambda x: x['similarity'], reverse=True)
        return candidates[:top_n]

class ParallelHSSearcher:
    def __init__(self, hs_manager):
        self.hs_manager = hs_manager
        self.tariff_searcher = TariffTableSearcher()
    
    def parallel_search(self, query, logger):
        """병렬적 HS코드 검색"""
        
        # 경로 1: 관세율표 → 해설서 (2단계)
        logger.log_actual("SEARCH", "Path 1: Tariff Table → Manual search starting...")
        path1_results = self.tariff_to_manual_search(query, logger)
        
        # 경로 2: 해설서 직접 검색 (기존 방법)
        logger.log_actual("SEARCH", "Path 2: Direct manual search starting...")
        path2_results = self.direct_manual_search(query, logger)
        
        # 결과 종합
        logger.log_actual("AI", "Consolidating parallel search results...")
        final_results = self.consolidate_results(path1_results, path2_results, logger)
        
        return final_results
    
    def tariff_to_manual_search(self, query, logger):
        """경로 1: 관세율표 → 해설서"""
        # 1단계: 관세율표에서 HS코드 후보 선정
        tariff_start = time.time()
        hs_candidates = self.tariff_searcher.search_by_tariff_table(query, top_n=15)
        tariff_time = time.time() - tariff_start
        
        logger.log_actual("DATA", f"Tariff table search completed", 
                         f"{len(hs_candidates)} candidates in {tariff_time:.2f}s")
        
        if not hs_candidates:
            return []
            
        # 상위 후보들의 HS코드 리스트 생성
        candidate_codes = [item['hs_code'] for item in hs_candidates[:10]]
        logger.log_actual("INFO", f"Top HS candidates from tariff", 
                         f"{', '.join(candidate_codes[:5])}...")
        
        # 2단계: 해당 HS코드들을 해설서에서 검색
        manual_start = time.time()
        manual_results = []
        
        for candidate in hs_candidates[:10]:
            hs_code = candidate['hs_code']
            # 해설서에서 해당 HS코드 관련 내용 검색
            manual_content = self.search_manual_by_hs_code(hs_code, query)
            if manual_content:
                manual_results.append({
                    'hs_code': hs_code,
                    'tariff_similarity': candidate['similarity'],
                    'tariff_name': candidate['korean_name'],
                    'manual_content': manual_content,
                    'source': 'tariff_to_manual'
                })
        
        manual_time = time.time() - manual_start
        logger.log_actual("SUCCESS", f"Manual search for candidates completed", 
                         f"{len(manual_results)} results in {manual_time:.2f}s")
        
        return manual_results
    
    def search_manual_by_hs_code(self, hs_code, query):
        """특정 HS코드에 대한 해설서 내용 검색"""
        try:
            explanation, type_explanation, number_explanation = lookup_hscode(hs_code, 'knowledge/grouped_11_end.json')
            
            content = ""
            if explanation and explanation.get('text'):
                content += f"부 해설: {explanation['text']}\n"
            if type_explanation and type_explanation.get('text'):
                content += f"류 해설: {type_explanation['text']}\n"
            if number_explanation and number_explanation.get('text'):
                content += f"호 해설: {number_explanation['text']}\n"
                
            return content if content else None
        except:
            return None
    
    def direct_manual_search(self, query, logger):
        """경로 2: 해설서 직접 검색 (기존 방법)"""
        manual_start = time.time()
        
        # 기존 multi-agent 방식 활용
        direct_results = []
        for i in range(5):  # 5개 그룹 검색
            group_results = self.hs_manager.search_domestic_group(query, i, max_results=2)
            for result in group_results:
                direct_results.append({
                    'source_group': i,
                    'content': result,
                    'source': 'direct_manual'
                })
        
        manual_time = time.time() - manual_start
        logger.log_actual("SUCCESS", f"Direct manual search completed", 
                         f"{len(direct_results)} results in {manual_time:.2f}s")
        
        return direct_results
    
    def extract_hs_codes_from_content(self, content):
        """해설서 내용에서 HS코드 추출"""
        if isinstance(content, dict):
            text_content = json.dumps(content, ensure_ascii=False)
        else:
            text_content = str(content)
            
        # HS코드 패턴 추출
        codes = extract_hs_codes(text_content)
        return codes[:3]  # 최대 3개만
    
    def consolidate_results(self, path1_results, path2_results, logger):
        """두 경로의 결과를 종합"""
        consolidation_start = time.time()
        
        # 가중치 설정
        TARIFF_WEIGHT = 0.4  # 관세율표 경로 가중치
        MANUAL_WEIGHT = 0.6  # 해설서 직접 경로 가중치
        
        final_scores = defaultdict(float)
        result_details = {}
        
        # 경로 1 결과 처리 (관세율표 → 해설서)
        for result in path1_results:
            hs_code = result['hs_code']
            # 관세율표 유사도 * 가중치
            score = result['tariff_similarity'] * TARIFF_WEIGHT
            final_scores[hs_code] += score
            
            if hs_code not in result_details:
                result_details[hs_code] = {
                    'hs_code': hs_code,
                    'tariff_name': result.get('tariff_name', ''),
                    'manual_content': result.get('manual_content', ''),
                    'path1_score': score,
                    'path2_score': 0,
                    'sources': ['tariff_to_manual']
                }
            else:
                result_details[hs_code]['sources'].append('tariff_to_manual')
        
        # 경로 2 결과 처리 (해설서 직접)
        for result in path2_results:
            # HS코드 추출 로직 (해설서 내용에서)
            extracted_codes = self.extract_hs_codes_from_content(result['content'])
            
            for hs_code in extracted_codes:
                # 해설서 직접 검색 점수 (빈도 기반)
                score = 0.5 * MANUAL_WEIGHT  # 기본 점수
                final_scores[hs_code] += score
                
                if hs_code not in result_details:
                    result_details[hs_code] = {
                        'hs_code': hs_code,
                        'tariff_name': '',
                        'manual_content': str(result['content']),
                        'path1_score': 0,
                        'path2_score': score,
                        'sources': ['direct_manual']
                    }
                else:
                    result_details[hs_code]['path2_score'] += score
                    if 'direct_manual' not in result_details[hs_code]['sources']:
                        result_details[hs_code]['sources'].append('direct_manual')
        
        # 최종 순위 정렬
        sorted_results = sorted(final_scores.items(), key=lambda x: x[1], reverse=True)
        
        consolidation_time = time.time() - consolidation_start
        logger.log_actual("SUCCESS", f"Results consolidation completed", 
                         f"{len(sorted_results)} unique HS codes in {consolidation_time:.2f}s")
        
        # 상위 5개 결과 반환
        top_results = []
        for hs_code, final_score in sorted_results[:5]:
            if hs_code in result_details:
                details = result_details[hs_code]
                details['final_score'] = final_score
                details['confidence'] = 'HIGH' if len(details['sources']) > 1 else 'MEDIUM'
                top_results.append(details)
        
        return top_results
    
    def create_enhanced_context(self, search_results):
        """검색 결과를 컨텍스트로 변환"""
        context = ""
        
        for i, result in enumerate(search_results, 1):
            context += f"\n=== 후보 {i}: HS코드 {result['hs_code']} ===\n"
            context += f"신뢰도: {result['confidence']}\n"
            context += f"최종점수: {result['final_score']:.3f}\n"
            
            if result['tariff_name']:
                context += f"관세율표 품목명: {result['tariff_name']}\n"
            
            context += f"검색경로: {', '.join(result['sources'])}\n"
            
            if result['manual_content']:
                context += f"해설서 내용:\n{result['manual_content'][:500]}...\n"
            
            context += "\n"
        
        return context

def handle_hs_manual_with_parallel_search(user_input, context, hs_manager, logger):
    """병렬 검색을 활용한 HS 해설서 분석"""
    
    # 병렬 검색 수행
    parallel_searcher = ParallelHSSearcher(hs_manager)
    search_results = parallel_searcher.parallel_search(user_input, logger)
    
    # 결과를 컨텍스트로 변환
    enhanced_context = parallel_searcher.create_enhanced_context(search_results)
    
    logger.log_actual("INFO", f"Enhanced context prepared", f"{len(enhanced_context)} chars")
    
    # Gemini에 전달할 프롬프트 구성
    prompt = f"""{context}

[병렬 검색 결과]
{enhanced_context}

사용자 질문: {user_input}

위의 병렬 검색 결과를 바탕으로 다음을 포함하여 답변해주세요:

1. **가장 적합한 HS 코드 추천**
   - 최고 신뢰도의 HS코드와 그 근거
   - 관세율표 품목명과 해설서 설명 종합

2. **분류 근거 및 분석**
   - 관세율표 기반 검색 결과
   - 해설서 기반 검색 결과
   - 두 검색 경로의 일치성 분석

3. **신뢰도 평가**
   - HIGH: 두 검색 경로 모두에서 발견
   - MEDIUM: 한 검색 경로에서만 발견
   - 각 후보의 신뢰도와 점수

4. **추가 고려사항**
   - 유사 품목과의 구분 기준
   - 분류 시 주의점
   - 필요 시 추가 정보 요청 사항

답변은 전문적이면서도 이해하기 쉽게 작성해주세요.
"""
    
    # Gemini 처리
    logger.log_actual("AI", "Processing with enhanced parallel search context...")
    ai_processing_start = time.time()
    
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )
    
    ai_processing_time = time.time() - ai_processing_start
    final_answer = clean_text(response.text)
    
    logger.log_actual("SUCCESS", "Gemini processing completed", 
                     f"{ai_processing_time:.2f}s, input: {len(prompt)} chars, output: {len(final_answer)} chars")
    
    return final_answer

# 질문 유형 분류 함수 (LLM 기반)
def classify_question(user_input):
    """
    LLM(Gemini)을 활용하여 사용자의 질문을 아래 네 가지 유형 중 하나로 분류합니다.
    - 'web_search': 물품 개요, 용도, 기술개발, 무역동향, 산업동향 등
    - 'hs_classification': HS 코드, 품목분류, 관세 등
    - 'hs_manual': HS 해설서 본문 심층 분석
    - 'overseas_hs': 해외(미국/EU) HS 분류 사례
    """
    system_prompt = """
아래는 HS 품목분류 전문가를 위한 질문 유형 분류 기준입니다.

질문 유형:
1. "web_search" : "뉴스", "최근", "동향", "해외", "산업, 기술, 무역동향" 등 일반 정보 탐색이 필요한 경우.
2. "hs_classification": HS 코드, 품목분류, 관세, 세율 등 HS 코드 관련 정보가 필요한 경우.
3. "hs_manual": HS 해설서 본문 심층 분석이 필요한 경우.
4. "overseas_hs": "미국", "해외", "외국", "US", "America", "EU", "유럽" 등 해외 HS 분류 사례가 필요한 경우.
5. "hs_manual_raw": HS 코드만 입력하여 해설서 원문을 보고 싶은 경우.

아래 사용자 질문을 읽고, 반드시 위 다섯 가지 중 하나의 유형만 한글이 아닌 소문자 영문으로 답변하세요.
질문: """ + user_input + """\n답변:"""

    response = client.models.generate_content(
        model="gemini-2.0-flash", # 또는 최신 모델로 변경 가능
        contents=system_prompt,
        )
    answer = response.text.strip().lower()
    # 결과가 정확히 네 가지 중 하나인지 확인
    if answer in ["web_search", "hs_classification", "hs_manual", "overseas_hs", "hs_manual_raw"]:
        return answer
    # 예외 처리: 분류 실패 시 기본값
    return "hs_classification"

# 질문 유형별 처리 함수
def handle_web_search(user_input, context, hs_manager):
    # 웹검색 전용 컨텍스트로 수정
    web_context = """당신은 HS 품목분류 전문가입니다. 
사용자의 질문에 대해 최신 웹 정보를 검색하여 물품개요, 용도, 기술개발, 무역동향, 산업동향 등의 정보를 제공해주세요.
국내 HS 분류 사례가 아닌 일반적인 시장 정보와 동향을 중심으로 답변해주세요."""
    
    grounding_tool = types.Tool(google_search=types.GoogleSearch())
    config = types.GenerateContentConfig(tools=[grounding_tool])
    
    prompt = f"{web_context}\n\n사용자: {user_input}\n"
    
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=config)
    
    return clean_text(response.text)

def handle_hs_classification_cases(user_input, context, hs_manager):
    """국내 HS 분류 사례 처리 (그룹별 Gemini + Head Agent)"""
    # 5개 그룹별로 각각 Gemini에 부분 답변 요청
    group_answers = []
    for i in range(5):  # 3 → 5로 변경
        relevant = hs_manager.get_domestic_context_group(user_input, i)
        prompt = f"{context}\n\n관련 데이터 (국내 관세청, 그룹{i+1}):\n{relevant}\n\n사용자: {user_input}\n"
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )
        group_answers.append(clean_text(response.text))

    # Head Agent가 5개 부분 답변을 취합하여 최종 답변 생성
    head_prompt = f"{context}\n\n아래는 국내 HS 분류 사례 데이터 5개 그룹별 분석 결과입니다. 각 그룹의 답변을 종합하여 최종 전문가 답변을 작성하세요.\n\n"
    for idx, ans in enumerate(group_answers):
        head_prompt += f"[그룹{idx+1} 답변]\n{ans}\n\n"
    head_prompt += f"\n사용자: {user_input}\n"
    head_response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=head_prompt
    )
    return clean_text(head_response.text)

def handle_hs_manual(user_input, context, hs_manager):
    # 예: HS 해설서 분석 전용 컨텍스트 추가
    manual_context = context + "\n(심층 해설서 분석 모드)"
    hs_codes = extract_hs_codes(user_input)
    explanations = get_hs_explanations(hs_codes) if hs_codes else ""
    prompt = f"{manual_context}\n\n관련 데이터:\n{explanations}\n\n사용자: {user_input}\n"
    # client.models.generate_content 사용
    response = client.models.generate_content(
        model="gemini-2.5-flash", # 모델명 단순화
        contents=prompt
    )
    return clean_text(response.text)

def handle_overseas_hs(user_input, context, hs_manager):
    """해외 HS 분류 사례 처리 (그룹별 Gemini + Head Agent)"""
    overseas_context = context + "\n(해외 HS 분류 사례 분석 모드)"
    
    # 5개 그룹별로 각각 Gemini에 부분 답변 요청
    group_answers = []
    for i in range(5):
        relevant = hs_manager.get_overseas_context_group(user_input, i)
        prompt = f"{overseas_context}\n\n관련 데이터 (해외 관세청, 그룹{i+1}):\n{relevant}\n\n사용자: {user_input}\n"
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )
        group_answers.append(clean_text(response.text))

    # Head Agent가 5개 부분 답변을 취합하여 최종 답변 생성
    head_prompt = f"{overseas_context}\n\n아래는 해외 HS 분류 사례 데이터 5개 그룹별 분석 결과입니다. 각 그룹의 답변을 종합하여 최종 전문가 답변을 작성하세요.\n\n"
    for idx, ans in enumerate(group_answers):
        head_prompt += f"[그룹{idx+1} 답변]\n{ans}\n\n"
    head_prompt += f"\n사용자: {user_input}\n"
    head_response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=head_prompt
    )
    return clean_text(head_response.text)