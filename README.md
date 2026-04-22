# UBPM Buyback System

UBPM ХХК-ийн e-waste худалдан авалтын автомат систем — иргэд, компаниудаас эвдэрсэн гар утас, нөүтбүүк, таблет, камер зэргийг үнэлж, худалдан авах процессыг бүрэн дижиталжуулсан.

**Stack:** Django 5 · PostgreSQL 16 · Tailwind CSS · Alpine.js · HTMX

---

## Quick start (dev)

```bash
# 1. Install uv (one-time, if not installed)
pip install uv

# 2. Create venv + install deps
uv venv --python 3.11
uv sync

# 3. Copy env file and edit if needed
cp .env.example .env

# 4. (Optional) Start Postgres + pgAdmin via Docker
docker compose up -d
# Then in .env set: DATABASE_URL=postgres://ubpm:ubpm@localhost:5432/ubpm

# 5. Migrate + run
uv run python manage.py migrate
uv run python manage.py runserver
```

Visit http://localhost:8000

pgAdmin: http://localhost:5050 (admin@ubpm.local / admin)

---

## Project layout

```
ubpm/
├── ubpm/settings/      # base / dev / prod split
├── apps/
│   ├── accounts/       # custom User (email login)
│   ├── core/           # shared mixins, base views
│   ├── branches/       # UBPM салбар + хамтрагч цэгүүд
│   ├── intake/         # үнэ асуух хүсэлт workflow
│   ├── quotes/         # үнэ санал, статусын түүх
│   ├── notifications/  # email
│   └── reports/        # Excel/CSV export, dashboard stats
├── templates/          # public / dashboard / emails
├── static/
└── tests/
```

---

## Common commands

```bash
uv run python manage.py runserver        # dev server
uv run python manage.py makemigrations
uv run python manage.py migrate
uv run python manage.py createsuperuser
uv run python manage.py shell

uv run pytest                            # run tests
uv run pytest --cov                      # with coverage
uv run ruff check .                      # lint
uv run ruff format .                     # format
```

---

## Progress

- [x] **Phase 0** — Project scaffold (settings split, apps, base template, Tailwind, docker-compose)
- [ ] **Phase 1** — Custom User + Branches
- [ ] **Phase 2** — Intake (request workflow + multi-step form + image upload)
- [ ] **Phase 3** — Quotes + status workflow + operator dashboard
- [ ] **Phase 4** — Notifications (email)
- [ ] **Phase 5** — Reports + Excel/CSV export
- [ ] **Phase 6** — Pickup module + public pages + media gallery
- [ ] **Phase 7** — Production deployment (Dockerfile, gunicorn, nginx)

---

## Holboo barih

UBPM ХХК · 7774-6465 · 9915-6465 · 8025-6465
Ажиллах цаг: 10:00–17:30 (амралтын өдөр ч)
