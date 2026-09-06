from datetime import date
from unittest.mock import patch

import pytest
from django.test import override_settings
from django.urls import reverse

from apps.accounts.models import User
from apps.intake.models import IntakeRequest


@pytest.fixture
def staff_client(client, django_user_model):
    staff = django_user_model.objects.create_user(
        email="op@ubpm.mn", password="x", role=django_user_model.Role.ADMIN
    )
    client.force_login(staff)
    return client


def _make_requests(n):
    for i in range(n):
        IntakeRequest.objects.create(contact_name=f"Хэрэглэгч {i}", contact_phone="9911")


@pytest.mark.django_db
def test_request_list_defaults_to_25_per_page(staff_client):
    _make_requests(30)
    resp = staff_client.get(reverse("dashboard:request_list"))
    assert resp.status_code == 200
    assert resp.context["per_page"] == "25"
    assert len(resp.context["requests"]) == 25
    assert resp.context["total"] == 30
    assert resp.context["page_obj"].paginator.num_pages == 2


@pytest.mark.django_db
@pytest.mark.parametrize("per_page,expected", [("10", 10), ("25", 25), ("50", 30)])
def test_request_list_per_page_choices(staff_client, per_page, expected):
    _make_requests(30)
    resp = staff_client.get(reverse("dashboard:request_list"), {"per_page": per_page})
    assert len(resp.context["requests"]) == expected


@pytest.mark.django_db
def test_request_list_all_disables_pagination(staff_client):
    _make_requests(30)
    resp = staff_client.get(reverse("dashboard:request_list"), {"per_page": "all"})
    assert resp.context["page_obj"] is None
    assert len(resp.context["requests"]) == 30


@pytest.mark.django_db
def test_request_list_second_page(staff_client):
    _make_requests(30)
    resp = staff_client.get(reverse("dashboard:request_list"), {"page": "2"})
    assert resp.context["page_obj"].number == 2
    assert len(resp.context["requests"]) == 5


@pytest.mark.django_db
def test_request_list_invalid_per_page_falls_back_to_default(staff_client):
    _make_requests(5)
    resp = staff_client.get(reverse("dashboard:request_list"), {"per_page": "9999"})
    assert resp.context["per_page"] == "25"


@pytest.mark.django_db
def test_request_list_pagination_keeps_filters(staff_client):
    """Хуудас солиход шүүлтүүр хадгалагдана ({% querystring %} тагийн үүрэг)."""
    _make_requests(30)
    resp = staff_client.get(reverse("dashboard:request_list"), {"per_page": "10", "q": ""})
    content = resp.content.decode()
    assert "per_page=10" in content
    assert "page=2" in content


@pytest.mark.django_db
def test_request_detail_shows_email_log(staff_client):
    from apps.notifications.models import EmailLog

    intake = IntakeRequest.objects.create(contact_name="A", contact_phone="9911")
    EmailLog.objects.create(
        recipient_email="a@b.com",
        subject="Үнэ санал",
        intake_request=intake,
        success=False,
        error="SMTPAuthenticationError: bad credentials",
    )
    resp = staff_client.get(
        reverse("dashboard:request_detail", args=[intake.request_code])
    )
    assert resp.status_code == 200
    assert b"SMTPAuthenticationError" in resp.content


@pytest.mark.django_db
def test_dashboard_pages_render(staff_client):
    """Icon солилтын дараа dashboard-ийн бүх хуудас алдаагүй render хийгдэнэ."""
    intake = IntakeRequest.objects.create(
        contact_name="A",
        contact_phone="9911",
        pickup_required=True,
        pickup_lat="47.918800",
        pickup_lng="106.917600",
    )
    for name, args in [
        ("dashboard:overview", []),
        ("dashboard:request_list", []),
        ("dashboard:delivery", []),
        ("dashboard:pickup_list", []),
        ("dashboard:reports", []),
        ("dashboard:request_detail", [intake.request_code]),
    ]:
        resp = staff_client.get(reverse(name, args=args))
        assert resp.status_code == 200, name


@pytest.mark.django_db
def test_dashboard_lists_use_font_awesome_not_emoji(staff_client):
    """Цэс болон жагсаалтууд emoji биш, icon класс ашиглана."""
    resp = staff_client.get(reverse("dashboard:overview"))
    content = resp.content.decode()
    assert 'class="fa-regular fa-chart-bar fa-fw"' in content
    assert "\U0001F4CA" not in content  # 📊


# ---------------------------------------------------------------------------
# Email оношилгооны хуудас
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_email_status_page_is_admin_only(client):
    url = reverse("dashboard:email_status")

    # Нэвтрээгүй — login руу.
    assert client.get(url).status_code == 302

    # Энгийн хэрэглэгч — эрхгүй, нүүр рүү буцаана.
    User.objects.create_user(email="op@x.mn", password="1234", role=User.Role.CUSTOMER)
    client.login(email="op@x.mn", password="1234")
    res = client.get(url)
    assert res.status_code == 302
    assert res["Location"] == reverse("core:home")
    client.logout()

    # Админ — нэвтэрнэ.
    User.objects.create_user(email="boss@x.mn", password="1234", role=User.Role.ADMIN)
    client.login(email="boss@x.mn", password="1234")
    assert client.get(url).status_code == 200


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend")
def test_email_status_flags_console_backend(client):
    User.objects.create_user(email="boss@x.mn", password="1234", role=User.Role.ADMIN)
    client.login(email="boss@x.mn", password="1234")

    # POST = холболт шалгах. Console backend дээр захиа хүрэхгүйг хэлэх ёстой.
    html = client.post(reverse("dashboard:email_status")).content.decode()
    assert "EMAIL_BACKEND нь SMTP биш" in html
    assert "EMAIL_HOST_USER" in html


@pytest.mark.django_db
def test_email_status_never_shows_the_password(client):
    User.objects.create_user(email="boss@x.mn", password="1234", role=User.Role.ADMIN)
    client.login(email="boss@x.mn", password="1234")

    with override_settings(EMAIL_HOST_PASSWORD="super-secret-app-password"):
        html = client.get(reverse("dashboard:email_status")).content.decode()

    assert "super-secret-app-password" not in html
    # Зөвхөн тавигдсан эсэх, урт нь харагдана.
    assert "тавигдсан (25 тэмдэгт)" in html


# --- Төлөвийн өнгө + ижил загварын үнэ ----------------------------------------


@pytest.mark.django_db
def test_status_colours_are_shared_between_pages(staff_client):
    """Ижил төлөв бүх жагсаалт дээр ижил өнгөтэй — өнгө нэг эх сурвалжаас."""
    intake = IntakeRequest.objects.create(
        contact_name="A", contact_phone="9911", status=IntakeRequest.Status.PURCHASED
    )
    colour = IntakeRequest.STATUS_BADGE_CLASSES[IntakeRequest.Status.PURCHASED]

    for url in [
        reverse("dashboard:request_list"),
        reverse("dashboard:overview"),
        reverse("dashboard:request_detail", kwargs={"code": intake.request_code}),
        intake.public_tracking_url(),
    ]:
        assert colour in staff_client.get(url).content.decode(), url


@pytest.mark.django_db
def test_every_status_has_its_own_colour():
    seen = {}
    for status, _label in IntakeRequest.Status.choices:
        css = IntakeRequest(status=status).status_badge_class
        assert css != IntakeRequest.DEFAULT_BADGE_CLASS, status
        assert css not in seen, f"{status} нь {seen.get(css)}-той ижил өнгөтэй байна"
        seen[css] = status


@pytest.mark.django_db
def test_unknown_status_falls_back_to_grey():
    # Жагсаалтаас хассан хуучин төлөвтэй мөр үлдсэн ч хуудас унахгүй.
    assert IntakeRequest(status="REJECTED").status_badge_class == IntakeRequest.DEFAULT_BADGE_CLASS


def _category(slug="phone", name="Гар утас"):
    from apps.intake.models import DeviceCategory

    category, _ = DeviceCategory.objects.get_or_create(slug=slug, defaults={"name": name})
    return category


def _phone(intake, brand="Apple", model="iPhone 13", slug="phone", **kwargs):
    from apps.intake.models import DeviceItem

    return DeviceItem.objects.create(
        intake_request=intake, category=_category(slug), brand=brand, model=model, **kwargs
    )


def _quoted(
    brand,
    model,
    *,
    low,
    high,
    final=None,
    slug="phone",
    status=IntakeRequest.Status.PRICE_SENT,
):
    from apps.quotes.models import Quotation

    intake = IntakeRequest.objects.create(contact_name="B", contact_phone="9911", status=status)
    _phone(intake, brand=brand, model=model, slug=slug)
    Quotation.objects.create(
        intake_request=intake,
        quoted_price_min=low,
        quoted_price_max=high,
        final_offer_price=final,
    )
    return intake


@pytest.mark.django_db
def test_detail_lists_previous_prices_for_the_same_brand_and_category(staff_client):
    """Загвар яг таарах шаардлагагүй — Apple гар утас бүхэн жагсаалтад орно."""
    current = IntakeRequest.objects.create(contact_name="A", contact_phone="9911")
    _phone(current, brand="Apple", model="iPhone 13")

    same_model = _quoted("Apple", "iPhone 13", low=300000, high=450000, final=400000)
    other_model = _quoted("Apple", "iPhone 15 Pro", low=800000, high=900000)
    _quoted("Samsung", "Galaxy S21", low=100000, high=200000)  # өөр бренд — орохгүй
    _quoted("Apple", "MacBook Pro", low=1, high=2, slug="laptop")  # өөр ангилал — орохгүй

    resp = staff_client.get(
        reverse("dashboard:request_detail", kwargs={"code": current.request_code})
    )
    rows = resp.context["similar_quotes"]
    assert {r["request"].pk for r in rows} == {same_model.pk, other_model.pk}

    body = resp.content.decode()
    assert "Ижил бренд/ангиллын өмнөх үнэ" in body
    assert "400000₮" in body
    # Аль загвар нь болохыг мөрөндөө харуулна, мөр нь дэлгэрэнгүй рүү холбогдоно.
    assert "iPhone 15 Pro" in body
    assert same_model.get_absolute_url() in body


@pytest.mark.django_db
def test_previous_prices_ignore_case_and_the_request_itself(staff_client):
    current = IntakeRequest.objects.create(contact_name="A", contact_phone="9911")
    _phone(current, brand="apple", model="iphone 13")

    old = _quoted("Apple", "iPhone 12", low=1, high=2)

    resp = staff_client.get(
        reverse("dashboard:request_detail", kwargs={"code": current.request_code})
    )
    assert [r["request"].pk for r in resp.context["similar_quotes"]] == [old.pk]


@pytest.mark.django_db
def test_previous_prices_capped_at_twenty_newest_first(staff_client):
    current = IntakeRequest.objects.create(contact_name="A", contact_phone="9911")
    _phone(current)
    for _ in range(22):
        _quoted("Apple", "iPhone 13", low=1, high=2)

    resp = staff_client.get(
        reverse("dashboard:request_detail", kwargs={"code": current.request_code})
    )
    rows = resp.context["similar_quotes"]
    assert len(rows) == 20
    dates = [r["request"].created_at for r in rows]
    assert dates == sorted(dates, reverse=True)


@pytest.mark.django_db
def test_purchased_requests_are_listed_with_their_status(staff_client):
    """Хэлцэл болсон эсэхийг мөрийн төлөвөөс шууд харна."""
    current = IntakeRequest.objects.create(contact_name="A", contact_phone="9911")
    _phone(current)
    done = _quoted(
        "Apple", "iPhone 13", low=1, high=2, final=350000,
        status=IntakeRequest.Status.PURCHASED,
    )

    resp = staff_client.get(
        reverse("dashboard:request_detail", kwargs={"code": current.request_code})
    )
    assert [r["request"].pk for r in resp.context["similar_quotes"]] == [done.pk]
    body = resp.content.decode()
    assert IntakeRequest.STATUS_BADGE_CLASSES[IntakeRequest.Status.PURCHASED] in body
    assert "350000₮" in body


@pytest.mark.django_db
def test_requests_without_a_quote_are_not_listed(staff_client):
    current = IntakeRequest.objects.create(contact_name="A", contact_phone="9911")
    _phone(current)
    other = IntakeRequest.objects.create(contact_name="B", contact_phone="9911")
    _phone(other)  # үнэ өгөөгүй

    resp = staff_client.get(
        reverse("dashboard:request_detail", kwargs={"code": current.request_code})
    )
    assert resp.context["similar_quotes"] == []


@pytest.mark.django_db
def test_no_brand_means_no_reference_list(staff_client):
    """Бренд нь бөглөгдөөгүй бол юутай нь жиших нь тодорхойгүй — хоосон."""
    current = IntakeRequest.objects.create(contact_name="A", contact_phone="9911")
    _phone(current, brand="", model="Тодорхойгүй")
    _quoted("Apple", "iPhone 13", low=1, high=2)

    resp = staff_client.get(
        reverse("dashboard:request_detail", kwargs={"code": current.request_code})
    )
    assert resp.context["similar_quotes"] == []


# --- AI-ийн үнийн санал — дэлгэрэнгүй хуудасны товч ---------------------------
AI_REPLY = {
    "recommended_price": 380000,
    "suggested_min": 350000,
    "suggested_max": 420000,
    "confidence": "HIGH",
    "rationale": "Сүүлийн хэлцлүүд 350-420 мянганы хооронд байна.",
    "comparables": ["REQ-A1"],
}


def _ai_result(suggestion=AI_REPLY, count=20):
    return {
        "request_code": "",
        "model": "gemini-3.8-flash",
        "comparables_count": count,
        "suggestion": suggestion,
    }


@pytest.fixture
def with_history(db):
    """Үнэ тогтоох гэж буй хүсэлт + жиших өмнөх хэлцэл."""
    current = IntakeRequest.objects.create(contact_name="A", contact_phone="9911")
    _phone(current)
    _quoted("Apple", "iPhone 13", low=350000, high=420000, final=390000)
    return current


@pytest.mark.django_db
def test_ai_button_fills_the_quote_form(staff_client, with_history):
    """Товч дарахад санал session-оор буцаж ирж, үнийн форм түүгээр дүүрнэ."""
    with patch("apps.quotes.ai_pricing.suggest_price", return_value=_ai_result()) as ask:
        resp = staff_client.post(
            reverse("dashboard:ai_price", kwargs={"code": with_history.request_code}),
            follow=True,
        )

    assert resp.status_code == 200
    assert ask.call_args.args[0].pk == with_history.pk
    assert resp.context["ai_suggestion"]["recommended_price"] == 380000

    initial = resp.context["quote_form"].initial
    assert initial["quoted_price_min"] == 350000
    assert initial["quoted_price_max"] == 420000
    assert initial["final_offer_price"] == 380000

    body = resp.content.decode()
    assert "AI-ийн санал" in body
    assert "Итгэл: HIGH" in body
    assert AI_REPLY["rationale"] in body


@pytest.mark.django_db
def test_ai_suggestion_is_shown_once(staff_client, with_history):
    """Дахин ачаалахад хуучин санал үлдэхгүй — дахин асуумаар бол товчоо дарна."""
    with patch("apps.quotes.ai_pricing.suggest_price", return_value=_ai_result()):
        staff_client.post(
            reverse("dashboard:ai_price", kwargs={"code": with_history.request_code}),
            follow=True,
        )
    resp = staff_client.get(
        reverse("dashboard:request_detail", kwargs={"code": with_history.request_code})
    )
    assert resp.context["ai_suggestion"] is None
    assert resp.context["quote_form"].initial.get("quoted_price_min") is None


@pytest.mark.django_db
def test_ai_button_reports_a_failure_instead_of_a_price(staff_client, with_history):
    from apps.quotes.ai_pricing import AIPricingConfigError

    with patch(
        "apps.quotes.ai_pricing.suggest_price",
        side_effect=AIPricingConfigError("GEMINI_API_KEY-г тохируулна уу."),
    ):
        resp = staff_client.post(
            reverse("dashboard:ai_price", kwargs={"code": with_history.request_code}),
            follow=True,
        )

    assert resp.status_code == 200
    assert resp.context["ai_suggestion"] is None
    assert "GEMINI_API_KEY" in resp.content.decode()


@pytest.mark.django_db
def test_ai_button_warns_when_there_is_nothing_to_compare(staff_client):
    """Жиших хэлцэлгүй бол загварыг дуудахгүй — сануулга үлдээнэ."""
    current = IntakeRequest.objects.create(contact_name="A", contact_phone="9911")
    _phone(current)
    empty = {**_ai_result(suggestion=None, count=0), "detail": "Жиших зүйл алга."}
    with patch("apps.quotes.ai_pricing.suggest_price", return_value=empty):
        resp = staff_client.post(
            reverse("dashboard:ai_price", kwargs={"code": current.request_code}), follow=True
        )
    assert resp.context["ai_suggestion"] is None
    assert "Жиших зүйл алга." in resp.content.decode()


@pytest.mark.django_db
def test_ai_price_is_staff_only(client, with_history):
    """Нэвтрээгүй хүн AI-аас үнэ асууж чадахгүй — нэвтрэх хуудас руу явна."""
    url = reverse("dashboard:ai_price", kwargs={"code": with_history.request_code})
    with patch("apps.quotes.ai_pricing.suggest_price") as ask:
        resp = client.post(url)
    assert resp.status_code == 302
    assert resp.headers["Location"].startswith(reverse("accounts:login"))
    ask.assert_not_called()


# --- IMEI — хуулж авах талбар --------------------------------------------------


@pytest.mark.django_db
def test_detail_shows_imei_with_a_copy_button(staff_client):
    intake = IntakeRequest.objects.create(contact_name="A", contact_phone="9911")
    _phone(intake, imei_or_serial="356938035643809")

    body = staff_client.get(
        reverse("dashboard:request_detail", kwargs={"code": intake.request_code})
    ).content.decode()

    assert "IMEI / Сериал" in body
    assert "356938035643809" in body
    assert 'aria-label="IMEI / Сериал хуулах"' in body
    assert "window.copyText" in body


@pytest.mark.django_db
def test_imei_field_is_shown_even_when_empty(staff_client):
    """Талбар нь үргэлж харагдана — дугаар байхгүйг оператор шууд мэднэ."""
    intake = IntakeRequest.objects.create(contact_name="A", contact_phone="9911")
    _phone(intake, imei_or_serial="")

    body = staff_client.get(
        reverse("dashboard:request_detail", kwargs={"code": intake.request_code})
    ).content.decode()

    assert "IMEI / Сериал" in body
    # Хуулах утга байхгүй тул товч ч гарахгүй.
    assert "хуулах" not in body


# --- Зургийн lightbox ----------------------------------------------------------


def _image_file(name="test.jpg"):
    """1x1 пиксел JPEG — жинхэнэ ImageField валидацийг давна."""
    from io import BytesIO

    from django.core.files.uploadedfile import SimpleUploadedFile
    from PIL import Image

    buf = BytesIO()
    Image.new("RGB", (1, 1), "white").save(buf, format="JPEG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/jpeg")


@pytest.mark.django_db
def test_detail_collects_every_image_for_the_lightbox(staff_client):
    """Бүх төхөөрөмжийн зураг нэг жагсаалтад — тэндээсээ өмнөх/дараах руу гүйлгэнэ."""
    from apps.intake.models import DeviceImage

    intake = IntakeRequest.objects.create(contact_name="A", contact_phone="9911")
    first = _phone(intake, model="iPhone 13")
    second = _phone(intake, model="Galaxy S21")
    images = [
        DeviceImage.objects.create(device_item=first, image=_image_file("a.jpg")),
        DeviceImage.objects.create(device_item=first, image=_image_file("b.jpg")),
        DeviceImage.objects.create(device_item=second, image=_image_file("c.jpg")),
    ]

    resp = staff_client.get(
        reverse("dashboard:request_detail", kwargs={"code": intake.request_code})
    )
    assert resp.context["gallery_images"] == [img.image.url for img in images]

    body = resp.content.decode()
    assert 'id="gallery-images"' in body
    assert body.count("Зургийг томруулж харах") == 3
    # Шинэ цонх биш — lightbox нээгдэнэ.
    assert "function lightbox(" in body
    assert 'aria-label="Дараагийн зураг"' in body


@pytest.mark.django_db
def test_detail_without_images_has_an_empty_gallery(staff_client):
    intake = IntakeRequest.objects.create(contact_name="A", contact_phone="9911")
    _phone(intake)

    resp = staff_client.get(
        reverse("dashboard:request_detail", kwargs={"code": intake.request_code})
    )
    assert resp.context["gallery_images"] == []
    assert "Зургийг томруулж харах" not in resp.content.decode()


# --- Очиж авалтын жагсаалт -----------------------------------------------------


def _pickup_request(*, scheduled=False, paid=False, days_ago=0, status=None, address="Хороолол 12"):
    """Очиж авахыг хүссэн хүсэлт (шаардвал товлогдсон, төлөгдсөнөөр нь)."""
    from datetime import timedelta

    from django.utils import timezone

    from apps.quotes.models import Pickup

    intake = IntakeRequest.objects.create(
        contact_name="A",
        contact_phone="9911",
        pickup_required=True,
        address_line=address,
        status=status or IntakeRequest.Status.NEW,
    )
    # created_at нь auto_now_add тул шууд update-аар л ухраана.
    IntakeRequest.objects.filter(pk=intake.pk).update(
        created_at=timezone.now() - timedelta(days=days_ago)
    )
    if scheduled:
        Pickup.objects.create(
            intake_request=intake,
            pickup_date=timezone.now(),
            pickup_address=address,
            payment_status=Pickup.PaymentStatus.PAID if paid else Pickup.PaymentStatus.PENDING,
        )
    intake.refresh_from_db()
    return intake


@pytest.mark.django_db
def test_pickup_list_shows_requests_that_asked_for_pickup(staff_client):
    """Товлоогүй ч гэсэн, очиж авахыг хүссэн бүх хүсэлт жагсаалтад орно."""
    wants = _pickup_request()
    scheduled = _pickup_request(scheduled=True, days_ago=1)
    IntakeRequest.objects.create(contact_name="B", contact_phone="9911")  # хүргэлт хүсээгүй

    resp = staff_client.get(reverse("dashboard:pickup_list"))
    assert resp.status_code == 200
    assert {r.pk for r in resp.context["rows"]} == {wants.pk, scheduled.pk}
    assert resp.context["total"] == 2

    body = resp.content.decode()
    assert wants.request_code in body
    # Товлоогүй мөрөнд шууд товлох холбоос гарна.
    assert reverse("dashboard:schedule_pickup", kwargs={"code": wants.request_code}) in body
    assert "1 товлохыг хүлээж байна" in body


@pytest.mark.django_db
def test_pickup_list_orders_unscheduled_then_unpaid_then_the_rest(staff_client):
    paid = _pickup_request(scheduled=True, paid=True, days_ago=1)
    unpaid = _pickup_request(scheduled=True, days_ago=2)
    old_wants = _pickup_request(days_ago=10)
    new_wants = _pickup_request(days_ago=3)
    # Хаагдсан хүсэлт товлоогүй ч дээрээ гарахгүй.
    closed = _pickup_request(days_ago=0, status=IntakeRequest.Status.CANCELLED)

    rows = staff_client.get(reverse("dashboard:pickup_list")).context["rows"]
    assert [r.pk for r in rows] == [new_wants.pk, old_wants.pk, unpaid.pk, closed.pk, paid.pk]


@pytest.mark.django_db
def test_pickup_list_shows_25_per_page(staff_client):
    for i in range(30):
        _pickup_request(days_ago=i)

    resp = staff_client.get(reverse("dashboard:pickup_list"))
    assert len(resp.context["rows"]) == 25
    assert resp.context["total"] == 30
    assert resp.context["page_obj"].paginator.num_pages == 2

    second = staff_client.get(reverse("dashboard:pickup_list"), {"page": 2})
    assert len(second.context["rows"]) == 5


@pytest.mark.django_db
def test_pickup_list_page_out_of_range_falls_back(staff_client):
    _pickup_request()

    resp = staff_client.get(reverse("dashboard:pickup_list"), {"page": 9})
    assert resp.status_code == 200
    assert len(resp.context["rows"]) == 1


@pytest.mark.django_db
def test_empty_pickup_list_still_renders(staff_client):
    resp = staff_client.get(reverse("dashboard:pickup_list"))
    assert resp.status_code == 200
    assert resp.context["total"] == 0
    assert "Очиж авах хүсэлт байхгүй" in resp.content.decode()


@pytest.mark.django_db
def test_scheduled_pickups_stay_listed_even_without_the_flag(staff_client):
    """Ажилтан гараар товлосон бол хэрэглэгч чагт тавиагүй ч жагсаалтад үлдэнэ."""
    from django.utils import timezone

    from apps.quotes.models import Pickup

    intake = IntakeRequest.objects.create(
        contact_name="A", contact_phone="9911", pickup_required=False
    )
    Pickup.objects.create(
        intake_request=intake, pickup_date=timezone.now(), pickup_address="Хороолол 1"
    )

    rows = staff_client.get(reverse("dashboard:pickup_list")).context["rows"]
    assert [r.pk for r in rows] == [intake.pk]


# --- Тойм — хугацааны шүүлтүүр --------------------------------------------------


def _request_on(day, **kwargs):
    """Тодорхой өдрөөр үүссэн хүсэлт (created_at нь auto_now_add тул update-аар)."""
    from datetime import datetime, time

    from django.utils import timezone

    intake = IntakeRequest.objects.create(contact_name="A", contact_phone="9911", **kwargs)
    stamp = timezone.make_aware(datetime.combine(day, time(12, 0)))
    IntakeRequest.objects.filter(pk=intake.pk).update(created_at=stamp)
    intake.refresh_from_db()
    return intake


@pytest.mark.django_db
def test_overview_defaults_to_this_year(staff_client):
    from django.utils import timezone

    today = timezone.localdate()
    this_year = _request_on(today)
    _request_on(today.replace(year=today.year - 1, month=6, day=15))

    resp = staff_client.get(reverse("dashboard:overview"))
    assert resp.status_code == 200
    assert resp.context["period"] == "this_year"
    assert resp.context["date_from"] == today.replace(month=1, day=1).isoformat()
    assert resp.context["date_to"] == today.replace(month=12, day=31).isoformat()
    # Тоо, жагсаалт хоёулаа шүүлтүүрийг дагана; "Нийт" нь бүх хугацааных.
    assert resp.context["period_count"] == 1
    assert [r.pk for r in resp.context["recent"]] == [this_year.pk]
    assert resp.context["total"] == 2


@pytest.mark.django_db
def test_overview_period_choices_cover_the_asked_presets(staff_client):
    values = [value for value, _label in staff_client.get(
        reverse("dashboard:overview")
    ).context["period_choices"]]
    assert values == ["this_month", "last_month", "last_quarter", "this_year", "custom"]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "period,expected",
    [
        ("this_month", (date(2026, 8, 1), date(2026, 8, 31))),
        ("last_month", (date(2026, 7, 1), date(2026, 7, 31))),
        ("last_quarter", (date(2026, 4, 1), date(2026, 6, 30))),
        ("this_year", (date(2026, 1, 1), date(2026, 12, 31))),
    ],
)
def test_period_ranges(period, expected):
    from apps.reports.views import _period_range

    assert _period_range(period, date(2026, 8, 23)) == expected


def test_last_quarter_wraps_into_the_previous_year():
    from apps.reports.views import _period_range

    assert _period_range("last_quarter", date(2026, 2, 10)) == (date(2025, 10, 1), date(2025, 12, 31))


@pytest.mark.django_db
def test_overview_custom_range_uses_the_given_dates(staff_client):
    inside = _request_on(date(2026, 6, 10))
    _request_on(date(2026, 7, 10))

    resp = staff_client.get(
        reverse("dashboard:overview"),
        {"period": "custom", "date_from": "2026-06-01", "date_to": "2026-06-30"},
    )
    assert resp.context["period"] == "custom"
    assert resp.context["date_from"] == "2026-06-01"
    assert resp.context["date_to"] == "2026-06-30"
    assert [r.pk for r in resp.context["recent"]] == [inside.pk]

    body = resp.content.decode()
    # "Бусад" сонгосон үед огнооны талбарууд маягтад байна.
    assert 'name="date_from"' in body and 'name="date_to"' in body


@pytest.mark.django_db
def test_overview_custom_range_swaps_reversed_dates(staff_client):
    resp = staff_client.get(
        reverse("dashboard:overview"),
        {"period": "custom", "date_from": "2026-06-30", "date_to": "2026-06-01"},
    )
    assert (resp.context["date_from"], resp.context["date_to"]) == ("2026-06-01", "2026-06-30")


@pytest.mark.django_db
def test_overview_falls_back_to_the_default_on_a_bad_period(staff_client):
    resp = staff_client.get(reverse("dashboard:overview"), {"period": "хулгай"})
    assert resp.status_code == 200
    assert resp.context["period"] == "this_year"


@pytest.mark.django_db
def test_overview_charts_follow_the_filter(staff_client):
    """График, төлөвийн задаргаа ч сонгосон хугацааг дагана."""
    from django.utils import timezone

    today = timezone.localdate()
    _request_on(today, status=IntakeRequest.Status.PURCHASED)
    _request_on(today.replace(year=today.year - 1, month=6, day=15))

    by_status = staff_client.get(reverse("dashboard:overview")).context["by_status"]
    assert [(row["status"], row["c"]) for row in by_status] == [("PURCHASED", 1)]


# ---------- Хүсэлт устгах ----------


@pytest.mark.django_db
def test_request_list_shows_delete_and_detail_actions(staff_client):
    req = IntakeRequest.objects.create(contact_name="Дорж", contact_phone="9911")
    body = staff_client.get(reverse("dashboard:request_list")).content.decode()
    assert reverse("dashboard:request_delete", args=[req.request_code]) in body
    assert reverse("dashboard:request_detail", args=[req.request_code]) in body


@pytest.mark.django_db
def test_request_delete_removes_the_request(staff_client):
    req = IntakeRequest.objects.create(contact_name="Дорж", contact_phone="9911")
    url = reverse("dashboard:request_delete", args=[req.request_code])
    resp = staff_client.post(url, {"next": "/dashboard/requests/?per_page=10"})
    assert resp.status_code == 302
    assert resp.url == "/dashboard/requests/?per_page=10"
    assert not IntakeRequest.objects.filter(pk=req.pk).exists()


@pytest.mark.django_db
def test_request_delete_ignores_an_offsite_next(staff_client):
    """Open redirect-ээс сэргийлж, гадны хаяг руу буцаахгүй."""
    req = IntakeRequest.objects.create(contact_name="Дорж", contact_phone="9911")
    resp = staff_client.post(
        reverse("dashboard:request_delete", args=[req.request_code]),
        {"next": "https://evil.example/"},
    )
    assert resp.url == reverse("dashboard:request_list")


@pytest.mark.django_db
def test_request_delete_needs_post(staff_client):
    """GET-ээр устгахгүй — линк дарахад санамсаргүй устахаас хамгаална."""
    req = IntakeRequest.objects.create(contact_name="Дорж", contact_phone="9911")
    resp = staff_client.get(reverse("dashboard:request_delete", args=[req.request_code]))
    assert resp.status_code == 302
    assert IntakeRequest.objects.filter(pk=req.pk).exists()


@pytest.mark.django_db
@pytest.mark.parametrize("status", [IntakeRequest.Status.PURCHASED, IntakeRequest.Status.CANCELLED])
def test_request_delete_keeps_a_processed_request(staff_client, status):
    """Худалдан авсан / цуцалсан хүсэлт бүртгэл болж үлдэнэ."""
    req = IntakeRequest.objects.create(contact_name="Дорж", contact_phone="9911", status=status)
    resp = staff_client.post(reverse("dashboard:request_delete", args=[req.request_code]))
    assert resp.status_code == 302
    assert IntakeRequest.objects.filter(pk=req.pk).exists()


@pytest.mark.django_db
def test_request_list_disables_delete_for_a_processed_request(staff_client):
    """Устгах товч гарахгүй — оператор дэмий дараад алдаа авахгүй."""
    req = IntakeRequest.objects.create(
        contact_name="Дорж", contact_phone="9911", status=IntakeRequest.Status.PURCHASED
    )
    body = staff_client.get(reverse("dashboard:request_list")).content.decode()
    assert reverse("dashboard:request_delete", args=[req.request_code]) not in body
    assert "Боловсруулагдсан хүсэлтийг устгах боломжгүй" in body


@pytest.mark.django_db
def test_request_delete_rejects_a_customer(client, django_user_model):
    customer = django_user_model.objects.create_user(
        email="hereglegch@ubpm.mn", password="x", role=django_user_model.Role.CUSTOMER
    )
    client.force_login(customer)
    req = IntakeRequest.objects.create(contact_name="Дорж", contact_phone="9911")
    client.post(reverse("dashboard:request_delete", args=[req.request_code]))
    assert IntakeRequest.objects.filter(pk=req.pk).exists()


# ---------- Тойм хуудсыг сэргээх ----------


@pytest.mark.django_db
def test_overview_offers_a_refresh_button(staff_client):
    """Дэлгэцээ дээш чирэлгүйгээр датаа дахин татах товч."""
    resp = staff_client.get(reverse("dashboard:overview"))
    body = resp.content.decode()
    assert "Сэргээх" in body
    assert "window.location.reload()" in body


@pytest.mark.django_db
def test_overview_shows_when_the_data_was_fetched(staff_client):
    """Товчны хажуугийн цаг нь хуудас зурагдсан мөчийг заана."""
    from django.utils import timezone

    before = timezone.localtime()
    resp = staff_client.get(reverse("dashboard:overview"))
    generated = resp.context["generated_at"]
    assert before <= generated <= timezone.localtime()
    assert generated.strftime("%H:%M:%S") in resp.content.decode()
