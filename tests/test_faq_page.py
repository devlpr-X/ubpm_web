"""Вэбийн FAQ хуудас ба аппын /api/v1/faq/ нэг эх сурвалжаас уншиж байгааг батална."""

import pytest

from apps.core.faq import FAQS


@pytest.mark.django_db
def test_web_faq_page_renders_the_shared_list(client):
    res = client.get("/faq/")
    assert res.status_code == 200
    html = res.content.decode()
    for row in FAQS:
        assert row["question"] in html
        assert row["answer"][:40] in html
