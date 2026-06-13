import uuid

from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.shortcuts import redirect, render
from django.views.generic import DetailView, FormView, TemplateView

from .forms import DeviceItemFormSet, IntakeRequestForm, TrackingTokenForm
from .models import DeviceCategory, DeviceImage, IntakeRequest


class RequestNewView(TemplateView):
    """4 алхамт хүсэлт илгээх форм. Бүх талбарууд 1 формд, Alpine.js step-ээр харуулна."""

    template_name = "public/request_new.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["request_form"] = IntakeRequestForm()
        ctx["device_formset"] = DeviceItemFormSet(prefix="dev")
        ctx["categories"] = DeviceCategory.objects.filter(is_active=True)
        ctx["max_images"] = settings.MAX_IMAGES_PER_REQUEST
        return ctx

    def post(self, request, *args, **kwargs):
        request_form = IntakeRequestForm(request.POST)
        device_formset = DeviceItemFormSet(request.POST, prefix="dev")

        # Зочин хүн email заавал өгнө
        if not request.user.is_authenticated:
            request_form.fields["contact_email"].required = True

        if not (request_form.is_valid() and device_formset.is_valid()):
            ctx = self.get_context_data()
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
            intake.save()

            # Олон төхөөрөмж — бөглөгдсөн (хоосон биш) формуудыг хадгална.
            devices = []
            for form in device_formset:
                if not form.has_changed():
                    continue
                device = form.save(commit=False)
                device.intake_request = intake
                device.save()
                devices.append(device)

            # Зургуудыг эхний төхөөрөмжид хавсаргана.
            first_device = devices[0]
            for idx, f in enumerate(request.FILES.getlist("device_images")[: settings.MAX_IMAGES_PER_REQUEST]):
                DeviceImage.objects.create(device_item=first_device, image=f, sort_order=idx)

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
