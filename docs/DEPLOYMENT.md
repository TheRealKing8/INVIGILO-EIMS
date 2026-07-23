# Deployment — Vercel (frontend) + Render (backend)

This runbook puts the Invigilo exam-invigilation system into production on **free tiers** of two well-known platforms:

- **Frontend** (Next.js) → [Vercel](https://vercel.com)
- **Backend** (Django + DRF) + **Postgres** → [Render](https://render.com)

Total ongoing cost: **$0** until you outgrow the free tier. The first deploy takes about 10 minutes.

---

## What's already in the repo

- `backend/render.yaml` — Render Blueprint that defines the Postgres DB and the Django web service.
- `frontend/vercel.json` — Vercel config (framework preset + security headers).
- `backend/invigilo/settings/prod.py` — production settings (TLS redirect, HSTS, JSON logging, optional Sentry). Already wired.
- `frontend/src/lib/api.ts` — the frontend reads `NEXT_PUBLIC_API_BASE_URL` from env (defaults to `http://127.0.0.1:8000`).

You should not need to touch the code. Only env vars.

---

## Step 0 — Prerequisites

- A GitHub account with the Invigilo repo pushed to `main`.
- A Vercel account (sign in with GitHub).
- A Render account (sign in with GitHub).
- A password manager (you'll generate ~5 secrets).
- **20 minutes** of your time.

---

## Step 1 — Deploy the backend to Render

The frontend needs the backend's URL, so backend first.

### 1.1 Create the Blueprint

1. Sign in at <https://render.com>.
2. Click **New +** → **Blueprint**.
3. Pick the Invigilo repo. If Render asks for the path, point it at `backend/render.yaml`.
4. Render reads the Blueprint and previews two services:
   - **`invigilo-db`** — a free PostgreSQL 16 instance.
   - **`invigilo-api`** — a free Python web service.
5. Click **Apply**. Wait ~3 minutes for the first build to finish.

### 1.2 Replace the placeholder secret

The Blueprint ships with a placeholder `DJANGO_SECRET_KEY` value. **Before the first request works, replace it:**

1. In the Render dashboard, click the `invigilo-api` service.
2. Open the **Environment** tab.
3. Find the `DJANGO_SECRET_KEY` row. Click **Edit** and paste a fresh 50-char random value:
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(50))"
   ```
4. Set the **same** value for `JWT_SIGNING_KEY` (the codebase reuses the same key for both).
5. Click **Save Changes**. Render auto-redeploys (~2 minutes).

### 1.3 Verify the health check

```bash
curl https://invigilo-api.onrender.com/api/health/
```

You should see `{"status":"ok"}`. If you see a 5xx, check the **Logs** tab in the Render dashboard.

### 1.4 Seed the database

The free tier doesn't give you a shell that survives deploys, so use a one-off management command via the Render Shell:

1. In the Render dashboard, click `invigilo-api` → **Shell** (top right).
2. Run the seed:
   ```bash
   python manage.py shell -c "
   from apps.accounts.seed import PERMISSIONS, ROLES, ROLE_PERMISSIONS
   from apps.accounts.models import Permission, Role, RolePermission
   for p in PERMISSIONS:
       Permission.objects.update_or_create(codename=p['codename'], defaults={'name': p['name']})
   for r in ROLES:
       Role.objects.update_or_create(code=r['code'], defaults={'name': r['name'], 'is_active': True})
   for code, perms in ROLE_PERMISSIONS:
       role = Role.objects.get(code=code)
       for c in perms:
           perm = Permission.objects.get(codename=c)
           RolePermission.objects.update_or_create(role=role, permission=perm)
   print('seeded')
   "
   ```
3. (Optional) seed a demo student user:
   ```bash
   python manage.py shell -c "
   from django.contrib.auth import get_user_model
   from apps.accounts.models import Role, UserRole
   U = get_user_model()
   role = Role.objects.get(code='STUDENT')
   u, _ = U.objects.update_or_create(
       email='student.invigilo@gmail.com',
       defaults={'full_name': 'Brian Otieno', 'is_email_verified': True, 'is_active': True},
   )
   u.set_password('Demo@2026Student'); u.save()
   UserRole.objects.update_or_create(user=u, role=role)
   print('student user ready')
   "
   ```

### 1.5 Sanity check

```bash
curl https://invigilo-api.onrender.com/api/v1/exams/sessions/ | head -50
```

You should get a paginated JSON response (empty list is fine — the seed didn't add sessions).

---

## Step 2 — Deploy the frontend to Vercel

### 2.1 Create the project

1. Sign in at <https://vercel.com>.
2. Click **Add New** → **Project**.
3. Pick the Invigilo repo. **Set the root directory to `frontend`** (Vercel's UI has a "Edit" link next to the root).
4. Framework preset: **Next.js** (auto-detected).
5. **Do not deploy yet** — first set the env var:
   - **Name**: `NEXT_PUBLIC_API_BASE_URL`
   - **Value**: `https://invigilo-api.onrender.com` (the URL from step 1.3 — without a trailing slash).
6. Click **Deploy**. The first build takes ~2 minutes. When it finishes you'll have a URL like `https://invigilo-frontend.vercel.app`.

### 2.2 Smoke test

Open the Vercel URL in a browser. You should see the public landing page. Click **Sign in** and log in as `admininvigilo@gmail.com` / `Invigilo@2026` (the seeded admin). The dashboard should load.

If you see CORS errors, go to step 3.

---

## Step 3 — Close the CORS loop

The backend was told to allow `https://invigilo-frontend.vercel.app` as a CORS origin in the Blueprint. If your actual Vercel URL is different (Vercel often appends a random suffix), you need to update the backend's env var:

1. In Render, click `invigilo-api` → **Environment**.
2. Find `DJANGO_CORS_ALLOWED_ORIGINS` and edit it to the **exact** URL Vercel assigned you (no trailing slash). Multiple origins go in a comma-separated list.
3. Click **Save Changes**. Render auto-redeploys (~2 minutes).
4. Refresh the Vercel URL — the dashboard should now load without CORS errors.

---

## Step 4 — End-to-end smoke test

1. Visit the Vercel URL.
2. Log in as `admininvigilo@gmail.com` / `Invigilo@2026`. Confirm the operations dashboard loads with live data.
3. Sign out, register a new account at `/register`. The form auto-demotes to STUDENT (Phase 21) — confirm the role badge says "Student".
4. Log in as the new student. The sidebar should show **"My exams"** (the new Phase 25 entry).
5. If you seeded a `StudentRegistration` row tied to an exam session, navigate to `/dashboard/student/exams/[id]/card` and confirm the QR PNG renders.
6. From the operations side, log back in as admin and visit `/dashboard/exams` — confirm the rest of the app is unaffected.

If all six steps work, the deployment is done.

---

## Free-tier caveats — read these

| Limitation | What it means | Workaround |
|---|---|---|
| Render free Postgres **expires after 90 days** | Render emails a 7-day warning. After 90 days, the DB is deleted unless you upgrade. | Re-provision before the deadline, or back up with `pg_dump` regularly. |
| Render free web service **sleeps after 15 min** of inactivity | First request after sleep takes 30-50s. | Acceptable for a demo. For a live exam day, upgrade to a paid plan or put a keep-alive ping in front (e.g. cron-job.org hitting `/api/health/` every 10 min). |
| **No free Celery worker** | Background email tasks would normally run in a separate worker process. On free tier, set `CELERY_TASK_ALWAYS_EAGER=1` (already in the Blueprint) so tasks run synchronously in the web process. | Email delivery falls through to the console backend (set in the Blueprint). For real email, upgrade or use an external SMTP relay like SendGrid. |
| Vercel free tier: **100GB bandwidth / month** | Plenty for a demo, marginal for a real university. | Upgrade to Pro ($20/mo) for more headroom. |
| Vercel free tier: **10s function timeout** | Not relevant — this app is SSR with no edge functions. | — |
| **No real Celery means no real scheduled tasks** | `django-celery-beat` schedule entries (e.g. daily report generation) don't run on the free tier. | Run the equivalent code on-demand from the dashboard, or upgrade. |

---

## Secrets checklist

| Variable | Where | How to generate |
|---|---|---|
| `DJANGO_SECRET_KEY` | Render dashboard | `python -c "import secrets; print(secrets.token_urlsafe(50))"` |
| `JWT_SIGNING_KEY` | Render dashboard | Same value as `DJANGO_SECRET_KEY` is fine |
| `POSTGRES_PASSWORD` | Render dashboard | Auto-generated by the Postgres service |
| `NEXT_PUBLIC_API_BASE_URL` | Vercel dashboard | The Render URL from step 1.3 |

**Never** put any of these in git. The Blueprint file in this repo has placeholders only.

---

## Rotating secrets

1. **JWT/Django secret**: generate a new random value, paste it into Render, save. The web service redeploys. All existing sessions are invalidated (users must log in again).
2. **Postgres password**: click the `invigilo-db` service in Render → **Access** → rotate. Render auto-updates the `POSTGRES_PASSWORD` env var on the web service.
3. **OpenRouter API key** (if you set one): rotate in the OpenRouter dashboard, then paste the new value into Render.

---

## Going to production beyond the free tier

When you're ready to upgrade, the migration is small:

- **Render Postgres** → upgrade to the Starter plan ($7/mo). No code change.
- **Render web service** → upgrade to Starter ($7/mo). Sleep behaviour stops. Set `workers` to 3+ in the Blueprint.
- **Celery worker** → add a second Render service of type `worker` running `celery -A invigilo worker -l info`. Set `CELERY_TASK_ALWAYS_EAGER=False` in the web service env.
- **Email** → switch the `EMAIL_BACKEND` env var from `console` to `django.core.mail.backends.smtp.EmailBackend` and add your SMTP creds.
- **Custom domain** → Vercel Domains tab → add `invigilo.example.edu` → update `DJANGO_ALLOWED_HOSTS` + `DJANGO_CORS_ALLOWED_ORIGINS` in Render to include it.

Total cost at the "small university" tier: ~$30-50/month.
