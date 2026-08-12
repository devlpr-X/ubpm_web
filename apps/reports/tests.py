import pytest
from django.urls import reverse

from apps.intake.models import IntakeRequest


@pytest.fixture
def staff_client(client, django_user_model):
    staff = django_user_model.objects.create_user(
        email="op@ubpm.mn", password="x", role=django_user_model.Role.OPERATOR
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
