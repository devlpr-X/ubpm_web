import pytest
from django.urls import reverse

from apps.accounts.models import User


@pytest.mark.django_db
def test_create_user_with_email():
    u = User.objects.create_user(email="a@b.com", password="x")
    assert u.email == "a@b.com"
    assert u.role == User.Role.CUSTOMER
    assert not u.is_staff


@pytest.mark.django_db
def test_create_superuser():
    u = User.objects.create_superuser(email="root@x.com", password="x")
    assert u.is_superuser and u.is_staff
    assert u.role == User.Role.ADMIN


@pytest.mark.django_db
def test_is_staff_role():
    op = User.objects.create_user(email="op@x.com", password="x", role=User.Role.OPERATOR)
    cust = User.objects.create_user(email="c@x.com", password="x")
    assert op.is_staff_role
    assert not cust.is_staff_role


@pytest.mark.django_db
def test_login_redirects_staff_to_dashboard(client):
    User.objects.create_user(
        email="op@x.com", password="pw1234", role=User.Role.OPERATOR, is_staff=True
    )
    resp = client.post(
        reverse("accounts:login"),
        {"username": "op@x.com", "password": "pw1234"},
        follow=False,
    )
    assert resp.status_code == 302
    assert "dashboard" in resp.url


# ---------------------------------------------------------------------------
# Холбоо барих мэдээлэл — профайл ↔ хүсэлт
# ---------------------------------------------------------------------------
def test_customer_type_choices_match_intake():
    """Профайл ба хүсэлтийн хоорондох утгууд яг таарч байх ёстой (шууд хуулагддаг)."""
    from apps.intake.models import IntakeRequest

    assert User.CustomerType.choices == IntakeRequest.CustomerType.choices


@pytest.mark.django_db
def test_contact_initial_prefills_from_profile():
    from apps.accounts.contact import contact_initial

    user = User.objects.create_user(
        email="c@x.com",
        password="1234",
        full_name="Бат",
        phone="99110011",
        city="Дархан",
        district="1-р баг",
    )
    initial = contact_initial(user)
    assert initial["contact_name"] == "Бат"
    assert initial["contact_phone"] == "99110011"
    assert initial["contact_email"] == "c@x.com"
    assert initial["city"] == "Дархан"
    assert initial["district"] == "1-р баг"


@pytest.mark.django_db
def test_contact_initial_is_empty_for_guests():
    from django.contrib.auth.models import AnonymousUser

    from apps.accounts.contact import contact_initial

    assert contact_initial(AnonymousUser()) == {}
    assert contact_initial(None) == {}


@pytest.mark.django_db
def test_save_contact_to_profile_fills_then_updates():
    from apps.accounts.contact import save_contact_to_profile
    from apps.intake.models import IntakeRequest

    user = User.objects.create_user(email="c@x.com", password="1234")
    first = IntakeRequest.objects.create(
        contact_name="Бат", contact_phone="99110011", city="Улаанбаатар", district="ХУД"
    )
    save_contact_to_profile(user, first)
    user.refresh_from_db()
    assert (user.full_name, user.phone, user.district) == ("Бат", "99110011", "ХУД")

    # Дараагийн хүсэлт дээр өөрчилсөн утга профайлд шинэчлэгдэнэ.
    second = IntakeRequest.objects.create(
        contact_name="Бат", contact_phone="88220022", city="Улаанбаатар", district=""
    )
    save_contact_to_profile(user, second)
    user.refresh_from_db()
    assert user.phone == "88220022"
    # Хоосон утга хуучин мэдээллийг дардаггүй.
    assert user.district == "ХУД"


@pytest.mark.django_db
def test_save_contact_to_profile_never_touches_login_email():
    from apps.accounts.contact import save_contact_to_profile
    from apps.intake.models import IntakeRequest

    user = User.objects.create_user(email="login@x.com", password="1234")
    intake = IntakeRequest.objects.create(
        contact_name="Бат", contact_phone="99110011", contact_email="other@x.com"
    )
    save_contact_to_profile(user, intake)
    user.refresh_from_db()
    assert user.email == "login@x.com"


@pytest.mark.django_db
def test_profile_form_requires_company_name_for_companies(client):
    User.objects.create_user(email="c@x.com", password="1234")
    client.login(username="c@x.com", password="1234")
    url = reverse("accounts:profile")

    resp = client.post(url, {"full_name": "Бат", "customer_type": "COMPANY"})
    assert resp.status_code == 200
    assert resp.context["form"].errors["company_name"]

    resp = client.post(
        url, {"full_name": "Бат", "customer_type": "COMPANY", "company_name": "ХХК"}
    )
    assert resp.status_code == 302
    assert User.objects.get(email="c@x.com").company_name == "ХХК"


@pytest.mark.django_db
def test_staff_profile_is_never_overwritten_by_a_request():
    """Оператор үйлчлүүлэгчийн өмнөөс хүсэлт үүсгэвэл өөрийнх нь профайл хэвээр."""
    from apps.accounts.contact import contact_initial, save_contact_to_profile
    from apps.intake.models import IntakeRequest

    op = User.objects.create_user(
        email="op@x.com", password="1234", full_name="Оператор", role=User.Role.OPERATOR
    )
    intake = IntakeRequest.objects.create(contact_name="Үйлчлүүлэгч", contact_phone="99110011")

    assert save_contact_to_profile(op, intake) == []
    assert contact_initial(op) == {}
    op.refresh_from_db()
    assert op.full_name == "Оператор"
    assert op.phone == ""
