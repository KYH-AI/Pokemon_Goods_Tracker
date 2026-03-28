#!/usr/bin/env python3
"""
BrickLink API 스텁 — v2 예정.
config/sources.json의 bricklink.enabled 가 false인 동안 실행 시 즉시 종료.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent.parent.parent


def main():
    sources_path = ROOT / "config/sources.json"
    if sources_path.exists():
        sources = json.loads(sources_path.read_text(encoding="utf-8"))
        enabled = sources.get("lego_sources", {}).get("bricklink", {}).get("enabled", False)
    else:
        enabled = False

    if not enabled:
        print("[bricklink_api] 비활성화 상태 (enabled: false). v2 예정. 스킵.")
        sys.exit(0)

    # 이 코드는 enabled: true 로 변경 전까지 실행되지 않음
    print("[bricklink_api] 활성화됨. BrickLink API 수집 시작 (미구현).")
    # TODO: v2에서 OAuth 1.0a 인증 후 카탈로그 가격 수집 구현


if __name__ == "__main__":
    main()
