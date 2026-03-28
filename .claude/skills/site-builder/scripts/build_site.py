#!/usr/bin/env python3
"""
site/templates/index.html → site/build/index.html (last-updated 메타 주입).
site/static/ → site/build/static/ 복사.
data/*.json → site/build/data/ 복사.
site/build/build_info.json 생성.
"""
import json
import shutil
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent.parent.parent
KST = timezone(timedelta(hours=9))

TEMPLATE_DIR = ROOT / "site/templates"
STATIC_DIR = ROOT / "site/static"
DATA_DIR = ROOT / "data"
BUILD_DIR = ROOT / "site/build"


def inject_meta(html: str, build_time: str) -> str:
    """HTML에 빌드 시각 메타 태그 주입."""
    meta_tag = f'<meta name="last-updated" content="{build_time}">\n'
    if "<head>" in html:
        html = html.replace("<head>", f"<head>\n    {meta_tag}", 1)
    return html


def copy_static():
    """site/static/ → site/build/static/ 복사."""
    static_dest = BUILD_DIR / "static"
    if STATIC_DIR.exists():
        if static_dest.exists():
            shutil.rmtree(static_dest)
        shutil.copytree(STATIC_DIR, static_dest)
        print(f"[build_site] static 복사 완료: {STATIC_DIR} → {static_dest}")
    else:
        print(f"[build_site] static 디렉토리 없음, 스킵: {STATIC_DIR}")
        static_dest.mkdir(parents=True, exist_ok=True)


def copy_data_json() -> list:
    """data/*.json → site/build/data/ 복사. 복사된 파일 목록 반환."""
    data_dest = BUILD_DIR / "data"
    data_dest.mkdir(parents=True, exist_ok=True)
    copied = []

    for json_file in ("cards.json", "lego.json", "events.json"):
        src = DATA_DIR / json_file
        if src.exists():
            shutil.copy2(src, data_dest / json_file)
            copied.append(json_file)
            print(f"[build_site] {json_file} 복사")
        else:
            print(f"[build_site] {json_file} 없음, 스킵")

    return copied


def build_html(build_time: str):
    """templates/index.html → build/index.html (메타 주입)."""
    template_path = TEMPLATE_DIR / "index.html"
    if not template_path.exists():
        print(f"[build_site] 오류: 템플릿 없음 {template_path}")
        sys.exit(1)

    html = template_path.read_text(encoding="utf-8")
    html = inject_meta(html, build_time)

    out_path = BUILD_DIR / "index.html"
    out_path.write_text(html, encoding="utf-8")
    print(f"[build_site] index.html 생성: {out_path}")


def write_build_info(build_time: str, copied_files: list):
    """site/build/build_info.json 생성."""
    # 각 데이터 파일에서 updated_at 추출
    data_info = {}
    for fname in copied_files:
        fpath = BUILD_DIR / "data" / fname
        try:
            d = json.loads(fpath.read_text(encoding="utf-8"))
            data_info[fname] = {"updated_at": d.get("updated_at", "")}
        except Exception:
            pass

    build_info = {
        "built_at": build_time,
        "data_files": data_info,
        "pipeline_version": "1.0",
    }
    info_path = BUILD_DIR / "build_info.json"
    info_path.write_text(json.dumps(build_info, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[build_site] build_info.json 생성")


def verify_output():
    """빌드 성공 기준 확인: index.html + data/cards.json 존재."""
    index_ok = (BUILD_DIR / "index.html").exists()
    cards_ok = (BUILD_DIR / "data" / "cards.json").exists()
    if not index_ok or not cards_ok:
        print(f"[build_site] 오류: 빌드 검증 실패 (index.html={index_ok}, cards.json={cards_ok})")
        sys.exit(1)
    print("[build_site] 빌드 검증 통과")


def main():
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    build_time = datetime.now(KST).isoformat()

    print(f"[build_site] 빌드 시작: {build_time}")
    build_html(build_time)
    copy_static()
    copied = copy_data_json()
    write_build_info(build_time, copied)
    verify_output()
    print(f"[build_site] 완료: {BUILD_DIR}")


if __name__ == "__main__":
    main()
