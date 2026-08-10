import json
import re

import pytest
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


@pytest.mark.django_db
def test_private_pages_are_noindex(client):
    for url in (reverse("intake:track"), reverse("accounts:login")):
        html = client.get(url).content.decode()
        assert '<meta name="robots" content="noindex, nofollow">' in html, url
