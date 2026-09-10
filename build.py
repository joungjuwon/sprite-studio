#!/usr/bin/env python3
"""
Sprite Studio 빌드 스크립트.

실행:
    python build.py

sprite_studio.spec 이 같은 폴더에 있으면 그것을 사용하고,
없으면 명령줄 옵션으로 직접 빌드합니다.
"""

import argparse
import os
import shutil
import subprocess
import sys

DEPS = ["pillow", "numpy", "scipy", "tkinterdnd2", "pyinstaller"]


def human(nbytes):
    for unit in ("B", "KB", "MB", "GB"):
        if nbytes < 1024 or unit == "GB":
            return f"{nbytes:.1f} {unit}"
        nbytes /= 1024


def run(cmd, label):
    print(f"  $ {' '.join(cmd)}")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"\n[실패] {label} 단계에서 오류가 발생했습니다.")
        return False
    return True


def open_folder(path):
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.run(["open", path])
        else:
            subprocess.run(["xdg-open", path])
    except Exception:
        pass


def main():
    ap = argparse.ArgumentParser(description="Sprite Studio 실행 파일 빌드")
    ap.add_argument("--source", default="sprite_studio.py", help="빌드할 파이썬 파일")
    ap.add_argument("--spec", default="sprite_studio.spec", help="PyInstaller spec 파일")
    ap.add_argument("--name", default="SpriteStudio", help="실행 파일 이름")
    ap.add_argument("--onedir", action="store_true",
                    help="단일 파일 대신 폴더로 빌드 (실행이 훨씬 빠름)")
    ap.add_argument("--skip-deps", action="store_true", help="라이브러리 설치 단계 생략")
    ap.add_argument("--console", action="store_true", help="콘솔 창 함께 표시 (디버깅용)")
    args = ap.parse_args()

    print("=" * 52)
    print("  Sprite Studio 빌드")
    print("=" * 52)
    print(f"파이썬: {sys.version.split()[0]}  ({sys.executable})")

    if not os.path.exists(args.source):
        print(f"\n[오류] '{args.source}' 을(를) 찾을 수 없습니다.")
        print("이 스크립트를 sprite_studio.py 와 같은 폴더에 두고 실행하세요.")
        print(f"현재 폴더: {os.getcwd()}")
        return 1

    # 1) 라이브러리
    if args.skip_deps:
        print("\n[1/3] 라이브러리 설치 생략")
    else:
        print("\n[1/3] 필요한 라이브러리 설치 중…")
        if not run([sys.executable, "-m", "pip", "install", "--upgrade", *DEPS],
                   "라이브러리 설치"):
            return 1

    # 2) 정리
    print("\n[2/3] 이전 빌드 정리")
    for d in ("build", "dist"):
        if os.path.isdir(d):
            shutil.rmtree(d, ignore_errors=True)
            print(f"  {d}/ 삭제")

    # 3) 빌드
    print("\n[3/3] 실행 파일 생성 중… (2~5분 걸립니다)")
    if os.path.exists(args.spec) and not args.onedir:
        cmd = [sys.executable, "-m", "PyInstaller", args.spec, "--noconfirm", "--clean"]
    else:
        cmd = [sys.executable, "-m", "PyInstaller",
               "--onedir" if args.onedir else "--onefile",
               "--console" if args.console else "--windowed",
               "--name", args.name,
               "--collect-all", "tkinterdnd2",
               "--hidden-import", "scipy.ndimage",
               "--noconfirm", "--clean", args.source]
        if os.path.exists("sprite_studio.ico"):
            cmd += ["--icon", "sprite_studio.ico"]
        if os.path.exists(args.spec) and args.onedir:
            print("  (--onedir 이므로 spec 파일 대신 명령줄 옵션 사용)")

    if not run(cmd, "PyInstaller 빌드"):
        print("\n자주 있는 원인:")
        print("  · 백신이 빌드 폴더를 잠금 → 실시간 검사에서 이 폴더를 예외 처리")
        print("  · 이전에 만든 exe 가 실행 중 → 종료 후 다시 시도")
        return 1

    # 결과 확인
    print("\n" + "=" * 52)
    exe_name = args.name + (".exe" if sys.platform.startswith("win") else "")
    candidates = [os.path.join("dist", exe_name),
                  os.path.join("dist", args.name, exe_name)]
    found = next((p for p in candidates if os.path.exists(p)), None)
    if found:
        print(f"  완료: {found}  ({human(os.path.getsize(found))})")
        if args.onedir:
            total = sum(os.path.getsize(os.path.join(r, f))
                        for r, _, fs in os.walk(os.path.join("dist", args.name))
                        for f in fs)
            print(f"  폴더 전체 크기: {human(total)} (폴더째로 압축해서 배포하세요)")
    else:
        print("  빌드는 끝났지만 실행 파일을 찾지 못했습니다. dist 폴더를 확인하세요.")
    print("=" * 52)
    open_folder("dist")
    return 0


if __name__ == "__main__":
    code = main()
    if sys.platform.startswith("win"):
        input("\n엔터를 누르면 창이 닫힙니다…")
    sys.exit(code)
