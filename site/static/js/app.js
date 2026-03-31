/**
 * 포켓몬 굿즈 시세 — CSR 앱
 * data/cards.json, lego.json, events.json을 fetch하여 렌더링.
 */

'use strict';

// ========== 상태 ==========
const state = {
  cards: [],
  lego: [],
  events: [],
  activeTab: 'cards',
  filters: {
    edition: 'all',
    category: 'all',
    event_status: 'all',
  },
  sourceStatus: {},
  buildInfo: {},
  loading: { cards: true, lego: true, events: true },
};

// ========== 유틸 ==========
function fmt(num, currency = 'KRW') {
  if (num == null) return '—';
  if (currency === 'KRW') return num.toLocaleString('ko-KR') + '원';
  if (currency === 'USD') return '$' + num.toFixed(2);
  return String(num);
}

function dateStr(isoStr) {
  if (!isoStr) return '';
  return isoStr.slice(0, 10);
}

function isFresh(dateIso) {
  if (!dateIso) return false;
  const diff = Date.now() - new Date(dateIso).getTime();
  return diff < 86400 * 1000; // 24시간 이내
}

function escHtml(str) {
  return String(str || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function badge(text, cls) {
  return `<span class="badge ${cls}">${escHtml(text)}</span>`;
}

// ========== 데이터 fetch ==========
async function fetchJSON(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${path}`);
  return res.json();
}

async function loadAllData() {
  const BASE = 'data/';

  const [cardsResult, legoResult, eventsResult] = await Promise.allSettled([
    fetchJSON(BASE + 'cards.json'),
    fetchJSON(BASE + 'lego.json'),
    fetchJSON(BASE + 'events.json'),
  ]);

  if (cardsResult.status === 'fulfilled') {
    const data = cardsResult.value;
    state.cards = data.cards || [];
    state.sourceStatus = { ...state.sourceStatus, ...data.source_status };
    updateLastUpdated(data.updated_at);
  } else {
    console.error('cards.json 로드 실패:', cardsResult.reason);
  }
  state.loading.cards = false;

  if (legoResult.status === 'fulfilled') {
    const data = legoResult.value;
    state.lego = data.sets || [];
    state.sourceStatus = { ...state.sourceStatus, ...data.source_status };
  } else {
    console.error('lego.json 로드 실패:', legoResult.reason);
  }
  state.loading.lego = false;

  if (eventsResult.status === 'fulfilled') {
    state.events = eventsResult.value.events || [];
  } else {
    console.error('events.json 로드 실패:', eventsResult.reason);
  }
  state.loading.events = false;

  // 빌드 정보
  try {
    state.buildInfo = await fetchJSON('build_info.json');
  } catch (_) {}

  renderAll();
}

function updateLastUpdated(isoStr) {
  const el = document.getElementById('lastUpdated');
  if (!el) return;
  if (!isoStr) { el.textContent = ''; return; }
  const d = new Date(isoStr);
  const fmt = d.toLocaleString('ko-KR', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  el.textContent = `업데이트: ${fmt}`;
}

// ========== 렌더 전체 ==========
function renderAll() {
  renderCards();
  renderEvents();
  renderLego();
  renderInfo();
}

// ========== 카드 렌더 ==========
function getFilteredCards() {
  return state.cards.filter(card => {
    const { edition, category } = state.filters;
    if (edition !== 'all') {
      const editions = card.editions || [];
      if (!editions.includes(edition)) return false;
    }
    if (category !== 'all' && card.category !== category) return false;
    return true;
  });
}

function renderCardBadges(card) {
  const badges = [];
  const editions = card.editions || [];
  if (editions.includes('kr')) badges.push(badge('KR', 'badge-kr'));
  if (editions.includes('en')) badges.push(badge('EN', 'badge-en'));
  if (card.category) badges.push(badge(card.category === 'collab' ? '콜라보' : card.category, 'badge-category'));
  if (card.warning_flags && card.warning_flags.length > 0) {
    badges.push(badge('⚠ 이상치', 'badge-anomaly'));
  }
  return badges.join('');
}

function renderCardItem(card) {
  const thumbHtml = card.thumbnail_url
    ? `<img class="card-thumbnail" src="${escHtml(card.thumbnail_url)}" alt="${escHtml(card.name_ko || card.name_en || '')}" loading="lazy">`
    : `<div class="card-thumbnail-placeholder">&#127132;</div>`;

  const mainPrice = card.avg_price_krw
    ? fmt(card.avg_price_krw)
    : (card.tcgplayer_market_krw ? fmt(card.tcgplayer_market_krw) : '시세 없음');

  const subPrices = [];
  if (card.tcgplayer_market_usd) subPrices.push(`TCG ${fmt(card.tcgplayer_market_usd, 'USD')}`);
  if (card.ebay_avg_sold_usd) subPrices.push(`eBay ${fmt(card.ebay_avg_sold_usd, 'USD')}`);
  if (card.bunjang_avg_krw) subPrices.push(`번개 ${fmt(card.bunjang_avg_krw)}`);

  const freshness = isFresh(card.last_seen_date);
  const freshnessHtml = card.last_seen_date
    ? `<span class="last-seen"><span class="freshness-dot ${freshness ? 'fresh' : 'stale'}"></span>${dateStr(card.last_seen_date)}</span>`
    : '';

  return `
    <div class="price-card" data-card-id="${escHtml(card.id)}" role="button" tabindex="0" aria-label="${escHtml(card.name_ko || card.name_en || '')} 상세 보기">
      ${thumbHtml}
      <div class="card-body">
        <div class="card-badges">${renderCardBadges(card)}</div>
        <div class="card-name-ko">${escHtml(card.name_ko || card.name_en || card.id)}</div>
        <div class="card-name-en">${escHtml(card.name_en || '')}</div>
        <div class="card-price-main">${escHtml(mainPrice)}</div>
        ${subPrices.length ? `<div class="card-price-sub">${subPrices.map(escHtml).join(' · ')}</div>` : ''}
        ${freshnessHtml}
      </div>
    </div>`;
}

function renderCards() {
  const grid = document.getElementById('cardGrid');
  if (!grid) return;

  if (state.loading.cards) {
    grid.innerHTML = '<div class="loading-spinner"><div class="spinner"></div><p>시세 데이터 로딩 중...</p></div>';
    return;
  }

  const filtered = getFilteredCards();
  if (filtered.length === 0) {
    grid.innerHTML = '<div class="empty-state"><div>&#128274;</div><p>조건에 맞는 카드가 없습니다.</p></div>';
    return;
  }

  grid.innerHTML = filtered.map(renderCardItem).join('');

  // 클릭 이벤트
  grid.querySelectorAll('.price-card').forEach(el => {
    el.addEventListener('click', () => openCardModal(el.dataset.cardId));
    el.addEventListener('keydown', e => { if (e.key === 'Enter') openCardModal(el.dataset.cardId); });
  });
}

// ========== 카드 상세 모달 ==========
function openCardModal(cardId) {
  const card = state.cards.find(c => c.id === cardId);
  if (!card) return;

  const modal = document.getElementById('cardModal');
  const body = document.getElementById('modalBody');
  if (!modal || !body) return;

  body.innerHTML = buildModalContent(card);
  modal.hidden = false;
  document.body.style.overflow = 'hidden';
  modal.querySelector('.modal-close').focus();
}

function buildModalContent(card) {
  const name = card.name_ko || card.name_en || card.id;
  let html = `<h2 class="modal-card-name">${escHtml(name)}</h2>`;
  if (card.name_en) html += `<p style="color:var(--text-muted);font-size:0.82rem;margin-bottom:12px">${escHtml(card.name_en)}</p>`;

  // 가격 테이블
  const priceRows = [];
  if (card.tcgplayer_market_usd) priceRows.push(['TCGPlayer 시세', fmt(card.tcgplayer_market_usd, 'USD'), fmt(card.tcgplayer_market_krw)]);
  if (card.pc_raw_usd) priceRows.push(['PriceCharting (미채점)', fmt(card.pc_raw_usd, 'USD'), fmt(card.pc_raw_krw)]);
  if (card.ebay_avg_sold_usd) priceRows.push([`eBay 낙찰가 (${card.ebay_recent_sold_count || '?'}건)`, fmt(card.ebay_avg_sold_usd, 'USD'), '—']);
  if (card.bunjang_avg_krw) priceRows.push(['번개장터 희망가↗', '—', fmt(card.bunjang_avg_krw)]);
  if (card.daangn_avg_krw) priceRows.push(['당근마켓 희망가↗', '—', fmt(card.daangn_avg_krw)]);

  if (priceRows.length > 0) {
    html += `<div class="modal-section-title">가격 정보</div>`;
    html += `<table class="modal-price-table">
      <thead><tr><th>소스</th><th>USD</th><th>KRW</th></tr></thead>
      <tbody>${priceRows.map(r => `<tr><td>${escHtml(r[0])}</td><td>${escHtml(r[1])}</td><td>${escHtml(r[2])}</td></tr>`).join('')}</tbody>
    </table>`;
  }

  // 등급별 가격
  const graded = card.graded_prices || [];
  if (graded.length > 0) {
    html += `<div class="modal-section-title">등급별 가격 (PriceCharting)</div>`;
    html += `<table class="modal-price-table">
      <thead><tr><th>등급</th><th>USD</th><th>KRW (환산)</th></tr></thead>
      <tbody>${graded.map(g => `<tr><td>${escHtml(g.company)} ${escHtml(g.grade)}</td><td>${fmt(g.price_usd, 'USD')}</td><td>${fmt(g.price_krw)}</td></tr>`).join('')}</tbody>
    </table>`;
  }

  // eBay 등급별 낙찰가
  const ebayGraded = card.ebay_graded_sold || [];
  if (ebayGraded.length > 0) {
    html += `<div class="modal-section-title">eBay 등급별 낙찰가</div>`;
    html += `<table class="modal-price-table">
      <thead><tr><th>등급</th><th>평균 낙찰가</th><th>건수</th></tr></thead>
      <tbody>${ebayGraded.map(g => `<tr><td>${escHtml(g.company)} ${escHtml(g.grade)}</td><td>${fmt(g.avg_sold_usd, 'USD')}</td><td>${escHtml(String(g.recent_sold_count || '?'))}건</td></tr>`).join('')}</tbody>
    </table>`;
  }

  // 국내 매물
  const domestic = card.domestic_listings || [];
  if (domestic.length > 0) {
    html += `<div class="modal-section-title">국내 매물 (희망가 · 비공식)</div>`;
    domestic.forEach(li => {
      html += `<div class="domestic-listing-item">
        <span style="flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${escHtml(li.title || '')}</span>
        <span style="font-weight:700;white-space:nowrap">${fmt(li.price_krw)}</span>
        <span class="badge badge-category" style="white-space:nowrap">${escHtml(li.source || '')}</span>
      </div>`;
    });
    html += `<p style="font-size:0.72rem;color:var(--text-muted);margin-top:6px">↗ 판매 희망가 (수수료 미포함)</p>`;
  }

  // 이상치 경고
  if (card.warning_flags && card.warning_flags.length > 0) {
    html += `<div style="margin-top:12px;padding:10px;background:#fef3c7;border-radius:8px;font-size:0.8rem;color:#92400e">
      ⚠ 가격 이상치 감지: 전일 대비 큰 폭의 변동이 있습니다. 직접 확인을 권장합니다.
    </div>`;
  }

  return html;
}

function closeModal() {
  const modal = document.getElementById('cardModal');
  if (modal) {
    modal.hidden = true;
    document.body.style.overflow = '';
  }
}

// ========== 이벤트 렌더 ==========
function getFilteredEvents() {
  const { event_status } = state.filters;
  if (event_status === 'all') return state.events;
  return state.events.filter(e => e.event_status === event_status);
}

function renderEventItem(event) {
  const statusLabel = { ongoing: '진행중', upcoming: '예정', ended: '종료' }[event.event_status] || '';
  const statusClass = event.event_status || 'ended';

  const thumbHtml = event.thumbnail_url
    ? `<img class="event-thumbnail" src="${escHtml(event.thumbnail_url)}" alt="${escHtml(event.title)}" loading="lazy">`
    : '';

  let dateHtml = '';
  if (event.start_date) {
    dateHtml = event.end_date && event.end_date !== event.start_date
      ? `${dateStr(event.start_date)} ~ ${dateStr(event.end_date)}`
      : dateStr(event.start_date);
  }

  const linkHtml = event.url
    ? `<a href="${escHtml(event.url)}" target="_blank" rel="noopener" style="font-size:0.78rem;color:var(--pokemon-blue)">자세히 보기 →</a>`
    : '';

  const categoryLabels = { offline_event: '오프라인', cardshop_event: '카드샵', collab_event: '콜라보', new_release: '신규 출시' };
  const catLabel = categoryLabels[event.category] || '';

  return `
    <div class="event-item status-${escHtml(statusClass)}">
      ${thumbHtml}
      <div class="event-body">
        <div class="event-title">${escHtml(event.title)}</div>
        <div class="event-date">
          <span class="status-dot status-${escHtml(statusClass)}"></span>
          <strong>${escHtml(statusLabel)}</strong>
          ${dateHtml ? ' · ' + escHtml(dateHtml) : ''}
        </div>
        ${catLabel ? `<div class="event-category">${escHtml(catLabel)}</div>` : ''}
        ${linkHtml}
      </div>
    </div>`;
}

function renderEvents() {
  const list = document.getElementById('eventList');
  if (!list) return;

  if (state.loading.events) {
    list.innerHTML = '<div class="loading-spinner"><div class="spinner"></div><p>이벤트 데이터 로딩 중...</p></div>';
    return;
  }

  const filtered = getFilteredEvents();
  if (filtered.length === 0) {
    list.innerHTML = '<div class="empty-state"><div>&#128197;</div><p>이벤트 정보가 없습니다.</p></div>';
    return;
  }

  list.innerHTML = filtered.map(renderEventItem).join('');
}

// ========== 레고 렌더 ==========
function renderLegoItem(set) {
  const thumbHtml = set.thumbnail_url
    ? `<img class="lego-thumbnail" src="${escHtml(set.thumbnail_url)}" alt="${escHtml(set.name_ko || '')}" loading="lazy">`
    : `<div class="lego-thumbnail" style="background:var(--bg-secondary);display:flex;align-items:center;justify-content:center;font-size:2rem;">&#129307;</div>`;

  const premiumHtml = set.premium_pct != null
    ? `<div class="lego-price-row">
        <span class="lego-price-label">프리미엄</span>
        <span class="lego-price-value ${set.premium_pct >= 0 ? 'premium-positive' : 'premium-negative'}">
          ${set.premium_pct >= 0 ? '+' : ''}${set.premium_pct}%
        </span>
      </div>`
    : '';

  const stockHtml = set.in_stock != null
    ? `<div class="lego-price-row">
        <span class="lego-price-label">공식몰</span>
        <span class="lego-price-value">${set.in_stock ? '재고 있음' : '품절'}</span>
      </div>`
    : '';

  const retiredHtml = set.retired
    ? badge('단종', 'badge badge-retired-badge')
    : '';

  return `
    <div class="lego-card">
      ${thumbHtml}
      <div class="lego-body">
        <div class="card-badges" style="margin-bottom:6px">${retiredHtml}</div>
        <div class="lego-name">${escHtml(set.name_ko || set.id)}</div>
        <div class="lego-set-number">세트번호 ${escHtml(set.set_number || '')}</div>
        ${set.retail_price_krw ? `<div class="lego-price-row"><span class="lego-price-label">정가</span><span class="lego-price-value">${fmt(set.retail_price_krw)}</span></div>` : ''}
        ${set.used_krw ? `<div class="lego-price-row"><span class="lego-price-label">중고 시세</span><span class="lego-price-value">${fmt(set.used_krw)}</span></div>` : ''}
        ${set.new_krw ? `<div class="lego-price-row"><span class="lego-price-label">새 상품 시세</span><span class="lego-price-value">${fmt(set.new_krw)}</span></div>` : ''}
        ${set.bunjang_avg_krw ? `<div class="lego-price-row"><span class="lego-price-label">번개장터↗</span><span class="lego-price-value">${fmt(set.bunjang_avg_krw)}${set.bunjang_count ? ` <span style="font-size:0.75em;opacity:0.6">(${set.bunjang_count}건)</span>` : ''}</span></div>` : ''}
        ${premiumHtml}
        ${stockHtml}
      </div>
    </div>`;
}

function renderLego() {
  const grid = document.getElementById('legoGrid');
  if (!grid) return;

  if (state.loading.lego) {
    grid.innerHTML = '<div class="loading-spinner"><div class="spinner"></div><p>레고 데이터 로딩 중...</p></div>';
    return;
  }

  if (state.lego.length === 0) {
    grid.innerHTML = '<div class="empty-state"><div>&#129307;</div><p>레고 데이터가 없습니다.</p></div>';
    return;
  }

  grid.innerHTML = state.lego.map(renderLegoItem).join('');
}

// ========== 정보 탭 렌더 ==========
function renderInfo() {
  renderSourceStatus();
  renderBuildInfo();
}

function renderSourceStatus() {
  const container = document.getElementById('sourceStatus');
  if (!container) return;

  const statusMap = state.sourceStatus;
  const keys = Object.keys(statusMap).filter(k => !k.includes('_'));
  if (keys.length === 0) {
    container.innerHTML = '<p style="color:var(--text-muted);font-size:0.82rem">소스 상태 정보 없음</p>';
    return;
  }

  const labels = { tcgplayer: 'TCGPlayer', pricecharting: 'PriceCharting', ebay: 'eBay', naver_cafe: '네이버카페', bunjang: '번개장터', daangn: '당근마켓', brickeconomy: 'BrickEconomy', lego_official: 'LEGO공식' };

  container.innerHTML = keys.map(key => {
    const val = statusMap[key];
    let cls = 'source-badge-ok';
    let label = 'OK';
    if (val === 'missing') { cls = 'source-badge-missing'; label = '데이터없음'; }
    else if (val === 'blocked') { cls = 'source-badge-blocked'; label = '차단됨'; }
    else if (val !== 'ok') { cls = 'source-badge-missing'; label = val; }
    return `<span class="source-badge ${cls}">${escHtml(labels[key] || key)}: ${escHtml(label)}</span>`;
  }).join('');
}

function renderBuildInfo() {
  const el = document.getElementById('buildInfo');
  if (!el || !state.buildInfo.built_at) return;

  const d = new Date(state.buildInfo.built_at);
  el.innerHTML = `빌드: ${d.toLocaleString('ko-KR')} · 버전 ${escHtml(state.buildInfo.pipeline_version || '?')}`;
}

// ========== 탭 전환 ==========
function initTabs() {
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const tab = btn.dataset.tab;
      state.activeTab = tab;

      document.querySelectorAll('.tab-btn').forEach(b => {
        b.classList.toggle('active', b.dataset.tab === tab);
        b.setAttribute('aria-selected', b.dataset.tab === tab ? 'true' : 'false');
      });
      document.querySelectorAll('.tab-content').forEach(s => {
        s.classList.toggle('active', s.id === `tab-${tab}`);
      });
    });
  });
}

// ========== 필터 이벤트 ==========
function initFilters() {
  // 버튼 필터
  document.querySelectorAll('.filter-btn[data-filter]').forEach(btn => {
    btn.addEventListener('click', () => {
      const filterName = btn.dataset.filter;
      const value = btn.dataset.value;
      state.filters[filterName] = value;

      // 같은 그룹 버튼 active 토글
      btn.closest('.btn-group')?.querySelectorAll('.filter-btn').forEach(b => {
        b.classList.toggle('active', b.dataset.value === value);
      });

      if (filterName === 'edition' || filterName === 'category') renderCards();
      if (filterName === 'event_status') renderEvents();
    });
  });

  // 카테고리 셀렉트
  const catSelect = document.getElementById('categoryFilter');
  if (catSelect) {
    catSelect.addEventListener('change', e => {
      state.filters.category = e.target.value;
      renderCards();
    });
  }
}

// ========== 모달 이벤트 ==========
function initModal() {
  const modal = document.getElementById('cardModal');
  if (!modal) return;

  document.getElementById('modalClose')?.addEventListener('click', closeModal);
  document.getElementById('modalBackdrop')?.addEventListener('click', closeModal);

  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && !modal.hidden) closeModal();
  });
}

// ========== 초기화 ==========
document.addEventListener('DOMContentLoaded', () => {
  initTabs();
  initFilters();
  initModal();
  loadAllData();
});
