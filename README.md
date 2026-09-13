<div align="center">

# Sprite Studio

Extract sprites from a sprite sheet, then pack the ones you need into a new sheet.<br>
스프라이트 시트에서 스프라이트를 추출하고, 필요한 것만 모아 새 시트로 묶습니다.<br>
スプライトシートからスプライトを抽出し、必要なものだけを新しいシートにまとめます。

[![Open the web app](https://img.shields.io/badge/Web_app-Open_in_browser-0b7285?style=for-the-badge)](https://joungjuwon.github.io/sprite-studio/)
[![Download for Windows](https://img.shields.io/badge/Windows-SpriteStudio.exe-3c3f41?style=for-the-badge)](https://github.com/joungjuwon/sprite-studio/releases/latest)

**[English](#english)** · **[한국어](#korean)** · **[日本語](#japanese)**

</div>

The web app runs entirely in your browser: nothing to install, and your images are never uploaded.<br>
웹 앱은 브라우저 안에서만 동작합니다. 설치할 것이 없고 이미지는 업로드되지 않습니다.<br>
Web アプリはブラウザの中だけで動作します。インストール不要で、画像はアップロードされません。

---

<a id="english"></a>

## English

### Web app or desktop app

Both give the same results; they run the same detection and packing code.

| | Web app | Desktop app (Windows) |
|---|---|---|
| Start | [Open the link](https://joungjuwon.github.io/sprite-studio/). The first load takes a few seconds | Download [`SpriteStudio.exe`](https://github.com/joungjuwon/sprite-studio/releases/latest) and run it |
| Saving | Downloads a `.zip` | Writes to a folder you choose |
| Atlas file next to the sheet | Load it yourself | Linked automatically |
| Sheets after closing | Cleared | Restored on next launch |

Supported images: PNG, JPG, BMP, GIF, WEBP, TGA.
Supported atlas files: TexturePacker JSON, Sparrow/Starling XML, Cocos2d plist, libGDX atlas.

Option panels on the right open and close when you click their title.

### 1. Extract sprites

1. Drag one or more sheet images onto the window, or click **Add sheets…**.
   Each sheet appears as a thumbnail on the left. Click a thumbnail to switch sheets.
2. Sprites are detected automatically and outlined in cyan. The number found is shown under the image.
3. If the outlines are wrong, open **Extract options** and adjust. Results update as you move a slider.

   | Problem | Fix |
   |---|---|
   | One sprite is split into several boxes | Raise **Merge gap (px)** |
   | Small specks are picked up | Raise **Min width/height (px)** or **Min pixel count** |
   | The background is not transparent | Check **Solid background**, click **Picker**, then click the background in the image |
   | Background edges remain around sprites | Raise **Background tolerance** |

   These options apply to the selected sheet only. To use them everywhere, click **Apply these settings to all sheets**.
4. To export only some sprites, click a sprite or drag across an empty area to select several.
   Shift+click or Shift+drag adds to the selection. Selected sprites turn yellow.
5. In **Crop and naming**, set how files are cut and named:
   - **Padding (px)**: empty space around each sprite
   - **Pad all to equal squares**: every file gets the same square size
   - **Name prefix**: files are named `prefix_000.png`, `prefix_001.png`, …
   - **Save coordinates too** (web only): also writes a JSON file with each sprite's position in the sheet
6. Click the large export button at the bottom right.
   It exports the selected sprites if any are selected, otherwise all of them.
   - Web: `<prefix>_sprites.zip` is downloaded.
   - Desktop: choose an **Output folder** first.

   **Export every sheet at once** saves every registered sheet, one folder per sheet.

### 2. Use an existing atlas file

If the sheet came with an atlas file, its frame coordinates are used instead of pixel detection.
Trimmed and rotated frames are restored to their original shape.

1. Link the file:
   - Desktop: keep the file next to the image with the same name (`hero.png` and `hero.json`). It is linked when the sheet is added.
   - Web: add the sheet first, then open **Atlas file** and click **Load…**, or drop the atlas file onto the window.
2. Check the result. Under **Atlas file**:
   - **Use the atlas file**: turn off to go back to pixel detection
   - **Restore trimmed size**: keeps the original frame size, including trimmed transparent space
   - **Flip rotation**: use this if rotated frames come out sideways
3. Export the same way as in step 6 above.

### 3. Build a new sheet

1. Collect sprites. Any of these works:
   - Drag a sheet thumbnail from the left onto the **2. Build sheet** tab.
   - On tab 1, under **Add to new sheet**, click **Add this sheet** or **Add all sheets**.
   - On tab 1, select sprites and click **Add selection only**.
   - On tab 2, click **Add images…** or drop separate image files.
2. Open the **2. Build sheet** tab. Sprites are placed automatically.
3. Arrange them:
   - **Auto pack**: packs sprites tightly
   - **Grid align**: lines sprites up in a grid, in their current on-screen order
   - Drag a sprite to move it. **Snap (px)** sets the step size.
   - Overlapping sprites are outlined in red.
4. Adjust **Layout options** if needed:
   - **Max width**: the widest the sheet may get. Leave blank for automatic.
   - **Spacing (px)**: gap between sprites
   - **Round size to power of two**: sheet size becomes 256, 512, 1024, …
5. Click **Export new sheet**.
   - Web: `packed_sheet.zip` is downloaded, containing `packed_sheet.png` and `packed_sheet.json`.
   - Desktop: choose where to save `packed_sheet.png`. The JSON is saved next to it.

   The JSON lists every frame's position so a game engine can find it:

   ```json
   {
     "image": "packed_sheet.png",
     "size": { "w": 256, "h": 128 },
     "frames": [
       { "name": "hero_000", "x": 0, "y": 0, "w": 32, "h": 48, "source": "hero" }
     ]
   }
   ```

### Controls

| Action | Input |
|---|---|
| Zoom | Mouse wheel |
| Pan | Drag with the middle or right mouse button |
| Fit to window | Double-click, or press F |
| Select an area | Drag across an empty area |
| Add to selection | Shift+click or Shift+drag |
| Select all | Ctrl+A |
| Remove selected from the new sheet | Del (tab 2) |

### Language

The app opens in your browser or system language: English, Korean or Japanese.
Any other language opens in English. To change it, use the **Language** menu at the top left.
Your choice is remembered.

### Privacy

In the web app, images are processed inside your browser and never sent anywhere.
Anonymous visit and feature-use counts are collected with [Umami](https://umami.is/): no cookies, and no images, file names or error messages.
Your browser's Do Not Track setting is respected.

---

<a id="korean"></a>

## 한국어

### 웹 앱과 데스크톱 앱

둘 다 같은 감지·배치 코드를 쓰기 때문에 결과가 같습니다.

| | 웹 앱 | 데스크톱 앱 (Windows) |
|---|---|---|
| 시작 | [링크를 엽니다](https://joungjuwon.github.io/sprite-studio/). 처음에는 몇 초 걸립니다 | [`SpriteStudio.exe`](https://github.com/joungjuwon/sprite-studio/releases/latest)를 받아 실행합니다 |
| 저장 | `.zip` 파일로 내려받습니다 | 지정한 폴더에 저장합니다 |
| 시트 옆의 좌표 파일 | 직접 불러옵니다 | 자동으로 연결됩니다 |
| 닫은 뒤의 시트 목록 | 사라집니다 | 다음 실행 때 복원됩니다 |

지원하는 이미지: PNG, JPG, BMP, GIF, WEBP, TGA.
지원하는 좌표 파일: TexturePacker JSON, Sparrow/Starling XML, Cocos2d plist, libGDX atlas.

오른쪽 옵션 칸은 제목을 누르면 펼쳐지고 접힙니다.

### 1. 스프라이트 추출

1. 시트 이미지를 창에 끌어다 놓거나 **시트 추가…** 를 누릅니다. 여러 장을 한 번에 넣을 수 있습니다.
   시트는 왼쪽에 썸네일로 쌓이고, 썸네일을 누르면 그 시트로 바뀝니다.
2. 스프라이트가 자동으로 감지되어 하늘색 테두리가 그려집니다. 감지된 개수는 그림 아래에 표시됩니다.
3. 테두리가 맞지 않으면 **추출 옵션** 을 열어 조정합니다. 슬라이더를 움직이면 결과가 바로 바뀝니다.

   | 증상 | 조정 |
   |---|---|
   | 스프라이트 하나가 여러 칸으로 쪼개짐 | **조각 합치기(px)** 를 올립니다 |
   | 자잘한 점까지 잡힘 | **최소 가로·세로(px)** 또는 **최소 픽셀 수** 를 올립니다 |
   | 배경이 투명하지 않음 | **단색 배경** 을 켜고 **스포이트** 를 누른 뒤 그림의 배경을 클릭합니다 |
   | 스프라이트 둘레에 배경색이 남음 | **배경색 허용 범위** 를 올립니다 |

   이 옵션은 선택한 시트에만 적용됩니다. 모든 시트에 쓰려면 **이 설정을 모든 시트에 적용** 을 누릅니다.
4. 일부만 내보내려면 스프라이트를 클릭하거나, 빈 곳을 드래그해 여러 개를 고릅니다.
   Shift를 누른 채 클릭하거나 드래그하면 선택에 더해집니다. 선택된 스프라이트는 노란색으로 바뀝니다.
5. **잘라내기 · 파일 이름** 에서 파일을 자르는 방식과 이름을 정합니다.
   - **여백(px)**: 스프라이트 둘레에 남길 빈 공간
   - **정사각형으로 크기 통일**: 모든 파일을 같은 크기의 정사각형으로 맞춤
   - **이름 접두어**: 파일 이름이 `접두어_000.png`, `접두어_001.png` … 로 붙음
   - **좌표 파일 함께 저장** (웹 전용): 시트 안에서 각 스프라이트의 위치를 적은 JSON도 저장
6. 오른쪽 아래의 큰 내보내기 버튼을 누릅니다.
   선택한 스프라이트가 있으면 그것만, 없으면 전부 내보냅니다.
   - 웹: `<접두어>_sprites.zip` 을 내려받습니다.
   - 데스크톱: 먼저 **저장 폴더** 를 지정합니다.

   **모든 시트 한 번에 내보내기** 는 등록된 시트를 전부 시트별 폴더로 나눠 저장합니다.

### 2. 기존 좌표 파일 쓰기

시트와 함께 받은 좌표 파일이 있으면 픽셀 감지 대신 그 좌표로 자릅니다.
트리밍되거나 회전된 프레임도 원래 모습으로 되돌립니다.

1. 좌표 파일을 연결합니다.
   - 데스크톱: 이미지와 같은 이름으로 같은 폴더에 두면(`hero.png` 와 `hero.json`) 시트를 추가할 때 자동으로 연결됩니다.
   - 웹: 시트를 먼저 추가한 뒤 **좌표 파일 (아틀라스)** 에서 **불러오기…** 를 누르거나, 좌표 파일을 창에 끌어다 놓습니다.
2. 결과를 확인합니다. **좌표 파일 (아틀라스)** 안에서:
   - **좌표 파일 사용**: 끄면 픽셀 감지로 돌아갑니다
   - **트리밍 원래 크기로 복원**: 잘려 나간 투명 여백까지 포함해 원래 프레임 크기로 저장합니다
   - **회전 방향 반대로**: 회전된 프레임이 옆으로 누워 나오면 켭니다
3. 위 1번 과정의 6단계와 같은 방법으로 내보냅니다.

### 3. 새 시트 만들기

1. 스프라이트를 모읍니다. 다음 중 편한 방법을 쓰면 됩니다.
   - 왼쪽 시트 썸네일을 **2. 새 시트 만들기** 탭으로 끌어다 놓습니다.
   - 1번 탭의 **새 시트에 추가** 에서 **이 시트 추가** 또는 **모든 시트 추가** 를 누릅니다.
   - 1번 탭에서 스프라이트를 고른 뒤 **선택만 추가** 를 누릅니다.
   - 2번 탭에서 **이미지 추가…** 를 누르거나 낱장 이미지 파일을 끌어다 놓습니다.
2. **2. 새 시트 만들기** 탭을 엽니다. 스프라이트가 자동으로 배치되어 있습니다.
3. 배치를 정리합니다.
   - **자동 배치**: 빈틈 없이 촘촘하게 채웁니다
   - **격자 정렬**: 지금 화면에 놓인 순서대로 격자에 맞춰 줄 세웁니다
   - 스프라이트를 드래그하면 옮겨집니다. 한 번에 움직이는 간격은 **스냅(px)** 으로 정합니다.
   - 서로 겹친 스프라이트는 빨간 테두리로 표시됩니다.
4. 필요하면 **배치 옵션** 을 조정합니다.
   - **최대 너비**: 시트의 최대 가로 크기. 비워 두면 자동으로 정합니다.
   - **간격(px)**: 스프라이트 사이의 간격
   - **2의 거듭제곱 크기로 맞춤**: 시트 크기를 256, 512, 1024 … 로 맞춤
5. **새 시트로 내보내기** 를 누릅니다.
   - 웹: `packed_sheet.png` 와 `packed_sheet.json` 이 든 `packed_sheet.zip` 을 내려받습니다.
   - 데스크톱: `packed_sheet.png` 를 저장할 곳을 고르면 JSON이 그 옆에 함께 저장됩니다.

   JSON에는 게임 엔진이 프레임을 찾을 수 있도록 각 프레임의 위치가 적힙니다.

   ```json
   {
     "image": "packed_sheet.png",
     "size": { "w": 256, "h": 128 },
     "frames": [
       { "name": "hero_000", "x": 0, "y": 0, "w": 32, "h": 48, "source": "hero" }
     ]
   }
   ```

### 조작

| 동작 | 조작 |
|---|---|
| 확대·축소 | 마우스 휠 |
| 화면 이동 | 가운데 또는 오른쪽 버튼으로 드래그 |
| 화면에 맞춤 | 더블클릭 또는 F |
| 범위 선택 | 빈 곳을 드래그 |
| 선택에 더하기 | Shift+클릭 또는 Shift+드래그 |
| 전체 선택 | Ctrl+A |
| 새 시트에서 선택 항목 빼기 | Del (2번 탭) |

### 언어

브라우저 또는 운영체제 언어에 맞춰 영어·한국어·일본어로 열립니다.
그 밖의 언어는 영어로 열립니다. 바꾸려면 왼쪽 위의 **Language** 메뉴를 쓰세요.
직접 고른 언어는 기억됩니다.

### 개인정보

웹 앱에서 이미지는 브라우저 안에서만 처리되고 어디로도 전송되지 않습니다.
[Umami](https://umami.is/)로 익명의 방문 수와 기능 사용 횟수만 셉니다. 쿠키를 쓰지 않으며 이미지, 파일 이름, 오류 문구는 보내지 않습니다.
브라우저의 추적 거부(Do Not Track) 설정을 따릅니다.

---

<a id="japanese"></a>

## 日本語

### Web アプリとデスクトップアプリ

どちらも同じ検出・配置コードを使うので、結果は同じです。

| | Web アプリ | デスクトップアプリ (Windows) |
|---|---|---|
| 起動 | [リンクを開きます](https://joungjuwon.github.io/sprite-studio/)。初回は数秒かかります | [`SpriteStudio.exe`](https://github.com/joungjuwon/sprite-studio/releases/latest) をダウンロードして実行します |
| 保存 | `.zip` ファイルをダウンロード | 指定したフォルダーに保存 |
| シートと同じ場所の座標ファイル | 手動で読み込み | 自動で関連付け |
| 閉じた後のシート一覧 | 消えます | 次回起動時に復元 |

対応画像: PNG, JPG, BMP, GIF, WEBP, TGA。
対応座標ファイル: TexturePacker JSON, Sparrow/Starling XML, Cocos2d plist, libGDX atlas。

右側のオプション欄は、タイトルをクリックすると開閉します。

### 1. スプライトを抽出する

1. シート画像をウィンドウにドラッグするか、**シート追加…** を押します。複数枚まとめて追加できます。
   シートは左側にサムネイルで並び、サムネイルをクリックするとそのシートに切り替わります。
2. スプライトが自動で検出され、水色の枠が表示されます。検出数は画像の下に表示されます。
3. 枠が合わない場合は **抽出オプション** を開いて調整します。スライダーを動かすと結果がすぐ変わります。

   | 症状 | 調整 |
   |---|---|
   | 1つのスプライトが複数の枠に分かれる | **断片を結合(px)** を上げる |
   | 細かい点まで検出される | **最小の幅・高さ(px)** または **最小ピクセル数** を上げる |
   | 背景が透明ではない | **単色背景** をオンにし、**スポイト** を押して画像の背景をクリック |
   | スプライトの周りに背景色が残る | **背景色の許容範囲** を上げる |

   これらのオプションは選択中のシートにのみ適用されます。全シートに使うには **この設定を全シートに適用** を押します。
4. 一部だけを出力するには、スプライトをクリックするか、空いている所をドラッグして複数選択します。
   Shift を押しながらクリックまたはドラッグすると選択に追加されます。選択されたスプライトは黄色になります。
5. **切り出しとファイル名** で切り出し方と名前を決めます。
   - **余白(px)**: スプライトの周りに残す空白
   - **正方形でサイズを統一**: すべてのファイルを同じサイズの正方形にそろえる
   - **名前の接頭辞**: ファイル名が `接頭辞_000.png`, `接頭辞_001.png` … になる
   - **座標ファイルも保存** (Web のみ): シート内での各スプライトの位置を記した JSON も保存
6. 右下の大きな出力ボタンを押します。
   選択したスプライトがあればそれだけを、なければすべてを出力します。
   - Web: `<接頭辞>_sprites.zip` がダウンロードされます。
   - デスクトップ: 先に **保存フォルダー** を指定します。

   **全シートを一括出力** は、登録されたすべてのシートをシートごとのフォルダーに分けて保存します。

### 2. 既存の座標ファイルを使う

シートに座標ファイルが付いている場合は、ピクセル検出の代わりにその座標で切り出します。
トリミングや回転がかかったフレームも元の形に戻します。

1. 座標ファイルを関連付けます。
   - デスクトップ: 画像と同じ名前で同じフォルダーに置いておくと (`hero.png` と `hero.json`)、シート追加時に自動で関連付けられます。
   - Web: 先にシートを追加し、**座標ファイル (アトラス)** の **読み込み…** を押すか、座標ファイルをウィンドウにドラッグします。
2. 結果を確認します。**座標ファイル (アトラス)** の中で:
   - **座標ファイルを使う**: オフにするとピクセル検出に戻ります
   - **トリミングを元のサイズに復元**: 切り取られた透明な余白も含め、元のフレームサイズで保存します
   - **回転方向を反転**: 回転したフレームが横向きになる場合にオンにします
3. 上の手順 1 の 6 と同じ方法で出力します。

### 3. 新しいシートを作る

1. スプライトを集めます。次のどの方法でも構いません。
   - 左のシートサムネイルを **2. 新シート作成** タブにドラッグする。
   - 1番タブの **新シートに追加** で **このシートを追加** または **全シートを追加** を押す。
   - 1番タブでスプライトを選択し、**選択分のみ追加** を押す。
   - 2番タブで **画像を追加…** を押すか、個別の画像ファイルをドラッグする。
2. **2. 新シート作成** タブを開きます。スプライトは自動で配置されています。
3. 配置を整えます。
   - **自動配置**: 隙間なく詰めて並べます
   - **グリッド整列**: 今の画面上の並び順のまま、グリッドにそろえます
   - スプライトはドラッグで移動できます。1回に動く幅は **スナップ(px)** で決めます。
   - 重なっているスプライトは赤い枠で表示されます。
4. 必要に応じて **配置オプション** を調整します。
   - **最大幅**: シートの最大の横幅。空欄なら自動で決まります。
   - **間隔(px)**: スプライト同士の間隔
   - **2の累乗サイズに合わせる**: シートサイズを 256, 512, 1024 … にそろえる
5. **新シートとして出力** を押します。
   - Web: `packed_sheet.png` と `packed_sheet.json` を含む `packed_sheet.zip` がダウンロードされます。
   - デスクトップ: `packed_sheet.png` の保存先を選ぶと、JSON がその隣に保存されます。

   JSON には、ゲームエンジンがフレームを見つけられるよう各フレームの位置が記録されます。

   ```json
   {
     "image": "packed_sheet.png",
     "size": { "w": 256, "h": 128 },
     "frames": [
       { "name": "hero_000", "x": 0, "y": 0, "w": 32, "h": 48, "source": "hero" }
     ]
   }
   ```

### 操作

| 動作 | 操作 |
|---|---|
| 拡大・縮小 | マウスホイール |
| 画面の移動 | 中ボタンまたは右ボタンでドラッグ |
| 画面に合わせる | ダブルクリックまたは F |
| 範囲選択 | 空いている所をドラッグ |
| 選択に追加 | Shift+クリックまたは Shift+ドラッグ |
| すべて選択 | Ctrl+A |
| 新シートから選択項目を外す | Del (2番タブ) |

### 言語

ブラウザまたは OS の言語に合わせて、英語・韓国語・日本語で開きます。
それ以外の言語では英語で開きます。変更するには左上の **Language** メニューを使ってください。
自分で選んだ言語は記憶されます。

### プライバシー

Web アプリでは、画像はブラウザの中だけで処理され、どこにも送信されません。
[Umami](https://umami.is/) で匿名の訪問数と機能の利用回数だけを集計しています。Cookie は使わず、画像・ファイル名・エラーメッセージは送信しません。
ブラウザのトラッキング拒否 (Do Not Track) 設定に従います。

---

## Development

### Run from source

Python 3.8 or later is required.

```bash
pip install -r desktop/requirements.txt
python desktop/sprite_studio.py
```

Without `tkinterdnd2`, drag and drop is disabled and the file buttons are used instead.
`scipy` is optional. Without it, detection uses a pure numpy path with the same results. The web app uses this path.

To try the web app locally:

```bash
python web/serve.py
```

Pushing to `main` deploys the web app to GitHub Pages through GitHub Actions.

### Build the Windows executable

Double-click `desktop/build.bat`, or run:

```bash
python desktop/build.py            # single file: desktop/dist/SpriteStudio.exe
python desktop/build.py --onedir   # folder build, starts faster
```

Pushing a `v*` tag builds the executable and attaches it to a GitHub release.

### Command line

To process a single sheet without the GUI:

```bash
python desktop/extract_sprites.py sheet.png -o out/ --merge 5
python desktop/extract_sprites.py sheet.png -o out/ --mode grid --cell 32x32
```

Run `python desktop/extract_sprites.py -h` for all options.

### Project layout

The desktop and web apps share `spritecore/`.

```
spritecore/            shared core, no UI dependencies (numpy + Pillow only)
  detect.py              find and crop sprites from pixels
  packing.py             new sheet layout
  atlas.py               atlas file parsing (TexturePacker / Sparrow / Cocos2d / libGDX)
  i18n.py                translations used by both apps
  constants.py           shared constants
  util.py                name cleanup, checkerboard

desktop/               desktop app (tkinter)
  sprite_studio.py       the app
  extract_sprites.py     command-line extractor
  build.py · build.bat   executable build
  sprite_studio.spec     PyInstaller config
  requirements.txt       desktop dependencies

web/                   browser app (Pyodide)
  index.html · style.css · app.js   page and tab 1
  layout.js              tab 2 (build sheet)
  track.js               anonymous usage counts (Umami)
  bridge.py              wraps spritecore for the browser
  serve.py               local server for testing

requirements.txt       core dependencies (pillow, numpy)
```

`spritecore` does not depend on tkinter, so it runs unchanged in the browser.
Functions that touch the file system have a counterpart that takes contents instead:
`parse_atlas_file(path)` ↔ `parse_atlas_data(data, ext)`.

## License

MIT
