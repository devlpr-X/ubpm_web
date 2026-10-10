import uuid

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.views.generic import DetailView, FormView, TemplateView

from apps.accounts.contact import contact_initial, save_contact_to_profile

from .forms import DeviceItemFormSet, IntakeRequestForm, TrackingTokenForm
from .models import DeviceCategory, DeviceImage, IntakeRequest

REQUEST_TYPE_PARAMS = {
    "working": IntakeRequest.RequestType.WORKING,
    "broken": IntakeRequest.RequestType.BROKEN,
}


def _phone_category():
    """«Гар утас» ангилал (ажиллагаатай утасны флоуд автоматаар сонгогдоно)."""
    return (
        DeviceCategory.objects.filter(is_active=True, slug="phone").first()
        or DeviceCategory.objects.filter(is_active=True, name__icontains="утас").first()
    )


def request_form_context(request, request_type, request_form=None, device_formset=None):
    """Үнэ асуух маягтын контекст — вэбийн болон ажилтны (dashboard) хуудас хоёулаа ашиглана."""
    categories = DeviceCategory.objects.filter(is_active=True)
    return {
        "request_type": request_type,
        "request_form": request_form or IntakeRequestForm(),
        "device_formset": device_formset or DeviceItemFormSet(prefix="dev"),
        "categories": categories,
        # JS брендийн шүүлтэд: ангиллын id → slug
        "category_slugs": {str(c.pk): c.slug for c in categories},
        "max_images": settings.MAX_IMAGES_PER_REQUEST,
        # Ажиллагаатай утасны флоу — ангилал нь "Гар утас"-аар түгжигдэнэ.
        "phone_category": _phone_category(),
    }


def parse_request_type(raw):
    """`working` / `broken` → (параметр, RequestType). Бусад нь эвдэрсэн гэж үзнэ."""
    param = raw if raw in REQUEST_TYPE_PARAMS else "broken"
    return param, REQUEST_TYPE_PARAMS[param]


def save_intake_request(
    request, request_form, device_formset, request_type, *, submitted_by, source, comment
):
    """Баталгаажсан маягтаас хүсэлт, төхөөрөмж, зураг, түүхийг хадгалаад мэдэгдэл илгээнэ."""
    from apps.notifications.services import notify_new_request_customer, notify_new_request_staff
    from apps.quotes.models import StatusHistory

    with transaction.atomic():
        intake = request_form.save(commit=False)
        intake.submitted_by = submitted_by
        if not intake.contact_email and submitted_by is not None:
            intake.contact_email = submitted_by.email
        intake.source = source
        intake.request_type = request_type
        if not intake.pickup_required:
            intake.pickup_lat = None
            intake.pickup_lng = None
        intake.save()

        # Олон төхөөрөмж — бөглөгдсөн (хоосон биш) формуудыг хадгална.
        # Зургууд төхөөрөмж бүрийн доор "<prefix>-images" нэрээр ирнэ.
        phone_cat = _phone_category()
        for form in device_formset:
            if not form.has_changed():
                continue
            device = form.save(commit=False)
            device.intake_request = intake
            # Ажиллагаатай утас — ангилал үргэлж "Гар утас".
            if request_type == IntakeRequest.RequestType.WORKING and phone_cat:
                device.category = phone_cat
            device.save()
            files = request.FILES.getlist(f"{form.prefix}-images")
            for idx, f in enumerate(files[: settings.MAX_IMAGES_PER_REQUEST]):
                DeviceImage.objects.create(device_item=device, image=f, sort_order=idx)

        StatusHistory.objects.create(
            intake_request=intake,
            old_status="",
            new_status=intake.status,
            comment=comment,
            changed_by=request.user,
        )

        notify_new_request_customer(intake)
        notify_new_request_staff(intake)
    return intake


class RequestNewView(TemplateView):
    """2 алхамт хүсэлт илгээх форм. Эхлээд төрөл сонгоно (ажиллагаатай / эвдэрсэн).

    Үнэ асуухад бүртгэл заавал. Төрөл сонгох дэлгэц нь нээлттэй (хайлтын
    системд индексжинэ), харин маягт болон илгээх хэсэг нэвтрэлт шаардана —
    нэвтрээгүй хүнийг сонгосон төрлөөр нь буцаах `next`-тэй нэвтрэх хуудас
    руу явуулна.
    """

    template_name = "public/request_new.html"
    choose_template_name = "public/request_choose.html"

    def get(self, request, *args, **kwargs):
        # Төрөл сонгоогүй бол эхлээд сонголтын дэлгэц харуулна.
        if request.GET.get("type") not in REQUEST_TYPE_PARAMS:
            return render(request, self.choose_template_name)
        if not request.user.is_authenticated:
            return self._login_first(request)
        return super().get(request, *args, **kwargs)

    def _login_first(self, request):
        messages.info(request, "Үнэ асуухын тулд нэвтэрнэ үү. Бүртгэлгүй бол бүртгүүлээрэй.")
        return redirect_to_login(request.get_full_path())

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        type_param, _ = parse_request_type(self.request.GET.get("type"))
        # Профайл дээрх холбоо барих мэдээллээр урьдчилан дүүргэнэ.
        ctx.update(
            request_form_context(
                self.request,
                type_param,
                IntakeRequestForm(initial=contact_initial(self.request.user)),
            )
        )
        return ctx

    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self._login_first(request)
        request_form = IntakeRequestForm(request.POST)
        device_formset = DeviceItemFormSet(request.POST, prefix="dev")
        type_param, request_type = parse_request_type(request.POST.get("request_type"))

        if not (request_form.is_valid() and device_formset.is_valid()):
            messages.error(request, "Маягтыг бүрэн бөглөнө үү.")
            ctx = request_form_context(request, type_param, request_form, device_formset)
            return render(request, self.template_name, ctx)

        intake = save_intake_request(
            request,
            request_form,
            device_formset,
            request_type,
            submitted_by=request.user,
            source=IntakeRequest.Source.WEB,
            comment="Хүсэлт үүссэн",
        )
        # Холбоо барих мэдээллийг профайлд хадгална — дараагийн хүсэлт дээр
        # маягт автоматаар дүүрнэ.
        save_contact_to_profile(request.user, intake)

        messages.success(
            request,
            "Хүсэлт амжилттай илгээгдлээ! Та хүсэлтээ бүртгэлээрээ «Миний хүсэлтүүд» хэсгээс шалгана уу.",
        )
        return redirect("intake:submitted", token=str(intake.tracking_token))


class RequestSubmittedView(DetailView):
    template_name = "public/request_submitted.html"
    context_object_name = "request_obj"
    slug_field = "tracking_token"
    slug_url_kwarg = "token"
    model = IntakeRequest


class TrackEntryView(FormView):
    template_name = "public/track_entry.html"
    form_class = TrackingTokenForm

    def form_valid(self, form):
        raw = form.cleaned_data["token"].strip()
        try:
            token = uuid.UUID(raw)
        except (ValueError, TypeError):
            messages.error(self.request, "Кодны формат буруу байна.")
            return self.form_invalid(form)
        if not IntakeRequest.objects.filter(tracking_token=token).exists():
            messages.error(self.request, "Хүсэлт олдсонгүй.")
            return self.form_invalid(form)
        return redirect("intake:track_detail", token=str(token))


class TrackDetailView(DetailView):
    template_name = "public/track_detail.html"
    context_object_name = "request_obj"
    slug_field = "tracking_token"
    slug_url_kwarg = "token"
    model = IntakeRequest

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["history"] = self.object.history.all()
        ctx["latest_quote"] = self.object.quotes.order_by("-created_at").first()
        return ctx


@require_POST
def track_accept(request, token):
    """Хэрэглэгч өөрийн хүсэлтийн үнэ саналыг хянах хуудаснаасаа зөвшөөрнө.

    Нэвтрэх шаардлагагүй — хаяг дахь tracking_token нь өөрөө нууц түлхүүр
    (хүсэлтийг харах эрх ч мөн үүгээр олгогддог). Апп/API-гийн accept-той ижил
    төлөвт (Зөвшөөрсөн) оруулж, түүхэнд бичлэг үлдээнэ.

    Үнэ саналын хүчинтэй хугацаа өнгөрсөн эсэхийг ЗОРИУД шалгахгүй — хүмүүс
    захиагаа хожуу нээдэг бөгөөд тэр болгонд дахин үнэ илгээж шинээр эхлэхээс
    аль аль талдаа холбогдсон нь дээр.
    """
    from apps.notifications.services import notify_quote_accepted
    from apps.quotes.models import StatusHistory

    intake = get_object_or_404(IntakeRequest, tracking_token=token)
    if intake.status != IntakeRequest.Status.PRICE_SENT:
        messages.error(request, "Энэ хүсэлтэд одоогоор хариу өгөх боломжгүй байна.")
        return redirect("intake:track_detail", token=str(token))

    old = intake.status
    intake.status = IntakeRequest.Status.APPROVED
    intake.save(update_fields=["status", "updated_at"])
    StatusHistory.objects.create(
        intake_request=intake,
        old_status=old,
        new_status=intake.status,
        comment="Хэрэглэгч үнийг зөвшөөрсөн",
        changed_by=request.user if request.user.is_authenticated else None,
    )
    # Зөвшөөрөл өгсөн даруйд ажилтан/админ хайрцаг руу мэдэгдэнэ — хэн нэгэн
    # хянах самбараа нээх хүртэл хүлээх шалтгаангүй.
    notify_quote_accepted(intake)
    messages.success(request, "Та үнэ саналыг зөвшөөрлөө. Бид тун удахгүй холбогдоно.")
    return redirect("intake:track_detail", token=str(token))
