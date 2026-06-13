"""API views for the mobile (Expo) customer app."""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Prefetch
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
from apps.quotes.models import StatusHistory

from .serializers import (
    BranchSerializer,
    DeviceCategorySerializer,
    DeviceImageSerializer,
    IntakeRequestCreateSerializer,
    IntakeRequestDetailSerializer,
    IntakeRequestListSerializer,
    PartnerLocationSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegisterSerializer,
    UserSerializer,
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
