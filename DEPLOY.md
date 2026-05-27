# 🚀 VVIT Portal — Live Deployment Guide

Two platforms are pre-configured: **Render** (recommended) and **Railway**.
Both are free, both give you a public `https://` URL in under 10 minutes.
Pick one and follow its section below.

---

## OPTION A — Deploy on Render (Recommended)

Render is the easiest option. Its free tier stays alive as long as someone
visits the site at least once every 15 minutes (otherwise it "sleeps" and
takes ~30 seconds to wake up on the next visit — that's normal on free tier).

### Step 1 — Push your code to GitHub

If you haven't used Git before, here are the exact commands.
Open a terminal inside the `VVITU_Portal` folder and run:

```bash
git init
git add .
git commit -m "Initial commit — VVIT Portal"
```

Now create a free account at https://github.com and make a **new repository**
(click the + icon → New repository). Name it `vvit-portal`, keep it public,
and **don't** tick "Add a README" (you already have one). Then run:

```bash
git remote add origin https://github.com/YOUR_USERNAME/vvit-portal.git
git branch -M main
git push -u origin main
```

Replace `YOUR_USERNAME` with your actual GitHub username.

### Step 2 — Create a free Render account

Go to https://render.com and sign up (you can use "Continue with GitHub" to
link the two accounts in one click — this makes Step 3 easier).

### Step 3 — Create a new Web Service

Inside the Render dashboard, click **"New +"** → **"Web Service"**.
Select your `vvit-portal` GitHub repository from the list.

Render will auto-detect the `render.yaml` file in your repo and pre-fill
most settings. Verify these fields match:

| Field              | Value                                                   |
|--------------------|---------------------------------------------------------|
| **Name**           | vvit-portal                                             |
| **Region**         | Singapore (closest to India)                           |
| **Branch**         | main                                                    |
| **Build Command**  | `pip install -r requirements.txt && python manage.py collectstatic --no-input && python manage.py migrate` |
| **Start Command**  | `gunicorn VVITU_Portal.wsgi:application --bind 0.0.0.0:$PORT --workers 4` |

### Step 4 — Add the PostgreSQL database

On the same page, scroll to **"Add-ons"** and click **"Add a database"** →
choose **PostgreSQL (Free)**. Render will create it and automatically inject
the `DATABASE_URL` environment variable into your web service.

### Step 5 — Add environment variables

Still on the same page, scroll to **"Environment Variables"** and add:

| Key                        | Value                              |
|----------------------------|------------------------------------|
| `DJANGO_SETTINGS_MODULE`   | `VVITU_Portal.settings_prod`        |
| `SECRET_KEY`               | (click "Generate" — Render does this automatically if you use render.yaml) |

### Step 6 — Click "Create Web Service"

Render will now build your project. Watch the build log — the whole thing
takes about 2–3 minutes. When it says **"Your service is live"** you'll see
a URL like `https://vvit-portal.onrender.com`.

### Step 7 — Load the sample data (first time only)

Click **"Shell"** in the Render dashboard sidebar and run:

```bash
python manage.py shell < sample_data.py
```

This creates all the test accounts so you can log in immediately.

🎉 **Your VVIT Portal is now live at `https://vvit-portal.onrender.com`**

---

## OPTION B — Deploy on Railway

Railway is slightly faster to deploy but its free tier has a monthly usage
limit (500 hours/month). That's enough for a demo or small college use.

### Step 1 — Push to GitHub (same as Render Step 1 above)

### Step 2 — Create a Railway account

Go to https://railway.app and sign up with your GitHub account.

### Step 3 — New Project → Deploy from GitHub Repo

Click **"New Project"** → **"Deploy from GitHub Repo"** → select `vvit-portal`.

Railway reads `railway.json` and auto-configures the build and start commands.

### Step 4 — Add PostgreSQL plugin

Inside your project, click **"New"** → **"Database"** → **"Add PostgreSQL"**.
Railway automatically sets `DATABASE_URL` in your environment.

### Step 5 — Add environment variable

Go to your web service → **"Variables"** tab → add:

| Key                      | Value                          |
|--------------------------|--------------------------------|
| `DJANGO_SETTINGS_MODULE` | `VVITU_Portal.settings_prod`   |
| `SECRET_KEY`             | any long random string, e.g. `vvit-super-secret-2024-change-this-xyz` |

### Step 6 — Deploy

Railway deploys automatically after you set variables. Wait ~2 minutes and
click the generated URL (looks like `https://vvit-portal-production.up.railway.app`).

### Step 7 — Load sample data via Railway Shell

Open the Railway shell and run:
```bash
python manage.py shell < sample_data.py
```

---

## Login credentials (same on both platforms)

| Role    | Username       | Password   |
|---------|----------------|------------|
| Admin   | `admin`        | `vvit@1234`|
| Faculty | `EMP001`       | `vvit@1234`|
| Student | `24BQ1A4942`   | `vvit@1234`|

---

## Troubleshooting

**Build fails with "No module named psycopg2"** — make sure `psycopg2-binary`
is in `requirements.txt` (it is, by default). The `-binary` variant doesn't
need any system C compiler, so it works on all cloud platforms.

**Static files (CSS/JS) not loading after deploy** — run
`python manage.py collectstatic --no-input` in the shell. WhiteNoise then
serves them directly from Gunicorn without needing a separate Nginx server.

**"DisallowedHost" error** — your domain isn't in `ALLOWED_HOSTS`. The
`settings_prod.py` already adds `.onrender.com` and `.up.railway.app` so
this should not happen. If you use a custom domain, add it to the
`ALLOWED_HOSTS` environment variable as a comma-separated list.

**Database migrations haven't run** — run `python manage.py migrate` in
the cloud shell. The build command runs this automatically, but if you
push new model changes later you'll need to run it again.

**App sleeps on Render free tier** — the first request after 15 minutes of
inactivity takes ~30 seconds to wake. This is normal. Upgrade to the
"Starter" plan ($7/month) for always-on behaviour.
