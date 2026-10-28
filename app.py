import os
import json
import ollama
from datetime import datetime, timedelta
from flask import Flask, jsonify, send_from_directory, request, Response
from search_engines import google_search
from typing import List, Dict
import time
import requests


# --- 모듈 임포트 ---
from crawler import get_news_data
try:
    from product_recommender import recommend_product
except ImportError:
    def recommend_product(articles: List[Dict] = None):
        print("⚠️ 'product_recommender' 모듈을 찾을 수 없습니다. 더미 함수를 사용합니다.")
        return {"type": "404", "name": "상품추천 사항 없음", "description": "상품 추천 모듈을 찾을 수 없습니다."}

# --- Flask 앱 및 설정 ---
app = Flask(__name__, static_folder='static')
CACHE_FILE = 'news_cache.json'
CACHE_DURATION_SECONDS = 4 * 60 * 60

# --- LLM 및 검색 유틸리티 ---
def call_llm(model, prompt, is_json=False):
    """Ollama를 호출하는 범용 함수"""
    print(f"🤖 Ollama({model}) 호출 중...")
    try:
        response = ollama.chat(
            model=model,
            messages=[{'role': 'user', 'content': prompt}],
            format='json' if is_json else ''
        )
        content = response['message']['content']
        print("✅ Ollama 응답 수신 완료")
        return json.loads(content) if is_json else content
    except Exception as e:
        print(f"🚨 Ollama({model}) 호출 중 오류 발생: {e}")
        if is_json:
            return {"error": str(e)}
        return f"오류 발생: {e}"

def extract_keywords_from_question(question: str) -> List[str]:
    """심층질문에서 검색에 적합한 의미적 키워드/구를 추출합니다."""
    try:
        prompt = f"""다음 질문에서 검색엔진에 사용할 핵심 키워드나 구를 추출하세요. 
중요한 것은 질문의 맥락과 의미를 유지하면서 검색 가능한 구문을 만드는 것입니다.

질문: {question}

추출 규칙:
1. 단순히 단어를 분할하지 말고, 의미적으로 연결된 구문을 유지하세요
2. 질문의 핵심 의도를 담은 검색어를 생성하세요
3. 3-4개의 서로 다른 관점의 검색어를 만드세요

JSON 형식으로 반환하세요:
{{"keywords": ["검색어1", "검색어2", "검색어3"]}}

예시:
질문: "2차전지 관련 데이터 부족 이유는?"
결과: {{"keywords": ["2차전지 데이터 부족", "배터리 시장 정보 부족", "전기차 배터리 통계 부족", "2차전지 산업 데이터"]}}

질문: "반도체 공급망 위기가 자동차 산업에 미치는 영향은?"
결과: {{"keywords": ["반도체 공급망 위기 자동차", "칩 부족 자동차 생산", "반도체 부족 자동차 산업", "자동차 반도체 공급 문제"]}}"""

        result = call_llm('gemma3:1b', prompt, is_json=True)
        if isinstance(result, dict) and 'keywords' in result:
            keywords = result['keywords'][:4]  # 최대 4개로 제한
            # 키워드가 너무 짧거나 의미없는 경우 필터링
            filtered_keywords = []
            for kw in keywords:
                if len(kw.strip()) >= 5 and kw.strip() != question.strip():
                    filtered_keywords.append(kw.strip())
            
            if filtered_keywords:
                return filtered_keywords
            else:
                # 백업: 질문 자체를 사용하되 적절히 단축
                return [question[:80]]
        else:
            # 백업: 질문 자체를 사용
            return [question[:80]]
    except Exception as e:
        print(f"키워드 추출 실패: {e}")
        return [question[:80]]

import re, time
import requests
from typing import List, Dict
from urllib.parse import urlparse

# 검색 시 사용할 공통 헤더(403/봇차단 회피에 도움)
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/123.0.0.0 Safari/537.36"
)
HEADERS = {"User-Agent": USER_AGENT}
BAD_HOSTS = ("google.", "zhihu.", "baidu.")  # 무의미/동의 페이지 필터

def _detect_country(query: str) -> str:
    # 한글 포함 시 KR, 그 외 US
    return "kr" if re.search(r"[\uac00-\ud7a3]", query) else "us"

def _filter_useful(items: List[Dict]) -> List[Dict]:
    out = []
    for it in items or []:
        u = (it.get("url") or "").strip()
        if not u:
            continue
        host = ""
        try:
            host = urlparse(u).hostname or ""
        except Exception:
            pass
        if any(b in host for b in BAD_HOSTS):
            continue
        out.append({
            "title": (it.get("title") or "").strip() or "(제목 없음)",
            "url": u,
            "preview_text": (it.get("preview_text") or "").strip()
        })
    return out

def _fetch_with_engine(mod, query: str, country: str, need: int, max_pages: int = 2) -> List[Dict]:
    """search_engines.{engine}.py 모듈 하나를 사용해 n개까지 수집"""
    results_all: List[Dict] = []
    url = mod.get_search_url(query, latest=True, country=country)
    for _ in range(max_pages):
        resp = requests.get(url, timeout=7, headers=HEADERS)
        html = resp.text
        results, next_url = mod.extract_search_results(html, url)  # ← 공식 API
        results_all.extend(_filter_useful(results))
        if len(results_all) >= need or not next_url:
            break
        url = next_url
        time.sleep(0.2)  # 과도한 연속요청 방지
    return results_all[:need]

# app.py 상단에 추가/정리
import re, time, requests
from typing import List, Dict
from urllib.parse import urlparse, urljoin

# Bing 등에서 봇차단/동의페이지 회피에 도움이 되는 기본 헤더
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": UA,
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
BAD_HOSTS = ("consent.google", "google.com/sorry", "zhihu.com", "baidu.com")

def _is_korean(text: str) -> bool:
    return bool(re.search(r"[가-힣]", text or ""))

def _filter_useful(items: List[Dict]) -> List[Dict]:
    out = []
    for it in items or []:
        u = (it.get("url") or "").strip()
        if not u:
            continue
        try:
            host = urlparse(u).hostname or ""
        except Exception:
            host = ""
        if any(b in host for b in BAD_HOSTS):
            continue
        out.append({
            "title": (it.get("title") or "").strip() or "(제목 없음)",
            "url": u,
            "preview_text": (it.get("preview_text") or "").strip()
        })
    return out

def _fetch_with_engine(mod, query: str, country: str, need: int,
                       latest: bool, max_pages: int = 2, sleep_secs: float = 0.25) -> List[Dict]:
    """search_engines.{engine} 모듈 하나로 n개까지 수집"""
    url = mod.get_search_url(query, latest=latest, country=country)
    all_items: List[Dict] = []

    for _ in range(max_pages):
        resp = requests.get(url, headers=HEADERS, timeout=8, allow_redirects=True)
        if resp.status_code != 200:
            break

        html = resp.text
        results, next_url = mod.extract_search_results(html, url)  # 패키지 공식 사용법
        all_items.extend(_filter_useful(results))
        if len(all_items) >= need or not next_url:
            break

        # next_url이 상대경로일 수 있어 보정
        if next_url.startswith("/"):
            next_url = urljoin(url, next_url)
        url = next_url
        time.sleep(sleep_secs)

    return all_items[:need]

def search_web(query: str, num_results: int = 5) -> List[Dict]:
    """
    search_engines만 사용한 캐스케이드:
    1) Bing(Web, latest=False) → 2) Yahoo(Web) → 3) Bing News → 4) Yahoo News
    5) Ask(Web) → 6) Dogpile(Web) → 7) Google(Web, 최후순위)
    """
    print(f"🔍 웹 검색 수행 (search_engines cascade): '{query}'")
    country = "kr" if _is_korean(query) else "us"

    try:
        from search_engines import (
            bing_search, yahoo_search, bing_news, yahoo_news,
            ask_search, dogpile_search, google_search
        )
    except Exception as e:
        print(f"🚨 search_engines import 오류: {e}")
        return []

    ENGINE_PLAN = [
        ("Bing",        bing_search,   {"latest": False}),
        ("Yahoo",       yahoo_search,  {"latest": True}),
        ("BingNews",    bing_news,     {"latest": True}),
        ("YahooNews",   yahoo_news,    {"latest": True}),
        ("Ask",         ask_search,    {"latest": True}),
        ("Dogpile",     dogpile_search,{"latest": True}),
        ("Google",      google_search, {"latest": True}),  # 종종 동의/차단 → 최후순위
    ]

    for name, mod, opts in ENGINE_PLAN:
        try:
            items = _fetch_with_engine(
                mod, query, country, num_results,
                latest=opts.get("latest", True),
                max_pages=2
            )
            print(f"  → {name} hit: {len(items)}")
            if items:
                return items
        except Exception as e:
            print(f"  → {name} 실패: {e}")
            continue

    print("  → 모든 엔진 무응답/무의미 결과")
    return []



def get_strategy_from_llm(articles: list) -> dict:
    """Ollama를 사용하여 여러 뉴스 요약본을 바탕으로 투자 전략을 생성합니다."""
    news_context = "\n\n".join(
        [f"뉴스 제목: {a.get('title', '')}\n요약: {a.get('summary', '')}" for a in articles]
    )
    prompt = f"""
    ### 지시:
    당신은 펀드매니저 수준의 금융 데이터 분석가입니다. 아래 제공된 최신 뉴스 기사들의 요약본을 바탕으로, '원인 분석', '투자 전략', '결론 및 리스크' 형식에 맞춰 투자 전략 보고서를 작성해 주십시오. 답변은 반드시 한국어로, 그리고 다음 JSON 형식으로만 제공해야 합니다.
    ### 분석할 뉴스 요약:
    {news_context}
    ### 출력 형식 (JSON):
    {{
      "cause": "현재 금융 시장 상황에 대한 원인 분석.",
      "effect": "구체적인 투자 전략 제시.",
      "conclusion": "전략에 대한 결론 및 잠재적 리스크 요약."
    }}
    """
    try:
        strategy_data = call_llm('qwen3:8b', prompt, is_json=True)
        if "error" in strategy_data:
            raise Exception(strategy_data["error"])
        return strategy_data
    except Exception as e:
        print(f"🚨 투자 전략 생성 중 오류 발생: {e}")
        return {
            "cause": "오류",
            "effect": "AI 투자 전략 모델을 호출하는 중 문제가 발생했습니다.",
            "conclusion": f"오류 상세 정보: {str(e)}"
        }

# --- API 라우팅 ---
@app.route('/')
def serve_index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/api/trending-news')
def trending_news():
    news_data = []
    force_refresh = request.args.get('force_refresh', 'false').lower() == 'true'
    try:
        use_cache = False
        if os.path.exists(CACHE_FILE) and not force_refresh:
            file_mod_time = datetime.fromtimestamp(os.path.getmtime(CACHE_FILE))
            if datetime.now() - file_mod_time < timedelta(seconds=CACHE_DURATION_SECONDS):
                print("✅ 캐시된 뉴스 데이터를 사용합니다.")
                with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                    news_data = json.load(f)
                use_cache = True
        
        if not use_cache:
            if force_refresh: print("🔄 새로고침 요청으로 새로운 데이터를 수집하고 요약합니다.")
            else: print("✨ 캐시가 없거나 만료되어 새로운 데이터를 수집하고 요약합니다.")
            news_data = get_news_data()
            if news_data and "error" not in news_data[0].get("id", ""):
                with open(CACHE_FILE, 'w', encoding='utf-8') as f:
                    json.dump(news_data, f, ensure_ascii=False, indent=4)
                print(f"💾 새로운 뉴스 {len(news_data)}개를 캐시에 저장했습니다.")
    
    except Exception as e:
        print(f"🚨 /api/trending-news 처리 중 오류 발생: {e}")
        return jsonify({"detail": "뉴스 데이터 로딩 중 서버 오류가 발생했습니다."}), 500
    
    # ---! 오류 수정: 어떤 경우에도 반드시 jsonify를 통해 응답을 반환하도록 수정 !---
    return jsonify(news_data)


@app.route('/api/financial-strategy', methods=['GET', 'POST'])
def financial_strategy():
    if request.method == 'GET':
        # SSE 스트림 방식
        def generate():
            try:
                # POST 데이터는 별도로 받아야 함
                yield f"data: {json.dumps({'type': 'progress', 'step': 1, 'message': '🤖 Ollama(qwen3:8b) 호출 중...'}, ensure_ascii=False)}\n\n"
                
                # 임시로 빈 전략 반환 (실제로는 POST 데이터가 필요)
                strategy = {
                    "cause": "분석할 뉴스 데이터가 필요합니다.",
                    "effect": "Feed 탭에서 뉴스를 선택해주세요.",
                    "conclusion": "뉴스 선택 후 다시 시도해주세요."
                }
                
                yield f"data: {json.dumps({'type': 'complete', 'strategy': strategy, 'products': []}, ensure_ascii=False)}\n\n"
                
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
        
        return Response(generate(), mimetype='text/event-stream')
    
    else:
        # POST 방식 - 기존 방식 유지
        try:
            data = request.get_json()
            selected_articles = data.get('articles', []) if data else []
            
            if not selected_articles or len(selected_articles) == 0:
                return jsonify({"detail": "분석할 기사를 1개 이상 선택해야 합니다."}), 400
            
            strategy = get_strategy_from_llm(selected_articles)
            product = recommend_product(selected_articles)
            strategy["recommended_product"] = product
            return jsonify(strategy)
        except Exception as e:
            print(f"🚨 /api/financial-strategy 처리 중 오류 발생: {e}")
            return jsonify({"detail": "전략 수립 중 서버에서 오류가 발생했습니다."}), 500

@app.route('/api/financial-strategy-stream', methods=['POST'])
def financial_strategy_stream():
    def generate():
        try:
            selected_articles = request.get_json()
            if not selected_articles or not isinstance(selected_articles, list) or len(selected_articles) == 0:
                yield f"data: {json.dumps({'error': '분석할 기사를 1개 이상 선택해야 합니다.'}, ensure_ascii=False)}\n\n"
                return

            start_time = time.time()
                        # 1단계: 분석 시작
            yield f"data: {json.dumps({'type': 'progress', 'step': 1, 'progress': 25, 'message': '🤖 Ollama(qwen3:8b) 호출 중...'}, ensure_ascii=False)}\n\n"
            
            # 2단계: 전략 분석
            def progress_callback(msg):
                return f"data: {json.dumps({'type': 'log', 'message': msg}, ensure_ascii=False)}\n\n"
            
            strategy = get_strategy_from_llm_with_logging(selected_articles, generate_callback=progress_callback)
            
            yield f"data: {json.dumps({'type': 'progress', 'step': 2, 'progress': 50, 'message': '✅ Ollama 응답 수신 완료'}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'progress', 'step': 3, 'progress': 75, 'message': f'🤖 Ollama 호출: {len(selected_articles)}개 기사 기반 시장 국면 분석 요청'}, ensure_ascii=False)}\n\n"           
            # 3단계: 상품 추천
            product = recommend_product(selected_articles)
            
            yield f"data: {json.dumps({'type': 'progress', 'step': 4, 'progress': 100, 'message': '✅ Ollama 분석 완료: 시장 국면 분석 및 상품 추천 완료'}, ensure_ascii=False)}\n\n"
            
            # 최종 결과
            strategy["recommended_product"] = product
            elapsed = int(time.time() - start_time)
            
            yield f"data: {json.dumps({'type': 'result', 'data': strategy, 'elapsed': elapsed}, ensure_ascii=False)}\n\n"
            
        except Exception as e:
            print(f"🚨 /api/financial-strategy-stream 처리 중 오류 발생: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': f'전략 수립 중 오류가 발생했습니다: {str(e)}'}, ensure_ascii=False)}\n\n"

    return Response(
        generate(),
        mimetype='text/event-stream; charset=utf-8',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',
        }
    )

def get_strategy_from_llm_with_logging(articles: list, generate_callback=None) -> dict:
    """로깅 기능이 추가된 투자 전략 생성 함수"""
    news_context = "\n\n".join(
        [f"뉴스 제목: {a.get('title', '')}\n요약: {a.get('summary', '')}" for a in articles]
    )
    prompt = f"""
    ### 지시:
    당신은 펀드매니저 수준의 금융 데이터 분석가입니다. 아래 제공된 최신 뉴스 기사들의 요약본을 바탕으로, '원인 분석', '투자 전략', '결론 및 리스크' 형식에 맞춰 투자 전략 보고서를 작성해 주십시오. 답변은 반드시 한국어로, 그리고 다음 JSON 형식으로만 제공해야 합니다.
    ### 분석할 뉴스 요약:
    {news_context}
    ### 출력 형식 (JSON):
    {{
      "cause": "현재 금융 시장 상황에 대한 원인 분석.",
      "effect": "구체적인 투자 전략 제시.",
      "conclusion": "전략에 대한 결론 및 잠재적 리스크 요약."
    }}
    """
    try:
        if generate_callback:
            generate_callback("🤖 Ollama 호출: 투자 전략 분석 요청")
        
        strategy_data = call_llm('qwen3:8b', prompt, is_json=True)
        
        if generate_callback:
            generate_callback("✅ Ollama 분석 완료: 투자 전략 생성")
        
        if "error" in strategy_data:
            raise Exception(strategy_data["error"])
        return strategy_data
    except Exception as e:
        print(f"🚨 투자 전략 생성 중 오류 발생: {e}")
        return {
            "cause": "오류",
            "effect": "AI 투자 전략 모델을 호출하는 중 문제가 발생했습니다.",
            "conclusion": f"오류 상세 정보: {str(e)}"
        }

@app.route('/api/deep-research')
def deep_research():
    from datetime import datetime
    query = request.args.get('query')
    is_agentic = request.args.get('agentic', 'false').lower() == 'true'
    feedback_loops = int(request.args.get('feedback_loops', '5'))
    debug_mode = request.args.get('debug', '0') in ('1', 'true', 'yes')

    if not query:
        return Response(json.dumps({"error": "리서치 주제를 입력해야 합니다."}),
                        status=400, mimetype='application/json')

    def generate():
        start_time = time.time()
        research_context = {
            'query': query,
            'collected_sources': [],
            'analysis_steps': [],
            'insights': [],
            'actions_taken': []
        }
        
        try:
            # === 1단계: 초기 정보 수집 ===
            yield f"data: {json.dumps({'type': 'progress', 'status': '🔍 초기 정보 수집 시작', 'progress': 10, 'step': 1}, ensure_ascii=False)}\n\n"
            
            # 뉴스 데이터 수집 (8개 고정)
            news_articles = []
            try:
                news_articles = get_news_data(query, page_size=8)
                research_context['collected_sources'].extend([{'type': 'news', 'data': a} for a in news_articles])
                yield f"data: {json.dumps({'type': 'news_collected', 'articles': news_articles}, ensure_ascii=False)}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'type': 'action_log', 'action': f'뉴스 수집 실패: {str(e)}'}, ensure_ascii=False)}\n\n"

            # 웹 검색 결과 수집
            web_results = []
            try:
                web_results = search_web(query, num_results=6)
                research_context['collected_sources'].extend([{'type': 'web', 'data': r} for r in web_results])
                yield f"data: {json.dumps({'type': 'web_search_results', 'results': web_results}, ensure_ascii=False)}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'type': 'action_log', 'action': f'웹 검색 실패: {str(e)}'}, ensure_ascii=False)}\n\n"

            yield f"data: {json.dumps({'type': 'progress', 'status': '📊 1단계 완료: 기초 자료 수집', 'progress': 25, 'step': 2}, ensure_ascii=False)}\n\n"

            # === 2단계: 초기 분석 및 이해 (gemma3:1b 사용) ===
            yield f"data: {json.dumps({'type': 'progress', 'status': '🤖 초기 분석 및 요약 생성', 'progress': 35, 'step': 2}, ensure_ascii=False)}\n\n"
            
            initial_context = ""
            if news_articles:
                initial_context += "=== 뉴스 정보 ===\n" + "\n".join([f"- {a.get('title', '')}: {a.get('summary', '')}" for a in news_articles[:4]])
            if web_results:
                initial_context += "\n\n=== 웹 검색 정보 ===\n" + "\n".join([f"- {r.get('title', '')}: {r.get('preview_text', '')}" for r in web_results[:4]])

            summary_prompt = f"다음 정보를 바탕으로 '{query}'에 대한 간단한 요약을 작성하세요:\n\n{initial_context}"
            initial_summary = call_llm('gemma3:1b', summary_prompt)
            
            yield f"data: {json.dumps({'type': 'analysis_update', 'analysis_type': 'initial_summary', 'content': initial_summary}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'action_log', 'action': 'gemma3:1b 모델로 초기 요약 생성 완료'}, ensure_ascii=False)}\n\n"

            if not is_agentic:
                # 비-Agentic 모드: 간단한 보고서 생성
                yield f"data: {json.dumps({'type': 'progress', 'status': '📝 최종 보고서 생성', 'progress': 80, 'step': 3}, ensure_ascii=False)}\n\n"
                
                final_prompt = f"""'{query}'에 대한 최종 보고서를 작성하세요.

수집된 정보:
{initial_context}

초기 분석:
{initial_summary}

구조화된 보고서를 작성해주세요."""
                
                final_report = call_llm('qwen3:8b', final_prompt)
                
                total_sources = len(news_articles) + len(web_results)
                elapsed = int(time.time() - start_time)
                
                yield f"data: {json.dumps({'type': 'final_result', 'report': final_report, 'summary': initial_summary, 'total_sources': total_sources, 'elapsed': elapsed, 'insights': [initial_summary]}, ensure_ascii=False)}\n\n"
                return

            # === Agentic 모드: 심층 분석 진행 ===
            yield f"data: {json.dumps({'type': 'progress', 'status': '🧠 심층 사고 및 분석 계획 수립', 'progress': 45, 'step': 3}, ensure_ascii=False)}\n\n"
            
            # 3단계: 비판적 분석 및 추가 질문 생성 (qwen3:8b 사용)
            critique_prompt = f"""당신은 전문 분석가입니다. 다음 정보와 초기 분석을 비판적으로 검토하고, 더 깊이 있는 분석을 위한 구체적인 질문 3-5개를 생성하세요.

주제: {query}
초기 분석: {initial_summary}
수집된 정보: {initial_context}

JSON 형식으로 질문들을 반환하세요:
{{"questions": ["질문1", "질문2", "질문3"]}}"""

            questions_response = call_llm('qwen3:8b', critique_prompt, is_json=True)
            deep_questions = questions_response.get('questions', []) if isinstance(questions_response, dict) else []
            
            yield f"data: {json.dumps({'type': 'analysis_update', 'analysis_type': 'deep_questions', 'content': deep_questions}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'action_log', 'action': f'qwen3:8b 모델로 {len(deep_questions)}개 심층 질문 생성'}, ensure_ascii=False)}\n\n"

            # 4단계: 추가 정보 탐색 (키워드 기반)
            yield f"data: {json.dumps({'type': 'progress', 'status': '🔍 심층 정보 탐색 진행', 'progress': 60, 'step': 4}, ensure_ascii=False)}\n\n"
            
            additional_sources = []
            max_questions = min(len(deep_questions), feedback_loops)  # 피드백 루프 횟수만큼 처리
            
            for i, question in enumerate(deep_questions[:max_questions]):
                try:
                    yield f"data: {json.dumps({'type': 'thinking', 'content': f'질문 {i+1} 분석 중: {question}'}, ensure_ascii=False)}\n\n"
                    
                    # 질문에서 키워드 추출
                    keywords = extract_keywords_from_question(question)
                    yield f"data: {json.dumps({'type': 'thinking', 'content': f'추출된 키워드: {keywords}'}, ensure_ascii=False)}\n\n"
                    
                    # 각 키워드로 검색 수행
                    for j, keyword in enumerate(keywords[:3]):  # 최대 3개 키워드
                        try:
                            yield f"data: {json.dumps({'type': 'thinking', 'content': f'키워드 검색 중: {keyword}'}, ensure_ascii=False)}\n\n"
                            search_results = search_web(keyword, num_results=2)
                            additional_sources.extend(search_results)
                            research_context['collected_sources'].extend([{'type': 'additional', 'data': r} for r in search_results])
                            time.sleep(0.3)  # 검색 간격
                        except Exception as e:
                            yield f"data: {json.dumps({'type': 'thinking', 'content': f'키워드 {keyword} 검색 실패: {str(e)}'}, ensure_ascii=False)}\n\n"
                    
                except Exception as e:
                    yield f"data: {json.dumps({'type': 'thinking', 'content': f'질문 {i+1} 처리 실패: {str(e)}'}, ensure_ascii=False)}\n\n"

            yield f"data: {json.dumps({'type': 'web_search_results', 'results': additional_sources}, ensure_ascii=False)}\n\n"

            # 5단계: 종합 분석 및 인사이트 생성
            yield f"data: {json.dumps({'type': 'progress', 'status': '💡 종합 분석 및 인사이트 도출', 'progress': 75, 'step': 5}, ensure_ascii=False)}\n\n"
            
            comprehensive_context = initial_context
            if additional_sources:
                comprehensive_context += "\n\n=== 추가 탐색 정보 ===\n" + "\n".join([f"- {r.get('title', '')}: {r.get('preview_text', '')}" for r in additional_sources])

            insights_prompt = f"""전문 애널리스트로서 다음 정보를 종합 분석하여 핵심 인사이트 3-5개를 도출하세요.

주제: {query}
종합 정보: {comprehensive_context}
심층 질문들: {deep_questions}

각 인사이트는 구체적이고 실용적이어야 합니다."""

            insights_text = call_llm('qwen3:8b', insights_prompt)
            insights = [insight.strip() for insight in insights_text.split('\n') if insight.strip() and not insight.strip().startswith('#')][:5]
            
            yield f"data: {json.dumps({'type': 'analysis_update', 'analysis_type': 'insights', 'content': insights}, ensure_ascii=False)}\n\n"

            # 6단계: 최종 보고서 생성
            yield f"data: {json.dumps({'type': 'progress', 'status': '📋 최종 보고서 작성', 'progress': 90, 'step': 6}, ensure_ascii=False)}\n\n"
            
            final_report_prompt = f"""최고 수준의 분석 보고서를 작성하세요.

주제: {query}
수집된 모든 정보: {comprehensive_context}
도출된 인사이트: {insights}
탐색한 질문들: {deep_questions}

다음 구조로 보고서를 작성하세요:
1. 요약
2. 주요 발견사항
3. 심층 분석
4. 결론 및 시사점

전문적이고 구체적인 내용으로 작성해주세요."""

            final_report = call_llm('qwen3:8b', final_report_prompt)
            
            # 최종 결과 전송
            total_sources = len(news_articles) + len(web_results) + len(additional_sources)
            elapsed = int(time.time() - start_time)
            
            yield f"data: {json.dumps({'type': 'final_result', 'report': final_report, 'summary': initial_summary, 'insights': insights, 'questions': deep_questions, 'total_sources': total_sources, 'elapsed': elapsed}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'action_log', 'action': f'분석 완료! 총 {total_sources}개 소스, {elapsed}초 소요'}, ensure_ascii=False)}\n\n"

        except Exception as e:
            print(f"🚨 /api/deep-research 처리 중 오류: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': f'리서치 중 오류가 발생했습니다: {e}'}, ensure_ascii=False)}\n\n"

    return Response(
        generate(),
        mimetype='text/event-stream; charset=utf-8',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',
        }
    )


# --- 서버 실행 ---
if __name__ == '__main__':
    print("🚀 AI 금융 리서치 서버를 시작합니다.")
    print("👉 웹 브라우저에서 http://127.0.0.1:5001 로 접속하세요.")
    app.run(host='127.0.0.1', port=5001, debug=False)