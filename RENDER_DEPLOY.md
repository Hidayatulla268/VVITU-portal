# 🚀 Deploying VVITU Portal on Render (render.com)

This step-by-step guide walks you through deploying the **VVITU University Portal** on **Render** using a new/free Render account.

---

## 📋 Prerequisites Checklist

1. A free account on [Render.com](https://render.com) (created with any email/Google account).
2. Your code pushed to GitHub: `https://github.com/Hidayatulla268/VVITU-portal.git`.
3. (Optional) A free [Google AI Studio](https://aistudio.google.com/app/apikey) Gemini API key for the AI Assistant.

---

## ⚡ Method 1: Automated 1-Click Blueprint (Fastest & Recommended)

Render supports Infrastructure-as-Code using the included `render.yaml` file.

1. Log into your **Render Dashboard** ([dashboard.render.com](https://dashboard.render.com)).
2. Click **New +** (top right) ➔ Select **Blueprint**.
3. Connect your GitHub repository (`VVITU-portal`) or paste the Public Git URL.
4. Render will detect `render.yaml` and show:
   - **Web Service**: `vvitu-portal` (Python)
   - **Database**: `vvitu-db` (PostgreSQL)
5. Click **Apply**.
6. Render will automatically create the PostgreSQL database, run `build.sh` (install packages, collect static files, apply migrations), and start Gunicorn!

---

## 🛠️ Method 2: Manual Web Service Setup (Step-by-Step)

If you prefer to configure the service manually:

### Step 1: Create a Free PostgreSQL Database
1. In Render Dashboard, click **New +** ➔ **PostgreSQL**.
2. Set:
   - **Name**: `vvitu-db`
   - **Database**: `vvitu_db`
   - **User**: `vvitu_admin`
   - **Region**: Oregon (or nearest)
   - **Plan**: Free
3. Click **Create Database**.
4. Once created, copy the **Internal Database URL** (e.g., `postgres://vvitu_admin:...@dpg-xxx:5432/vvitu_db`).

---

### Step 2: Create the Django Web Service
1. Click **New +** ➔ **Web Service**.
2. Select **"Public Git repository"** and enter:
   ```
   https://github.com/Hidayatulla268/VVITU-portal.git
   ```
   *(Or select your linked repository)*.
3. Configure the service settings:
   - **Name**: `vvitu-portal` (or any unique name you like)
   - **Region**: Same region as your database (e.g. Oregon)
   - **Branch**: `main`
   - **Root Directory**: *(leave blank if root contains manage.py)*
   - **Runtime**: `Python 3`
   - **Build Command**:
     ```bash
     ./build.sh
     ```
   - **Start Command**:
     ```bash
     gunicorn VVITU_Portal.wsgi:application
     ```
   - **Plan**: Free

---

### Step 3: Add Environment Variables
Scroll down to **Environment Variables** and add:

| Key | Value | Description |
| :--- | :--- | :--- |
| `PYTHON_VERSION` | `3.11.9` | Python runtime version |
| `DJANGO_SETTINGS_MODULE` | `VVITU_Portal.settings_prod` | Production settings |
| `SECRET_KEY` | *(Click "Generate" or enter a random 50-char string)* | Django security key |
| `DATABASE_URL` | *(Paste Internal Database URL from Step 1)* | PostgreSQL connection |
| `ALLOWED_HOSTS` | `.onrender.com,localhost,127.0.0.1` | Allowed domain hosts |
| `CSRF_TRUSTED_ORIGINS` | `https://*.onrender.com` | Allowed CSRF origins |
| `GEMINI_API_KEY` | *(Optional: paste your Gemini API key)* | VBot AI features |

4. Click **Create Web Service**.

---

## 💾 Step 4: Seed Initial Academic Data & Superuser

Once your service finishes deploying and the status is **Live**:

1. In Render Dashboard, click on your **vvitu-portal** web service.
2. Click the **Shell** tab on the left menu (or click **Manual Deploy** ➔ **Run a Command**).
3. Type and run:
   ```bash
   python manage.py seed_data
   ```
4. This command will instantly populate:
   - Superuser: **`admin`** / Password: **`vvit@1234`**
   - All 8 Engineering Branches (CSE, ECE, EEE, IT, CSM, CSD, CIVIL, MECH)
   - Student & Faculty accounts
   - 6-Day Weekly Timetables & 3 Months of Attendance Logs
   - Daily Class Diaries, Syllabus Plans, and Exam Schedules

---

## 🌐 Step 5: Access Your Live Portal

Open your Render URL in your browser:
```
https://<your-service-name>.onrender.com
```

### Default Login Accounts:
- **Admin**: `admin` / `vvit@1234`
- **Faculty / HOD / Student**: See [learning_journal.md](file:///c:/Users/HP/OneDrive/Desktop/vvitu/vvitu-portal/vvitu_portal/learning_journal.md) for full credential listings.

---

## 💡 Pro-Tip for Permanent Free Database (Never Expires)
Render free databases expire after 30 days. To keep your database live forever for free:
1. Create a free permanent PostgreSQL database on **[Neon.tech](https://neon.tech)** or **[Supabase.com](https://supabase.com)**.
2. Paste the Neon / Supabase connection string as `DATABASE_URL` in your Render environment variables!
