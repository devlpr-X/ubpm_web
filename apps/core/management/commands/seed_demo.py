"""Seed demo data: branches, partners, categories, sample requests."""

import random
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import User
from apps.branches.models import Branch, PartnerLocation
from apps.intake.models import DeviceCategory, DeviceItem, IntakeRequest
from apps.quotes.models import StatusHistory

CATEGORIES = [
    {"name": "Гар утас", "slug": "phone", "icon": "📱", "sort_order": 1},
    {"name": "Нөүтбүүк", "slug": "laptop", "icon": "💻", "sort_order": 2},
    {"name": "Таблет", "slug": "tablet", "icon": "📲", "sort_order": 3},
    {"name": "Камер", "slug": "camera", "icon": "📷", "sort_order": 4},
    {"name": "Бусад", "slug": "other", "icon": "📦", "sort_order": 5},
]

BRANCHES = [
    {
        "name": "Төв салбар — Сүхбаатар",
        "address_line": "Сүхбаатар дүүрэг, 8-р хороо, UBPM байр",
        "district": "Сүхбаатар",
        "phones": ["7774-6465", "9915-6465"],
        "working_hours": "10:00–17:30 (амралтын өдөр ч)",
        "description": "Манай гол салбар. Бүх төрлийн төхөөрөмж хүлээн авна.",
    },
    {
        "name": "Хан-Уул салбар",
        "address_line": "Хан-Уул дүүрэг, 11-р хороо, Зайсангийн гудамж",
        "district": "Хан-Уул",
        "phones": ["8025-6465"],
        "working_hours": "10:00–17:30",
    },
    {
        "name": "Баянзүрх салбар",
        "address_line": "Баянзүрх дүүрэг, 13-р хороо, Энхтайваны өргөн чөлөө",
        "district": "Баянзүрх",
        "phones": ["7774-6465"],
        "working_hours": "10:00–17:30",
    },
]

PARTNERS = [
    {"name": "TechRepair Center", "partner_company": "TRC ХХК", "address": "Сүхбаатар дүүрэг, 1-р хороо", "phone": "9911-2233"},
    {"name": "MobileFix Хороолол", "partner_company": "MobileFix LLC", "address": "Баянгол дүүрэг, 17-р хороо", "phone": "9944-5566"},
    {"name": "iService Зайсан", "partner_company": "iService", "address": "Хан-Уул дүүрэг, Зайсан", "phone": "9977-8899"},
    {"name": "PhoneMaster", "partner_company": "PM ХХК", "address": "Чингэлтэй, 4-р хороо", "phone": "9000-1111"},
    {"name": "GadgetHub", "partner_company": "GH LLC", "address": "Баянзүрх, Сансар", "phone": "9555-4444"},
]

SAMPLE_REQUESTS = [
    {"name": "Болормаа", "phone": "99112233", "email": "bolormaa@example.mn", "brand": "Apple", "model": "iPhone 12", "issue": "Дэлгэц хагарсан, асахгүй"},
    {"name": "Дорж", "phone": "88445566", "email": "dorj@example.mn", "brand": "Samsung", "model": "Galaxy S21", "issue": "Батарей сул, ус ороогүй"},
    {"name": "Сараа", "phone": "95001122", "email": "saraa@example.mn", "brand": "Xiaomi", "model": "Redmi Note 11", "issue": "Зурагдсан, асна"},
    {"name": "Бат", "phone": "94778899", "email": "", "brand": "Apple", "model": "MacBook Pro 2018", "issue": "Дэлгэц гэрэлтэхгүй"},
    {"name": "Энхтайван", "phone": "99000011", "email": "enkh@example.mn", "brand": "Apple", "model": "iPad Air", "issue": "Бүтэн, хэрэглэхээ больсон"},
]


class Command(BaseCommand):
    help = "Seed demo data into the database"

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Wipe demo data first")

    def handle(self, *args, **opts):
        if opts["reset"]:
            self.stdout.write("Resetting demo data...")
            IntakeRequest.objects.all().delete()
            PartnerLocation.objects.all().delete()
            Branch.objects.all().delete()
            DeviceCategory.objects.all().delete()

        for c in CATEGORIES:
            DeviceCategory.objects.update_or_create(slug=c["slug"], defaults=c)
        self.stdout.write(self.style.SUCCESS(f"OK:{len(CATEGORIES)} categories"))

        branches = []
        for b in BRANCHES:
            obj, _ = Branch.objects.update_or_create(name=b["name"], defaults=b)
            branches.append(obj)
        self.stdout.write(self.style.SUCCESS(f"OK:{len(branches)} branches"))

        for p in PARTNERS:
            PartnerLocation.objects.update_or_create(name=p["name"], defaults=p)
        self.stdout.write(self.style.SUCCESS(f"OK:{len(PARTNERS)} partner locations"))

        operator, created = User.objects.get_or_create(
            email="operator@ubpm.mn",
            defaults={
                "full_name": "Жишээ Оператор",
                "role": User.Role.OPERATOR,
                "is_staff": True,
            },
        )
        if created:
            operator.set_password("operator1234")
            operator.save()
            self.stdout.write(self.style.SUCCESS("OK: operator@ubpm.mn / operator1234"))
        else:
            self.stdout.write("- operator@ubpm.mn already exists")

        statuses = list(IntakeRequest.Status)
        phone_cat = DeviceCategory.objects.get(slug="phone")
        laptop_cat = DeviceCategory.objects.get(slug="laptop")
        for i, s in enumerate(SAMPLE_REQUESTS):
            req = IntakeRequest.objects.create(
                contact_name=s["name"],
                contact_phone=s["phone"],
                contact_email=s["email"],
                preferred_branch=random.choice(branches),
                status=statuses[i % len(statuses)].value,
                created_at=timezone.now() - timedelta(days=i),
            )
            req.created_at = timezone.now() - timedelta(days=i)
            req.save(update_fields=["created_at"])
            DeviceItem.objects.create(
                intake_request=req,
                category=laptop_cat if "MacBook" in s["model"] else phone_cat,
                brand=s["brand"],
                model=s["model"],
                issue_description=s["issue"],
            )
            StatusHistory.objects.create(
                intake_request=req,
                old_status="",
                new_status=req.status,
                comment="Seed data",
            )
        self.stdout.write(self.style.SUCCESS(f"OK:{len(SAMPLE_REQUESTS)} sample requests"))

        self.stdout.write(self.style.SUCCESS("\nDONE: Demo data ready."))
