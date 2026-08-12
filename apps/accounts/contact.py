"""Хэрэглэгчийн профайл ↔ хүсэлтийн холбоо барих мэдээллийн sync.

Нэвтэрсэн хэрэглэгч хүсэлт илгээхэд бөглөсөн холбоо барих мэдээлэл нь профайлд
нь хадгалагдаж, дараагийн хүсэлт дээр маягт автоматаар дүүрнэ. Вэб (intake) ба
апп (api) хоёулаа энэ модулийг ашиглана.
"""

# (User талбар, IntakeRequest талбар) хосууд — хоёр тийш нь хуулагдана.
CONTACT_FIELDS = (
    ("full_name", "contact_name"),
    ("phone", "contact_phone"),
    ("customer_type", "customer_type"),
    ("company_name", "company_name"),
    ("city", "city"),
    ("district", "district"),
    ("address_line", "address_line"),
)


def _is_customer(user):
    """Зөвхөн хэрэглэгчийн (CUSTOMER) профайлыг ашиглана.

    Оператор нийтийн маягтаар үйлчлүүлэгчийн өмнөөс хүсэлт үүсгэх үед түүний
    ажилтны профайл руу үйлчлүүлэгчийн мэдээлэл бичигдэхээс сэргийлнэ.
    """
    return bool(user) and user.is_authenticated and not user.is_staff_role


def contact_initial(user):
    """Хүсэлтийн маягтыг урьдчилан дүүргэх `initial` dict.

    Зочин (нэвтрээгүй) болон ажилтанд хоосон dict буцаана. Профайл дээр хоосон
    байгаа талбарыг алгасна — маягтын өөрийнх нь default (ж: Хот = Улаанбаатар)
    хэвээр үлдэнэ.
    """
    if not _is_customer(user):
        return {}

    initial = {}
    for user_field, request_field in CONTACT_FIELDS:
        value = getattr(user, user_field, "")
        if value:
            initial[request_field] = value
    if user.email:
        initial["contact_email"] = user.email
    return initial


def save_contact_to_profile(user, intake):
    """Хүсэлтэд бөглөсөн холбоо барих мэдээллийг профайл руу буцааж хадгална.

    Эхний хүсэлтээр профайл дүүрч, дараагийнхаар хамгийн сүүлийн утга руугаа
    шинэчлэгдэнэ. Хоосон утга хуучин мэдээллийг дардаггүй. `email` нь нэвтрэх
    нэр учир хэзээ ч дарж бичихгүй.

    Өөрчлөлт орсон талбаруудын нэрсийг буцаана (тест/логт хэрэгтэй).
    """
    if not _is_customer(user):
        return []

    changed = []
    for user_field, request_field in CONTACT_FIELDS:
        value = getattr(intake, request_field, "") or ""
        if not value or getattr(user, user_field) == value:
            continue
        setattr(user, user_field, value)
        changed.append(user_field)

    if changed:
        user.save(update_fields=changed)
    return changed
