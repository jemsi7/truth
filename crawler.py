"""
뉴스 데이터를 가져와 요약하는 모듈.

DeepSearch API 대신 newsapi.org의 API를 사용하도록 수정되었습니다. 사용자는
미리 newsapi.org에서 발급받은 API 키를 `.env` 파일에 `NEWS_API_KEY` 또는
`NEWSAPI_KEY` 변수로 저장해야 합니다. 기존의 LLM 요약 기능은 그대로 유지하며,
경제·기술 관련 기사를 최근 7일 범위에서 가져와 요약합니다.
"""

import os
from datetime import datetime, timedelta
from typing import List, Dict

import requests
import ollama
from dotenv import load_dotenv


# .env 파일에서 환경 변수 로드
load_dotenv()

NEWS_API_KEY: str = os.getenv("NEWS_API_KEY") or os.getenv("NEWSAPI_KEY")
NEWS_API_URL: str = "https://newsapi.org/v2/everything"


def summarize_article_with_llm(content: str, title: str) -> str:
    """
    Ollama를 사용하여 개별 뉴스 기사의 내용을 한국어로 요약합니다.
    """
    content_limit = 2000
    truncated_content = content[:content_limit] if content else ""

    prompt = f"""
    ### 지시:
    당신은 금융 뉴스 에디터입니다. 다음 뉴스 기사를 전문적이고 간결하게 3~4문장으로 요약해 주세요. 핵심 내용만 한국어로 담아주세요.

    ### 뉴스 제목:
    {title}

    ### 뉴스 본문:
    {truncated_content}

    ### 요약:
    """

    try:
        print(f"  -> 📰 기사 요약 요청: '{title}'")
        response = ollama.chat(
            model='gemma3:1b',
            messages=[{'role': 'user', 'content': prompt}],
        )
        summary = response['message']['content']
        print(f"  <- ✅ 기사 요약 완료: '{title}'")
        return summary.strip()
    except Exception as e:
        print(f"  <- 🚨 기사 요약 중 오류 발생: {e}")
        return "AI 요약 생성 중 오류가 발생했습니다."


def get_news_data(query: str = None, page_size: int = 10) -> List[Dict[str, str]]:
    """
    지정된 키워드로 최근 7일간의 뉴스를 newsapi.org에서 가져와 요약합니다.
    query가 없으면 기본 금융 키워드를 사용합니다.

    Args:
        query (str, optional): 검색할 키워드. Defaults to None.
        page_size (int, optional): 가져올 기사 수. Defaults to 10.

    Returns:
        list: 요약된 뉴스 항목 리스트.
    """
    if not NEWS_API_KEY or NEWS_API_KEY == "your_newsapi_key_here":
        print("🚨 NEWS_API_KEY 환경 변수가 설정되지 않았습니다. 데모 데이터를 사용합니다.")
        # 데모 데이터 반환
        demo_articles = [
            {
                "id": "demo-1",
                "title": "코스피, 외국인 매수세에 상승 마감",
                "summary": "코스피가 외국인 투자자들의 매수세에 힘입어 상승 마감했습니다. 반도체와 자동차 업종이 상승을 주도했으며, 시장 전문가들은 긍정적인 전망을 내놓고 있습니다.",
                "url": "https://example.com/news1",
                "published_at": datetime.now().isoformat()
            },
            {
                "id": "demo-2", 
                "title": "한국은행, 기준금리 동결 결정",
                "summary": "한국은행이 기준금리를 현 수준에서 동결하기로 결정했습니다. 인플레이션 압력과 경제성장률을 종합적으로 고려한 결과로 분석됩니다.",
                "url": "https://example.com/news2",
                "published_at": (datetime.now() - timedelta(hours=2)).isoformat()
            },
            {
                "id": "demo-3",
                "title": "원달러 환율, 1,300원대 중반 등락",
                "summary": "원달러 환율이 1,300원대 중반에서 등락을 거듭하고 있습니다. 미국의 통화정책 변화와 국내 경제지표가 주요 변수로 작용하고 있습니다.",
                "url": "https://example.com/news3", 
                "published_at": (datetime.now() - timedelta(hours=4)).isoformat()
            },
            {
                "id": "demo-4",
                "title": "부동산 시장, 정부 정책에 따른 변화 주목",
                "summary": "정부의 부동산 정책 변화에 따라 시장 참여자들의 관심이 집중되고 있습니다. 전문가들은 신중한 접근이 필요하다고 조언하고 있습니다.",
                "url": "https://example.com/news4",
                "published_at": (datetime.now() - timedelta(hours=6)).isoformat()
            },
            {
                "id": "demo-5",
                "title": "국채 금리 상승, 채권 시장 변동성 확대",
                "summary": "국채 금리가 상승하면서 채권 시장의 변동성이 확대되고 있습니다. 투자자들은 포트폴리오 재조정을 검토하고 있는 상황입니다.",
                "url": "https://example.com/news5",
                "published_at": (datetime.now() - timedelta(hours=8)).isoformat()
            },
            {
                "id": "demo-6",
                "title": "글로벌 경제 불확실성 속 국내 증시 전망",
                "summary": "글로벌 경제의 불확실성이 지속되는 가운데 국내 증시에 대한 전망이 엇갈리고 있습니다. 전문가들은 선별적 투자 전략을 권고하고 있습니다.",
                "url": "https://example.com/news6",
                "published_at": (datetime.now() - timedelta(hours=10)).isoformat()
            },
            {
                "id": "demo-7",
                "title": "중소기업 금융 지원 정책 확대",
                "summary": "정부가 중소기업을 위한 금융 지원 정책을 확대하기로 했습니다. 저금리 대출과 보증 지원을 통해 경영 안정화를 도모할 예정입니다.",
                "url": "https://example.com/news7",
                "published_at": (datetime.now() - timedelta(hours=12)).isoformat()
            },
            {
                "id": "demo-8",
                "title": "디지털 화폐 시장 동향과 규제 방향",
                "summary": "디지털 화폐 시장이 급성장하면서 관련 규제 방향에 대한 관심이 높아지고 있습니다. 정부는 혁신과 안정성의 균형을 추구하고 있습니다.",
                "url": "https://example.com/news8",
                "published_at": (datetime.now() - timedelta(hours=14)).isoformat()
            }
        ]
        return demo_articles

    today = datetime.utcnow()
    seven_days_ago = today - timedelta(days=7)
    start_date = seven_days_ago.strftime('%Y-%m-%d')
    end_date = today.strftime('%Y-%m-%d')

    # 쿼리가 없으면 기본 금융 키워드 사용
    if not query:
        query = "경제 OR 금융 OR 코스피 OR 국채 OR 환율 OR 부동산"

    params = {
        "q": query, "from": start_date, "to": end_date,
        "sortBy": "publishedAt", "language": "ko",
        "pageSize": page_size, "apiKey": NEWS_API_KEY,
    }

    print(f"🔍 NewsAPI 호출 (주제: {query}): {NEWS_API_URL}")

    try:
        response = requests.get(NEWS_API_URL, params=params)
        response.raise_for_status()
        data = response.json()

        if data.get('status') != 'ok':
            message = data.get('message', '알 수 없는 오류')
            print(f"🚨 NewsAPI 응답 오류: {message}")
            return []

        articles = data.get('articles', [])
        if not articles:
            print(f"✅ 주제 '{query}'에 대한 뉴스가 없습니다.")
            return []

        print(f"\n✅ 총 {len(articles)}개 기사 수신 완료. LLM 요약을 시작합니다.")

        summarized_news: List[Dict[str, str]] = []
        for article in articles:
            content = article.get('content') or article.get('description') or ""
            if not content:
                continue

            title = article.get('title', '제목 없음')
            url = article.get('url', '#')
            published_at = article.get('publishedAt', '')

            summary = summarize_article_with_llm(content, title)

            summarized_news.append({
                "id": url, "title": title, "summary": summary,
                "url": url, "published_at": published_at
            })
        return summarized_news

    except requests.exceptions.HTTPError as http_err:
        print(f"🚨 뉴스 API HTTP 오류 발생: {http_err}")
        return []
    except Exception as e:
        print(f"🚨 get_news_data 함수에서 예외 발생: {e}")
        return []

if __name__ == "__main__":
    news_list = get_news_data()
    if news_list:
        print("\n--- 최종 요약 뉴스 ---")
        for news in news_list:
            print(f"\n✅ 제목: {news['title']}")
            print(f"   - 요약: {news['summary']}")
            print(f"   - 링크: {news['url']}")