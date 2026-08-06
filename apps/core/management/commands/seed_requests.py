"""Seed realistic example IntakeRequests (devices, history, quotes, pickups).

Uses the EXISTING active branches and device categories — it never creates or
deletes branches/categories. Idempotent: re-running skips samples already added
(matched by contact phone).
"""

import random
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.branches.models import Branch
from apps.intake.models import DeviceCategory, DeviceItem, IntakeRequest
from apps.quotes.models import Pickup, Quotation, StatusHistory

S = IntakeRequest.Status

# device: (category slug, brand, model, issue, screen, battery, body)
SAMPLES = [
    {
        "name": "Болормаа Бат", "phone": "9911-2233", "email": "bolormaa@example.mn",
        "status": S.NEW, "days": 0, "expected": 350000,
        "devices": [("phone", "Apple", "iPhone 13", "Дэлгэц хагарсан, асна", "CRACKED", "WEAK", "SCRATCHED")],
    },
    {
        "name": "Дорж Ган", "phone": "8844-5566", "email": "dorj@example.mn",
        "status": S.NEW, "days": 1, "expected": 500000,
        "devices": [
            ("phone", "Samsung", "Galaxy S22", "Ус орсон, асахгүй", "DEAD", "DEAD", "OK"),
            ("phone", "Xiaomi", "Redmi Note 12", "Зурагдсан, хэвийн", "OK", "OK", "SCRATCHED"),
        ],
    },
    {
        "name": "Сараа Энх", "phone": "9500-1122", "email": "saraa@example.mn",
        "status": S.PRICE_SENT, "days": 2, "expected": 1200000,
        "devices": [("laptop", "Apple", "MacBook Air M1", "Дэлгэц гэрэлтэхгүй", "DEAD", "OK", "OK")],
    },
    {
        "name": "Батаа Төр", "phone": "9477-8899", "email": "bataa@example.mn",
        "status": S.PRICE_SENT, "days": 3, "expected": 280000,
        "devices": [("tablet", "Apple", "iPad Air 4", "Бүтэн, хэрэглэхээ больсон", "OK", "OK", "OK")],
    },
    {
        "name": "Энхтайван Сүх", "phone": "9900-0011", "email": "enkh@example.mn",
        "status": S.APPROVED, "days": 5, "expected": 750000,
        "devices": [("phone", "Apple", "iPhone 12 Pro", "Арын шил хагарсан", "OK", "WEAK", "BROKEN")],
    },
    {
        "name": "Оюун Цэрэн", "phone": "9088-7766", "email": "oyun@example.mn",
        "status": S.PURCHASED, "days": 8, "expected": 420000,
        "devices": [("camera", "Canon", "EOS 200D", "Хальт зурагдсан, хэвийн", "OK", "OK", "SCRATCHED")],
    },
    {
        "name": "Ганаа Бямба", "phone": "9555-4433", "email": "ganaa@example.mn",
        "status": S.PURCHASED, "days": 12, "expected": 950000,
        "devices": [("laptop", "Dell", "XPS 13", "Гар эвдэрсэн, асна", "OK", "WEAK", "SCRATCHED")],
    },
    {
        "name": "Тэмүүлэн Жаргал", "phone": "9333-2211", "email": "",
        "status": S.CANCELLED, "days": 15, "expected": 150000,
        "devices": [("phone", "Apple", "iPhone X", "Асахгүй, эд анги", "DEAD", "DEAD", "BROKEN")],
    },
]


class Command(BaseCommand):
    help = "Seed example intake requests (uses existing branches & categories)"

    def handle(self, *args, **opts):
        branches = list(Branch.objects.filter(is_active=True))
        if not branches:
            self.stderr.write("Идэвхтэй салбар алга. Эхлээд салбар үүсгэнэ үү.")
            return
        cats = {c.slug: c for c in DeviceCategory.objects.all()}
        if not cats:
            self.stderr.write("Ангилал алга. `seed_demo`-г эхлүүлж ангилал үүсгэнэ үү.")
            return
        any_cat = next(iter(cats.values()))
        now = timezone.now()
        created = 0

        for s in SAMPLES:
            if IntakeRequest.objects.filter(contact_phone=s["phone"], contact_name=s["name"]).exists():
                continue

            req = IntakeRequest.objects.create(
                contact_name=s["name"],
                contact_phone=s["phone"],
                contact_email=s["email"],
                preferred_branch=random.choice(branches),
                expected_price=s["expected"],
                status=s["status"],
                source=IntakeRequest.Source.WEB,
            )
            ts = now - timedelta(days=s["days"])
            IntakeRequest.objects.filter(pk=req.pk).update(created_at=ts, updated_at=ts)

            for slug, brand, model, issue, screen, battery, body in s["devices"]:
                DeviceItem.objects.create(
                    intake_request=req,
                    category=cats.get(slug, any_cat),
                    brand=brand,
                    model=model,
                    issue_description=issue,
                    screen_status=screen,
                    battery_status=battery,
                    body_status=body,
                )

            self._history_and_extras(req, s["status"], s["expected"], ts, branches)
            created += 1
            self.stdout.write(self.style.SUCCESS(f"OK: {req.request_code} — {s['name']} ({req.get_status_display()})"))

        self.stdout.write(self.style.SUCCESS(f"\nDONE: {created} жишээ хүсэлт нэмлээ."))

    def _history_and_extras(self, req, status, expected, ts, branches):
        flow = ["", S.NEW]
        if status in {S.PRICE_SENT, S.APPROVED, S.PURCHASED}:
            flow.append(S.PRICE_SENT)
        if status in {S.APPROVED, S.PURCHASED}:
            flow.append(S.APPROVED)
        if status == S.PURCHASED:
            flow.append(S.PURCHASED)
        if status == S.CANCELLED:
            flow.append(S.CANCELLED)

        comments = {
            S.NEW: "Хүсэлт үүссэн",
            S.PRICE_SENT: "Үнэ санал илгээв",
            S.APPROVED: "Хэрэглэгч үнийг зөвшөөрсөн",
            S.PURCHASED: "Худалдан авалт хийгдэв",
            S.CANCELLED: "Хүсэлт цуцлагдсан",
        }
        for i in range(1, len(flow)):
            StatusHistory.objects.create(
                intake_request=req,
                old_status=flow[i - 1],
                new_status=flow[i],
                comment=comments.get(flow[i], ""),
            )

        if status in {S.PRICE_SENT, S.APPROVED, S.PURCHASED}:
            lo = int(expected * 0.8)
            hi = int(expected * 1.05)
            Quotation.objects.create(
                intake_request=req,
                quoted_price_min=lo,
                quoted_price_max=hi,
                final_offer_price=int(expected * 0.95),
                note="Төлөв байдалд үндэслэсэн үнэлгээ.",
                sent_to_customer_at=ts,
            )

        if status == S.PURCHASED:
            Pickup.objects.create(
                intake_request=req,
                pickup_date=ts + timedelta(days=1),
                pickup_address=f"{req.preferred_branch.name}, хүлээн авах цэг",
                actual_buy_price=int(expected * 0.95),
                payment_status=Pickup.PaymentStatus.PAID,
                payment_method=Pickup.PaymentMethod.CASH,
            )
