# 4. 주요 산출물 파일 형식

## 4.1 cards.json (카드 시세)
```json
{
  "updated_at": "2026-03-28T09:00:00+09:00",
  "source_status": {
    "tcgplayer": "ok",
    "pricecharting": "ok",
    "ebay": "ok",
    "naver_cafe": "ok",
    "bunjang": "ok",
    "daangn": "blocked"
  },
  "cards": [
    {
      "id": "sv-pikachu-vangogh",
      "name_ko": "반고흐 피카츄",
      "name_en": "Pikachu with Grey Felt Hat",
      "set": "SVP Black Star Promos",
      "category": "collab",
      "thumbnail_url": "https://product-images.tcgplayer.com/...",
      "editions": [
        {
          "edition": "en",
          "edition_label": "영어판",
          "prices": {
            "raw": {
              "market_avg_usd": 125.50,
              "market_avg_krw": 168000,
              "low_usd": 110.00,
              "high_usd": 145.00,
              "price_change_pct": -2.3
            },
            "graded": [
              {
                "company": "PSA",
                "grade": "10",
                "market_avg_usd": 850.00,
                "market_avg_krw": 1139000,
                "price_change_pct": 5.2
              },
              {
                "company": "BGS",
                "grade": "9.5",
                "market_avg_usd": 550.00,
                "market_avg_krw": 737000,
                "price_change_pct": 2.5
              }
            ]
          },
          "sources": ["tcgplayer", "pricecharting", "ebay"],
          "ebay_sold": {
            "recent_sold_count": 12,
            "avg_sold_usd": 122.00,
            "last_sold_date": "2026-03-27",
            "last_scraped": "2026-03-28T09:00:00+09:00"
          }
        },
        {
          "edition": "kr",
          "edition_label": "한국판",
          "prices": {
            "raw": {
              "market_avg_krw": 95000,
              "low_krw": 85000,
              "high_krw": 110000,
              "price_change_pct": 3.1
            },
            "graded": [
              {
                "company": "PSA",
                "grade": "10",
                "market_avg_krw": 450000,
                "price_change_pct": 12.0
              }
            ]
          },
          "domestic_listings": {
            "bunjang": {
              "active_count": 5,
              "price_range_krw": [82000, 115000],
              "avg_krw": 93000,
              "last_scraped": "2026-03-28T09:00:00+09:00",
              "status": "ok"
            },
            "daangn": {
              "active_count": 2,
              "price_range_krw": [90000, 100000],
              "avg_krw": 95000,
              "last_scraped": "2026-03-28T09:00:00+09:00",
              "status": "ok"
            }
          },
          "sources": ["naver_cafe", "bunjang", "daangn"],
          "source_note": "커뮤니티 시세 + 중고플랫폼 매물 기반 (비공식, 판매 희망가)"
        }
      ],
      "last_updated": "2026-03-28T09:00:00+09:00",
      "last_seen_date": "2026-03-28",
      "warning_flags": []
    }
  ]
}
```

**카드 데이터 모델 설계 원칙**:

| 구분 | 규칙 |
|------|------|
| **에디션 키** | `kr` (한국판), `en` (영어판). `jp` (일본판)은 v2 예정 (수집 방법 미확인) |
| **그레이딩 등급** | PSA: `10`, `9`, `8` / BGS: `10`, `9.5`, `9`, `8.5` 만 추적 |
| **미그레이딩 (raw)** | `prices.raw` 필드에 별도 저장. 모든 카드에 필수 |
| **가격 단위** | 해외판: USD + KRW 환산 병기. 국내판: KRW만 |
| **가격 없음 처리** | 해당 등급 거래 데이터가 없으면 `graded` 배열에서 해당 항목 제외 (null 사용 금지) |
| **국내판 그레이딩 데이터** | 한국판 PSA/BGS 데이터는 있으면 표시, 없으면 `graded` 배열에서 생략 (데이터 희박) |
| **eBay 데이터 적용 범위** | `ebay_sold` 필드는 **영어판(en) 에디션에만** 포함. 한국판(kr)에는 eBay 데이터 없음 |
| **국내판 소스 표시** | `source_note` 필드로 비공식 소스임을 명시 |
| **국내 실거래 매물 (`domestic_listings`)** | 번개장터/당근마켓 매물 정보. 각 소스별 `status` 필드로 수집 상태 관리 (`ok` / `blocked` / `error`) |
| **매물 가격 = 판매 희망가** | 당근/번개장터 가격은 실거래가가 아닌 판매 희망가임을 UI에 명시. 번개장터는 수수료(6%+) 별도 |
| **소스 자동 비활성화** | 3일 연속 차단 시 해당 소스 `status`를 `disabled`로 변경, 수동 재활성화 필요 |
| **last_seen_date** | 마지막으로 이 카드의 시세 데이터가 수집된 날짜. 콜라보 카드 등 거래가 드문 카드의 데이터 신선도 표시에 사용 |
| **이상치 임계값** | `price_change_pct` 절대값 ≥ 30% 이상 변동 시 `warning_flags`에 플래그. 경고 배지 + 현재가 그대로 표시 (데이터 숨기지 않음) |
| **썸네일 이미지** | TCGPlayer/PriceCharting 이미지 URL을 직접 참조. 레포에 저장 안 함 |

---

## 4.2 lego.json (레고 가격)
```json
{
  "updated_at": "2026-03-28T09:00:00+09:00",
  "items": [
    {
      "id": "lego-pokemon-xxxxx",
      "name_ko": "포켓몬 피카츄 레고",
      "set_number": "XXXXX",
      "retail_price_krw": 59900,
      "used_market_price_krw": 96000,
      "premium_pct": 60.3,
      "availability": "in_stock",
      "sources": ["brickeconomy", "lego_official"],
      "last_updated": "2026-03-28T09:00:00+09:00"
    }
  ]
}
```

> `premium_pct` = `(used_market_price_krw / retail_price_krw - 1) × 100`. 예: 정가 59,900원, 중고 96,000원 → 프리미엄 +60%.
> **BrickLink API는 v2 예정**. v1에서는 BrickEconomy 크롤링 + LEGO 공식 사이트만 수집.

---

## 4.3 events.json (이벤트/행사)
```json
{
  "updated_at": "2026-03-28T09:00:00+09:00",
  "events": [
    {
      "id": "evt-20260401-pokemon-center",
      "title": "포켓몬센터 서울 오픈 기념 이벤트",
      "category": "offline_event",
      "date_start": "2026-04-01",
      "date_end": "2026-04-15",
      "location": "서울 강남",
      "description": "...",
      "source": "pokemon_korea_official",
      "source_url": "https://...",
      "last_updated": "2026-03-28T09:00:00+09:00"
    }
  ]
}
```

이벤트 카테고리 값: `offline_event` | `cardshop_event` | `collab_event` | `new_release`

---

## 4.4 watchlist.json (추적 대상 설정)
```json
{
  "cards": [
    {
      "id": "sv-pikachu-vangogh",
      "name_en": "Pikachu with Grey Felt Hat",
      "name_ko": "반고흐 피카츄",
      "set": "SVP Black Star Promos",
      "category": "collab",
      "editions": ["en", "kr"],
      "tcgplayer_id": "...",
      "pricecharting_id": "...",
      "ebay_search_keywords": ["Pikachu Grey Felt Hat", "Pikachu Van Gogh promo"],
      "naver_cafe_keywords": ["반고흐 피카츄", "반고흐피카츄", "Van Gogh Pikachu"],
      "domestic_search_keywords": ["반고흐 피카츄", "반고흐피카츄 카드", "피카츄 반고흐"]
    }
  ],
  "lego": [
    {
      "id": "lego-pokemon-xxxxx",
      "name_ko": "포켓몬 피카츄 레고",
      "set_number": "XXXXX",
      "bricklink_id": "...",
      "brickeconomy_url": "..."
    }
  ]
}
```

---

## 4.5 grading_config.json (추적할 그레이딩 등급)
```json
{
  "grading_companies": {
    "PSA": {
      "grades": ["10", "9", "8"],
      "labels": {
        "10": "Gem Mint",
        "9": "Mint",
        "8": "NM-MT"
      }
    },
    "BGS": {
      "grades": ["10", "9.5", "9", "8.5"],
      "labels": {
        "10": "Pristine / Black Label",
        "9.5": "Gem Mint",
        "9": "Mint",
        "8.5": "NM-MT+"
      }
    }
  }
}
```
