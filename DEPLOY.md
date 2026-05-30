# Deploying footymodel — plain-English guide (no coding)

You do **not** need to use a terminal. Everything below happens in your web browser.
The config files in this folder make the hosting platform set itself up automatically.

---

## Step 1 — Put the files on GitHub (your free online folder)

1. Make a free account at **github.com**.
2. Click the **+** (top right) → **New repository**. Name it `footymodel`. Click **Create**.
3. On the new repo page, click **Add file → Upload files**.
4. Drag in **all** the footymodel files **and the `static` folder**. Important: keep
   `index.html` inside the `static` folder (drag the whole folder, don't flatten it).
5. Click **Commit changes**.

That's your code online. You never have to touch it again unless you want to change something.

---

## Step 2 — Deploy (pick ONE platform)

### Option A — Render  (recommended for beginners; truly free tier)
1. Make a free account at **render.com** and connect your GitHub when asked.
2. Click **New + → Blueprint**.
3. Pick your `footymodel` repo. Render reads `render.yaml` and fills everything in for you.
4. Click **Apply / Create**. Wait a few minutes.
5. You get a public link like `https://footymodel.onrender.com`. Done.

> Note: on the free tier the app "sleeps" after ~15 min idle and takes ~30 seconds to
> wake on the next visit. Normal — just wait a moment on first load.

### Option B — Railway  (also easy; usage-based free credit)
1. Make a free account at **railway.app** and connect GitHub.
2. Click **New Project → Deploy from GitHub repo** → pick `footymodel`.
3. Railway reads `railway.json` + `Dockerfile` and builds automatically.
4. When it's live, go to **Settings → Networking → Generate Domain** to get your public link.

---

## Step 3 — (Optional) turn on live data

Without this, the app runs on a built-in realistic sample — everything works.
For real match data, get a **free** key at football-data.org/client/register, then:

- **Render:** your service → **Environment** → **Add Environment Variable** →
  key `FOOTBALL_DATA_TOKEN`, value = your key → save (it redeploys).
- **Railway:** your service → **Variables** → **New Variable** → same key/value.

The badge in the top corner of the app shows **LIVE DATA** vs **SNAPSHOT MODE**.

---

## If something goes wrong

First deploys sometimes hiccup on a small detail — that's normal, not you doing
anything wrong. The build log on either platform shows the error in red. Copy that
red text and it's almost always a one-line fix. Common ones:

- **"index.html not found"** → the `static` folder got flattened during upload;
  re-upload so `static/index.html` keeps that exact path.
- **Build fails on dependencies** → make sure `requirements.txt` was uploaded.
- **App loads but won't wake / very slow** → free-tier sleep; just wait 30 seconds.

---

## What each config file does (for your curiosity — you don't need to edit these)

| File | Purpose |
|------|---------|
| `Dockerfile` | Recipe to build the app in a clean container. Works on any platform. |
| `render.yaml` | Tells Render exactly how to build/run it — no form-filling. |
| `railway.json` | Same idea for Railway. |
| `Procfile` | A fallback some platforms auto-detect for the start command. |
| `runtime.txt` | Pins the Python version (3.12). |
| `requirements.txt` | The Python packages to install. |
| `.gitignore` | Keeps junk files out of your GitHub upload. |
