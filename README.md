# Sprite Studio

스프라이트 시트를 분리하고 다시 조립하는 데스크톱 도구입니다.

시트를 끌어다 놓으면 그려진 객체를 자동으로 찾아 개별 이미지로 분리합니다. 여러 시트를 등록해 놓고 원하는 스프라이트만 골라 담아, 배치를 눈으로 확인하며 새 시트와 좌표 JSON으로 다시 묶을 수 있습니다.

한국어 · English · 日本語를 지원합니다.

## 다운로드
If you want to use it right away without installation, download `SpriteStudio.exe` from the [latest release](https://github.com/joungjuwon/sprite-studio/releases/latest)

설치 없이 바로 쓰려면 [최신 릴리스](https://github.com/joungjuwon/sprite-studio/releases/latest)에서 `SpriteStudio.exe`를 받으세요.

## 주요 기능

- **자동 분리** — 투명 배경과 단색 배경 모두 지원. 슬라이더로 결과를 실시간 조정
- **좌표 파일 읽기** — TexturePacker JSON, Sparrow/Starling XML, Cocos2d plist, libGDX atlas를 읽어 트리밍·회전된 프레임을 원본 크기 그대로 복원
- **여러 시트 관리** — 썸네일 목록으로 관리하고 시트마다 설정을 따로 기억. 종료 후에도 유지
- **배치 편집** — 드래그로 위치를 직접 수정, 자동 배치와 격자 정렬, 겹침 경고
- **확대와 선택** — 휠 확대, 화면 이동, 범위 드래그로 여러 개 선택
- **출력** — 개별 PNG, 시트별 폴더 일괄 저장, 새 시트 + 좌표 JSON

## 설치

Python 3.8 이상이 필요합니다.

```bash
pip install -r requirements.txt
python sprite_studio.py
```

`tkinterdnd2`가 없으면 드래그앤드롭 대신 파일 선택 버튼으로 동작합니다. `scipy`는 없어도 되지만 큰 시트에서 처리 속도가 크게 차이 납니다.

## 실행 파일 만들기

Windows에서 `build.bat`을 더블클릭하거나:

```bash
python build.py
```

`dist/SpriteStudio.exe` 하나만 배포하면 됩니다. 폴더 방식이 필요하면 `python build.py --onedir`을 쓰세요. 실행 속도가 훨씬 빠릅니다.

## 사용법

**1. 시트 분리 탭** — 시트 이미지를 창에 끌어다 놓으면 자동으로 분석됩니다. 감지 결과가 맞지 않으면 오른쪽 슬라이더를 조정하세요. 파츠가 쪼개지면 "덩어리 묶기"를 올리고, 자잘한 조각이 잡히면 "최소 크기"를 올립니다. 배경이 투명이 아니면 "스포이트"로 배경색을 지정하세요.

시트와 같은 이름의 좌표 파일(`hero.png` ↔ `hero.json`)이 옆에 있으면 자동으로 연결되어 그 좌표를 사용합니다.

**2. 새 시트 배치 탭** — 왼쪽 썸네일을 이 탭으로 끌어다 놓거나 "담기"를 누르면 스프라이트가 모입니다. 드래그로 위치를 조정하고, 자동 배치나 격자 정렬로 정돈한 뒤 출력하세요.

### 조작

| 동작 | 조작 |
|---|---|
| 확대·축소 | 마우스 휠 |
| 화면 이동 | 가운데 또는 오른쪽 버튼 드래그 |
| 화면 맞춤 | 빈 곳 더블클릭 또는 F |
| 범위 선택 | 빈 곳에서 왼쪽 버튼 드래그 |
| 선택 추가 | Shift + 클릭 |
| 전체 선택 | Ctrl+A |
| 선택 제거 | Del |

## 명령줄 도구

GUI 없이 한 장만 빠르게 처리하려면 `extract_sprites.py`를 쓰세요.

```bash
python extract_sprites.py sheet.png -o out/ --merge 5
python extract_sprites.py sheet.png -o out/ --mode grid --cell 32x32
```

## 라이선스

MIT

---

# Sprite Studio (English)

A desktop tool that splits sprite sheets apart and packs them back together.

Drop a sheet and it finds the drawn objects and cuts them into individual images. Register several sheets, pick only the sprites you want, adjust the layout visually, and export a new sheet with a coordinate JSON.

## Features

- **Automatic splitting** — works with transparent or solid backgrounds, with live sliders
- **Atlas import** — reads TexturePacker JSON, Sparrow/Starling XML, Cocos2d plist and libGDX atlas, restoring trimmed and rotated frames to their original size
- **Multi-sheet library** — thumbnails, per-sheet settings, restored between sessions
- **Layout editing** — drag to reposition, auto pack, grid align, overlap warnings
- **Zoom and selection** — wheel zoom, panning, box selection
- **Export** — individual PNGs, batch export per sheet, or a packed sheet with JSON

## Quick start

```bash
pip install -r requirements.txt
python sprite_studio.py
```

To build a standalone Windows executable, run `python build.py` and share `dist/SpriteStudio.exe`.

---

# Sprite Studio (日本語)

スプライトシートを分割し、再び組み立てるデスクトップツールです。

シートをドロップすると描かれたオブジェクトを自動で探し、個別画像に切り出します。複数のシートを登録し、必要なスプライトだけを集めて、配置を目で確認しながら新しいシートと座標JSONとして出力できます。

## 主な機能

- **自動分割** — 透明背景・単色背景の両方に対応、スライダーでリアルタイム調整
- **座標ファイルの読み込み** — TexturePacker JSON、Sparrow/Starling XML、Cocos2d plist、libGDX atlas に対応し、トリミング・回転されたフレームを元のサイズに復元
- **複数シート管理** — サムネイル一覧、シートごとの設定、終了後も保持
- **配置編集** — ドラッグで位置調整、自動配置、グリッド整列、重なり警告
- **拡大と選択** — ホイール拡大、画面移動、範囲ドラッグでの複数選択
- **出力** — 個別PNG、シートごとの一括保存、新シート＋座標JSON

## はじめに

```bash
pip install -r requirements.txt
python sprite_studio.py
```

Windows用の実行ファイルは `python build.py` で作成できます。
