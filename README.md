# 🔵🔴 Culers Hub — FC Barcelona Telegram Bot

A high-performance, AI-powered Telegram bot for FC Barcelona fans.
Supports **English 🇬🇧 · Arabic 🇸🇦 · French 🇫🇷**.

---

## 📁 Project Structure

```
culers_hub/
├── main.py                  # Entry point, scheduler, handler registration
├── config.py                # All settings & env-var loading
├── languages.json           # All static UI strings (no AI needed)
├── requirements.txt
├── render.yaml              # Render deployment manifest
├── .env.example
│
├── handlers/
│   ├── start.py             # /start, language picker
│   └── menu.py              # All inline-keyboard callbacks
│
├── services/
│   ├── football_api.py      # API-Football wrapper + cache logic
│   ├── gemini.py            # Gemini Flash — commentary & summaries
│   ├── match_tracker.py     # ★ Master tracker + broadcast engine
│   └── news_service.py      # RSS fetcher + AI summarisation
│
└── utils/
    ├── cache.py             # In-process TTL cache (Redis-compatible API)
    ├── db.py                # SQLite — users, language prefs, subscribers
    └── i18n.py              # Translation helper (reads languages.json)
```

---

## 🔑 API Keys You Need

| Service | Where to get it | Free tier |
|---|---|---|
| Telegram Bot Token | [@BotFather](https://t.me/BotFather) on Telegram | ✅ Free |
| Google Gemini API Key | [aistudio.google.com](https://aistudio.google.com) | ✅ Free (Flash model) |
| API-Football | [api-sports.io](https://api-sports.io) | ✅ 100 calls/day free |

---

## 🚀 Deploy on Render (Free Tier) — Step by Step

### Step 1 — Push to GitHub

```bash
git init
git add .
git commit -m "Initial commit — Culers Hub Bot"
# Create a new repo on github.com, then:
git remote add origin https://github.com/YOUR_USERNAME/culers-hub-bot.git
git push -u origin main
```

> ⚠️ Make sure `.env` is in your `.gitignore` — never commit your API keys!

```bash
echo ".env" >> .gitignore
echo "data/" >> .gitignore
```

### Step 2 — Create a Render Account

1. Go to [render.com](https://render.com) and sign up (free).
2. Connect your GitHub account.

### Step 3 — Create a New Background Worker

1. Click **"New +"** → **"Background Worker"**
2. Select your `culers-hub-bot` repository
3. Render will auto-detect `render.yaml` — click **"Apply"**

### Step 4 — Set Environment Variables

In the Render dashboard → your service → **"Environment"** tab, add:

| Key | Value |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Your token from @BotFather |
| `GEMINI_API_KEY` | Your Gemini API key |
| `FOOTBALL_API_KEY` | Your api-sports.io key |

### Step 5 — Deploy

Click **"Manual Deploy"** → **"Deploy latest commit"**.

Watch the logs — you should see:
```
Database initialised at /opt/render/project/src/data/culers_hub.db
Scheduler started.
Culers Hub Bot is running 🔵🔴
```

### Step 6 — Test Your Bot

Open Telegram, find your bot, send `/start` — you're live! 🎉

---

## 💡 Token Cost Strategy (How We Save Money)

```
User A (Arabic)  ─┐
User B (Arabic)  ─┤                          ┌─ send text_ar ─► User A
User C (French)  ─┤─► 1 API-Football call ──►│─ send text_ar ─► User B
User D (English) ─┤   3 Gemini calls         └─ send text_fr ─► User C
User E (English) ─┘   (1 per language)         send text_en ─► User D, E
                                                              
   N users = N Telegram sends, but always ≤ 3 Gemini calls per event
```

### Cache TTLs

| Data | TTL | Rationale |
|---|---|---|
| Standings | 1 hour | Changes only after matches |
| News articles | 1 hour | Updated a few times per day |
| Today's fixture | 24 hours | Set once, re-fetched at 06:00 |
| AI news summary | 1 hour | Same article, same summary |
| Live events | No cache | Always fresh during match |

---

## 🔧 Local Development

```bash
cd culers_hub
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # Fill in your keys
python main.py
```

---

## ⚠️ Render Free Tier Limits

- **750 hours/month** of compute time (enough for 1 always-on service)
- **Spins down after 15 min of inactivity** — for bots using polling this is
  fine because the bot itself keeps the process alive.
- **1 GB ephemeral disk** — sufficient for SQLite database.
- If you need the bot 24/7 reliably, consider Render's **$7/month** Starter plan.
