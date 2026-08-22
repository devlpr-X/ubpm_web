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


def _phone(intake, brand="Apple", model="iPhone 13", **kwargs):
    from apps.intake.models import DeviceCategory, DeviceItem

    category, _ = DeviceCategory.objects.get_or_create(slug="phone", defaults={"name": "Гар утас"})
    return DeviceItem.objects.create(
        intake_request=intake, category=category, brand=brand, model=model, **kwargs
    )


def _quoted(brand, model, *, low, high, final=None, status=IntakeRequest.Status.PRICE_SENT):
    from apps.quotes.models import Quotation

    intake = IntakeRequest.objects.create(contact_name="B", contact_phone="9911", status=status)
    _phone(intake, brand=brand, model=model)
    Quotation.objects.create(
        intake_request=intake,
        quoted_price_min=low,
        quoted_price_max=high,
        final_offer_price=final,
    )
    return intake


@pytest.mark.django_db
def test_detail_lists_previous_prices_for_the_same_model(staff_client):
    current = IntakeRequest.objects.create(contact_name="A", contact_phone="9911")
    _phone(current, brand="Apple", model="iPhone 13")

    old = _quoted("Apple", "iPhone 13", low=300000, high=450000, final=400000)
    _quoted("Samsung", "Galaxy S21", low=100000, high=200000)  # өөр загвар — орохгүй

    resp = staff_client.get(
        reverse("dashboard:request_detail", kwargs={"code": current.request_code})
    )
    rows = resp.context["similar_quotes"]
    assert [r["request"].pk for r in rows] == [old.pk]

    body = resp.content.decode()
    assert "Ижил загварын өмнөх үнэ" in body
    assert "400000₮" in body
    # Мөр бүр тухайн хүсэлтийн дэлгэрэнгүй рүү холбогдоно.
    assert old.get_absolute_url() in body


@pytest.mark.django_db
def test_previous_prices_ignore_case_and_the_request_itself(staff_client):
    current = IntakeRequest.objects.create(contact_name="A", contact_phone="9911")
    _phone(current, brand="apple", model="iphone 13")

    old = _quoted("Apple", "iPhone 13", low=1, high=2)

    resp = staff_client.get(
        reverse("dashboard:request_detail", kwargs={"code": current.request_code})
    )
    assert [r["request"].pk for r in resp.context["similar_quotes"]] == [old.pk]


@pytest.mark.django_db
def test_previous_prices_capped_at_ten_newest_first(staff_client):
    current = IntakeRequest.objects.create(contact_name="A", contact_phone="9911")
    _phone(current)
    for _ in range(12):
        _quoted("Apple", "iPhone 13", low=1, high=2)

    resp = staff_client.get(
        reverse("dashboard:request_detail", kwargs={"code": current.request_code})
    )
    rows = resp.context["similar_quotes"]
    assert len(rows) == 10
    dates = [r["request"].created_at for r in rows]
    assert dates == sorted(dates, reverse=True)


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
