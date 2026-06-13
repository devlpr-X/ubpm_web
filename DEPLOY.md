# Railway дээр deploy хийх

UBPM нь Dockerfile-аар Railway дээр deploy хийгдэнэ. Container эхлэхдээ
автоматаар `migrate` хийж, `admin / 1234` superuser үүсгээд, gunicorn-оор
ажиллана (`$PORT`-д холбогдоно).

## Алхамууд

1. **Project үүсгэх** — [railway.app](https://railway.app) → **New Project**
   → **Deploy from GitHub repo** → `devlpr-X/ubpm_web`. Railway нь `railway.json`
   /`Dockerfile`-ийг автоматаар олж build хийнэ.

2. **PostgreSQL нэмэх** — мөн project дотроо **New** → **Database** →
   **Add PostgreSQL**. (Service-ийн нэр `Postgres` байна.)

3. **Орчны хувьсагч (Variables)** — web service → **Variables** → **Raw Editor**
   рүү дараах блокийг шууд хуулж тавина (`railway.env` файлд бэлэн байгаа):

   ```
   SECRET_KEY=<урт_санамсаргүй_тэмдэгт>
   DEBUG=False
   DJANGO_SETTINGS_MODULE=ubpm.settings.prod
   DATABASE_URL=${{Postgres.DATABASE_URL}}
   ALLOWED_HOSTS=*
   DEFAULT_FROM_EMAIL=UBPM <noreply@ubpm.mn>
   ```

   `DATABASE_URL` нь Postgres service рүү reference хийнэ — Railway нь
   `${{Postgres.DATABASE_URL}}`-ийг автоматаар бодит холболтоор сольно.

4. **Domain** — Settings → **Networking** → **Generate Domain** дарж нийтийн
   `*.up.railway.app` хаяг авна. `RAILWAY_PUBLIC_DOMAIN`-г Railway автоматаар
   өгдөг тул CSRF-д автоматаар итгэнэ.

5. **Deploy** — Railway автоматаар build & deploy хийнэ. Push хийх бүрт дахин
   deploy хийгдэнэ.

## Нэвтрэх

- Django admin: `https://<your-domain>/admin/` → **admin** / **1234**
- Эхний нэвтрэлтийн дараа нууц үгээ солихыг зөвлөж байна.

## Нэмэлт (optional) хувьсагчид

| Хувьсагч | Зориулалт |
|---|---|
| `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | SMTP имэйл (байхгүй бол консолд хэвлэнэ) |
| `USE_S3=True` + `AWS_*` | Зураг/видеог object storage / CDN рүү (S3-нийцтэй) |
| `SECURE_SSL_REDIRECT=False` | Healthcheck HTTP дээр асуудалтай бол |
| `ALLOWED_HOSTS=ubpm.mn,www.ubpm.mn` | Эцсийн домэйнд хязгаарлах |

> ⚠️ `railway.env` файл нь бодит SECRET_KEY агуулсан тул git-д орохгүй
> (`.gitignore`-д байгаа). Зөвхөн Railway-д хуулж тавихад зориулсан.
