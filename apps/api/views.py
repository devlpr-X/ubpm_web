"""API views for the mobile (Expo) customer + staff app."""

from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Count, DecimalField, Prefetch, Sum
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from django.utils import timezone
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from rest_framework import generics, mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.branches.models import Branch, PartnerLocation
from apps.intake.models import DeviceCategory, DeviceImage, IntakeRequest
from apps.quotes.models import Pickup, StatusHistory

from .permissions import IsStaffRole
from .serializers import (
    AssignSerializer,
    BranchSerializer,
    DeviceCategorySerializer,
    DeviceImageSerializer,
    IntakeRequestCreateSerializer,
    IntakeRequestDetailSerializer,
    IntakeRequestListSerializer,
    PartnerLocationSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    PickupSerializer,
    QuotationCreateSerializer,
    RegisterSerializer,
    StaffRequestDetailSerializer,
    StaffRequestListSerializer,
    StaffUserSerializer,
    StatusChangeSerializer,
    UserSerializer,
    staff_queryset,
)

User = get_user_model()


def _tokens_for(user):
    """Issue a SimpleJWT access/refresh pair plus the serialized user."""
    refresh = RefreshToken.for_user(user)
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
        "user": UserSerializer(user).data,
    }


# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------
class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]


class PasswordResetRequestView(APIView):
    """Step 1: email a 4-digit reset code to the account (if it exists)."""

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        from apps.accounts.services import send_reset_code

        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        send_reset_code(serializer.validated_data["email"])
        # Same response whether or not the email exists (don't leak accounts).
        return Response(
            {"detail": "Хэрэв энэ и-мэйл бүртгэлтэй бол баталгаажуулах код илгээлээ."}
        )


class PasswordResetConfirmView(APIView):
    """Step 2: verify the emailed code and set a new 4-digit PIN."""

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        from apps.accounts.services import reset_password_with_code

        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            reset_password_with_code(
                email=data["email"], code=data["code"], new_password=data["new_password"]
            )
        except DjangoValidationError as exc:
            raise ValidationError({"detail": exc.messages[0]}) from None
        return Response({"detail": "Нууц үг шинэчлэгдлээ. Одоо шинэ PIN-ээрээ нэвтэрнэ үү."})


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class GoogleAuthView(APIView):
    """Sign in / sign up with a Google ID token from the mobile app.

    The app obtains an ID token via Google Sign-In and POSTs it here; we verify
    it with Google, then upsert a CUSTOMER user and return JWT tokens.
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        token = request.data.get("id_token")
        if not token:
            raise ValidationError({"id_token": "id_token шаардлагатай."})

        allowed = settings.GOOGLE_OAUTH_CLIENT_IDS
        if not allowed:
            raise AuthenticationFailed("Google нэвтрэлт серверт тохируулагдаагүй байна.")

        try:
            # audience=None: verify signature/issuer/expiry, then check aud below.
            info = google_id_token.verify_oauth2_token(token, google_requests.Request())
        except ValueError:
            raise AuthenticationFailed("Google token хүчингүй байна.") from None

        if info.get("iss") not in ("accounts.google.com", "https://accounts.google.com"):
            raise AuthenticationFailed("Google token-ийн эх сурвалж буруу байна.")
        if info.get("aud") not in allowed:
            raise AuthenticationFailed("Google token энэ аппад зориулагдаагүй байна.")

        email = (info.get("email") or "").lower().strip()
        if not email or not info.get("email_verified"):
            raise AuthenticationFailed("Google бүртгэлийн email баталгаажаагүй байна.")

        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                "full_name": info.get("name", ""),
                "role": User.Role.CUSTOMER,
            },
        )
        if created:
            user.set_unusable_password()
            user.save(update_fields=["password"])

        data = _tokens_for(user)
        return Response(data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Reference data (public)
# ---------------------------------------------------------------------------
class DeviceCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = DeviceCategorySerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = None
    queryset = DeviceCategory.objects.filter(is_active=True)


class BranchViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = BranchSerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = None
    lookup_field = "code"
    queryset = Branch.objects.filter(is_active=True)


class PartnerLocationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PartnerLocationSerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = None
    queryset = PartnerLocation.objects.filter(is_active=True)


# ---------------------------------------------------------------------------
# Intake requests (owner-scoped)
# ---------------------------------------------------------------------------
class IntakeRequestViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    lookup_field = "request_code"

    def get_queryset(self):
        qs = IntakeRequest.objects.filter(submitted_by=self.request.user)
        if self.action == "retrieve":
            qs = qs.prefetch_related(
                Prefetch("items__images"),
                "items__category",
                "history",
                "quotes",
            )
        return qs

    def get_serializer_class(self):
        if self.action == "create":
            return IntakeRequestCreateSerializer
        if self.action == "list":
            return IntakeRequestListSerializer
        return IntakeRequestDetailSerializer

    def perform_destroy(self, instance):
        # Only open requests may be withdrawn by the customer. Cascade delete
        # removes DeviceItem -> DeviceImage rows; django-cleanup deletes files.
        if not instance.is_open:
            raise PermissionDenied("Боловсруулагдсан хүсэлтийг устгах боломжгүй.")
        instance.delete()

    # --- Customer decision on a quote -------------------------------------
    @action(detail=True, methods=["post"])
    def accept(self, request, request_code=None):
        return self._decide(request, accept=True)

    @action(detail=True, methods=["post"])
    def reject(self, request, request_code=None):
        return self._decide(request, accept=False)

    def _decide(self, request, *, accept):
        intake = self.get_object()
        if intake.status != IntakeRequest.Status.PRICE_SENT:
            raise ValidationError("Энэ хүсэлтэд одоогоор хариу өгөх боломжгүй байна.")

        old = intake.status
        intake.status = (
            IntakeRequest.Status.APPROVED if accept else IntakeRequest.Status.CANCELLED
        )
        intake.save(update_fields=["status", "updated_at"])
        StatusHistory.objects.create(
            intake_request=intake,
            old_status=old,
            new_status=intake.status,
            comment=("Хэрэглэгч үнийг зөвшөөрсөн" if accept else "Хэрэглэгч татгалзсан"),
            changed_by=request.user,
        )
        return Response(IntakeRequestDetailSerializer(intake, context={"request": request}).data)

    # --- Image upload / delete --------------------------------------------
    @action(
        detail=True,
        methods=["get", "post"],
        parser_classes=[MultiPartParser, FormParser],
    )
    def images(self, request, request_code=None):
        intake = self.get_object()
        device = intake.items.first()
        if device is None:
            raise ValidationError("Энэ хүсэлтэд төхөөрөмж бүртгэгдээгүй байна.")

        if request.method == "GET":
            ser = DeviceImageSerializer(
                device.images.all(), many=True, context={"request": request}
            )
            return Response(ser.data)

        # POST — accept one or many files under the "image" key.
        if not intake.is_open:
            raise PermissionDenied("Боловсруулагдсан хүсэлтэд зураг нэмэх боломжгүй.")

        files = request.FILES.getlist("image")
        if not files:
            raise ValidationError({"image": "Зураг файл шаардлагатай."})

        existing = device.images.count()
        limit = settings.MAX_IMAGES_PER_REQUEST
        if existing + len(files) > limit:
            raise ValidationError(
                {"image": f"Нэг хүсэлтэд дээд тал нь {limit} зураг оруулна."}
            )

        created = [
            DeviceImage.objects.create(device_item=device, image=f, sort_order=existing + i)
            for i, f in enumerate(files)
        ]
        ser = DeviceImageSerializer(created, many=True, context={"request": request})
        return Response(ser.data, status=status.HTTP_201_CREATED)

    @action(
        detail=True,
        methods=["delete"],
        url_path=r"images/(?P<image_id>[^/.]+)",
    )
    def delete_image(self, request, request_code=None, image_id=None):
        intake = self.get_object()
        if not intake.is_open:
            raise PermissionDenied("Боловсруулагдсан хүсэлтийн зургийг устгах боломжгүй.")
        try:
            image = DeviceImage.objects.get(
                pk=image_id, device_item__intake_request=intake
            )
        except DeviceImage.DoesNotExist:
            raise ValidationError({"image_id": "Зураг олдсонгүй."}) from None
        image.delete()  # django-cleanup removes the underlying file
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Public tracking by token (no auth)
# ---------------------------------------------------------------------------
class TrackView(generics.RetrieveAPIView):
    serializer_class = IntakeRequestDetailSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = "tracking_token"
    lookup_url_kwarg = "token"
    queryset = IntakeRequest.objects.all().prefetch_related(
        "items__images", "items__category", "history", "quotes"
    )


# ===========================================================================
# Staff / Admin API — mirrors the web dashboard (apps/reports/views.py).
# All endpoints require a staff role (ADMIN / MANAGER / OPERATOR).
# ===========================================================================
def _change_status(intake, new_status, by_user, comment):
    """Apply a status change + history row + customer notification.

    Same behaviour as reports.views._change_status.
    """
    from apps.notifications.services import notify_status_changed

    old = intake.status
    intake.status = new_status
    intake.save(update_fields=["status", "updated_at"])
    StatusHistory.objects.create(
        intake_request=intake,
        old_status=old,
        new_status=new_status,
        comment=comment,
        changed_by=by_user,
    )
    notify_status_changed(intake, old, new_status, comment)


class StaffDashboardView(APIView):
    """Overview statistics — parity with reports.views.overview.

    Optional ``date_from`` / ``date_to`` (YYYY-MM-DD) scope the totals and the
    by_status / by_branch / by_category breakdowns to that created_at range —
    used by the reports screen's period filter. Without a range it reports over
    all data (the dashboard tab). The relative today/week cards are always
    global.
    """

    permission_classes = [IsStaffRole]

    def get(self, request):
        today = timezone.localdate()
        week_ago = today - timedelta(days=7)

        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")

        scoped = IntakeRequest.objects.all()
        if date_from:
            scoped = scoped.filter(created_at__date__gte=date_from)
        if date_to:
            scoped = scoped.filter(created_at__date__lte=date_to)

        total = scoped.count()
        today_count = IntakeRequest.objects.filter(created_at__date=today).count()
        week_count = IntakeRequest.objects.filter(created_at__date__gte=week_ago).count()
        week_quoted = (
            IntakeRequest.objects.filter(
                created_at__date__gte=week_ago, quotes__isnull=False
            )
            .distinct()
            .count()
        )
        # Requests with at least one quote, within the scope.
        quoted_count = scoped.filter(quotes__isnull=False).distinct().count()
        purchased = scoped.filter(status=IntakeRequest.Status.PURCHASED)
        purchased_count = purchased.count()
        purchased_amount = Pickup.objects.filter(
            intake_request__in=purchased
        ).aggregate(
            total=Coalesce(Sum("actual_buy_price"), 0, output_field=DecimalField())
        )["total"]

        status_labels = dict(IntakeRequest.Status.choices)
        by_status = [
            {
                "status": row["status"],
                "label": status_labels.get(row["status"], row["status"]),
                "count": row["c"],
            }
            for row in scoped.values("status").annotate(c=Count("id")).order_by("-c")
        ]
        by_branch = [
            {"name": row["preferred_branch__name"], "count": row["c"]}
            for row in scoped.exclude(preferred_branch=None)
            .values("preferred_branch__name")
            .annotate(c=Count("id"))
            .order_by("-c")
        ]
        by_category = [
            {"name": row["items__category__name"], "count": row["c"]}
            for row in scoped.exclude(items__category__name=None)
            .values("items__category__name")
            .annotate(c=Count("id"))
            .order_by("-c")
        ]
        recent = (
            scoped.select_related("preferred_branch", "assigned_to")
            .order_by("-created_at")[:10]
        )

        return Response(
            {
                "total": total,
                "today_count": today_count,
                "week_count": week_count,
                "week_quoted": week_quoted,
                "quoted_count": quoted_count,
                "purchased_count": purchased_count,
                "purchased_amount": purchased_amount,
                "by_status": by_status,
                "by_branch": by_branch,
                "by_category": by_category,
                "recent": StaffRequestListSerializer(recent, many=True).data,
                "date_from": date_from,
                "date_to": date_to,
            }
        )


class StaffUserListView(generics.ListAPIView):
    """Assignable staff (for the assign dropdown)."""

    permission_classes = [IsStaffRole]
    serializer_class = StaffUserSerializer
    pagination_class = None
    queryset = staff_queryset().order_by("full_name", "email")


class StaffRequestViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    """All intake requests (not owner-scoped) + management actions."""

    permission_classes = [IsStaffRole]
    lookup_field = "request_code"
    # Filter by status / preferred_branch via DjangoFilterBackend (default).
    filterset_fields = ["status", "preferred_branch", "assigned_to", "source"]

    def get_queryset(self):
        qs = IntakeRequest.objects.select_related(
            "preferred_branch", "assigned_to", "submitted_by"
        )
        if self.action == "retrieve":
            qs = qs.prefetch_related(
                Prefetch("items__images"),
                "items__category",
                "history",
                "quotes",
            ).select_related("pickup", "pickup__assigned_staff")
        else:
            qs = self._apply_list_filters(qs)
        return qs.order_by("-created_at")

    def _apply_list_filters(self, qs):
        """Free-text search + date range, matching the web request_list."""
        from django.db.models import Q

        params = self.request.query_params
        if q := params.get("q"):
            qs = qs.filter(
                Q(request_code__icontains=q)
                | Q(contact_name__icontains=q)
                | Q(contact_phone__icontains=q)
                | Q(contact_email__icontains=q)
                | Q(company_name__icontains=q)
            )
        if date_from := params.get("created_at__gte"):
            qs = qs.filter(created_at__date__gte=date_from)
        if date_to := params.get("created_at__lte"):
            qs = qs.filter(created_at__date__lte=date_to)
        return qs

    def get_serializer_class(self):
        if self.action == "retrieve":
            return StaffRequestDetailSerializer
        return StaffRequestListSerializer

    def _detail_response(self, intake):
        intake = (
            IntakeRequest.objects.prefetch_related(
                "items__images", "items__category", "history", "quotes"
            )
            .select_related("preferred_branch", "assigned_to", "submitted_by", "pickup")
            .get(pk=intake.pk)
        )
        return Response(
            StaffRequestDetailSerializer(intake, context={"request": self.request}).data
        )

    # --- Add a quotation (price offer) -> emails the customer --------------
    @action(detail=True, methods=["post"])
    def quote(self, request, request_code=None):
        from apps.notifications.services import notify_quote_sent

        intake = get_object_or_404(IntakeRequest, request_code=request_code)
        serializer = QuotationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        quotation = serializer.save(
            intake_request=intake,
            quoted_by=request.user,
            sent_to_customer_at=timezone.now(),
        )
        notify_quote_sent(quotation)
        if intake.status == IntakeRequest.Status.NEW:
            _change_status(
                intake, IntakeRequest.Status.PRICE_SENT, request.user, "Үнэ санал илгээв"
            )
        return self._detail_response(intake)

    # --- Change status ----------------------------------------------------
    @action(detail=True, methods=["post"])
    def status(self, request, request_code=None):
        intake = get_object_or_404(IntakeRequest, request_code=request_code)
        serializer = StatusChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_status = serializer.validated_data["new_status"]
        comment = serializer.validated_data.get("comment", "")
        if new_status != intake.status:
            _change_status(intake, new_status, request.user, comment)
        return self._detail_response(intake)

    # --- Assign to a staff member -----------------------------------------
    @action(detail=True, methods=["post"])
    def assign(self, request, request_code=None):
        intake = get_object_or_404(IntakeRequest, request_code=request_code)
        serializer = AssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        intake.assigned_to = serializer.validated_data["assigned_to"]
        intake.save(update_fields=["assigned_to", "updated_at"])
        return self._detail_response(intake)

    # --- Schedule / update the pickup -------------------------------------
    @action(detail=True, methods=["get", "post"])
    def pickup(self, request, request_code=None):
        from apps.notifications.services import notify_pickup_scheduled

        intake = get_object_or_404(IntakeRequest, request_code=request_code)
        if request.method == "GET":
            existing = getattr(intake, "pickup", None)
            if existing is None:
                return Response(None)
            return Response(PickupSerializer(existing).data)

        serializer = PickupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        pickup, _ = Pickup.objects.update_or_create(
            intake_request=intake, defaults=serializer.validated_data
        )
        notify_pickup_scheduled(pickup)
        return Response(PickupSerializer(pickup).data, status=status.HTTP_200_OK)


class PickupViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Pickup list / detail / update — parity with reports.views.pickup_*."""

    permission_classes = [IsStaffRole]
    serializer_class = PickupSerializer
    queryset = Pickup.objects.select_related(
        "intake_request", "assigned_staff"
    ).order_by("-pickup_date")


class StaffExportView(APIView):
    """Export requests as xlsx / csv / pdf / png — reuses reports.views.

    NB: the desired file type is read from the ``fmt`` query param, NOT
    ``format`` — DRF reserves ``format`` for renderer/content negotiation
    (URL_FORMAT_OVERRIDE), so ``?format=xlsx`` would 404 here.
    """

    permission_classes = [IsStaffRole]

    def get(self, request):
        from apps.reports.views import (
            _build_export_queryset,
            _csv_export,
            _pdf_export,
            _png_export,
            _report_meta,
            _xlsx_export,
        )

        fmt = request.query_params.get("fmt", "xlsx")
        qs = _build_export_queryset(request.query_params)
        meta = _report_meta(request.query_params, qs)
        if fmt == "csv":
            return _csv_export(qs)
        if fmt == "pdf":
            return _pdf_export(qs, meta)
        if fmt == "png":
            return _png_export(qs, meta)
        return _xlsx_export(qs)
