# EBK Content Manifest / 4言語テキスト

対象: Entry Gate、ポップアップ通知、カンペ、注意事項、相互ポスターの説明本文。
Entry Gateは固定ID entry_gate.title / entry_gate.notice / entry_gate.full / entry_gate.closed を使用します。
Popup通知は notification.call.* / notification.order.* / notification.inventory.* / notification.service.assigned / notification.timeline.* の固定IDを使用します。
追加Timeline項目はWizard各行のContent ID（標準 timeline.extra.N）で4言語の項目名を公開します。GitHubのtextJa/textEn/textZh/textKoを変更すると受信者側言語で表示されます。
Starter Kit生成時はWizardで入力したEntry Gate・Popup通知・追加Timeline項目名の4言語文言を data/content_manifest.json へ自動出力します。
その他の表示内容はWizardで各行にContent IDを設定し、同じcontentIdを data/content_manifest.json に登録します。

## 4言語フィールド
- text / textJa: 日本語。textは旧Manifest互換のため残します。
- textEn: English
- textZh: 中文
- textKo: 한국어
- imageId: EBKの登録画像ID。Entry Gateではentry_gate.notice / full / closedに指定すると本文領域を画像表示できます。未設定・取得失敗時は4言語本文へ戻ります。

## Popup通知の置換文字
- {room}: 部屋名
- {player}: 呼び出し/注文した人
- {responder}: 対応者
- {item}: 商品名
- {area}: エリア名
- {count}: 在庫数
- {state}: 注文状態
- {minutes}: 残り分数
- {title}: イベント名
- {number}: ローテ番号
- {photo}: 集合写真ラベル
GitHubで文言を変えてもContent IDと置換文字は維持してください。

## Entry Gate画像
Wizardの「人・プロフィール > 登録プロフィール画像URL」で画像IDとHTTPS直リンクを登録し、同じIDをimageIdへ指定します。GitHub側ではcontent_manifest.jsonのimageIdを差し替えるだけで表示画像を切り替えられます。

## 例
```json
{
  "protocol": "EventBasicKit.ContentManifest",
  "schemaVersion": 1,
  "revision": "example-v2",
  "updatedAt": "2026-10-12T00:00:00Z",
  "contents": [
    {
      "contentId": "notice.welcome",
      "visibility": "public",
      "enabled": true,
      "text": "日本語本文",
      "textJa": "日本語本文",
      "textEn": "English text",
      "textZh": "中文内容",
      "textKo": "한국어 본문"
    }
  ]
}
```

既存のtextだけのManifestもそのまま読み込めます。未登録言語はEBKのフォールバック順で表示します。
visibility=public の行だけGitHub公開値として適用されます。Local only行は外部から上書きしません。
画像・配置・権限・VideoRoster slotはこのManifestの本文更新で変更しません。
