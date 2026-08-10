"""Sitemaps for the public site — everything Google is allowed to index.

Token-scoped pages (track/submitted), the dashboard and accounts are left out
on purpose; they are also blocked in robots.txt and carry a noindex tag.
"""

from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from apps.branches.models import Branch


class StaticViewSitemap(Sitemap):
    """The fixed marketing/utility pages."""

    protocol = "https"
    changefreq = "weekly"

    # url name -> priority
    PAGES = {
        "core:home": 1.0,
        "intake:request_new": 0.9,
        "branches:list": 0.8,
        "core:about": 0.7,
        "core:contact": 0.7,
        "core:faq": 0.6,
        "core:privacy": 0.3,
    }

    def items(self):
        return list(self.PAGES)

    def location(self, item):
        return reverse(item)

    def priority(self, item):
        return self.PAGES[item]


class BranchSitemap(Sitemap):
    """One entry per active branch — these are the local-search landing pages."""

    protocol = "https"
    changefreq = "monthly"
    priority = 0.6

    def items(self):
        return Branch.objects.filter(is_active=True)

    def lastmod(self, obj):
        return obj.created_at


sitemaps = {
    "static": StaticViewSitemap(),
    "branches": BranchSitemap(),
}
