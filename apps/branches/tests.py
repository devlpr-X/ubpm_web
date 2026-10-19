import pytest
from django.urls import reverse

from apps.branches.models import Branch, PartnerLocation


@pytest.mark.django_db
def test_branch_list_hides_partner_locations(client):
    """Хамтрагч цэгүүд нийтийн салбарын хуудсанд харагдахгүй."""
    Branch.objects.create(name="Төв салбар", code="HQ", city="Улаанбаатар", address_line="1-р байр")
    PartnerLocation.objects.create(
        name="Хамтрагч цэг А", address="Их дэлгүүрийн ард", phone="99110011"
    )

    resp = client.get(reverse("branches:list"))
    content = resp.content.decode()

    assert resp.status_code == 200
    assert "Төв салбар" in content
    assert "Хамтрагч цэг А" not in content
    assert "Хамтрагч цэгүүд" not in content


@pytest.mark.django_db
def test_branch_images_open_in_blurred_lightbox(client, settings, tmp_path):
    from django.core.files.uploadedfile import SimpleUploadedFile

    from apps.branches.models import BranchMedia

    settings.MEDIA_ROOT = tmp_path
    branch = Branch.objects.create(
        name="Хороолол",
        code="B5",
        address_line="X",
        cover_image=SimpleUploadedFile("cover.png", b"x", content_type="image/png"),
    )
    media = BranchMedia.objects.create(
        branch=branch,
        media_type="IMAGE",
        file=SimpleUploadedFile("g.png", b"x", content_type="image/png"),
    )

    body = client.get(reverse("branches:detail", args=[branch.code])).content.decode()
    assert f'data-full="{branch.cover_image.url}"' in body
    assert f'data-full="{media.file.url}"' in body
    assert "backdrop-blur-lg" in body
    assert "function lightbox(" in body

    # Нүүр болон салбарын жагсаалт дээрх зураг ч мөн адил томорно.
    for url in [reverse("core:home"), reverse("branches:list")]:
        body = client.get(url).content.decode()
        assert f'data-full="{branch.cover_image.url}"' in body, url
        assert "backdrop-blur-lg" in body and "function lightbox(" in body, url
