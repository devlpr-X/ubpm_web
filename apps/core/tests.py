import json
import re

import pytest
from django.test import override_settings
from django.urls import reverse

from apps.branches.models import Branch


@pytest.mark.django_db
def test_robots_txt(client):
    resp = client.get("/robots.txt")
    assert resp.status_code == 200
    assert resp["Content-Type"].startswith("text/plain")
    body = resp.content.decode()
    # Хувийн хэсгүүд хаалттай.
    for blocked in ("/admin/", "/dashboard/", "/accounts/", "/api/", "/request/track/"):
        assert f"Disallow: {blocked}" in body
    assert "Sitemap: http://testserver/sitemap.xml" in body


@pytest.mark.django_db
def test_sitemap_lists_public_pages_and_branches(client):
    branch = Branch.objects.create(name="Төв салбар", address_line="СБД, 1-р хороо")

    resp = client.get("/sitemap.xml")
    assert resp.status_code == 200
    locs = re.findall(r"<loc>(.*?)</loc>", resp.content.decode())
    paths = {loc.split("testserver", 1)[1] for loc in locs}

    assert reverse("core:home") in paths
    assert reverse("core:about") in paths
    assert reverse("branches:list") in paths
    assert reverse("intake:request_new") in paths
    assert branch.get_absolute_url() in paths
    # Токентой хуудсууд sitemap-д орохгүй.
    assert not any("/track/" in p or "/submitted/" in p for p in paths)


@pytest.mark.django_db
def test_inactive_branch_not_in_sitemap(client):
    Branch.objects.create(name="Хаагдсан", address_line="X", is_active=False)
    locs = re.findall(r"<loc>(.*?)</loc>", client.get("/sitemap.xml").content.decode())
    assert not any("haagdsan" in loc for loc in locs)


@pytest.mark.django_db
def test_public_page_seo_tags(client):
    html = client.get(reverse("core:home")).content.decode()

    assert '<meta name="robots" content="index, follow">' in html
    assert '<link rel="canonical" href="http://testserver/">' in html
    desc = re.search(r'<meta name="description" content="(.*?)">', html, re.S)
    assert desc and "гар утас" in desc.group(1)

    # Бүтэцлэгдсэн өгөгдөл нь хүчинтэй JSON байх ёстой.
    ld = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
    data = json.loads(ld.group(1))
    assert data["@type"] == "LocalBusiness"
    assert data["name"] == "UBPM"
    # Хайлтад хэрэг болох үйлчилгээний тодорхойлолт — зөвхөн бүтэцлэгдсэн өгөгдөл дотор.
    assert data["knowsAbout"] and data["makesOffer"]
    offers = {o["itemOffered"]["name"] for o in data["makesOffer"]}
    assert "Онлайн үнэлгээ" in offers


@pytest.mark.django_db
def test_keywords_are_page_specific_and_invisible(client):
    """Түлхүүр үгс meta дотор л байна — хуудасны биед харагдахгүй."""
    html = client.get(reverse("core:home")).content.decode()

    kw = re.search(r'<meta name="keywords" content="(.*?)">', html, re.S)
    assert kw and "дэлгэц хагарсан утас зарах" in kw.group(1)

    # Хуудас бүр өөрийн үгстэй — FAQ нь нүүрийнхээс өөр байх ёстой.
    faq_kw = re.search(
        r'<meta name="keywords" content="(.*?)">',
        client.get(reverse("core:faq")).content.decode(),
        re.S,
    )
    assert faq_kw and faq_kw.group(1) != kw.group(1)

    # <body> дотор түлхүүр үг цацагдаагүй байх (харагдах текстэд орохгүй).
    body = html.split("<body", 1)[1]
    assert "дэлгэц хагарсан утас зарах" not in body


@pytest.mark.django_db
def test_private_pages_are_noindex(client):
    for url in (reverse("intake:track"), reverse("accounts:login")):
        html = client.get(url).content.decode()
        assert '<meta name="robots" content="noindex, nofollow">' in html, url


@pytest.mark.django_db
@override_settings(
    CANONICAL_HOST="ubpm.mn", ALLOWED_HOSTS=["ubpm.mn", "www.ubpm.mn", "ubpm.up.railway.app"]
)
def test_non_canonical_hosts_redirect_to_ubpm_mn(client):
    """Railway болон www домайн нь ubpm.mn руу 301-ээр цугларна."""
    for host in ("ubpm.up.railway.app", "www.ubpm.mn"):
        resp = client.get("/faq/", HTTP_HOST=host)
        assert resp.status_code == 301, host
        assert resp["Location"] == "https://ubpm.mn/faq/", host


@pytest.mark.django_db
@override_settings(CANONICAL_HOST="ubpm.mn", ALLOWED_HOSTS=["ubpm.mn", "ubpm.up.railway.app"])
def test_canonical_redirect_keeps_query_string(client):
    resp = client.get("/branches/", {"q": "сансар"}, HTTP_HOST="ubpm.up.railway.app")
    assert resp.status_code == 301
    assert resp["Location"] == "https://ubpm.mn/branches/?q=%D1%81%D0%B0%D0%BD%D1%81%D0%B0%D1%80"


@pytest.mark.django_db
@override_settings(CANONICAL_HOST="ubpm.mn", ALLOWED_HOSTS=["ubpm.mn"])
def test_canonical_host_is_served_normally(client):
    assert client.get("/faq/", HTTP_HOST="ubpm.mn").status_code == 200


@pytest.mark.django_db
@override_settings(CANONICAL_HOST="ubpm.mn", ALLOWED_HOSTS=["ubpm.mn"])
def test_unknown_host_redirects_instead_of_400(client):
    """ALLOWED_HOSTS-д байхгүй домайн 400 биш 301 авна."""
    resp = client.get("/faq/", HTTP_HOST="ubpm.up.railway.app")
    assert resp.status_code == 301
    assert resp["Location"] == "https://ubpm.mn/faq/"


@pytest.mark.django_db
@override_settings(CANONICAL_HOST="ubpm.mn", ALLOWED_HOSTS=["ubpm.mn", "ubpm.up.railway.app"])
def test_api_is_exempt_from_canonical_redirect(client):
    """Мобайл аппын нөөц хаяг — /api/ шилжихгүй (301 нь POST-ыг эвддэг)."""
    resp = client.get("/api/v1/health/", HTTP_HOST="ubpm.up.railway.app")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}

    # Гэхдээ нийтийн хуудсууд шилжсэн хэвээр.
    assert client.get("/faq/", HTTP_HOST="ubpm.up.railway.app").status_code == 301


@pytest.mark.django_db
def test_no_redirect_when_canonical_host_unset(client):
    """CANONICAL_HOST хоосон үед (dev, эсвэл fallback горим) шилжүүлэг унтарна."""
    assert client.get("/faq/", HTTP_HOST="ubpm.up.railway.app").status_code == 200


@pytest.mark.django_db
def test_public_pages_render_after_icon_swap(client):
    """Icon солилтын дараа нийтийн хуудсууд алдаагүй render хийгдэнэ."""
    from django.urls import reverse

    from apps.branches.models import Branch

    branch = Branch.objects.create(
        name="Төв салбар", code="HQ", city="Улаанбаатар", address_line="1-р байр"
    )
    for url in [
        reverse("core:home"),
        reverse("core:about"),
        reverse("core:contact"),
        reverse("core:faq"),
        reverse("branches:list"),
        reverse("branches:detail", args=[branch.code]),
        reverse("intake:request_new"),
        reverse("intake:request_new") + "?type=broken",
    ]:
        assert client.get(url).status_code == 200, url


# --- Холбоо барих хуудсын засварлах боломж -----------------------------------


@pytest.mark.django_db
def test_contact_seeds_editable_blocks(client):
    """Хуудсыг эхний удаа үзэхэд блокууд анхны утгаараа үүснэ."""
    from apps.core.models import SiteContent

    resp = client.get(reverse("core:contact"))
    assert resp.status_code == 200

    keys = set(SiteContent.objects.values_list("key", flat=True))
    assert {"contact_main", "contact_cta"} <= keys

    body = resp.content.decode()
    assert 'href="tel:77746465"' in body
    assert "10:00 — 17:30" in body
    # Зочинд засварын маягт харагдахгүй.
    assert "<trix-editor" not in body


@pytest.mark.django_db
def test_contact_shows_edit_form_only_to_staff(client):
    from apps.accounts.models import User

    url = reverse("core:contact")

    customer = User.objects.create_user(email="c@x.com", password="x")
    client.force_login(customer)
    assert "<trix-editor" not in client.get(url).content.decode()

    admin = User.objects.create_user(email="a@x.com", password="x", role=User.Role.ADMIN)
    client.force_login(admin)
    body = client.get(url).content.decode()
    # Нэг том блок + доорх CTA блок — /about/-той адилхан "Засах" товчнууд.
    assert body.count("<trix-editor") == 2
    assert reverse("core:content_edit", kwargs={"key": "contact_main"}) in body


@pytest.mark.django_db
def test_admin_can_edit_contact_block(client):
    from apps.accounts.models import User
    from apps.core.models import SiteContent

    admin = User.objects.create_user(email="a@x.com", password="x", role=User.Role.ADMIN)
    client.force_login(admin)
    client.get(reverse("core:contact"))  # блокуудыг үүсгэнэ

    resp = client.post(
        reverse("core:content_edit", kwargs={"key": "contact_main"}),
        {
            "title": "",
            "body": '<div><strong>Утас</strong></div><div><a href="tel:99998888">9999-8888</a></div>',
            "next": reverse("core:contact"),
        },
    )
    assert resp.status_code == 302
    assert resp["Location"] == reverse("core:contact")

    block = SiteContent.objects.get(key="contact_main")
    assert block.updated_by == admin

    body = client.get(reverse("core:contact")).content.decode()
    assert 'href="tel:99998888"' in body
    # base.html-ийн JSON-LD дахь дугаар нь тусдаа (сайт даяарх) өгөгдөл тул
    # зөвхөн хуудсан дээрх холбоос солигдсоныг шалгана.
    assert 'href="tel:77746465"' not in body
    # meta тайлбар ч хамт шинэчлэгдэнэ — блокууд хооронд зай алдагдахгүй.
    assert 'content="UBPM-тэй холбогдох — Утас 9999-8888"' in body


@pytest.mark.django_db
def test_customer_cannot_edit_contact_block(client):
    from apps.accounts.models import User
    from apps.core.models import SiteContent

    client.get(reverse("core:contact"))
    before = SiteContent.objects.get(key="contact_main").body

    customer = User.objects.create_user(email="c@x.com", password="x")
    client.force_login(customer)
    resp = client.post(
        reverse("core:content_edit", kwargs={"key": "contact_main"}),
        {"title": "Хакердсан", "body": "24/7"},
    )
    assert resp.status_code == 302
    assert SiteContent.objects.get(key="contact_main").body == before


def test_plain_text_separates_blocks():
    """<meta> тайлбарт блокууд наалдалгүй, зайтай орно."""
    from apps.core.views import plain_text

    assert plain_text("<div>Утас</div><div>7774-6465</div>") == "Утас 7774-6465"
    assert plain_text("<p>A&amp;B</p>") == "A&B"
