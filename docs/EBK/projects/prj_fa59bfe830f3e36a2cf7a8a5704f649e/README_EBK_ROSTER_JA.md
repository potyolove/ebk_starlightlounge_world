# EventBasicKit GitHub Roster Starter Kit

Repository: `potyolove/ebk_starlightlounge_world`
Branch: `main`
Pages Base: `https://potyolove.github.io/ebk_starlightlounge_world/EBK/projects/prj_fa59bfe830f3e36a2cf7a8a5704f649e`

このZIPは、EBK WizardのGitHub設定から生成できるスターターキットです。

> **既存Repositoryへ導入する場合**  
> `data/roster_manifest.json` をそのまま上書きしないでください。既存Rosterをバックアップし、
> Python / Workflow / フォルダ構成だけ追加するか、既存manifestへ `videoRoster` ブロックを統合してください。


## 1. GitHubへ配置

ZIPの中身をRepositoryのルートへ配置してください。

主要ファイル:
- `data/roster_manifest.json`
- `prepare_video_roster_manifest.py`
- `github_manifest_to_video.py`
- `.github/workflows/auto_build_roster_video.yml`
- `images/portraits/...`
- `images/posters/...`

## 2. GitHub Pages

Settings → Pages のSourceを **GitHub Actions** にしてください。
同梱Workflowが `/docs` を明示的に公開します。Branchの生成commitだけに依存しません。
画像アルバム動画の導入・URLのVRChat内手動入力は `README_EBK_SLIDES_JA.md` を参照してください。

公開URL:
`https://potyolove.github.io/ebk_starlightlounge_world/EBK/projects/prj_fa59bfe830f3e36a2cf7a8a5704f649e`

EBK Roster:
`https://potyolove.github.io/ebk_starlightlounge_world/EBK/projects/prj_fa59bfe830f3e36a2cf7a8a5704f649e/data/roster_manifest.json`

VideoRoster:
`https://potyolove.github.io/ebk_starlightlounge_world/EBK/projects/prj_fa59bfe830f3e36a2cf7a8a5704f649e/videos/roster.mp4`

Frame Map:
`https://potyolove.github.io/ebk_starlightlounge_world/EBK/projects/prj_fa59bfe830f3e36a2cf7a8a5704f649e/data/roster_frame_map.txt`

## 3. 権限

`members[].hasPermission=true` のメンバーは `category` からEBK権限へ変換されます。

- Owner / Manager / Operator / Assistant → 4
- StaffLeader / Staff / SwitchCast → 3
- CastLeader / UpperCast / DownerCast / ConditionalCast → 2
- Regular → 1

`name` はVRChatの表示名と一致させてください。
必要なら `vrcName` を追加するとEBKはそちらを優先します。

## 4. Portrait

例:
`images/portraits/uppercast/slot3.png`

Wizardで予約Slotを事前登録しておけば、予約範囲内のcategory+slotは
Unity再BuildなしでGitHub JSONから追加できます。

## 5. Poster / Menu / Kanpe

- EventPoster → `images/posters/main/`
- FrontPoster → `images/posters/front/`
- SidePoster → `images/posters/side/`
- BackPoster → `images/posters/back/`
- Notice → `images/posters/notice/`
- Menu → `images/posters/menu/`
- Kanpe → `images/posters/kanpe/`

`slot0.png` から連番にしてください。
GitHub Actionsが実ファイルを検出し、VideoRoster用manifest/frame mapへ自動反映します。

## 6. VideoRoster

画像変更をpushするとGitHub Actionsが自動で:
1. 動的Poster manifest作成
2. 3フレーム中央取得用roster.mp4生成
3. roster_frame_map.txt生成
4. `/docs`へPages用成果物コピー
5. 生成物をRepositoryへcommit
6. アルバム動画とリンク一覧を含む `/docs` をGitHub Pagesへ公開

VRChat Video Playerではgithub.ioが標準Video Allowlist対象ではないため、
利用環境に応じてAllow Untrusted URLsまたはWorldのVideo Player Allowed Domains設定が必要です。
EBKは個別PNGフォールバックも維持します。
# 共通のGitHubルートとテーマ一覧

Core WizardのGitHub Repositoryと「ルートフォルダー」を一度指定します。リポジトリ直下ならルートは空欄です。
`ebk_media_root.json`に各モジュールのマニフェスト相対パスを登録し、Coreの「ルート一覧を取得・更新」で確認します。
VideoRosterをONにした場合、対応モジュールは標準で継承し、データが無い場合はWizardの設定を使用します。
個別の外部URLを使う場合だけ、モジュール側で「コアの設定を上書き」を選びます。

テーマは`themes/<テーマ名>/manifest.json`へ配置します。`auto_build_theme_catalog.yml`が`theme_catalog.json`を自動更新するので、Unityで各テーマのURLを入力する必要はありません。
Theme Managerの「テーマ一覧を取得・更新」から選択してまとめて取り込めます。手元で再生成する場合は`python build_theme_catalog.py --folder themes`。
親フォルダーを変更する場合は、ワークフローの対象パスと`EBK_THEME_FOLDER`、ルート一覧の`themes.manifestPath`を同じ親フォルダーへ合わせます。



## ポートレート画像の対応

名簿のcategoryとslotを基準にimages/portraits/<カテゴリ>/slot番号.png等へ画像を配置します。portraitUrlが違うslotを指す場合もURLを優先しません。対応画像がない場合は別slotへ代替せず、Wizardの素材を使用します。
