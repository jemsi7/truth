"""
product_recommender.py
~~~~~~~~~~~~~~~~~~~~~~~~

뉴스 기사의 맥락을 LLM으로 분석하여 시장 국면을 진단하고, 
해당 시점에 가장 적합한 최적의 금융 상품(주식, 채권, ETF, 예적금 등)을 지능적으로 추천하는 모듈.
"""

from __future__ import annotations

import os
import re
import json
import ollama
from functools import lru_cache
from typing import Dict, List, Optional

try:
    import pandas as pd
except ImportError:
    pd = None

MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(MODULE_DIR, "data")


# --- 1. LLM을 활용한 시장 국면 분석 ---
def analyze_market_scenario_with_llm(articles: List[Dict]) -> Dict:
    """Ollama를 사용하여 뉴스 기사들을 종합 분석하고 현재 시장 국면을 진단합니다."""
    news_context = "\n\n".join(
        [f"- 제목: {a.get('title', '')}\n  요약: {a.get('summary', '')}" for a in articles]
    )

    prompt = f"""
    ### 지시:
    당신은 최고의 금융 애널리스트입니다. 아래 뉴스 요약본들을 종합적으로 분석하여, 현재 시장 상황을 가장 잘 설명하는 단 하나의 '시장 국면'을 선택하고, 그렇게 판단한 '핵심 근거'를 1~2문장으로 요약해 주세요. 답변은 반드시 한국어로, 그리고 다음 JSON 형식으로만 제공해야 합니다.

    ### 선택 가능한 시장 국면:
    1. "안정 성장기": 경제 지표가 긍정적이고 시장이 점진적으로 상승하는 시기.
    2. "변동성 장세": 시장의 불확실성이 크고 주가 등락이 심한 시기.
    3. "금리 인상기": 중앙은행의 금리 인상 또는 긴축 정책이 예상되는 시기.
    4. "기술주 주도 장세": AI, 반도체 등 특정 기술 분야가 시장 상승을 이끄는 시기.
    5. "경기 둔화 우려": 경제 성장 둔화나 침체에 대한 우려가 커지는 시기.

    ### 분석할 뉴스 요약:
    {news_context}

    ### 출력 형식 (JSON):
    {{
      "scenario": "위 5가지 시장 국면 중 가장 적합한 것 하나",
      "rationale": "왜 그렇게 판단했는지에 대한 핵심적인 분석 근거"
    }}
    """

    try:
        print(f"🤖 Ollama 호출: {len(articles)}개 기사 기반 시장 국면 분석 요청")
        response = ollama.chat(
            model='qwen3:8b',
            messages=[{'role': 'user', 'content': prompt}],
            format='json'
        )
        analysis_result = json.loads(response['message']['content'])
        print(f"✅ Ollama 분석 완료: 시장 국면 '{analysis_result.get('scenario')}'")
        return analysis_result
    except Exception as e:
        print(f"🚨 Ollama 분석 중 오류 발생: {e}")
        return {
            "scenario": "분석 실패",
            "rationale": "시장 분석 모델 호출에 실패했습니다. 현재 시장 상황에 맞는 일반적인 추천을 제공합니다."
        }

# --- 2. 시장 국면 기반 지능형 상품 추천 로직 (LLM 활용) ---
def recommend_product_with_llm(scenario: str, rationale: str) -> Dict:
    """Ollama를 사용하여 분석된 시장 국면에 따라 최적의 금융 상품을 추천합니다."""
    prompt = f"""
    ### 지시:
    당신은 최고의 금융 애널리스트입니다. 주어진 시장 국면과 분석 근거를 바탕으로, 가장 적합한 하나의 금융 상품(주식, 채권, ETF, 예적금 등)을 추천해 주세요. 
    추천 상품은 실제 존재하는 한국 시장의 금융 상품(예: 삼성전자 주식, 국고채, KODEX ETF, 특정 은행 예적금 등) 중에서 선택해야 합니다.
    추천 이유는 시장 국면과 연계하여 1~2문장으로 설명해 주세요. 답변은 반드시 한국어로, 다음 JSON 형식으로만 제공해야 합니다.

    ### 시장 국면:
    {scenario}

    ### 분석 근거:
    {rationale}

    ### 출력 형식 (JSON):
    {{
      "type": "상품 유형 (예: 주식, 채권, ETF, 예적금)",
      "name": "상품 이름",
      "description": "추천 이유와 상품 설명 (분석 근거 포함)"
    }}
    """

    try:
        print(f"🤖 Ollama 호출: 시장 국면 '{scenario}' 기반 상품 추천 요청")
        response = ollama.chat(
            model='qwen3:8b',
            messages=[{'role': 'user', 'content': prompt}],
            format='json'
        )
        recommendation = json.loads(response['message']['content'])
        # 분석 근거를 추천 설명에 추가
        recommendation["description"] = f"【AI 분석】 {rationale}\n\n{recommendation.get('description', '')}"
        print(f"✅ Ollama 추천 완료: 상품 '{recommendation.get('name')}'")
        return recommendation
    except Exception as e:
        print(f"🚨 Ollama 추천 중 오류 발생: {e}")
        return {
            "type": "Error",
            "name": "404 Not Found",
            "description": f"【AI 분석】 {rationale}\n\n시장 분석에 실패했습니다. 상품 추천을 제공할 수 없습니다."
        }

# --- 3. 통합 추천 함수 ---
def recommend_product(articles: List[Dict]) -> Dict:
    """
    분석된 시장 국면에 따라 최적의 금융 상품을 추천합니다. (더미 데이터 대신 LLM 활용)
    """
    analysis = analyze_market_scenario_with_llm(articles)
    scenario = analysis.get("scenario")
    rationale = analysis.get("rationale")
    
    # LLM을 통해 동적으로 상품 추천
    recommendation = recommend_product_with_llm(scenario, rationale)

    # 예적금의 경우 CSV 데이터 보완 (기존 로직 유지, 하지만 필수 아님)
    if recommendation["type"] == "예적금":
        deposits = _load_deposit_products()
        if deposits:
            high_rate_deposits = [p for p in deposits if p.get("rate")]
            if high_rate_deposits:
                alt_recommendation = max(high_rate_deposits, key=lambda p: p["rate"])
                recommendation = alt_recommendation
                recommendation["description"] = f"【AI 분석】 {rationale}\n\n{recommendation.get('description', '')}"

    return recommendation


# --- 기존 CSV 로더 및 유틸리티 함수 (변경 없음) ---
@lru_cache(maxsize=1)
def _load_deposit_products() -> List[Dict]:
    products: List[Dict] = []
    if pd is None: return products
    candidate_files = ["예적금상품.csv", "kb예적금.csv"]
    deposit_path = next((os.path.join(DATA_DIR, f) for f in candidate_files if os.path.exists(os.path.join(DATA_DIR, f))), None)
    if not deposit_path: return products
    
    encodings = ["utf-8-sig", "cp949", "euc-kr"]
    df = None
    for enc in encodings:
        try:
            df = pd.read_csv(deposit_path, encoding=enc)
            break
        except Exception:
            continue
    if df is None: return products
    
    for _, row in df.iterrows():
        name = row.get("상품명")
        if not isinstance(name, str): continue
        desc = row.get("상품 설명") or row.get("상품요약") or ""
        rate = None
        if pd.notna(row.get("최대이율")):
            try: rate = float(row.get("최대이율")) / 100.0
            except (TypeError, ValueError): rate = None
        if rate is None:
            rate = _parse_interest_string(row.get("금리"))
            
        products.append({"type": "예적금", "name": name.strip(), "description": desc.strip() if isinstance(desc, str) else "", "rate": rate, "raw_interest": row.get("금리")})
    return products

def _parse_interest_string(rate_str: str) -> Optional[float]:
    if not isinstance(rate_str, str): return None
    numbers = re.findall(r"\d+(?:\.\d+)?", rate_str)
    return max(float(n) for n in numbers) / 100.0 if numbers else None

__all__ = ["recommend_product"]