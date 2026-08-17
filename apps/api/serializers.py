"""Serializers for the mobile (Expo) customer API."""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers

from apps.accounts.contact import save_contact_to_profile
from apps.branches.models import Branch, PartnerLocation
from apps.intake.models import DeviceCategory, DeviceImage, DeviceItem, IntakeRequest
from apps.quotes.models import Pickup, Quotation, StatusHistory

User = get_user_model()


# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------
class UserSerializer(serializers.ModelSerializer):
    """Профайл — холбоо барих мэдээлэл нь хүсэлтийн маягтыг дүүргэхэд ашиглагдана."""

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "full_name",
            "phone",
            "role",
            "customer_type",
            "company_name",
            "city",
            "district",
            "address_line",
        )
        read_only_fields = ("id", "email", "role")


PIN_FIELD_KWARGS = {
    "error_messages": {"invalid": "Нууц үг яг 4 оронтой тоо байх ёстой (ж: 1234)."},
}


class RegisterSerializer(serializers.ModelSerializer):
    # Accounts use a 4-digit numeric PIN instead of a long password.
    password = serializers.RegexField(
        r"^\d{4}$", write_only=True, style={"input_type": "password"}, **PIN_FIELD_KWARGS
    )

    class Meta:
        model = User
        fields = ("id", "email", "password", "full_name", "phone")

    def validate_email(self, value):
        value = value.lower().strip()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Энэ email хаягаар бүртгэл аль хэдийн үүссэн байна.")
        return value

    def create(self, validated_data):
        password = validated_data.pop("password")
        # Always a customer-role account from the public app.
        user = User.objects.create_user(
            email=validated_data.pop("email"),
            password=password,
            role=User.Role.CUSTOMER,
            **validated_data,
        )
        return user


class PasswordResetRequestSerializer(serializers.Serializer):
    """Step 1: ask for an emailed reset code."""

    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Step 2: verify the code and set a new 4-digit PIN."""

    email = serializers.EmailField()
    code = serializers.RegexField(
        r"^\d{4}$", error_messages={"invalid": "Баталгаажуулах код 4 оронтой тоо байна."}
    )
    new_password = serializers.RegexField(r"^\d{4}$", **PIN_FIELD_KWARGS)


# ---------------------------------------------------------------------------
# Branches (reference data)
# ---------------------------------------------------------------------------
class BranchSerializer(serializers.ModelSerializer):
    cover_image = serializers.ImageField(read_only=True, use_url=True)

    class Meta:
        model = Branch
        fields = (
            "id",
            "name",
            "code",
            "address_line",
            "city",
            "district",
            "latitude",
            "longitude",
            "phones",
            "working_hours",
            "cover_image",
            "description",
        )


class PartnerLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = PartnerLocation
        fields = ("id", "name", "partner_company", "address", "phone", "notes")


# ---------------------------------------------------------------------------
# Intake — reference + read + write
# ---------------------------------------------------------------------------
class DeviceCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceCategory
        fields = ("id", "name", "slug", "icon", "sort_order")


class DeviceImageSerializer(serializers.ModelSerializer):
    # `image` rendered as an absolute URL (needs request in context).
    image = serializers.ImageField(use_url=True)

    class Meta:
        model = DeviceImage
        fields = ("id", "image", "sort_order", "uploaded_at")
        read_only_fields = ("id", "uploaded_at")


class DeviceItemReadSerializer(serializers.ModelSerializer):
    images = DeviceImageSerializer(many=True, read_only=True)
    category = DeviceCategorySerializer(read_only=True)

    class Meta:
        model = DeviceItem
        fields = (
            "id",
            "category",
            "brand",
            "model",
            "quantity",
            "storage",
            "color",
            "imei_or_serial",
            "power_on_status",
            "screen_status",
            "battery_status",
            "body_status",
            "water_damage",
            "accessories",
            "issue_description",
            "condition_grade",
            "images",
        )


class DeviceItemWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceItem
        fields = (
            "category",
            "brand",
            "model",
            "quantity",
            "storage",
            "color",
            "imei_or_serial",
            "power_on_status",
            "screen_status",
            "battery_status",
            "body_status",
            "water_damage",
            "accessories",
            "issue_description",
        )


class QuotationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Quotation
        fields = (
            "id",
            "quoted_price_min",
            "quoted_price_max",
            "final_offer_price",
            "note",
            "valid_until",
            "sent_to_customer_at",
            "created_at",
        )


class StatusHistorySerializer(serializers.ModelSerializer):
    new_status_display = serializers.CharField(source="get_new_status_display", read_only=True)

    class Meta:
        model = StatusHistory
        fields = ("id", "old_status", "new_status", "new_status_display", "comment", "changed_at")


class IntakeRequestListSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    total_quantity = serializers.IntegerField(read_only=True)

    class Meta:
        model = IntakeRequest
        fields = (
            "id",
            "request_code",
            "tracking_token",
            "status",
            "status_display",
            "contact_name",
            "total_quantity",
            "created_at",
            "updated_at",
        )


class IntakeRequestDetailSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    request_type_display = serializers.CharField(
        source="get_request_type_display", read_only=True
    )
    items = DeviceItemReadSerializer(many=True, read_only=True)
    history = StatusHistorySerializer(many=True, read_only=True)
    quotes = QuotationSerializer(many=True, read_only=True)
    is_open = serializers.BooleanField(read_only=True)

    class Meta:
        model = IntakeRequest
        fields = (
            "id",
            "request_code",
            "tracking_token",
            "request_type",
            "request_type_display",
            "customer_type",
            "contact_name",
            "company_name",
            "contact_phone",
            "contact_email",
            "city",
            "district",
            "address_line",
            "preferred_branch",
            "expected_price",
            "pickup_required",
            "pickup_lat",
            "pickup_lng",
            "status",
            "status_display",
            "is_open",
            "items",
            "history",
            "quotes",
            "created_at",
            "updated_at",
        )


class IntakeRequestCreateSerializer(serializers.ModelSerializer):
    """Customer creates a request with one or more nested device items (JSON).

    Вэб дээрх формтой ижил — нэг хүсэлтээр олон төхөөрөмж зарж болно (`devices`).
    Хуучин аппын хувилбарууд ганц `device` илгээдэг тул тэрийг мөн хүлээж авна.

    Images are uploaded afterwards via the request's `images` endpoint, which
    returns each stored file's URL — same ImageField storage as the web flow.
    """

    devices = DeviceItemWriteSerializer(many=True, write_only=True, required=False)
    # Хуучин апп (v1.0) — ганц төхөөрөмж. Шинэ апп `devices` ашиглана.
    device = DeviceItemWriteSerializer(write_only=True, required=False)

    class Meta:
        model = IntakeRequest
        fields = (
            "request_type",
            "customer_type",
            "contact_name",
            "company_name",
            "contact_phone",
            "contact_email",
            "city",
            "district",
            "address_line",
            "preferred_branch",
            "pickup_required",
            "pickup_lat",
            "pickup_lng",
            "devices",
            "device",
        )

    def validate_devices(self, value):
        if not value:
            raise serializers.ValidationError("Дор хаяж нэг төхөөрөмж оруулна уу.")
        limit = settings.MAX_DEVICES_PER_REQUEST
        if len(value) > limit:
            raise serializers.ValidationError(
                f"Нэг хүсэлтэд дээд тал нь {limit} төхөөрөмж оруулна."
            )
        return value

    def validate(self, attrs):
        if attrs.get("customer_type") == IntakeRequest.CustomerType.COMPANY and not attrs.get(
            "company_name"
        ):
            raise serializers.ValidationError(
                {"company_name": "Компанийн нэрийг бөглөнө үү."}
            )
        if not attrs.get("devices") and not attrs.get("device"):
            raise serializers.ValidationError(
                {"devices": "Дор хаяж нэг төхөөрөмж оруулна уу."}
            )
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        # `devices` (шинэ) эсвэл `device` (хуучин апп) — хоёуланг нэг жагсаалт болгоно.
        devices_data = validated_data.pop("devices", None) or []
        legacy_device = validated_data.pop("device", None)
        if legacy_device and not devices_data:
            devices_data = [legacy_device]
        user = self.context["request"].user

        validated_data["submitted_by"] = user
        validated_data["source"] = IntakeRequest.Source.APP
        if not validated_data.get("contact_email"):
            validated_data["contact_email"] = user.email
        if not validated_data.get("pickup_required"):
            validated_data["pickup_lat"] = None
            validated_data["pickup_lng"] = None

        intake = IntakeRequest.objects.create(**validated_data)

        # Холбоо барих мэдээллийг профайлд хадгална — дараагийн хүсэлтэд апп нь
        # /me хариунаас маягтаа урьдчилан дүүргэнэ (вэбтэй ижил).
        save_contact_to_profile(user, intake)

        # Ажиллагаатай утас — ангилал үргэлж "Гар утас" (вэбтэй ижил).
        phone_cat = None
        if intake.request_type == IntakeRequest.RequestType.WORKING:
            phone_cat = (
                DeviceCategory.objects.filter(is_active=True, slug="phone").first()
                or DeviceCategory.objects.filter(
                    is_active=True, name__icontains="утас"
                ).first()
            )
        for device_data in devices_data:
            if phone_cat:
                device_data["category"] = phone_cat
            DeviceItem.objects.create(intake_request=intake, **device_data)

        StatusHistory.objects.create(
            intake_request=intake,
            old_status="",
            new_status=intake.status,
            comment="Хүсэлт үүссэн (апп)",
            changed_by=user,
        )

        from apps.notifications.services import (
            notify_new_request_customer,
            notify_new_request_staff,
        )

        notify_new_request_customer(intake)
        notify_new_request_staff(intake)
        return intake

    def to_representation(self, instance):
        return IntakeRequestDetailSerializer(instance, context=self.context).data


# ---------------------------------------------------------------------------
# Staff / Admin (dashboard parity with the web)
# ---------------------------------------------------------------------------
STAFF_ROLES = (User.Role.ADMIN, User.Role.MANAGER, User.Role.OPERATOR)


def staff_queryset():
    """Users who can be assigned to / own requests (same set as the web forms)."""
    return User.objects.filter(role__in=STAFF_ROLES)


class StaffUserSerializer(serializers.ModelSerializer):
    role_display = serializers.CharField(source="get_role_display", read_only=True)

    class Meta:
        model = User
        fields = ("id", "full_name", "email", "phone", "role", "role_display")


class PickupSerializer(serializers.ModelSerializer):
    payment_status_display = serializers.CharField(
        source="get_payment_status_display", read_only=True
    )
    payment_method_display = serializers.CharField(
        source="get_payment_method_display", read_only=True
    )
    assigned_staff_name = serializers.CharField(
        source="assigned_staff.full_name", read_only=True, default=""
    )
    request_code = serializers.CharField(
        source="intake_request.request_code", read_only=True
    )

    class Meta:
        model = Pickup
        fields = (
            "id",
            "request_code",
            "pickup_date",
            "pickup_address",
            "assigned_staff",
            "assigned_staff_name",
            "actual_buy_price",
            "payment_status",
            "payment_status_display",
            "payment_method",
            "payment_method_display",
            "notes",
            "created_at",
        )
        read_only_fields = ("id", "created_at")

    def validate_assigned_staff(self, value):
        if value is not None and value.role not in STAFF_ROLES and not value.is_superuser:
            raise serializers.ValidationError("Зөвхөн ажилтанг хариуцагчаар сонгоно.")
        return value


class StaffRequestListSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    source_display = serializers.CharField(source="get_source_display", read_only=True)
    total_quantity = serializers.IntegerField(read_only=True)
    preferred_branch_name = serializers.CharField(
        source="preferred_branch.name", read_only=True, default=""
    )
    assigned_to_name = serializers.CharField(
        source="assigned_to.full_name", read_only=True, default=""
    )

    class Meta:
        model = IntakeRequest
        fields = (
            "id",
            "request_code",
            "status",
            "status_display",
            "request_type",
            "source",
            "source_display",
            "contact_name",
            "contact_phone",
            "company_name",
            "city",
            "district",
            "address_line",
            "preferred_branch_name",
            "assigned_to_name",
            "total_quantity",
            "pickup_required",
            "pickup_lat",
            "pickup_lng",
            "created_at",
            "updated_at",
        )


class StaffRequestDetailSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    request_type_display = serializers.CharField(
        source="get_request_type_display", read_only=True
    )
    source_display = serializers.CharField(source="get_source_display", read_only=True)
    customer_type_display = serializers.CharField(
        source="get_customer_type_display", read_only=True
    )
    items = DeviceItemReadSerializer(many=True, read_only=True)
    history = StatusHistorySerializer(many=True, read_only=True)
    quotes = QuotationSerializer(many=True, read_only=True)
    is_open = serializers.BooleanField(read_only=True)
    total_quantity = serializers.IntegerField(read_only=True)
    preferred_branch_name = serializers.CharField(
        source="preferred_branch.name", read_only=True, default=""
    )
    assigned_to = StaffUserSerializer(read_only=True)
    submitted_by = StaffUserSerializer(read_only=True)
    pickup = PickupSerializer(read_only=True)
    latest_quote = serializers.SerializerMethodField()

    class Meta:
        model = IntakeRequest
        fields = (
            "id",
            "request_code",
            "tracking_token",
            "customer_type",
            "customer_type_display",
            "contact_name",
            "company_name",
            "contact_phone",
            "contact_email",
            "city",
            "district",
            "address_line",
            "preferred_branch",
            "preferred_branch_name",
            "expected_price",
            "pickup_required",
            "pickup_lat",
            "pickup_lng",
            "request_type",
            "request_type_display",
            "source",
            "source_display",
            "status",
            "status_display",
            "is_open",
            "total_quantity",
            "assigned_to",
            "submitted_by",
            "items",
            "history",
            "quotes",
            "latest_quote",
            "pickup",
            "created_at",
            "updated_at",
        )

    def get_latest_quote(self, obj):
        latest = obj.quotes.order_by("-created_at").first()
        return QuotationSerializer(latest).data if latest else None


class QuotationCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Quotation
        fields = (
            "id",
            "quoted_price_min",
            "quoted_price_max",
            "final_offer_price",
            "note",
            "valid_until",
        )
        read_only_fields = ("id",)

    def validate(self, attrs):
        # Mirror QuotationForm.clean (apps/quotes/forms.py): min must not exceed max.
        mn = attrs.get("quoted_price_min")
        mx = attrs.get("quoted_price_max")
        if mn is not None and mx is not None and mn > mx:
            raise serializers.ValidationError("Доод үнэ дээд үнээс их байж болохгүй.")
        return attrs


class StatusChangeSerializer(serializers.Serializer):
    # Only the live statuses (same set as the web StatusChangeForm).
    new_status = serializers.ChoiceField(choices=IntakeRequest.Status.choices)
    comment = serializers.CharField(required=False, allow_blank=True, default="")


class AssignSerializer(serializers.Serializer):
    assigned_to = serializers.PrimaryKeyRelatedField(
        queryset=staff_queryset(), allow_null=True
    )
