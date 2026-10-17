# EBK 画像フォルダ → スライド動画 導入手順

GitHubを扱える購入者向けの任意連携です。GitHub連携を使わないEBKの機能も維持されます。
このセットは画像の変換と公開までを自動化します。**URLはVRChat内で利用者が手動入力します。**
ボードへの自動登録・自動再生・定期監視はありません。

## 初回設定

1. EBK Wizardの「外部連携」で、購入者自身のRepository / Branch / Pages Base URLを設定します。
   「GitHub連携＋画像フォルダ→スライド動画 導入ZIPを保存」から保存します。
   MediaVisualの部屋別メディアボード設定にも同じ保存ボタンがあります。
2. ZIPを展開し、中身（`.github`を含む）を購入者のコンテンツ用Repositoryのルートへ配置します。
   EBK本体や購入素材のソースコードを公開する必要はありません。
   既存導入先では `data/roster_manifest.json` / `data/content_manifest.json` を上書きせず保持してください。
   Workflowを統合する場合は既存設定を比較し、Pagesへ公開する処理を1本にまとめます。
3. GitHub Settings → Actions → General → Workflow permissions を Read and write permissions に設定します。
4. Settings → Pages → Build and deployment → Source は **GitHub Actions** を選びます。
   旧手順の「Deploy from a branch / docs」のままにしません。
   `github-pages` Environmentにブランチ制限がある場合は `main` を許可します。
5. `data/room_media_slides.json` の `pagesBaseUrl` が `https://potyolove.github.io/ebk_starlightlounge_world/EBK/projects/prj_fa59bfe830f3e36a2cf7a8a5704f649e` であることを確認します。
   未設定テンプレートの `potyolove` / `ebk_starlightlounge_world` を使い続けないでください。
   GitHub Actionsの実行とPages公開が利用できるRepository/プランが必要です。

## 普段の使い方

`media/room-slides/` の直下に、好きな名前のフォルダを作り、画像をまとめて入れてcommit / pushします。

| GitHubへ入れる場所 | 自動生成する動画 |
| --- | --- |
| `media/room-slides/ポチョ/001.png`、`002.jpg`… | `ポチョ.mp4` |
| `media/room-slides/食べ物/001.jpg`、`002.png`… | `食べ物.mp4` |

日本語名・空白を使用できます。Windowsで使えない記号、予約名、先頭ドット、末尾空白/ピリオドは使えません。
アルバム内のサブフォルダは使用しません。フォルダ追加のたびにJSONへ登録する必要はありません。
同じフォルダへの追加・削除・差し替えで、同じ動画名・同じURLを更新します。
フォルダ名を変えるとURLも変わります。空フォルダは「画像待ち」で、空MP4は作りません。
画像をすべて削除したアルバム/削除したフォルダの古い動画は生成物から除去します。

対応: PNG / JPG / JPEG / WebP / BMP / TIFFの静止画像。
GIF、動画、アニメーションWebP、複数ページTIFFは対象外です。
画像はファイル名の自然順（1、2、10）で並びます。任意の順番にしたい場合は `001_名前.png` のようにします。
EXIFの向きを反映し、縦横比を保持して黒余白を付けます。透過部分は黒背景になります。
初期解像度は1920×1080。設定JSONのwidth/heightで変更できます。
30fps固定・各画像を正確に3フレーム・中央フレームを表示するH.264 MP4です。音声はありません。

## Ops Managerから画像を管理する

Ops 0.4.32の「画像・アルバム」で、フォルダ作成・削除、画像の一括追加・削除、サムネイル確認、動画URLコピーができます。
「すべての画像フォルダ」ではimages配下の名簿・ポスター等も管理できます。階層を開いて登録先を選びます。

- ファイルは複数選択、画像URLは1行1件で入力します。URLから実データをダウンロードして登録します。
- ファイルとURLは同じ処理で、画像の向き・縦横比を保持し、長辺2048px以下のPNGへ変換します。小さい画像は拡大しません。
- ポートレートはプレビュー横のslot番号を確認してから一括登録します。slot1・slot3・slot4は`slot1.png`・`slot3.png`・`slot4.png`になります。空いている番号を詰めません。
- 元の名前からslot番号が分からない画像は番号を指定します。番号の未指定や重複がある場合は登録しません。
- 同名PNGは差し替えます。別拡張子で残っている旧画像は一覧から選択して削除してください。
- 1回に200枚・合計100MiBまで登録できます。一括削除は確認画面に出る選択画像が対象です。
- 登録済み画像は24枚ずつ表示します。画像や公開状態を確認する際は「更新」を押します。
- 別の編集と競合した場合は登録を止めます。一覧を更新して再度確認してください。

## リンク取得とVRChat内での手動入力

Actionsの **Build EBK roster and slide albums** のbuild-video / deployの成功を待ちます。
初回は手動の Run workflow でも実行できます。workflow_dispatchは既定ブランチへのWorkflow登録が必要です。

リンク一覧: `https://potyolove.github.io/ebk_starlightlounge_world/EBK/projects/prj_fa59bfe830f3e36a2cf7a8a5704f649e/ebk-room-media/`

1. 一覧でアルバムの「リンクをコピー」を押します。
2. **VRChat内**で部屋別メディアボードのURL入力欄へ貼り付けます。
3. ボードの読込操作を行い、「前」「次」でスライドを送ります。既存の操作権限が適用されます。

一覧のリンクは日本語ファイル名をURLエンコード済みで、末尾に `?ebk-slides=3x30` が付きます。
この対応版のEBKは、手動入力したリンクから「スライド / EBK / 30fps」を選びます。
GitHubが共有ボードへ勝手に接続する仕組みではありません。
MP4の直接リンクを使う場合や旧EBKでは、ボード側で「スライド / EBK方式」を選び、Wizardの動画FPSを30にします。
画像を更新しても、既に開いているボードを自動で更新しません。公開完了後、同じURLを読み込み直してください。
ホスト側/クライアント側のキャッシュにより反映まで時間がかかる場合があります。

GitHub上の出力: `docs/ebk-room-media/videos/<フォルダ名>.mp4`、`manifest.json`、`links.tsv`、`index.html`。
`docs/ebk-room-media` は自動生成専用です。手作業のファイルを置かないでください。
このセットはRosterの動画/Frame Map/JSONも同じPages公開へ含めます。既存のdocs内のデータを保持します。

## 動作条件・失敗時

- GitHub Pagesの動画は公開URLです。閲覧者をEBKの権限で制限する配信ではありません。公開可能な画像を入れてください。
- VRChatのVideo Allowlistにgithub.ioは含まれていません。視聴者のAllow Untrusted URLsが必要です。
  Public / Group PublicではWorldのVideo Player Allowed Domainsにもホスト名（例 `owner.github.io`）を登録します。
- 1画像50MiB・4000万画素、1アルバム2000枚、1動画95MiB、本セットの公開データ900MiBを上限とします。
  大量画像は必要に応じてフォルダを分け、解像度を下げてください。GitHub側の利用上限も適用されます。
- 不正画像や容量超過では生成・公開を中止し、前回の公開内容を維持します。Actionsのエラーに対象が出ます。
- ブランチ保護が自動commitを禁止している場合は失敗します。コンテンツ用ブランチの運用設定を確認してください。
- `GITHUB_TOKEN`による生成commitだけではPages再ビルドが起きないため、同じWorkflowが明示的にdeployします。
- 別のPages公開Workflowと併用すると公開内容が置き換わります。コンテンツ専用Repositoryを基本にしてください。
- 名簿の役職変更Workflowだけを実行した後は、必要に応じてBuild EBK roster and slide albumsを手動実行します。

ローカルで変換する場合（Python 3.11以上、Pillow、FFmpeg/ffprobeのlibx264対応版が必要）:

```sh
python -m pip install pillow
python build_room_media_slides.py
```

## 確認に使った一次資料

- https://creators.vrchat.com/sdk/upgrade/current-unity-version/
- https://creators.vrchat.com/worlds/udon/video-players/
- https://creators.vrchat.com/worlds/udon/video-players/www-whitelist/
- https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits
- https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow
- https://github.com/actions/deploy-pages
- https://ffmpeg.org/ffmpeg-codecs.html

Unity 2022.3.22f1 / SDK Worlds 3.10.3向け。Python/FFmpeg生成検査とUnity/UdonSharp/VRChat実機確認は別です。

## 透過スライド（対応版EBK向け）

新規キットの`data/room_media_slides.json`は`"alphaMode": "auto"`。透過を含むアルバムだけ黒白ペア方式で生成します。`opaque`は従来方式、`dual-matte`は全アルバムを黒白ペアにします。既存設定でalphaModeがない場合は従来方式を維持します。

公開manifestのformat/alphaModeと、コピーするslideUrlの`ebk-alpha`が方式を表します。ボードへはパラメーターを含む**スライドURL全体**を貼ってください。対応版EBKは自動判定し、前/次で表示するフレームの透明度を復元します。通常のMP4直リンクだけでは透過方式を指定できません。

黒白ペアは動画の横幅が2倍です。論理画像幅は1920px以下にしてください。画像原本にalphaが残っている必要があります。全スライド画像の複製は作らず、選択中のフレームをScreenのShaderで表示します。黒文字は透明色として抜きません。透過時は不透明な背板Rendererだけ非表示にし、UI・Collider・Pickupを維持します。

`EBK/RoomMedia/Transparent Screen`をWizardが設定します。色空間に差が出る場合は比較テストで確認し、EBKRoomMediaBoardのUnity/AVPro別`dualMatte…SamplesAreLinear`を調整してください。Screenへコピーする場合も復元後のalphaと透過対応Materialを保持してください。Unity/VRChat実表示確認は別途必要です。
