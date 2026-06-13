"""Serializers for the mobile (Expo) customer API."""

from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers

from apps.branches.models import Branch, PartnerLocation
from apps.intake.models import DeviceCategory, DeviceImage, DeviceItem, IntakeRequest
from apps.quotes.models import Quotation, StatusHistory

User = get_user_model()


# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "email", "full_name", "phone", "role")
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
    """Customer creates a request with a single nested device item (JSON).

    Images are uploaded afterwards via the request's `images` endpoint, which
    returns each stored file's URL — same ImageField storage as the web flow.
    """

    device = DeviceItemWriteSerializer(write_only=True)

    class Meta:
        model = IntakeRequest
        fields = (
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
            "device",
        )

    def validate(self, attrs):
        if attrs.get("customer_type") == IntakeRequest.CustomerType.COMPANY and not attrs.get(
            "company_name"
        ):
            raise serializers.ValidationError(
                {"company_name": "Компанийн нэрийг бөглөнө үү."}
            )
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        device_data = validated_data.pop("device")
        user = self.context["request"].user

        validated_data["submitted_by"] = user
        validated_data["source"] = IntakeRequest.Source.APP
        if not validated_data.get("contact_email"):
            validated_data["contact_email"] = user.email

        intake = IntakeRequest.objects.create(**validated_data)
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
