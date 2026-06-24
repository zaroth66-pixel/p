# 📦 APK Poster Bot — Full Edition

A full-featured Telegram bot that posts APK files to groups/channels, supports 10 languages, has a referral/earning system, and runs on Railway.

---

## 📬 Post Format (sent to every group)
1. 🖼️ Image + caption
2. 📹 Installation video
3. 📦 APK file with version + changelog + size

---

## 💰 Referral System
- Each user gets a unique link: `t.me/yourbot?start=ref_USERID`
- User submits install screenshot → forwarded to admin → **deleted immediately**
- Admin approves → user gets **+40 ETB**
- Minimum withdrawal: **400 ETB (10 referrals)**
- Admin approves payouts manually via inline buttons

---

## 🌍 Supported Languages
Amharic, English, Afaan Oromo, Tigrigna, Arabic, French, Spanish, Swahili, Hindi, Portuguese

---

## 🔐 Channel Gate
- APK sent immediately on /start (no gate)
- Referral, balance, withdraw → requires channel membership (verified via Telegram API)

---

## 🚀 Setup

### 1. Create Bot
- Message @BotFather → `/newbot` → copy token

### 2. Get Your User ID
- Message @userinfobot → copy your numeric ID

### 3. Deploy to Railway
1. Push this folder to GitHub
2. railway.app → New Project → Deploy from GitHub
3. Add environment variables:

| Variable    | Value |
|-------------|-------|
| `BOT_TOKEN` | Your bot token |
| `ADMIN_IDS` | Your user ID (comma-separated for multiple admins) |

4. Railway reads `Procfile` → runs as Worker automatically

> 💡 Add a Railway **Volume** mounted at `/app` to keep `data.json` persistent across redeploys.

---

## ⚙️ First-Time Admin Setup (via /start)

1. **🔐 Channel Settings** → set your channel @username and numeric ID
2. **📎 APK Links** → add your GitHub raw APK URL, set as active
3. **🖼 Image** → set image URL or upload photo
4. **📹 Video** → set GitHub raw .mp4 URL
5. **💬 Caption** → edit main caption and extra lines
6. **📦 Version** → set version number and changelog
7. **⏰ Schedule** → set time and enable
8. Add bot to your groups/channels → it auto-registers and sends welcome message

---

## 📁 File Structure
```
tgbot2/
├── bot.py                  # Main entry point
├── handlers/
│   ├── user.py             # User flows (start, referral, withdraw)
│   ├── admin.py            # Admin panel
│   └── posting.py          # Scheduled posting
├── utils/
│   ├── db.py               # Data storage
│   ├── languages.py        # All 10 language strings
│   └── helpers.py          # Shared utilities
├── requirements.txt
├── Procfile
├── .env.example
├── .gitignore
└── README.md
```

---

## 🔗 GitHub URL Formats

APK:
```
https://raw.githubusercontent.com/USER/REPO/main/app.apk
https://github.com/USER/REPO/releases/download/v1.0/app.apk
```
Video:
```
https://raw.githubusercontent.com/USER/REPO/main/install.mp4
```
Image:
```
https://raw.githubusercontent.com/USER/REPO/main/banner.png
```
