# 3. 프로젝트 구조 및 에이전트 설계

## 3.1 폴더 구조

```
/pokemon-goods-tracker
├── CLAUDE.md                              # 메인 에이전트 지침
├── /.claude
│   ├── /skills
│   │   ├── /card-price-collector          # 카드 시세 수집
│   │   │   ├── SKILL.md
│   │   │   └── /scripts
│   │   │       ├── tcgplayer_scraper.py       # 해외판 시세 (영어판)
│   │   │       ├── pricecharting_scraper.py   # 해외판 시세 + 그레이딩별 가격
│   │   │       ├── ebay_scraper.py            # eBay 실거래 낙찰가 (API/크롤링)
│   │   │       ├── naver_cafe_price_scraper.py # 국내판 시세 (네이버 카페)
│   │   │       ├── bunjang_scraper.py         # 번개장터 실거래 매물 가격
│   │   │       └── daangn_scraper.py          # 당근마켓 실거래 매물 가격
│   │   ├── /lego-price-collector          # 레고 가격 수집
│   │   │   ├── SKILL.md
│   │   │   └── /scripts
│   │   │       ├── brickeconomy_scraper.py    # v1 기본 소스
│   │   │       ├── lego_official_scraper.py
│   │   │       └── bricklink_api.py           # v2 예정 (현재 미사용)
│   │   ├── /event-collector               # 이벤트/행사 수집
│   │   │   ├── SKILL.md
│   │   │   └── /scripts
│   │   │       ├── pokemon_korea_scraper.py   # 공식 웹사이트만 (SNS 제외)
│   │   │       └── naver_cafe_scraper.py      # 공개 게시판만
│   │   ├── /data-processor                # 데이터 정제/병합
│   │   │   ├── SKILL.md
│   │   │   └── /scripts
│   │   │       ├── card_name_mapper.py
│   │   │       ├── edition_tagger.py          # 에디션(kr/en) 태깅 (jp는 v2 예정)
│   │   │       ├── grading_normalizer.py      # PSA/BGS 등급 정규화
│   │   │       ├── price_normalizer.py
│   │   │       ├── event_deduplicator.py
│   │   │       └── data_merger.py
│   │   ├── /site-builder                  # 정적 사이트 생성
│   │   │   ├── SKILL.md
│   │   │   └── /scripts
│   │   │       └── build_site.py
│   │   └── /validator                     # 데이터 검증
│   │       ├── SKILL.md
│   │       └── /scripts
│   │           └── validate_data.py
│   └── /agents
│       └── /data-enrichment-agent         # 데이터 보강 서브에이전트
│           └── AGENT.md
├── /config
│   ├── watchlist.json                     # 추적 대상 카드/레고 목록 (에디션별)
│   ├── sources.json                       # 크롤링 대상 URL/API 설정
│   ├── card_name_map.json                 # 영문↔한국어 카드명 매핑 테이블
│   ├── grading_config.json                # 추적할 그레이딩 등급 정의 (PSA 10/9/8, BGS 10/9.5/9/8.5)
│   ├── ebay_config.json                   # eBay API 키, 검색 필터 설정 (영어판 전용)
│   └── exchange_rate.json                 # 환율 캐시 (한국은행 API, 최대 7일 캐시)
├── /data
│   ├── /raw                               # 소스별 원본 데이터
│   ├── cards.json                         # 정제된 카드 시세
│   ├── lego.json                          # 정제된 레고 가격
│   └── events.json                        # 정제된 이벤트 정보
├── /site
│   ├── /templates                         # HTML 템플릿
│   ├── /static                            # CSS, JS, 이미지
│   └── /build                             # 빌드 산출물 (gh-pages 배포 대상)
├── /logs                                  # 수집/검증 로그
├── /.github
│   └── /workflows
│       └── collect-and-deploy.yml         # GitHub Actions 워크플로우
└── /docs                                  # 참고 문서
    ├── api-guides.md                      # 외부 API 사용 가이드
    └── troubleshooting.md                 # 트러블슈팅
```

## 3.2 CLAUDE.md 핵심 섹션 목록

1. **프로젝트 개요** — 목적, 대상 사용자, 기술 스택
2. **워크플로우 개요** — 5단계 파이프라인 흐름 요약
3. **스킬 호출 규칙** — 어떤 상황에서 어떤 스킬을 호출하는지
4. **서브에이전트 호출 규칙** — data-enrichment-agent 트리거 조건
5. **데이터 규칙** — JSON 스키마, 파일 경로 규칙, 네이밍 규칙
6. **에러 핸들링 원칙** — 실패 시 행동 규칙 (스킵/재시도/중단)
7. **배포 규칙** — gh-pages 푸시 조건, 롤백 기준
8. **금지 사항** — 유료 API 무단 사용 금지, 차단 감지 후 강제 재시도 금지, API 키 코드 하드코딩 금지 (환경변수 사용), SNS(인스타/X) 크롤링 시도 금지
9. **국내 플랫폼 크롤링 정책** — 당근/번개장터 크롤링 시도 허용, 단 차단 시 즉시 스킵 + 3일 연속 차단 시 자동 비활성화. 네이버 카페는 공개 게시판만.
10. **LLM 호출 정책** — 신규/변경 데이터 감지 시만 Claude API 호출. 불필요한 호출 금지 (비용 절감)

## 3.3 에이전트 구조

**메인 에이전트 (CLAUDE.md)** — 오케스트레이터

전체 파이프라인을 순차 실행하며, 각 단계에서 적절한 스킬을 호출한다.

**서브에이전트: data-enrichment-agent**

| 항목 | 내용 |
|------|------|
| **역할** | 수집된 데이터의 LLM 기반 보강 처리 |
| **트리거** | **신규/변경 데이터가 감지될 때만** 호출. 변경 없으면 스킵 (비용 최적화) |
| **수행 작업** | (1) 미매핑 카드명 한국어 추론 (2) 네이버 카페 공개 게시판 비정형 시세글에서 가격/그레이딩 등급 추출 (3) 이벤트 유사도 판단/병합 (4) 이벤트 카테고리 분류 |
| **입력** | 미매핑 카드 목록 JSON, 네이버 카페 시세글 원문, 중복 의심 이벤트 쌍 JSON |
| **출력** | 매핑 결과 JSON, 구조화된 시세 데이터 JSON (카드명+에디션+등급+가격), 병합된 이벤트 JSON |
| **데이터 전달** | 파일 기반 (`/data/raw/` → 서브에이전트 → `/data/`) |

**LLM 호출 조건 (비용 최적화)**:

| 작업 | 호출 조건 | 예상 빈도 |
|------|-----------|----------|
| 카드명 한국어 매핑 | watchlist에 신규 카드 추가 시만 | 주 0~1회 |
| 네이버 카페 시세글 파싱 | 신규 공개 게시글 수집 시만 | 주 1~2회 |
| 이벤트 중복 제거 | 신규 이벤트 수집 시만 | 주 1~2회 |
| 이벤트 카테고리 분류 | 신규 이벤트 수집 시만 | 주 1~2회 |

> 하루 2회 전체 파이프라인 실행 중 LLM 실제 호출은 **주 1~2회 수준**으로, API 비용은 사실상 무료에 가까움.

**분리 근거**: 카드명 매핑, 비정형 시세글 파싱, 이벤트 분류는 모두 도메인 지식이 필요한 LLM 판단 작업으로, 크롤링/파싱 스크립트와 컨텍스트를 분리하면 각각의 지침을 가볍게 유지할 수 있다. 특히 네이버 카페 시세글(공개 게시판)은 형식이 제각각이라 LLM 기반 추출이 필수적이다.

## 3.4 스킬 목록 및 역할

| 스킬 | 역할 | 트리거 조건 | 참조 스크립트 |
|------|------|------------|-------------|
| `card-price-collector` | 해외판 시세(TCGPlayer, PriceCharting, **eBay 영어판 전용**) + 국내판 시세(네이버 카페 공개 게시판) + 국내 실거래(번개장터, 당근마켓) 수집. 그레이딩 등급별 가격 포함 | Step 1 시작 시 항상 | `tcgplayer_scraper.py`, `pricecharting_scraper.py`, `ebay_scraper.py`, `naver_cafe_price_scraper.py`, `bunjang_scraper.py`, `daangn_scraper.py` |
| `lego-price-collector` | **BrickEconomy 크롤링** + LEGO 공식에서 레고 가격 수집 (BrickLink API는 v2 예정) | Step 1 시작 시 항상 | `brickeconomy_scraper.py`, `lego_official_scraper.py` |
| `event-collector` | 포켓몬코리아 **공식 웹사이트** + 네이버 카페 공개 게시판에서 이벤트 수집 (SNS 제외) | Step 1 시작 시 항상 | `pokemon_korea_scraper.py`, `naver_cafe_scraper.py` |
| `data-processor` | 에디션 태깅, 그레이딩 정규화, 가격 정규화, 매핑, 병합 | Step 2 시작 시 항상 | `card_name_mapper.py`, `edition_tagger.py`, `grading_normalizer.py`, `price_normalizer.py`, `event_deduplicator.py`, `data_merger.py` |
| `validator` | 데이터 스키마 검증, 이상치 탐지 | Step 3 시작 시 항상 | `validate_data.py` |
| `site-builder` | JSON → 정적 HTML 사이트 생성 | Step 4 시작 시 항상 | `build_site.py` |
