# API 키 발급 및 GitHub Secrets 설정 가이드

## 1. eBay Developer Program API 키 발급

eBay Browse API를 사용하면 낙찰가를 보다 안정적으로 수집할 수 있습니다.
미설정 시 HTML 크롤링 폴백으로 동작합니다.

**발급 절차:**

1. [eBay Developer Program](https://developer.ebay.com) 접속 → 계정 생성
2. 로그인 후 **My Account → Application Keys** 메뉴 이동
3. **Create an Application** 버튼 클릭
   - Application Name: `PokemonGoodsPriceTracker` (임의 입력)
   - Environment: **Production** 선택
4. 생성 완료 후 **App ID (Client ID)** 복사
   - Production: `App ID` 열의 값

**주의사항:**
- eBay Browse API는 OAuth 2.0 인증이 필요합니다
- 현재 구현은 폴백 크롤링 사용 (API 키 없어도 기본 동작)
- API 키 설정 시 `ebay_scraper.py` 상단의 OAuth 인증 코드를 활성화 필요

---

## 2. 한국은행 ECOS API 키 발급

USD/KRW 환율 자동 갱신에 사용됩니다. 미설정 시 폴백 환율(1340원) 사용.

**발급 절차:**

1. [한국은행 ECOS](https://ecos.bok.or.kr) 접속
2. 우측 상단 **로그인** → 회원가입 (무료)
3. 로그인 후 **오픈 API → API 신청** 메뉴
4. **API 키 발급 신청** 버튼 클릭
   - 이용 목적: 환율 정보 조회 (개인 프로젝트)
5. 발급된 **API Key** 복사

**확인 방법:**
```
https://ecos.bok.or.kr/api/StatisticSearch/{YOUR_KEY}/json/kr/1/1/731Y001/DD/20260101/20260101/0000001
```
응답에 `DATA_VALUE` 필드에 환율값이 있으면 정상.

---

## 3. Anthropic API 키 발급

data-enrichment-agent의 LLM 기능에 사용됩니다. 미설정 시 LLM 작업 스킵.

**발급 절차:**

1. [Anthropic Console](https://console.anthropic.com) 접속
2. 계정 생성 후 로그인
3. **API Keys** 메뉴 → **Create Key** 버튼
4. Key Name: `pokemon-goods-tracker` 입력 후 생성
5. `sk-ant-...` 형태의 API 키 복사 (한 번만 표시됨)

**비용 안내:**
- 예상 월 사용량: 매우 적음 (주 1~2회, 신규 데이터 있을 때만 호출)
- Claude claude-opus-4-5 기준 입/출력 토큰 과금
- 초기 $5 무료 크레딧 제공 (충분한 수준)

---

## 4. GitHub Secrets 설정

수집한 API 키들을 GitHub Secrets에 등록합니다.

**등록 절차:**

1. GitHub 저장소 페이지 이동
2. **Settings** 탭 클릭
3. 좌측 메뉴 **Secrets and variables → Actions**
4. **New repository secret** 버튼 클릭
5. 아래 각 키를 등록:

| Secret Name | 값 | 필수 여부 |
|-------------|---|--------|
| `ANTHROPIC_API_KEY` | `sk-ant-...` | 선택 (없으면 LLM 스킵) |
| `EBAY_API_KEY` | eBay App ID | 선택 (없으면 크롤링 폴백) |
| `BOK_API_KEY` | 한국은행 ECOS 키 | 선택 (없으면 폴백 환율 사용) |
| `GOOGLE_SHEET_ID` | 구글시트 ID | 선택 (이벤트 수동 입력용) |

**구글시트 ID 찾기:**
- 시트 URL: `https://docs.google.com/spreadsheets/d/{여기가_ID}/edit`
- 공개 설정: **파일 → 공유 → 링크가 있는 모든 사용자 → 뷰어** 설정 필요

**구글시트 컬럼 형식 (이벤트 수동 입력):**
```
title, start_date, end_date, url, description, category
```

---

## 5. GitHub Pages 활성화

1. 저장소 **Settings → Pages** 이동
2. **Source**: `Deploy from a branch` 선택
3. **Branch**: `gh-pages` / `/ (root)` 선택
4. **Save** 클릭

첫 배포 후 `https://{username}.github.io/{repo-name}` 에서 접근 가능.

---

## 6. 워크플로우 수동 실행

GitHub Actions 탭 → **포켓몬 굿즈 시세 수집 및 배포** → **Run workflow** 버튼

옵션:
- `배포 스킵`: 체크 시 수집만 실행 (테스트 목적)
- `LLM 강제 실행`: 체크 시 변경 없어도 LLM 에이전트 실행
