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
   ALLOWED_HOSTS=ubpm.mn,www.ubpm.mn
   SITE_URL=https://ubpm.mn
   CANONICAL_HOST=ubpm.mn
   DEFAULT_FROM_EMAIL=UBPM <noreply@ubpm.mn>
   ```

   `DATABASE_URL` нь Postgres service рүү reference хийнэ — Railway нь
   `${{Postgres.DATABASE_URL}}`-ийг автоматаар бодит холболтоор сольно.

4. **Domain** — Settings → **Networking** → **Generate Domain** дарж нийтийн
   `*.up.railway.app` хаяг авна. `RAILWAY_PUBLIC_DOMAIN`-г Railway автоматаар
   өгдөг тул CSRF-д автоматаар итгэнэ.

5. **Deploy** — Railway автоматаар build & deploy хийнэ. Push хийх бүрт дахин
   deploy хийгдэнэ.

## ubpm.mn custom domain холбох

Үндсэн домайн нь **ubpm.mn**; Railway-ийн `ubpm.up.railway.app` хаяг нь
ubpm.mn ажиллахгүй үеийн нөөц (fallback) хэвээр үлдэнэ.

`CANONICAL_HOST=ubpm.mn` тохиргоотой үед `www.ubpm.mn` болон Railway домайн
хоёулаа `https://ubpm.mn` руу **301**-ээр шилжинэ. Хайлтын систем хоёр ижил
сайт харахгүйн тулд ингэсэн.

**ubpm.mn унасан үед** нөөц домайныг ажиллуулахын тулд Variables дээр:

1. `CANONICAL_HOST=` (хоосон) — шилжүүлгийг унтраана
2. `ALLOWED_HOSTS=ubpm.mn,www.ubpm.mn,<таны>.up.railway.app` — Railway домайныг
   ЗААВАЛ нэмнэ, эс тэгвээс Django `400 Bad Request` буцаана
3. `SITE_URL=https://<таны>.up.railway.app` — имэйл доторх линкүүд ажиллана

дараа нь дахин deploy хийнэ.

> Railway домайн одоо `ALLOWED_HOSTS`-д алга (`RAILWAY_PUBLIC_DOMAIN` нь custom
> домайныг заадаг болсон). Тиймээс дээрх 2-р алхмыг алгасах аргагүй. Хэвийн үед
> энэ нь асуудалгүй — middleware тэр домайныг 400 биш 301-ээр ubpm.mn руу
> шилжүүлдэг.

1. **Railway дээр домайн нэмэх** — web service → Settings → **Networking** →
   **Custom Domain** → `ubpm.mn` (мөн `www.ubpm.mn`-г тусад нь) нэмнэ.
   Railway домайн бүрт CNAME target (жишээ нь `xxxx.up.railway.app`) өгнө.
   CLI-ээр бол: `railway domain ubpm.mn` ба `railway domain www.ubpm.mn`.

2. **DNS бүртгэл** — домайны бүртгэгч (datacom.mn г.м.) дээр:
   - `www` → **CNAME** → Railway-ийн өгсөн target.
   - Root (`ubpm.mn` өөрөө) CNAME дэмждэггүй бол хамгийн хялбар нь DNS-ээ
     **Cloudflare** (үнэгүй) рүү шилжүүлж, `@` болон `www` дээр CNAME
     (flattening автоматаар хийгдэнэ) тавих. Cloudflare proxy асаавал
     SSL/TLS mode-г **Full** болгоно.

3. **Хүлээх** — DNS тархалт + Railway SSL сертификат (Let's Encrypt)
   автоматаар гарна. `https://ubpm.mn/api/v1/health/` 200 буцаавал бэлэн.

Домайн холбогдсоны дараа Variables дээр `ALLOWED_HOSTS=ubpm.mn,www.ubpm.mn`
болон `SITE_URL=https://ubpm.mn` байгааг шалгана (settings-ийн default нь
аль хэдийн ubpm.mn тул хоосон орхисон ч болно).

## Имэйл — Railway дээр SMTP ажиллахгүй

**Railway нь spam-аас сэргийлж гадагш SMTP портуудыг (25/465/587) хаадаг.**
Тиймээс Gmail-ийн App Password хэдий зөв ч контейнер дотроос холбогдох гэхэд
`[Errno 101] Network is unreachable` гэж унана. Порт солих (`465` + SSL) ч
тусалдаггүй — бүх SMTP порт хаалттай.

Шийдэл нь HTTPS (443) ашигладаг **HTTP API**-тай үйлчилгээ. Төсөлд
[Resend](https://resend.com)-ийн backend бэлэн байгаа
(`apps/notifications/backends.py`):

1. **Resend дээр бүртгүүлж домайнаа баталгаажуулна** — Domains → Add Domain →
   `ubpm.mn`. Resend өгсөн DKIM/SPF бичлэгүүдийг Namecheap → Advanced DNS дээр
   нэмнэ.

   > ⚠️ Домайн дээр аль хэдийн SPF бичлэг (`v=spf1 ...`) байгаа. Түүнийг **дарж
   > бичихгүй** — нэг домайн нэг л SPF TXT-тэй байх ёстой тул Resend-ийн
   > `include:` хэсгийг байгаа мөрөндөө нэмж бичнэ.

2. **API key үүсгээд** Railway → Variables дээр нэмнэ:

   ```
   RESEND_API_KEY=re_xxxxxxxx
   DEFAULT_FROM_EMAIL=UBPM <noreply@ubpm.mn>
   ```

   `RESEND_API_KEY` тавигдсан үед prod нь SMTP-ийн оронд автоматаар үүнийг
   ашиглана. `EMAIL_HOST_*` хувьсагчдыг устгах шаардлагагүй — хэрэглэгдэхгүй.

   From хаяг нь **баталгаажуулсан домайных** байх ёстой. Домайн баталгаажаагүй
   үед Resend `403 domain is not verified` буцаах бөгөөд тэр текст EmailLog дээр
   бүтнээрээ харагдана.

Локал хөгжүүлэлтэд Resend хэрэггүй — dev settings нь консол руу хэвлэдэг.

## Имэйл явахгүй бол (үнийн санал, нууц үг сэргээх код)

Мэдэгдлүүд background thread-д илгээгддэг тул алдаа хэрэглэгчид харагдахгүй —
үр дүн нь **EmailLog**-д бичигддэг. Дараах дарааллаар шалгана:

1. **Админ талаас** — `/dashboard/email-status/` (дашбоардын цэсэн дэх
   «Email»). Ажиллаж буй тохиргоо, холболтын шалгалт, сүүлийн 20 захиа алдаатай
   нь хамт харагдана. Хүсэлтийн дэлгэрэнгүй хуудсанд ч «Илгээсэн имэйл» самбар
   байгаа. (Эсвэл `/admin/notifications/emaillog/`.)

2. **Тохиргоог шалгах** — Railway-ийн container дотор:

   ```bash
   railway ssh "uv run python manage.py send_test_email \
       tanii@gmail.com --settings=ubpm.settings.prod"
   ```

   Энэ команд ажиллаж буй тохиргоог хэвлээд SMTP руу холбогдож, туршилтын
   захиа илгээнэ. Гарсан алдааг бүтнээр нь харуулна.

3. **Түгээмэл шалтгаанууд:**

   | Шинж тэмдэг | Шалтгаан / засвар |
   |---|---|
   | `[Errno 101] Network is unreachable` | **Railway SMTP портыг хаасан.** Порт солиод нэмэргүй — дээрх Resend хэсгийг үзнэ үү. |
   | `EMAIL_BACKEND` нь `console...` гэж гарвал | `RESEND_API_KEY` ч, `EMAIL_HOST_USER`/`EMAIL_HOST_PASSWORD` ч тавигдаагүй. Захиа хэнд ч хүрэхгүй; EmailLog дээр амжилтгүй гэж бичигдэнэ. |
   | `Resend API 403 ... domain is not verified` | Resend дээр `ubpm.mn` домайныг баталгаажуулаагүй, эсвэл From хаяг өөр домайных байна. |
   | `Resend API 401` | `RESEND_API_KEY` буруу эсвэл хүчингүй болсон. |
   | `SMTPAuthenticationError` | Gmail-ийн энгийн нууц үг ажиллахгүй. Google Account → Security → 2-Step Verification → **App passwords** дээрээс 16 тэмдэгт код үүсгэж тавина. |
   | Захиа явсан ч ирэхгүй | Spam хавтас, мөн Gmail-ийн өдрийн 500 захианы хязгаарыг шалгана. |

`EMAIL_TIMEOUT` (default 10 сек) нь SMTP хариу өгөхгүй үед хүсэлт мөнхөд
өлгөгдөхөөс сэргийлдэг — сүлжээ удаан бол нэмэгдүүлж болно.

## Нэвтрэх

- Django admin: `https://<your-domain>/admin/` → **admin** / **1234**
- Эхний нэвтрэлтийн дараа нууц үгээ солихыг зөвлөж байна.

## Нэмэлт (optional) хувьсагчид

| Хувьсагч | Зориулалт |
|---|---|
| `RESEND_API_KEY` | HTTP API-аар имэйл илгээх (Railway дээр ЭНЭ хэрэгтэй — SMTP хаалттай) |
| `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | SMTP имэйл (SMTP нээлттэй hosting дээр; байхгүй бол консолд хэвлэнэ) |
| `EMAIL_PORT=465` + `EMAIL_USE_SSL=True` | 587 порт хаалттай үеийн SSL хувилбар |
| `EMAIL_TIMEOUT` | SMTP хүлээх хугацаа, секундээр (default 10) |
| `USE_S3=True` + `AWS_*` | Зураг/видеог object storage / CDN рүү (S3-нийцтэй) |
| `SECURE_SSL_REDIRECT=False` | Healthcheck HTTP дээр асуудалтай бол |
| `ALLOWED_HOSTS=ubpm.mn,www.ubpm.mn` | Эцсийн домэйнд хязгаарлах |

> ⚠️ `railway.env` файл нь бодит SECRET_KEY агуулсан тул git-д орохгүй
> (`.gitignore`-д байгаа). Зөвхөн Railway-д хуулж тавихад зориулсан.
