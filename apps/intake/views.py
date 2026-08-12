import uuid

from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.shortcuts import redirect, render
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


class RequestNewView(TemplateView):
    """2 алхамт хүсэлт илгээх форм. Эхлээд төрөл сонгоно (ажиллагаатай / эвдэрсэн)."""

    template_name = "public/request_new.html"
    choose_template_name = "public/request_choose.html"

    def get(self, request, *args, **kwargs):
        # Төрөл сонгоогүй бол эхлээд сонголтын дэлгэц харуулна.
        if request.GET.get("type") not in REQUEST_TYPE_PARAMS:
            return render(request, self.choose_template_name)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        type_param = self.request.GET.get("type")
        if type_param not in REQUEST_TYPE_PARAMS:
            type_param = "broken"
        ctx["request_type"] = type_param
        # Нэвтэрсэн хэрэглэгчийн профайл дээрх холбоо барих мэдээллээр урьдчилан дүүргэнэ.
        ctx["request_form"] = IntakeRequestForm(initial=contact_initial(self.request.user))
        ctx["device_formset"] = DeviceItemFormSet(prefix="dev")
        ctx["categories"] = DeviceCategory.objects.filter(is_active=True)
        # JS брендийн шүүлтэд: ангиллын id → slug
        ctx["category_slugs"] = {str(c.pk): c.slug for c in ctx["categories"]}
        ctx["max_images"] = settings.MAX_IMAGES_PER_REQUEST
        # Ажиллагаатай утасны флоу — ангилал нь "Гар утас"-аар түгжигдэнэ.
        ctx["phone_category"] = _phone_category()
        return ctx

    def post(self, request, *args, **kwargs):
        request_form = IntakeRequestForm(request.POST)
        device_formset = DeviceItemFormSet(request.POST, prefix="dev")
        request_type = REQUEST_TYPE_PARAMS.get(
            request.POST.get("request_type"), IntakeRequest.RequestType.BROKEN
        )

        # Зочин хүн email заавал өгнө
        if not request.user.is_authenticated:
            request_form.fields["contact_email"].required = True

        if not (request_form.is_valid() and device_formset.is_valid()):
            ctx = self.get_context_data()
            ctx["request_type"] = (
                "working" if request_type == IntakeRequest.RequestType.WORKING else "broken"
            )
            ctx["request_form"] = request_form
            ctx["device_formset"] = device_formset
            messages.error(request, "Маягтыг бүрэн бөглөнө үү.")
            return render(request, self.template_name, ctx)

        with transaction.atomic():
            intake = request_form.save(commit=False)
            if request.user.is_authenticated:
                intake.submitted_by = request.user
                if not intake.contact_email:
                    intake.contact_email = request.user.email
            intake.source = IntakeRequest.Source.WEB
            intake.request_type = request_type
            if not intake.pickup_required:
                intake.pickup_lat = None
                intake.pickup_lng = None
            intake.save()

            # Холбоо барих мэдээллийг профайлд хадгална — дараагийн хүсэлт дээр
            # маягт автоматаар дүүрнэ.
            save_contact_to_profile(request.user, intake)

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

            from apps.quotes.models import StatusHistory

            StatusHistory.objects.create(
                intake_request=intake,
                old_status="",
                new_status=intake.status,
                comment="Хүсэлт үүссэн",
                changed_by=request.user if request.user.is_authenticated else None,
            )

            from apps.notifications.services import (
                notify_new_request_customer,
                notify_new_request_staff,
            )

            notify_new_request_customer(intake)
            notify_new_request_staff(intake)

        messages.success(request, "Хүсэлт амжилттай илгээгдлээ!")
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
