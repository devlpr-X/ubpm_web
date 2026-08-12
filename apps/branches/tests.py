import pytest
from django.urls import reverse

from apps.branches.models import Branch, PartnerLocation


@pytest.mark.django_db
def test_branch_list_hides_partner_locations(client):
    """Хамтрагч цэгүүд нийтийн салбарын хуудсанд харагдахгүй."""
    Branch.objects.create(
        name="Төв салбар", code="HQ", city="Улаанбаатар", address_line="1-р байр"
    )
    PartnerLocation.objects.create(
        name="Хамтрагч цэг А", address="Их дэлгүүрийн ард", phone="99110011"
    )

    resp = client.get(reverse("branches:list"))
    content = resp.content.decode()

    assert resp.status_code == 200
    assert "Төв салбар" in content
    assert "Хамтрагч цэг А" not in content
    assert "Хамтрагч цэгүүд" not in content
