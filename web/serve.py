#!/usr/bin/env python3
"""웹 버전 로컬 확인용 서버.

    python web/serve.py          →  http://localhost:8000

web/ 를 사이트 뿌리로 놓고 /spritecore/ 만 저장소의 실제 폴더로 연결한다.
배포 때 GitHub Actions 가 두 폴더를 한곳에 모아 올리므로, 로컬과 배포판의
경로가 같아진다 (코어를 복사해 두 벌로 만들 필요가 없다).
"""

import argparse
import functools
import http.server
import os
import socketserver
import webbrowser

ROOT = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(ROOT)


class Handler(http.server.SimpleHTTPRequestHandler):
    def translate_path(self, path):
        clean = path.split("?", 1)[0].split("#", 1)[0].lstrip("/")
        if clean.startswith("spritecore/"):
            rel = clean[len("spritecore/"):]
            # 상위 폴더로 빠져나가는 경로는 막는다
            target = os.path.normpath(os.path.join(REPO, "spritecore", rel))
            if target.startswith(os.path.join(REPO, "spritecore")):
                return target
        return super().translate_path(path)

    def end_headers(self):
        # 파이썬 파일을 고칠 때마다 새로 받아 오도록
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *args):
        if "404" in (fmt % args):
            super().log_message(fmt, *args)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-p", "--port", type=int, default=8000)
    ap.add_argument("--no-open", action="store_true", help="브라우저를 열지 않는다")
    args = ap.parse_args()

    handler = functools.partial(Handler, directory=ROOT)
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", args.port), handler) as httpd:
        url = f"http://localhost:{args.port}/"
        print(f"Sprite Studio web  →  {url}   (Ctrl+C 로 종료)")
        if not args.no_open:
            webbrowser.open(url)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n종료했습니다.")


if __name__ == "__main__":
    main()
