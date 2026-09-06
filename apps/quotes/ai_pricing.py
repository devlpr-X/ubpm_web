"""AI үнийн санал — Google Gemini (Interactions API).

Оператор шинэ хүсэлт дээр "хэдээр авах вэ?" гэдгээ шийдэхдээ дэлгэрэнгүй хуудасны
"Ижил бренд/ангиллын өмнөх үнэ" жагсаалтыг нүдээрээ жишдэг. Энэ модуль яг тэр
жагсаалтыг (сүүлийн SIMILAR_LIMIT = 20 хүсэлт) одоогийн хүсэлтийн
төхөөрөмжийн мэдээлэлтэй хамт Gemini рүү илгээж, эргээд тоон санал авчирна.

Загварт зөвхөн бидний өөрсдийн түүх очно — гадны үнийн мэдээлэл ашиглахгүй,
тиймээс санал нь UBPM-ийн бодит худалдан авалтын түвшинд тогтоно. Хариу нь JSON
schema-гаар хязгаарлагдсан тул талбарууд нь тогтмол.

Тохиргоо: GEMINI_API_KEY (заавал), GEMINI_MODEL, GEMINI_API_URL, GEMINI_TIMEOUT
— ubpm/settings/base.py-г үзнэ үү.
"""

import json

import requests
from django.conf import settings

from apps.quotes.models import Pickup


class AIPricingError(Exception):
    """Gemini рүү хийсэн дуудлага бүтэлгүйтэв (сүлжээ, статус, задлан шинжлэл)."""


class AIPricingConfigError(AIPricingError):
    """Үйлчилгээ тохируулагдаагүй — API түлхүүр алга (эндпойнт 503 буцаана)."""


# Загвараас буцаах JSON-ы бүтэц. Мөнгөн дүн бүр төгрөгөөр, бүхэл тоогоор.
RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "recommended_price": {
            "type": "integer",
            "description": "Санал болгож буй худалдан авах үнэ, төгрөгөөр.",
        },
        "suggested_min": {
            "type": "integer",
            "description": "Хэрэглэгчид хэлэх үнийн доод хязгаар, төгрөгөөр.",
        },
        "suggested_max": {
            "type": "integer",
            "description": "Хэрэглэгчид хэлэх үнийн дээд хязгаар, төгрөгөөр.",
        },
        "confidence": {
            "type": "string",
            "enum": ["LOW", "MEDIUM", "HIGH"],
            "description": "Жишиг хэлцлүүд хэр сайн тааруулж байгаагаас хамаарсан итгэл.",
        },
        "rationale": {
            "type": "string",
            "description": "Яагаад ийм үнэ гэдгийг монголоор, 2-4 өгүүлбэрт.",
        },
        "comparables": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Хамгийн их тулгуурласан жишиг хүсэлтүүдийн код.",
        },
    },
    "required": [
        "recommended_price",
        "suggested_min",
        "suggested_max",
        "confidence",
        "rationale",
    ],
}

SYSTEM_INSTRUCTION = (
    "Чи бол UBPM компанийн хуучин цахим бараа худалдан авах үнэлгээний туслах. "
    "Хэрэглэгчээс төхөөрөмж худалдан авахад бид хэдэн төгрөг санал болгох ёстойг "
    "тодорхойлно. Шийдвэрээ зөвхөн өгөгдсөн өмнөх хэлцлүүдэд (жишиг өгөгдөл) "
    "тулгуурла — гаднаас үнэ зохиож болохгүй. Бодит худалдан авсан үнэ "
    "(actual_buy_price) байгаа мөрүүдэд хамгийн их жин өг, дараа нь эцсийн санал "
    "(final_offer_price), эцэст нь үнийн муж. Төхөөрөмжийн төлөв (дэлгэц, батарей, "
    "бие, ус орсон эсэх, асах эсэх) муу байх тусам үнийг бууруул. Жишиг өгөгдөл "
    "хомс эсвэл тааруухан таарч байвал confidence-ийг LOW болгож, үүнийгээ rationale "
    "дотор шууд хэл. Нэг ч мөрөнд үнэ байхгүй бол үнэ тогтоох хангалттай түүх алга "
    "гэдгээ илэн далангүй хэлж, зөвхөн болгоомжтой доод хязгаар санал болго. "
    "Хэрэглэгчийн хүссэн үнэ (expected_price) бол зөвхөн лавлагаа — "
    "түүнд автах ёсгүй. Мөнгөн дүнг төгрөгөөр, бүхэл тоогоор буцаа. rationale-г "
    "монгол хэлээр бич."
)


def _num(value):
    """Decimal → int (эсвэл None), JSON-д цэвэрхэн орохын тулд."""
    return None if value is None else int(value)


def _device_payload(item):
    """Нэг төхөөрөмжийн үнэд нөлөөлөх бүх талбар."""
    return {
        "category": item.category.name,
        "brand": item.brand,
        "model": item.model,
        "quantity": item.quantity,
        "storage": item.storage,
        "color": item.color,
        "power_on": item.get_power_on_status_display(),
        "screen": item.get_screen_status_display(),
        "battery": item.get_battery_status_display(),
        "body": item.get_body_status_display(),
        "water_damage": item.water_damage,
        "accessories": item.accessories,
        "issue": item.issue_description,
        "grade": item.get_condition_grade_display() if item.condition_grade else "",
    }


def _current_payload(intake):
    """Одоо үнэ тогтоох гэж буй захиалга."""
    return {
        "request_code": intake.request_code,
        "created_at": intake.created_at.date().isoformat(),
        "request_type": intake.get_request_type_display(),
        "customer_type": intake.get_customer_type_display(),
        "source": intake.get_source_display(),
        "city": intake.city,
        "district": intake.district,
        "pickup_required": intake.pickup_required,
        "expected_price": _num(intake.expected_price),
        "devices": [_device_payload(item) for item in intake.items.all()],
    }


def build_context(intake, limit=None):
    """Загварт илгээх өгөгдөл: одоогийн захиалга + сүүлийн 20 ижил төстэй хүсэлт.

    Ижил төстэйг сонгох логик нь вэбийн дэлгэрэнгүй хуудастай яг нэг —
    `_similar_requests`-ийг дуудна (дугуй import-оос сэргийлж дотор нь).
    Түүн дээр нэмээд бодит худалдан авсан үнийг (Pickup) нэг query-гээр авчирч
    мөр бүрд залгана: AI-д хамгийн үнэ цэнэтэй дохио нь тэр.
    """
    from apps.reports.views import SIMILAR_LIMIT, _similar_requests

    rows = _similar_requests(intake, limit=limit or SIMILAR_LIMIT)
    bought = dict(
        Pickup.objects.filter(
            intake_request__in=[row["request"].pk for row in rows],
            actual_buy_price__isnull=False,
        ).values_list("intake_request_id", "actual_buy_price")
    )

    similar = []
    for row in rows:
        other, quote, device = row["request"], row["quote"], row["device"]
        entry = {
            "request_code": other.request_code,
            "created_at": other.created_at.date().isoformat(),
            "status": other.get_status_display(),
            # Үнэ өгөгдөөгүй хүсэлт ч жагсаалтад орж ирдэг — тэр мөр үнийн дохио
            # авчрахгүй ч ямар төхөөрөмж, ямар төлөвтэй байсныг хэлж өгнө.
            "quoted_price_min": _num(quote.quoted_price_min) if quote else None,
            "quoted_price_max": _num(quote.quoted_price_max) if quote else None,
            "final_offer_price": _num(quote.final_offer_price) if quote else None,
            "actual_buy_price": _num(bought.get(other.pk)),
        }
        if device is not None:
            entry["device"] = _device_payload(device)
        similar.append(entry)

    return {"current_request": _current_payload(intake), "similar_deals": similar}


def build_prompt(context):
    """Контекстийг загварт өгөх ганц асуулт болгож хувиргана."""
    return (
        "Доорх JSON-д (1) `current_request` — одоо үнэ тогтоох гэж буй захиалга, "
        "(2) `similar_deals` — ижил бренд/ангиллын сүүлийн үеийн хэлцлүүд байна.\n\n"
        f"{json.dumps(context, ensure_ascii=False, indent=2)}\n\n"
        "Энэ захиалгыг бид хэдэн төгрөгөөр авах вэ? Схемийн дагуу JSON-оор хариул."
    )


def _extract_text(data):
    """Interactions API-ийн хариунаас эцсийн текстийг цуглуулна."""
    if isinstance(data.get("output_text"), str) and data["output_text"].strip():
        return data["output_text"]
    chunks = []
    for step in data.get("steps") or []:
        if step.get("type") != "model_output":
            continue
        for block in step.get("content") or []:
            if block.get("type") == "text" and block.get("text"):
                chunks.append(block["text"])
    return "".join(chunks)


def _call_gemini(prompt):
    api_key = getattr(settings, "GEMINI_API_KEY", "")
    if not api_key:
        raise AIPricingConfigError(
            "AI үнэлгээ тохируулагдаагүй байна — GEMINI_API_KEY-г тохируулна уу."
        )

    payload = {
        "model": settings.GEMINI_MODEL,
        "input": prompt,
        "system_instruction": SYSTEM_INSTRUCTION,
        "generation_config": {"temperature": 0.2},
        "response_format": {
            "type": "text",
            "mime_type": "application/json",
            "schema": RESPONSE_SCHEMA,
        },
    }
    try:
        res = requests.post(
            settings.GEMINI_API_URL,
            json=payload,
            headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
            timeout=settings.GEMINI_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise AIPricingError(f"AI үйлчилгээ рүү холбогдож чадсангүй: {exc}") from exc

    if res.status_code != 200:
        raise AIPricingError(f"AI үйлчилгээ {res.status_code} буцаалаа: {res.text[:300]}")

    try:
        text = _extract_text(res.json())
    except ValueError as exc:
        raise AIPricingError("AI үйлчилгээнээс ирсэн хариу JSON биш байна.") from exc
    if not text.strip():
        raise AIPricingError("AI үйлчилгээ хоосон хариу буцаалаа.")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise AIPricingError("AI-ийн үнийн саналыг задлан шинжилж чадсангүй.") from exc


def suggest_price(intake, limit=None):
    """Хүсэлтэд AI-ийн үнийн санал буцаана.

    Жишиг өгөгдөл огт байхгүй (бренд бөглөөгүй, эсвэл ижил төстэй хэлцэл олдоогүй)
    бол загварыг огт дуудахгүйгээр `suggestion=None` буцаана — түүх байхгүй үед AI
    зүгээр л үнэ зохиох эрсдэлтэй.
    """
    context = build_context(intake, limit=limit)
    similar = context["similar_deals"]
    if not similar:
        return {
            "request_code": intake.request_code,
            "model": settings.GEMINI_MODEL,
            "comparables_count": 0,
            "suggestion": None,
            "detail": (
                "Ижил бренд/ангиллын өмнөх хэлцэл олдсонгүй — жиших зүйлгүй тул "
                "AI үнэ санал болгосонгүй."
            ),
        }

    return {
        "request_code": intake.request_code,
        "model": settings.GEMINI_MODEL,
        "comparables_count": len(similar),
        "suggestion": _call_gemini(build_prompt(context)),
    }
