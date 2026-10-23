# 3C／遊戲降價通知機器人

自動追蹤蝦皮、momo、酷澎的商品價格。找到真正的優惠時，用 Claude 寫一段短文案，再附上你的分潤連結，推送到 Telegram、Discord 和 LINE。

每 3 小時由 GitHub Actions 自動執行一次，不需要自己架主機。

## 運作方式

1. **抓價格**
   - 蝦皮：用聯盟行銷 Open API，依 `config.yaml` 的關鍵字抓熱銷商品，回傳的連結本身就是分潤連結。
   - momo／酷澎：讀取你在 `watchlist` 列出的商品頁價格，連結則使用你在後台產生的分潤連結。
2. **判斷是否為優惠**
   - 累積 7 天以上的價格資料後：比近 30 天中位數便宜 10% 以上，**而且**是近 30 天最低價，才算優惠。
   - 新商品資料不足時：賣家標示的折扣要 ≥ 40% 才算（原價常被灌水，所以門檻較嚴）。
   - 蝦皮商品另外要求評分 ≥ 4.5、銷量 ≥ 50。
3. **避免洗版**
   - 同一商品 7 天內不重複發，除非又降價超過 5%。
   - 每次執行最多發 5 則。
4. **AI 文案**
   - Claude 只負責寫標題和一句推薦理由。
   - 價格與連結由程式直接帶入，AI 寫錯數字也不會出現在貼文裡。
   - 沒有設定 API key 時，會改用固定模板。
5. **推送**
   - Telegram、Discord：全部優惠都推。
   - LINE：每天最多推 2 則、折扣 ≥ 20% 的精選，以節省月推播額度。
6. **揭露**：每則貼文都附上分潤連結揭露聲明，符合公平會規定。

價格歷史存在 `data/state.json`，每次執行後會自動 commit 回 repo。

## 設定步驟

到 GitHub repo 的 **Settings → Secrets and variables → Actions → New repository secret**，依下表新增。不用的平台可以不填，程式會自動跳過。

| Secret | 怎麼取得 |
|---|---|
| `SHOPEE_APP_ID`、`SHOPEE_SECRET` | 蝦皮聯盟行銷後台 → Open API 申請（需另外審核） |
| `ANTHROPIC_API_KEY` | console.anthropic.com → API Keys |
| `TELEGRAM_BOT_TOKEN` | Telegram 找 @BotFather，輸入 `/newbot` 建立機器人 |
| `TELEGRAM_CHAT_ID` | 建立公開頻道並把機器人加為管理員，填 `@你的頻道名稱` |
| `DISCORD_WEBHOOK_URL` | Discord 頻道設定 → 整合 → Webhook → 複製網址 |
| `LINE_CHANNEL_ACCESS_TOKEN` | LINE Developers → Messaging API channel → Channel access token |

接著：

1. **調整 `config.yaml`**：修改蝦皮搜尋關鍵字，並在 `watchlist` 加入想追蹤的 momo／酷澎商品（每項要有商品頁網址和你的分潤連結）。
2. **試跑**：到 **Actions → deal-bot → Run workflow**，勾選 `dry_run`，在執行紀錄裡就能看到會發出的貼文內容，不會真的推送。
3. **正式上線**：確認沒問題後就不用再管它，排程會自動執行（排程只在預設分支 master 上生效）。

在本機測試：

```bash
pip install -r requirements.txt pytest
python -m pytest
python -m dealbot.main --dry-run
```

## 注意事項

- **前 7 天幾乎只能靠蝦皮的賣家折扣判斷。** 價格歷史累積起來之後，判斷才會準。
- **蝦皮 Open API 的欄位名稱**是依官方 GraphQL 文件撰寫（`productOfferV2`）。取得權限後若回傳錯誤，請對照後台 API 文件調整 `dealbot/sources/shopee.py`。
- **momo／酷澎沒有公開的商品 API。** 程式從商品頁的結構化資料讀價格，可能會被網站阻擋，或在網站改版後失效。抓不到價格時，執行紀錄會出現 `price not found`，這時可以替該商品加上 `price_regex`。請保持追蹤清單精簡，不要提高執行頻率。
- **費用**：GitHub Actions 公開 repo 免費、私人 repo 每月有免費額度；Claude 文案每則約幾毛台幣；Telegram 與 Discord 免費；LINE 超過免費推播額度要付費。
