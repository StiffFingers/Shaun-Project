# In-Spec Team Work Journal

A simple daily log app for a small construction crew. Workers record what they did each day; you can filter the journal and export everything to an Excel spreadsheet.

## Features

- **New entry** — date, worker, project/job site, weather, hours, work performed, crew notes, materials, issues/delays, safety notes
- **Journal** — browse, filter (date range / worker / project), edit, delete
- **Crew & projects** — add workers and job sites; deactivate old ones without losing history
- **Excel export** — one `.xlsx` with summary sheets by worker and project
- **Login** — email/password via Streamlit Secrets
- **Permanent database** — **Supabase** (Postgres) when configured; local SQLite only for offline/dev

## Run locally

```bash
cd ~/construction-journal
pip3 install -r requirements.txt
streamlit run app.py
```

Open the URL Streamlit prints (usually http://localhost:8501).

## Deploy: Supabase (permanent data)

Streamlit Cloud’s disk is temporary. Use Supabase so journal entries survive restarts.

### 1. Create a free Supabase project

1. Sign up at [https://supabase.com](https://supabase.com)
2. **New project** → pick a name, database password, region
3. Wait until the project is ready

### 2. Create tables

1. In Supabase: **SQL Editor** → **New query**
2. Paste the full contents of `supabase_schema.sql` from this repo
3. Click **Run**

### 3. Copy API credentials

1. Supabase: **Project Settings** → **API**
2. Copy:
   - **Project URL**
   - **`service_role` key** (secret — under “Project API keys”)  
     Use **service_role**, not `anon`. The app runs only on the server and needs write access.

### 4. Add to Streamlit Secrets

Streamlit Cloud → your app → **Manage app** → **Settings** → **Secrets**.  
Keep your existing `[auth]` block and **add**:

```toml
[supabase]
url = "https://YOUR_PROJECT_REF.supabase.co"
key = "YOUR_SERVICE_ROLE_SECRET_KEY"
```

Save. The app should redeploy and the sidebar should say **Data: Supabase (cloud, permanent)**.

### 5. First use after switch

- Old entries that lived only on Streamlit’s temporary disk are **not** auto-migrated (they were already at risk of disappearing).
- Re-add **Crew & projects** if the new database is empty, then log new entries.
- Use **Excel export** regularly as an offline backup.

Full secrets template: `secrets.example.toml`.

## Login (email / password)

1. Generate a password hash:

```bash
python3 hash_password.py
```

2. In Streamlit Secrets:

```toml
[auth]
enabled = true

[auth.credentials]
"you@example.com" = "$2b$12$...."

[auth.names]
"you@example.com" = "Your Name"
```

Without `[auth]` secrets, the app runs open (local testing only).

## Suggested daily flow

1. Set real workers and job sites under **Crew & projects**.
2. Each day, **New entry** → save.
3. For reports or payroll overview: **Excel export**.

## Security notes

- Never commit real passwords, bcrypt hashes for production, or the Supabase **service_role** key to Git.
- Put them only in Streamlit **Secrets** (or local `.streamlit/secrets.toml`, which is gitignored).
