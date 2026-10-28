const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

let selectedNewsArticles = []; // 선택된 뉴스 기사 저장 배열

function showToast(msg, timeout = 3000) {
  const t = $("#toast");
  if (t) {
    t.textContent = msg;
    t.classList.add("show");
    setTimeout(() => t.classList.remove("show"), timeout);
  } else {
    // toast 요소가 없으면 콘솔에 메시지 출력
    console.log("Toast:", msg);
    // 또는 alert 사용 (개발 중에만)
    // alert(msg);
  }
}

function setDarkMode(on) {
  document.documentElement.classList.toggle("dark", on);
  localStorage.setItem("dark_mode", on ? "1" : "0");
}

function initDark() {
  // 다크모드 기능 비활성화
}

async function apiFetch(path, options = {}) {
  const url = path.startsWith('/') ? path : `/${path}`;
  try {
    const res = await fetch(url, options);
    if (res.ok) return res.json();
    const errorData = await res.json();
    throw new Error(errorData.detail || "알 수 없는 오류가 발생했습니다.");
  } catch (e) {
    throw e;
  }
}

function renderSkeletonCards(target, count = 9) {
  target.innerHTML = Array(count).fill(0).map(() => `
    <div class="news-card">
        <div class="card-content">
            <div class="skeleton" style="height: 20px; width: 80%; margin-bottom: 8px;"></div>
            <div class="skeleton" style="height: 14px; width: 40%; margin-bottom: 12px;"></div>
            <div class="skeleton" style="height: 14px; width: 100%;"></div>
            <div class="skeleton" style="height: 14px; width: 90%; margin-top: 8px;"></div>
        </div>
        <div class="card-footer">
            <div class="skeleton" style="height: 24px; width: 24px; border-radius: 4px;"></div>
        </div>
    </div>`).join("");
}

function initTabs() {
  $$(".app-nav .nav-item").forEach(item => {
    item.addEventListener("click", () => {
      $$(".app-nav .nav-item").forEach(i => i.classList.remove("active"));
      item.classList.add("active");
      $$(".tabpanel").forEach(p => p.classList.remove("active"));
      const targetTab = $("#tab-" + item.dataset.tab);
      if (targetTab) {
          targetTab.classList.add("active");
      }
      if (item.dataset.tab === 'strategy') {
          updateStrategyTabDisplay();
      }
    });
  });
}

// ======== 뉴스 브리핑 (Feed) ========
async function loadNews(forceRefresh = false) {
  const status = $("#newsStatus");
  const list = $("#newsList");
  const progressContainer = $("#newsProgressContainer");
  const progressBar = $("#newsProgressBar");

  // 안전한 DOM 요소 접근
  if (!status || !list || !progressContainer || !progressBar) {
    console.error('Required DOM elements not found in loadNews');
    showToast("페이지 요소를 찾을 수 없습니다. 페이지를 새로고침해주세요.");
    return;
  }

  status.textContent = "최신 뉴스를 불러오는 중...";
  
  // 진행률 바 표시
  progressContainer.classList.remove('hidden');
  progressBar.style.width = "0%";
  
  // progressLabel과 progressCount를 직접 찾기
  const progressLabel = progressContainer.querySelector('.progress-label');
  const progressCount = progressContainer.querySelector('.progress-count');
  
  if (progressLabel) progressLabel.textContent = "뉴스 데이터 요청 중...";
  if (progressCount) progressCount.textContent = "0/0";
  
  // 새로고침하거나, 처음 로드할 때만 스켈레톤 UI 표시
  if(forceRefresh || list.innerHTML.trim() === ""){
    list.innerHTML = '';
    renderSkeletonCards(list, 9);
  }

  try {
    const apiUrl = forceRefresh ? '/api/trending-news?force_refresh=true' : '/api/trending-news';
    
    // 20% 진행률 - API 호출 시작
    progressBar.style.width = "20%";
    if (progressLabel) progressLabel.textContent = "서버에서 뉴스 데이터 수신 중...";
    
    const data = await apiFetch(apiUrl);
    
    if (!Array.isArray(data)) throw new Error("서버에서 잘못된 형식의 데이터를 받았습니다.");

    // 40% 진행률 - 데이터 수신 완료
    progressBar.style.width = "40%";
    if (progressLabel) progressLabel.textContent = "뉴스 데이터 처리 중...";
    if (progressCount) progressCount.textContent = `0/${data.length}`;

    status.textContent = `총 ${data.length}개의 최신 뉴스를 확인하세요. (최대 3개 선택 가능)`;
    list.innerHTML = ""; 

    if (data.length === 0) {
        list.innerHTML = `<p class="placeholder-text" style="grid-column: 1 / -1; text-align: center;">표시할 뉴스가 없습니다.</p>`;
        progressContainer.classList.add('hidden');
        return;
    }

    // 뉴스 카드 생성 (60% ~ 100%)
    const totalNews = data.length;
    for (let i = 0; i < totalNews; i++) {
      const article = data[i];
      const card = document.createElement("div");
      card.className = "news-card fade-in";
      const pubDate = new Date(article.published_at).toLocaleDateString('ko-KR');
      const isChecked = selectedNewsArticles.some(a => a.id === article.id);

      card.innerHTML = `
        <div class="card-content">
            <p class="meta">${article.url ? new URL(article.url).hostname : '출처 불명'} &middot; ${pubDate}</p>
            <h3><a href="${article.url}" target="_blank" rel="noopener noreferrer">${article.title}</a></h3>
            <p>${article.summary}</p>
        </div>
        <div class="card-footer">
            <label for="check-${article.id}" style="font-weight: 500; font-size: 14px; cursor:pointer;">인사이트 생성에 포함</label>
            <input type="checkbox" class="news-card-checkbox" id="check-${article.id}" data-id="${article.id}" ${isChecked ? 'checked' : ''}>
        </div>
      `;
      list.appendChild(card);

      card.querySelector('.news-card-checkbox').addEventListener('change', (e) => {
          handleNewsSelection(e.target, article);
      });

      // 진행률 업데이트
      const progress = 40 + (60 * (i + 1) / totalNews);
      progressBar.style.width = progress + "%";
      if (progressLabel) progressLabel.textContent = `뉴스 카드 생성 중... (${i + 1}/${totalNews})`;
      if (progressCount) progressCount.textContent = `${i + 1}/${totalNews}`;
      
      // 부드러운 애니메이션을 위한 지연
      if (i < totalNews - 1) {
        await new Promise(resolve => setTimeout(resolve, 50));
      }
    }

    // 완료
    progressBar.style.width = "100%";
    if (progressLabel) progressLabel.textContent = "뉴스 로딩 완료!";
    
    // 1초 후 진행률 바 숨김
    setTimeout(() => {
      progressContainer.classList.add('hidden');
    }, 1000);
  } catch (e) {
    status.textContent = "오류 발생";
    list.innerHTML = `<p class="placeholder-text" style="grid-column: 1 / -1; text-align: center;">뉴스를 불러오는 데 실패했습니다: ${e.message}</p>`;
    showToast(`오류: ${e.message}`);
    progressContainer.classList.add('hidden');
  }
}

function handleNewsSelection(checkbox, article) {
    const articleId = article.id;
    if (checkbox.checked) {
        if (selectedNewsArticles.length >= 3) {
            checkbox.checked = false;
            return;
        }
        if (!selectedNewsArticles.some(a => a.id === articleId)) {
            selectedNewsArticles.push(article);
        }
    } else {
        selectedNewsArticles = selectedNewsArticles.filter(a => a.id !== articleId);
    }
    updateStrategyTabDisplay();
}

// ======== 금융 전략 (Summary / Insight) ========
function updateStrategyTabDisplay() {
    const listEl = $("#selectedNewsList");
    const btn = $("#btnGenerateStrategy");

    if (selectedNewsArticles.length === 0) {
        listEl.innerHTML = `<p class="placeholder-text">Feed 탭에서 분석할 뉴스를 선택해주세요.</p>`;
        btn.disabled = true;
    } else {
        listEl.innerHTML = selectedNewsArticles.map(article => {
             const pubDate = new Date(article.published_at).toLocaleDateString('ko-KR');
             return `
                <div class="news-card-mini">
                    <div class="card-content">
                        <p class="meta">${article.url ? new URL(article.url).hostname : '출처 불명'} &middot; ${pubDate}</p>
                        <h4>${article.title}</h4>
                        <p>${article.summary}</p>
                    </div>
                </div>
             `;
        }).join('');
        btn.disabled = false;
    }
}

async function generateStrategy() {
    if (selectedNewsArticles.length === 0) {
        showToast("분석할 뉴스를 선택해주세요.");
        return;
    }

    const btn = $("#btnGenerateStrategy");
    const resultEl = $("#strategyResult");
    const progressContainer = $("#strategyProgressContainer");
    const progressBar = $("#strategyProgressBar");
    const progressSteps = $("#strategyProgressSteps");

    // 안전한 DOM 요소 접근
    if (!btn || !resultEl || !progressContainer || !progressBar || !progressSteps) {
        console.error('Required DOM elements not found');
        showToast("페이지 요소를 찾을 수 없습니다. 페이지를 새로고침해주세요.");
        return;
    }

    btn.disabled = true;
    btn.innerHTML = `<span class="material-symbols-outlined">hourglass_empty</span> 분석 중...`;
    
    // 진행률 바 표시
    progressContainer.classList.remove('hidden');
    progressBar.style.width = "0%";
    progressSteps.innerHTML = '';
    
    // progressLabel과 progressCount를 직접 찾기
    const progressLabel = progressContainer.querySelector('.progress-label');
    const progressCount = progressContainer.querySelector('.progress-count');
    
    if (progressLabel) progressLabel.textContent = "AI 분석 시작...";
    if (progressCount) progressCount.textContent = "0/4";
    
    resultEl.innerHTML = "";

    try {
        // POST 방식으로 직접 데이터 전송하고 결과 받기
        const response = await fetch('/api/financial-strategy', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                articles: selectedNewsArticles
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const result = await response.json();
        
        // 진행률 시뮬레이션
        const steps = [
            "🤖 Ollama(qwen3:8b) 호출 중...",
            "✅ Ollama 응답 수신 완료",
            "🤖 Ollama 호출: 시장 국면 분석 요청",
            "✅ Ollama 분석 완료: 시장 국면 분석 및 상품 추천 완료"
        ];

        for (let i = 0; i < steps.length; i++) {
            const step = document.createElement('div');
            step.className = 'progress-step';
            step.innerHTML = `
                <div class="step-icon">
                    <span class="material-symbols-outlined">psychology</span>
                </div>
                <div class="step-content">
                    <div class="step-title">${steps[i]}</div>
                    <div class="step-time">${new Date().toLocaleTimeString()}</div>
                </div>
            `;
            progressSteps.appendChild(step);
            
            // 진행률 업데이트
            const progress = ((i + 1) / 4) * 100;
            progressBar.style.width = progress + "%";
            if (progressLabel) progressLabel.textContent = steps[i];
            if (progressCount) progressCount.textContent = `${i + 1}/4`;
            
            progressSteps.scrollTop = progressSteps.scrollHeight;
            
            // 각 단계마다 약간의 지연
            if (i < steps.length - 1) {
                await new Promise(resolve => setTimeout(resolve, 500));
            }
        }

        // 결과 표시
        const strategy = result;
        const products = result.recommended_product ? [result.recommended_product] : [];
        
        const productHtml = products.length > 0 ? `
            <div class="products-section">
                <h4>추천 금융상품</h4>
                <div class="products-grid">
                    ${products.map(product => renderProductCard(product)).join('')}
                </div>
            </div>
        ` : '';

        resultEl.innerHTML = `
            <div class="strategy-main-card">
                <h3>AI 분석 요약 및 인사이트</h3>
                <div class="insight-grid">
                    <div class="insight-item">
                        <h4><span class="num-badge">1</span> 원인 분석</h4>
                        <p>${strategy.cause.replace(/\n/g, '<br>')}</p>
                    </div>
                    <div class="insight-item">
                        <h4><span class="num-badge">2</span> 투자 전략</h4>
                        <p>${strategy.effect.replace(/\n/g, '<br>')}</p>
                    </div>
                    <div class="insight-item">
                        <h4><span class="num-badge">3</span> 결론 및 리스크</h4>
                        <p>${strategy.conclusion.replace(/\n/g, '<br>')}</p>
                    </div>
                </div>
                ${productHtml}
            </div>
        `;
        
        // 완료
        progressBar.style.width = "100%";
        if (progressLabel) progressLabel.textContent = "AI 분석 완료!";
        if (progressCount) progressCount.textContent = "4/4";
        
        btn.disabled = false;
        btn.innerHTML = `<span class="material-symbols-outlined">lightbulb</span> 인사이트 생성`;
        showToast("인사이트 생성이 완료되었습니다!");
        
        // 2초 후 진행률 바 숨김
        setTimeout(() => {
            progressContainer.classList.add('hidden');
        }, 2000);
        
    } catch (e) {
        console.error('Strategy generation error:', e);
        resultEl.innerHTML = `<div class="strategy-main-card"><p style="color:var(--danger-color)">전략 수립 중 오류: ${e.message}</p></div>`;
        showToast(`오류: ${e.message}`);
        progressContainer.classList.add('hidden');
        btn.disabled = false;
        btn.innerHTML = `<span class="material-symbols-outlined">lightbulb</span> 인사이트 생성`;
    }
}

function renderProductCard(product) {
    const rateStr = product.rate ? `${product.rate}%` : '';
    return `
        <div class="product-card">
            <div class="product-header">
                <h4>${product.name}</h4>
                <span class="product-type">${product.type}</span>
            </div>
            <div class="product-content">
                <p>${product.description}</p>
                ${rateStr ? `<p><strong>금리:</strong> ${rateStr}</p>` : ''}
            </div>
        </div>
    `;
}

// ======== 딥 리서치 ========
function loadResearch() {
    const btn = $("#btnLoadResearch");
    const query = $("#researchQuery").value.trim();
    const feedbackLoops = $("#researchFeedbackLoops").value;
    const isAgentic = $("#agentic-switch").checked;
    
    // 대시보드 요소들
    const dashboard = $("#research-dashboard");
    const totalSources = $("#total-sources");
    const analysisTime = $("#analysis-time");
    const currentPhase = $("#current-phase");
    const collectedNews = $("#collected-news");
    const collectedWebResults = $("#collected-web-results");
    const analysisTimeline = $("#analysis-timeline");
    const finalReport = $("#final-report");

    if (!query) {
        showToast("리서치 주제를 입력해주세요.");
        return;
    }

    // 초기화
    btn.disabled = true;
    btn.textContent = "리서치 진행 중...";
    dashboard.classList.remove('hidden');
    
    // 실시간 타이머 시작
    const startTime = Date.now();
    let timerInterval = setInterval(() => {
        const elapsed = Math.floor((Date.now() - startTime) / 1000);
        analysisTime.textContent = elapsed;
    }, 1000);

    const es = new EventSource(`/api/deep-research?query=${encodeURIComponent(query)}&agentic=${isAgentic}&feedback_loops=${feedbackLoops}&debug=1`);

    es.onmessage = function(event) {
        const data = JSON.parse(event.data);

        // 진행률 업데이트
        if (data.type === 'progress') {
            currentPhase.textContent = data.status;
            
            // 타임라인에 진행 단계 추가
            const step = document.createElement('div');
            step.className = 'timeline-item';
            step.innerHTML = `
                <div class="timeline-marker"></div>
                <div class="timeline-content">
                    <div class="step-title">${data.status}</div>
                    <div class="step-time">${new Date().toLocaleTimeString()}</div>
                </div>
            `;
            analysisTimeline.appendChild(step);
            analysisTimeline.scrollTop = analysisTimeline.scrollHeight;
        }

        // 뉴스 수집 완료
        if (data.type === 'news_collected') {
            collectedNews.innerHTML = data.articles.map(article => `
                <div class="data-card">
                    <h4>${article.title}</h4>
                    <p class="meta">${new URL(article.url || 'https://example.com').hostname} • ${new Date(article.published_at).toLocaleDateString()}</p>
                    <p>${article.summary}</p>
                </div>
            `).join('');
            
            totalSources.textContent = data.articles.length;
        }

        // 웹 검색 결과
        if (data.type === 'web_search_results') {
            collectedWebResults.innerHTML = data.results.map(result => `
                <div class="data-card">
                    <h4>${result.title}</h4>
                    <p class="meta">${new URL(result.url || 'https://example.com').hostname}</p>
                    <p>${result.preview_text}</p>
                </div>
            `).join('');
            
            const currentTotal = parseInt(totalSources.textContent) || 0;
            totalSources.textContent = currentTotal + data.results.length;
        }

        // 사고 과정 표시
        if (data.type === 'thinking') {
            const thinkingItem = document.createElement('div');
            thinkingItem.className = 'timeline-item thinking';
            thinkingItem.innerHTML = `
                <div class="timeline-marker thinking"></div>
                <div class="timeline-content">
                    <div class="step-title">💭 ${data.content}</div>
                    <div class="step-time">${new Date().toLocaleTimeString()}</div>
                </div>
            `;
            analysisTimeline.appendChild(thinkingItem);
            analysisTimeline.scrollTop = analysisTimeline.scrollHeight;
        }

        // 최종 결과
        if (data.type === 'final_result') {
            finalReport.innerHTML = marked.parse(data.report);
            
            // 타이머 정지
            clearInterval(timerInterval);
            const finalElapsed = Math.floor((Date.now() - startTime) / 1000);
            analysisTime.textContent = finalElapsed;
            
            btn.disabled = false;
            btn.textContent = "리서치 시작";
            showToast("리서치가 완료되었습니다!");
            es.close();
        }

        // 오류 처리
        if (data.type === 'error') {
            const errorStep = document.createElement('div');
            errorStep.className = 'timeline-item error';
            errorStep.innerHTML = `
                <div class="timeline-marker error"></div>
                <div class="timeline-content">
                    <div class="step-title" style="color: var(--danger-color)">❌ ${data.message}</div>
                    <div class="step-time">${new Date().toLocaleTimeString()}</div>
                </div>
            `;
            analysisTimeline.appendChild(errorStep);
            
            // 타이머 정지
            clearInterval(timerInterval);
            
            es.close();
            btn.disabled = false;
            btn.textContent = "리서치 시작";
            showToast("리서치 중 오류가 발생했습니다.");
        }
    };

    es.onerror = function() {
        const errorStep = document.createElement('div');
        errorStep.className = 'timeline-item error';
        errorStep.innerHTML = `
            <div class="timeline-marker error"></div>
            <div class="timeline-content">
                <div class="step-title" style="color: var(--danger-color)">연결 오류가 발생했습니다</div>
                <div class="step-time">${new Date().toLocaleTimeString()}</div>
            </div>
        `;
        analysisTimeline.appendChild(errorStep);
        
        // 타이머 정지
        clearInterval(timerInterval);
        
        es.close();
        btn.disabled = false;
        btn.textContent = "리서치 시작";
        showToast("서버 연결에 실패했습니다.");
    };
}

// ======== 초기화 ========
document.addEventListener("DOMContentLoaded", () => {
    initDark();
    initTabs();
    
    // 새로고침 버튼 이벤트 리스너
    const reloadBtn = document.querySelector("#reload-btn");
    if (reloadBtn) {
        reloadBtn.addEventListener("click", () => {
            const feedTab = document.querySelector("#tab-news");
            if (feedTab && feedTab.classList.contains("active")) {
                showToast("최신 뉴스를 다시 불러옵니다.");
                loadNews(true);
            } else {
                showToast("Feed 탭에서만 새로고침할 수 있습니다.");
            }
        });
    }

    // 딥 리서치 버튼 이벤트 리스너
    const researchBtn = document.querySelector("#btnLoadResearch");
    if (researchBtn) {
        researchBtn.addEventListener("click", loadResearch);
    }
    
    // 전략 생성 버튼 이벤트 리스너
    const strategyBtn = document.querySelector("#btnGenerateStrategy");
    if (strategyBtn) {
        strategyBtn.addEventListener("click", generateStrategy);
    }
    
    // 초기 뉴스 로딩
    loadNews(false);
});

