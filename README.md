<div align="center">

# Sprite Studio

Extract sprites from a sprite sheet, then pack the ones you need into a new sheet.<br>
스프라이트 시트에서 스프라이트를 추출하고, 필요한 것만 모아 새 시트로 묶습니다.<br>
スプライトシートからスプライトを抽出し、必要なものだけを新しいシートにまとめます。<br>
从精灵图集中提取精灵，只把需要的合并成新的图集。

[![Open the web app](https://img.shields.io/badge/Web_app-Open_in_browser-0b7285?style=for-the-badge)](https://joungjuwon.github.io/sprite-studio/)
[![Download for Windows](https://img.shields.io/badge/Windows-SpriteStudio.exe-3c3f41?style=for-the-badge)](https://github.com/joungjuwon/sprite-studio/releases/latest)

**[English](#english)** · **[한국어](#korean)** · **[日本語](#japanese)** · **[中文](#chinese)**

</div>

The web app runs entirely in your browser: nothing to install, and your images are never uploaded.<br>
웹 앱은 브라우저 안에서만 동작합니다. 설치할 것이 없고 이미지는 업로드되지 않습니다.<br>
Web アプリはブラウザの中だけで動作します。インストール不要で、画像はアップロードされません。<br>
网页版完全在浏览器中运行，无需安装，图片也不会被上传。

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
| Pan | Drag with the middle or right mouse button (tab 2: middle button only) |
| Draw to place (tab 2) | Drag with the right mouse button (Mac: also Control+drag) |
| Number sprites in click order (tab 1) | N, then click sprites in order. N or Esc to stop |
| Exclude selected sprites (tab 1) | Del (Mac: delete) |
| Fit to window | Double-click, or press F |
| Select an area | Drag across an empty area |
| Add to selection | Shift+click or Shift+drag (Mac: also ⌘+click) |
| Select all | Ctrl+A (Mac: ⌘A) |
| Remove selected from the new sheet | Del (tab 2, Mac: delete) |

### Language

The app opens in your browser or system language: English, Korean, Japanese or Chinese (Simplified).
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

   화면 오른쪽 위의 **되돌리기 (Ctrl+Z) / 다시 실행 (Ctrl+Y)** 로 이 탭에서 한 일을
   되돌릴 수 있습니다. 추출 옵션 변경, 스프라이트 제외, 시트 등록·제거·전체 비우기,
   좌표 파일 연결·해제, 모든 시트에 적용까지 40단계를 기억합니다. 슬라이더를 한 번
   끄는 동안 생긴 변화는 한 칸으로 묶여, 한 번만 되돌리면 원래 값으로 돌아옵니다.
   **두 탭의 기록은 서로 따로입니다** — 지금 보고 있는 탭의 것만 되돌아갑니다.

   | 증상 | 조정 |
   |---|---|
   | 스프라이트 하나가 여러 칸으로 쪼개짐 | **조각 합치기(px)** 를 올립니다 |
   | 자잘한 점까지 잡힘 | **최소 가로·세로(px)** 또는 **최소 픽셀 수** 를 올립니다 |
   | 배경이 투명하지 않음 | **단색 배경** 을 켜고 **스포이트** 를 누른 뒤 그림의 배경을 클릭합니다 |
   | 스프라이트 둘레에 배경색이 남음 | **배경색 허용 범위** 를 올립니다 |

   이 옵션은 선택한 시트에만 적용됩니다. 모든 시트에 쓰려면 **이 설정을 모든 시트에 적용** 을 누릅니다.
4. 감지된 스프라이트는 왼쪽 목록에서 그 시트 **아래에 달립니다.** 시트 줄 오른쪽 아래의
   **▸** 를 누르면 펼쳐지고, 다시 누르면 접힙니다. 하위 항목마다 미리보기·번호·크기가
   보이고 두 가지 단추가 있습니다.

   - **저장** : 그 스프라이트 하나만 바로 PNG 로 저장합니다(웹은 내려받습니다).
   - **보기** : 1번 탭으로 옮겨 가 그 스프라이트만 고르고, 화면 가운데로 확대해 보여 줍니다.

   하위 항목 줄을 **2번 탭 화면이나 탭 머리글로 끌어다 놓으면** 그 스프라이트 하나만
   새 시트에 담깁니다. 스프라이트가 많으면
   먼저 100개까지 보여 주고 맨 아래 **… N개 더 보기** 로 이어서 펼칩니다. 한 번이라도
   파일로 내보낸 시트에는 **추출 완료** 표시가 붙습니다.
5. 일부만 내보내려면 스프라이트를 클릭하거나, 빈 곳을 드래그해 여러 개를 고릅니다.
   Shift를 누른 채 클릭하거나 드래그하면 선택에 더해집니다. 선택된 스프라이트는 노란색으로 바뀝니다.
   필요 없는 것은 고른 뒤 **선택한 스프라이트 제외** (Del) 로 목록에서 뺄 수 있습니다.

   **번호 매기기** 에서 스프라이트 번호를 직접 정할 수 있습니다. 이 번호가 파일 이름
   (`prefix_003.png`)과 새 시트에서 놓이는 순서가 됩니다.
   - **클릭 순서로 번호 매기기 (N)**: 켜고 스프라이트를 원하는 순서대로 누르면 0, 1, 2 …
     가 매겨집니다. 고른 것이 있으면 그중 가장 작은 번호부터 이어서 매깁니다. N 이나 Esc 로 끝냅니다.
   - **선택한 것 번호 바꾸기…** (또는 스프라이트 더블클릭): 새 번호를 적으면 그 자리에 들어가고
     뒤의 번호는 하나씩 밀립니다.
   - **번호 초기화**: 감지된 순서로 되돌립니다.
   - 슬라이더를 움직여 다시 감지해도, 위치가 가장 가까운 스프라이트가 번호를 이어받습니다.
6. **잘라내기 · 파일 이름** 에서 파일을 자르는 방식과 이름을 정합니다.
   - **여백(px)**: 스프라이트 둘레에 남길 빈 공간
   - **정사각형으로 크기 통일**: 모든 파일을 같은 크기의 정사각형으로 맞춤
   - **이름 접두어**: 파일 이름이 `접두어_000.png`, `접두어_001.png` … 로 붙음
   - **좌표 파일 함께 저장** (웹 전용): 시트 안에서 각 스프라이트의 위치를 적은 JSON도 저장
7. 오른쪽 아래의 큰 내보내기 버튼을 누릅니다.
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
3. **그룹** 으로 나누어 배치를 정리합니다.

   스프라이트는 출처 시트별로 **그룹** 에 자동으로 묶이고(이름은 `그룹 1`, `그룹 2`
   … 로 붙습니다. 언제든 바꿀 수 있습니다), 그룹 하나가 시트의
   **가로 한 줄(밴드)** 을 차지합니다. 그룹마다 규칙을 따로 줄 수 있어서, 예를
   들어 걷기 시트는 **격자 정렬**, 표정 시트는 **자동 배치** 로 두고 한 장으로
   합칠 수 있습니다.

   - **그룹 목록**: 화면 바로 아래에 있고, 이름 · 개수 · 방식 · 칸 크기 · 고정
     여부가 보입니다. 줄 오른쪽의 **▲ ▼** 를 누르거나 **위아래로 끌면** 순서가 바뀌고,
     시트에서도 그 순서대로 쌓입니다 (목록에서 위가 시트에서도 위입니다). 목록에서
     고르면 그 그룹의 스프라이트가 화면에서도 선택되고, 배치 옵션이 그 그룹 값으로
     바뀝니다. 두 번 누르면 이름을 바꾸거나, **이름 바꾸기** 버튼을 누릅니다.
   - **그룹 펼치기**: 그룹 왼쪽의 펼침 단추를 누르면 들어 있는 스프라이트가 미리보기와
     1, 2, 3 … 순서로 보입니다. 줄을 누르면 그 스프라이트만 고르고, **▲ ▼** 로 그룹 안
     순서를 바꾸면 배치도 그 순서대로 바뀝니다.
   - **이름**: 새 시트의 스프라이트 이름은 `그룹명_000` 처럼 그룹 안 순서를 따릅니다.
     화면에 보이는 이름과 좌표 JSON 의 프레임 이름이 같습니다.
   - **번호 순서대로 배치** (배치 옵션, 기본 켜짐): 자동 배치·격자 정렬이 1번 탭에서 매긴
     번호 순서를 따릅니다. 끄면 자동 배치는 빈틈이 적게, 격자 정렬은 놓인 자리 순서로 채웁니다.
     목록에서 ▲ ▼ 로 직접 정한 순서는 이 옵션보다 우선합니다.
   - **새 그룹 만들기**: 화면에서 고른 스프라이트를 새 그룹으로 빼냅니다.
     한 시트에 걷기와 표정이 섞여 있을 때 쓰면 됩니다.
   - **합치기**: 고른 스프라이트가 걸쳐 있는 그룹들을 하나로 묶습니다.
   - **전체 다시 쌓기**: 지금 순서·규칙대로 처음부터 다시 배치합니다.
   - **되돌리기 (Ctrl+Z) / 다시 실행 (Ctrl+Y)**: 이 탭에서 한 일을 되돌립니다.
     스프라이트 추가·제거, 자동 배치·격자 정렬, 그룹 만들기·합치기·이름 바꾸기·순서
     바꾸기, 드래그 이동, 그어서 배치, 목록 비우기까지 40단계를 기억합니다.
   - **자동 배치 / 격자 정렬** 버튼은 목록에서 고른 그룹에 적용됩니다.
     고른 것이 없으면 모든 그룹에 적용됩니다.
   - **고정**: 스프라이트를 끌어다 놓거나 **그어서 배치** 한 그룹은 **고정** 되어,
     다시 쌓아도 그 그룹 안의 모양(그은 줄·격자, 옮겨 놓은 자리)이 그대로 남습니다.
     고정된 그룹도 한 줄을 차지하므로 **다른 그룹과 겹치지 않습니다.** 격자 그룹 안에서
     스프라이트를 끌면 칸 단위로 옮겨져 격자가 깨지지 않습니다. **고정 풀기** 를 누르거나
     배치 버튼을 다시 누르면 그룹 규칙대로 다시 배치됩니다.
   - 화면에는 그룹마다 **회색 테두리**(고정된 것은 주황색 점선)가 그려져 어디까지가
     한 그룹인지 보입니다.

   그룹이 여럿이면 시트 전체를 한 격자로는 나눌 수 없으므로, 격자 그룹마다
   **원점** 을 로그와 좌표 JSON에 적어 줍니다. 엔진에서 격자 시작 위치를 그 값으로
   두면(Unity `Offset`, Unreal `Margin X/Y`, Godot `margins`) 그 그룹만 잘라낼 수
   있습니다. 화면의 보라색 칸 경계선도 격자 그룹 위에만 그려집니다.

   격자 그룹의 밴드는 **칸 높이의 배수 자리에서 시작하도록** 자동으로 맞춰집니다.
   밴드 시작이 칸 높이의 배수면 `시작 + 줄 × 칸높이` 도 배수이므로, 엔진에서 원점을
   옮기지 않고 **(0, 0)부터 같은 칸 크기로 나눠도** 그 그룹의 프레임이 칸 경계에
   정확히 떨어집니다. 격자 범위를 칸 개수로 제한할 수 없는 Unity의 `Grid By Cell Size`
   에서 특히 도움이 됩니다(다른 그룹 자리에 생긴 빈 조각만 지우면 됩니다).
   Unreal은 `Num Cells X/Y`, Godot은 타일을 고르는 식으로 범위를 직접 한정할 수 있어
   원점만 맞추면 됩니다.

   - **자동 배치**: 빈틈 없이 촘촘하게 채웁니다
   - **격자 정렬**: 지금 화면에 놓인 순서대로 모든 칸을 같은 크기로 맞춰 줄 세웁니다.
     칸은 시트의 왼쪽 위 (0, 0) 에서 시작해 빈틈없이 이어지고 시트 크기도 칸의
     배수가 되므로, 엔진에서 **칸 크기로 잘라 쓰기**(Unity 의 Grid By Cell Size,
     RPG Maker 의 규격 시트 등) 를 하면 한 칸에 스프라이트가 하나씩 정확히
     들어갑니다. 정렬하고 나면 칸 크기가 로그와 화면 위쪽에 **칸 34×50** 처럼
     표시되니, 그 값을 엔진에 그대로 적어 주면 됩니다. 칸 경계는 화면에 보라색
     선으로 겹쳐 보여 주므로 내보내기 전에 눈으로 확인할 수 있습니다.
   - **그어서 배치**: 오른쪽 버튼으로 원하는 모양대로 그으면 그대로 놓입니다.
     왼쪽 버튼은 늘 선택과 이동입니다. 칸은 시트 (0, 0) 부터 이어지는 격자에 맞춰집니다.
     가로로 그으면 가로 한 줄, 세로로 그으면 세로 한 줄, 넓게 상자로 그으면 격자가 됩니다.
     거꾸로(오른쪽→왼쪽, 아래→위) 그으면 그 방향으로 놓입니다.
     스프라이트를 골라 두었으면 고른 것만, 아니면 전체가 대상입니다.
     손을 떼기 전까지 점선으로 미리 보여 줍니다.
     - 칸은 **격자 정렬과 같은 설정**(간격·격자·칸 안 정렬·2의 거듭제곱)으로 정해집니다.
       그은 순서가 곧 그룹 안 순서(이름 번호)가 됩니다.
     - 지금 설정으로 칸이 얼마가 되는지 옵션 바로 아래에 **칸 48×64** 처럼 표시됩니다.
   - 스프라이트를 드래그하면 옮겨집니다. 한 번에 움직이는 간격은 **스냅(px)** 으로 정합니다.
   - 서로 겹친 스프라이트는 빨간 테두리로 표시됩니다.
4. 필요하면 **배치 옵션** 을 조정합니다.
   - **최대 너비**: 시트의 최대 가로 크기. 비워 두면 자동으로 정합니다.
   - **간격(px)**: 스프라이트 사이의 간격. 격자 정렬에서는 이 간격까지 칸 크기에
     포함되므로, 칸은 `가장 큰 스프라이트 + 간격` 이 됩니다.
   - **격자(px)**: 칸 크기를 이 값의 배수로 올려 맞춥니다. 16이나 32를 넣으면
     모든 프레임이 그 배수 자리에 서기 때문에 타일 기반 엔진에 바로 들어갑니다.
     0이면 끄고 칸을 가장 큰 스프라이트에 딱 맞춥니다. **격자 정렬** 과
     **그어서 배치** 가 함께 씁니다. **2의 거듭제곱 크기로 맞춤** 이 켜져 있으면
     그쪽이 우선합니다.
   - **칸 안 정렬**: 격자 정렬·그어서 배치에서 스프라이트를 칸 안 어디에 놓을지 정합니다.
     가로는 늘 가운데이고 세로만 고릅니다.
     - **가운데**: 칸 정중앙. 기본값이고 대부분의 경우에 맞습니다.
     - **아래**: 칸 아래쪽에 붙입니다. 트리밍 때문에 프레임마다 높이가 달라져도
       **발 위치가 한 줄에 서기 때문에** 걷기 같은 동작에서 캐릭터가 위아래로
       떨리지 않습니다. 원본에서 발 높이가 일정해야 뜻이 있으므로,
       1번 탭의 **트리밍 원래 크기로 복원** 과 함께 쓰는 것이 좋습니다.
   - **2의 거듭제곱 크기로 맞춤**: 시트 크기를 256, 512, 1024 … 로 맞춥니다.
     격자 정렬과 함께 켜면 **칸 크기도 2의 거듭제곱으로 올립니다**. 칸을
     `2^a × m`(m은 홀수)이라 할 때 `열 수 × 칸 = 2^k` 는 m이 1일 때만
     성립하므로, 칸 자체가 2의 거듭제곱이라야 2의 거듭제곱 시트에서 격자가
     끝까지 딱 떨어지기 때문입니다. 칸이 커지면 그만큼 용량도 늘어나므로,
     올림이 일어나면 바뀐 값을 로그에 적어 줍니다. 칸을 그대로 두고 싶으면
     이 옵션을 끄세요.
5. **새 시트로 내보내기** 를 누릅니다.
   - 웹: `packed_sheet.png` 와 `packed_sheet.json` 이 든 `packed_sheet.zip` 을 내려받습니다.
   - 데스크톱: `packed_sheet.png` 를 저장할 곳을 고르면 JSON이 그 옆에 함께 저장됩니다.

   **그룹마다 시트 나누기** 를 켜면 그룹을 각각 따로 저장합니다.
   `packed_sheet_hero.png` + `packed_sheet_hero.json`, `packed_sheet_faces.png` + … 처럼
   그룹 이름이 뒤에 붙고, **PNG 한 장마다 JSON 한 개** 가 짝으로 나옵니다. 형식은
   한 장으로 낼 때와 똑같아서 엔진 쪽에서 따로 손볼 것이 없습니다.

   이렇게 하면 **시트 한 장에 격자가 하나뿐** 이 되므로, 격자 그룹의 PNG는 그 자체로
   `(0, 0)` 부터 칸이 딱 떨어지는 완전한 격자 시트가 됩니다(`grid.whole` 이 `true`,
   `origin` 이 `(0, 0)`). 엔진에는 **칸 크기만** 적으면 되고 원점을 옮길 필요가 없어서,
   세 엔진 모두에서 가장 깔끔합니다. 파일이 여러 개가 되는 것이 유일한 대가입니다.

   **2의 거듭제곱 크기로 맞춤** 을 함께 켜면, 나눠 저장할 때는 그룹 하나가 곧 시트
   한 장이므로 **칸 크기도 2의 거듭제곱으로 올라갑니다.** 그래야 2의 거듭제곱 시트에서
   격자가 끝까지 딱 떨어집니다.

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

   그룹이 여럿이면 `groups` 배열이 함께 적힙니다. 그룹마다 이름·방식·원점과
   (격자라면) 칸 정보, 그리고 속한 프레임 이름이 들어갑니다.

   ```json
   "groups": [
     { "name": "hero.png", "mode": "grid", "origin": { "x": 0, "y": 0 },
       "grid": { "cell": { "w": 32, "h": 46 }, "cols": 16, "rows": 1, "whole": false },
       "frames": ["w00", "w01"] },
     { "name": "faces.png", "mode": "auto", "origin": { "x": 0, "y": 48 },
       "frames": ["f00", "f01"] }
   ]
   ```

   시트 전체가 하나의 격자일 때는 `grid` 항목이 적힙니다. `origin` 은 격자가
   시작하는 자리이고, `whole` 은 시트 전체가 이 격자인지를 나타냅니다. 거짓이면
   그룹만 격자이므로 엔진에서 원점을 옮겨 그 부분만 잘라내야 합니다. 엔진 쪽
   임포터가 프레임 좌표만 보고 칸 크기를 되짚지 않아도 됩니다.

   ```json
   "grid": {
     "cell": { "w": 34, "h": 50 },
     "origin": { "x": 0, "y": 116 },
     "cols": 18, "rows": 12,
     "align": "bottom",
     "spacing": 2,
     "whole": false
   }
   ```

### 조작

| 동작 | 조작 |
|---|---|
| 확대·축소 | 마우스 휠 |
| 화면 이동 | 가운데 또는 오른쪽 버튼으로 드래그 (2번 탭은 가운데 버튼만) |
| 그어서 배치 (2번 탭) | 오른쪽 버튼으로 드래그 (맥: Control+드래그도 가능) |
| 클릭 순서로 번호 매기기 (1번 탭) | N 을 누르고 원하는 순서대로 클릭. N 이나 Esc 로 끝내기 |
| 선택한 스프라이트 제외 (1번 탭) | Del (맥: delete) |
| 화면에 맞춤 | 더블클릭 또는 F |
| 범위 선택 | 빈 곳을 드래그 |
| 선택에 더하기 | Shift+클릭 또는 Shift+드래그 (맥: ⌘+클릭도 가능) |
| 전체 선택 | Ctrl+A (맥: ⌘A) |
| 새 시트에서 선택 항목 빼기 | Del (2번 탭, 맥: delete) |

### 언어

브라우저 또는 운영체제 언어에 맞춰 영어·한국어·일본어·중국어(간체)로 열립니다.
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
| 画面の移動 | 中ボタンまたは右ボタンでドラッグ (2番タブは中ボタンのみ) |
| なぞって配置 (2番タブ) | 右ボタンでドラッグ (Mac: Control+ドラッグも可) |
| クリック順に番号を付ける (1番タブ) | N を押して好きな順にクリック。N か Esc で終了 |
| 選択したスプライトを除外 (1番タブ) | Del (Mac: delete) |
| 画面に合わせる | ダブルクリックまたは F |
| 範囲選択 | 空いている所をドラッグ |
| 選択に追加 | Shift+クリックまたは Shift+ドラッグ (Mac: ⌘+クリックも可) |
| すべて選択 | Ctrl+A (Mac: ⌘A) |
| 新シートから選択項目を外す | Del (2番タブ、Mac: delete) |

### 言語

ブラウザまたは OS の言語に合わせて、英語・韓国語・日本語・中国語 (簡体字) で開きます。
それ以外の言語では英語で開きます。変更するには左上の **Language** メニューを使ってください。
自分で選んだ言語は記憶されます。

### プライバシー

Web アプリでは、画像はブラウザの中だけで処理され、どこにも送信されません。
[Umami](https://umami.is/) で匿名の訪問数と機能の利用回数だけを集計しています。Cookie は使わず、画像・ファイル名・エラーメッセージは送信しません。
ブラウザのトラッキング拒否 (Do Not Track) 設定に従います。

---

<a id="chinese"></a>

## 中文

### 网页版与桌面版

两者结果相同，使用的是同一套检测与排列代码。

| | 网页版 | 桌面版 (Windows) |
|---|---|---|
| 启动 | [打开链接](https://joungjuwon.github.io/sprite-studio/)。首次加载需要几秒钟 | 下载 [`SpriteStudio.exe`](https://github.com/joungjuwon/sprite-studio/releases/latest) 后运行 |
| 保存 | 下载 `.zip` 文件 | 保存到你选择的文件夹 |
| 图集旁的坐标文件 | 需要手动载入 | 自动关联 |
| 关闭后的图集 | 清空 | 下次启动时恢复 |

支持的图片：PNG、JPG、BMP、GIF、WEBP、TGA。
支持的坐标文件：TexturePacker JSON、Sparrow/Starling XML、Cocos2d plist、libGDX atlas。

点击右侧选项面板的标题即可展开或收起。

### 1. 提取精灵

1. 把一张或多张图集图片拖到窗口里，或点击 **添加图集…**。
   每张图集会以缩略图显示在左侧，点击缩略图即可切换。
2. 精灵会被自动检测，并用青色边框标出。检测到的数量显示在图片下方。
3. 如果边框不对，打开 **提取选项** 调整。移动滑块时结果会立即更新。

   | 问题 | 解决方法 |
   |---|---|
   | 一个精灵被分成了好几个框 | 调高 **合并碎片(px)** |
   | 检测到了细小的杂点 | 调高 **最小宽·高(px)** 或 **最少像素数** |
   | 背景不是透明的 | 勾选 **纯色背景**，点击 **吸管**，再点击图片中的背景 |
   | 精灵周围残留背景边缘 | 调高 **背景色容差** |

   这些选项只应用于所选图集。要应用到全部，请点击 **将此设置应用到所有图集**。
   在右上角的 **撤销 (Ctrl+Z) / 重做 (Ctrl+Y)** 可以撤销此页中的操作（最多 40 步）。
   两个页面的记录是分开的。
4. 检测到的精灵会挂在左侧列表中该图集的 **下方**。点击图集行右下角的 **▸** 展开。
   每一行显示预览、编号和尺寸，并有两个按钮：
   - **保存**：只把这一个精灵保存为 PNG（网页版为下载）。
   - **查看**：切换到第 1 页，只选中这个精灵，并把它放大显示在画面中央。

   把这一行 **拖到第 2 页的画面或标签上**，就只会把这一个精灵加入新图集。
   导出过文件的图集会显示 **已提取**。
5. 若只想导出一部分，点击精灵，或在空白处拖动框选多个。
   按住 Shift 点击或拖动会追加选择。选中的精灵会变成黄色。
   不需要的精灵可以选中后用 **排除所选精灵** (Del) 从列表中去掉。

   在 **编号** 中可以自己决定精灵的编号。编号就是文件名（`prefix_003.png`），
   也是在新图集中的排列顺序。
   - **按点击顺序编号 (N)**：打开后按想要的顺序点击精灵，就会依次编为 0、1、2 …
     若已有选中的精灵，则从其中最小的编号开始接着编。按 N 或 Esc 结束。
   - **重新编号所选…**（或双击精灵）：输入新编号后插入到该位置，后面的编号依次后移。
   - **重置编号**：恢复为检测顺序。
   - 移动滑块重新检测后，位置最接近的精灵会继承原来的编号。
6. 在 **裁剪 · 文件名** 中设置裁剪方式和文件名：
   - **边距(px)**：精灵周围保留的空白
   - **统一为正方形**：所有文件都做成同样大小的正方形
   - **名称前缀**：文件名为 `prefix_000.png`、`prefix_001.png`、…
   - **同时保存坐标文件**（仅网页版）：另外保存记录每个精灵在图集中位置的 JSON
7. 点击右下角的大导出按钮。
   有选中的精灵时只导出所选，否则导出全部。
   - 网页版：下载 `<前缀>_sprites.zip`。
   - 桌面版：请先指定 **保存文件夹**。

   **一次导出所有图集** 会把所有已添加的图集按图集分文件夹保存。

### 2. 使用现有的坐标文件

如果图集附带坐标文件，会直接使用其中的帧坐标，而不是按像素检测。
被裁剪或旋转的帧会恢复成原来的样子。

1. 关联文件：
   - 桌面版：把文件和图片用同样的名字放在同一文件夹（`hero.png` 和 `hero.json`），添加图集时会自动关联。
   - 网页版：先添加图集，再打开 **坐标文件（图集数据）** 点击 **载入…**，或把坐标文件拖到窗口里。
2. 在 **坐标文件（图集数据）** 中确认结果：
   - **使用坐标文件**：关闭后改回像素检测
   - **恢复裁剪前的原始尺寸**：保留包括被裁掉的透明区域在内的原始帧尺寸
   - **反转旋转方向**：旋转过的帧方向颠倒时使用
3. 按上面第 7 步的方法导出。

### 3. 制作新图集

1. 收集精灵，以下任一方式都可以：
   - 把左侧的图集缩略图拖到 **2. 制作新图集** 标签上。
   - 在第 1 页的 **加入新图集** 中点击 **添加此图集** 或 **添加所有图集**。
   - 在第 1 页选中精灵后点击 **仅添加所选**。
   - 把左侧列表中精灵的那一行拖到第 2 页。
   - 在第 2 页点击 **添加图片…**，或直接拖入单张图片文件。
2. 打开 **2. 制作新图集** 页，精灵已经自动排好。
3. 用 **分组** 整理排列。

   精灵会按来源图集自动归入 **分组**（名称为 `分组 1`、`分组 2` …，可以随时修改），
   一个分组占用图集的 **一整行**。每个分组可以用不同的规则，例如走路动画用
   **网格对齐**、表情用 **自动排列**，再合并成一张。

   - **分组列表**：在画面正下方，显示名称 · 数量 · 方式 · 格子大小 · 是否固定。
     点击行右侧的 **▲ ▼** 或 **上下拖动** 可以调整顺序，图集中也会按此顺序堆叠
     （列表中靠上的在图集中也靠上）。在列表中选中分组后，画面中也会选中该组的精灵。
     双击或点击 **重命名** 可以改名。
   - **展开分组**：点击分组左侧的展开按钮，会显示组内精灵的预览和 1、2、3 … 顺序。
     点击行只选中该精灵；用 **▲ ▼** 调整组内顺序，排列也会随之改变。
   - **名称**：新图集中精灵的名称为 `分组名_000` 这种形式，按组内顺序编号。
     画面上显示的名称与坐标 JSON 中的帧名称一致。
   - **按编号顺序排列**（排列选项，默认开启）：自动排列和网格对齐会按第 1 页设定的
     编号顺序。关闭后，自动排列会尽量紧凑，网格对齐按当前位置顺序。
     在列表中用 ▲ ▼ 手动调整的顺序优先于此选项。
   - **新建分组**：把画面中选中的精灵移到一个新分组。
   - **合并**：把所选精灵所在的多个分组合并成一个。
   - **全部重新堆叠**：按当前顺序和规则从头重新排列。
   - **撤销 (Ctrl+Z) / 重做 (Ctrl+Y)**：撤销此页中的操作（最多 40 步）。
   - **自动排列 / 网格对齐** 按钮作用于列表中选中的分组；没有选中时作用于所有分组。
   - **固定**：拖动过精灵或 **划线排列** 过的分组会被 **固定**，重新堆叠时组内形状
     （划出的行列·网格、拖放的位置）保持不变。固定的分组也占用一整行，**不会与其他分组重叠**。
     在网格分组内拖动精灵时按格子移动，网格不会被打乱。点击 **解除固定** 或再次点击
     排列按钮，就会按分组规则重新排列。
   - 画面中每个分组都有 **灰色边框**（固定的为橙色虚线），可以看出分组的范围。

   排列方式：
   - **自动排列**：紧凑地排列精灵。
   - **网格对齐**：把所有格子做成同样大小排成网格。格子从图集左上角 (0, 0) 开始无缝排列，
     图集尺寸也是格子的整数倍，因此在引擎中 **按格子大小切分**（Unity 的 Grid By Cell Size、
     RPG Maker 的规格图集等）时，每个格子正好放一个精灵。对齐后格子大小会以 **格子 34×50**
     的形式显示在日志和画面上方，把这个值填到引擎里即可。格子边界会用紫色线显示。
   - **划线排列**：用 **右键** 按想要的形状划线，精灵就会那样排列。左键始终用于选择和移动。
     横向划线排成一行，纵向划线排成一列，划出较宽的方框则排成网格。反方向划线时也会按那个方向排列。
     若已选中精灵只排列所选的，否则排列全部。松开之前会用虚线预览。
     - 格子与 **网格对齐使用相同的设置**（间距·网格·格内对齐·2 的幂），并对齐到从 (0, 0) 开始的网格。
       划线的顺序就是组内顺序（名称编号）。
     - 当前设置下的格子大小会以 **格子 48×64** 的形式显示在选项下方。
   - 拖动精灵即可移动。每次移动的步长由 **吸附(px)** 决定。
   - 相互重叠的精灵会用红色边框标出。
4. 需要时调整 **排列选项**：
   - **最大宽度**：图集的最大宽度，留空则自动决定。
   - **间距(px)**：精灵之间的间距。网格对齐时间距也计入格子大小，格子为 `最大的精灵 + 间距`。
   - **网格(px)**：把格子大小向上取为此值的倍数。填 16 或 32 后，所有帧都会落在该倍数的位置上。
     0 为关闭。**网格对齐** 和 **划线排列** 共用此值。
   - **格内对齐**：网格对齐和划线排列时精灵在格子里的位置。水平方向总是居中，只选择垂直方向。
     - **居中**：格子正中间，默认值。
     - **底部**：贴着格子底部。即使裁剪导致每帧高度不同，**脚底也在同一条线上**，
       走路等动作中角色不会上下抖动。
   - **尺寸取 2 的幂**：图集尺寸变为 256、512、1024 …。与网格对齐一起使用时，
     **格子大小也会取 2 的幂**，这样在 2 的幂尺寸的图集中网格才能正好对齐到底。
5. 点击 **导出为新图集**。
   - 网页版：下载 `packed_sheet.zip`，其中包含 `packed_sheet.png` 和 `packed_sheet.json`。
   - 桌面版：选择 `packed_sheet.png` 的保存位置，JSON 会保存在它旁边。

   JSON 中列出了每一帧的位置，游戏引擎可以据此找到每一帧：

   ```json
   {
     "image": "packed_sheet.png",
     "size": { "w": 256, "h": 128 },
     "frames": [
       { "name": "分组 1_000", "x": 0, "y": 0, "w": 32, "h": 48, "source": "hero" }
     ]
   }
   ```

   有多个分组时会一并写入 `groups` 数组，包含每个分组的名称·方式·原点、（网格分组的）
   格子信息，以及所属的帧名称。整张图集是一个网格时会写入 `grid` 项。

   打开 **每个分组单独成图** 后，每个分组分别保存为 `packed_sheet_分组名.png` + `.json`。
   每张图集只有一个网格，在引擎中只需填写格子大小即可切分。

### 操作

| 操作 | 方式 |
|---|---|
| 缩放 | 鼠标滚轮 |
| 平移画面 | 中键或右键拖动（第 2 页只能用中键） |
| 划线排列（第 2 页） | 右键拖动（Mac：也可用 Control+拖动） |
| 按点击顺序编号（第 1 页） | 按 N 后按想要的顺序点击。按 N 或 Esc 结束 |
| 排除所选精灵（第 1 页） | Del（Mac：delete） |
| 适应窗口 | 双击或按 F |
| 框选 | 在空白处拖动 |
| 追加选择 | Shift+点击或 Shift+拖动（Mac：也可用 ⌘+点击） |
| 全选 | Ctrl+A（Mac：⌘A） |
| 从新图集中删除所选 | Del（第 2 页，Mac：delete） |

### 语言

会按浏览器或系统语言以英语·韩语·日语·中文（简体）打开。
其他语言会以英语打开。要切换语言，请使用左上角的 **Language** 菜单。
自己选择的语言会被记住。

### 隐私

网页版中，图片只在浏览器内处理，不会发送到任何地方。
通过 [Umami](https://umami.is/) 只统计匿名的访问次数和功能使用次数。不使用 Cookie，也不会发送图片、文件名或错误信息。
会遵循浏览器的"请勿跟踪"(Do Not Track) 设置。

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
