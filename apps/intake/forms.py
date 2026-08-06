from django import forms
from django.forms import formset_factory

from apps.branches.models import Branch

from .models import DeviceCategory, DeviceItem, IntakeRequest

INPUT = "w-full rounded-md border border-gray-300 px-3 py-2 focus:border-brand-500 focus:ring-1 focus:ring-brand-500"
SELECT = INPUT


class IntakeRequestForm(forms.ModelForm):
    """Step 4: contact + branch."""

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
            "pickup_required",
            "pickup_lat",
            "pickup_lng",
        )
        widgets = {
            "customer_type": forms.Select(attrs={"class": SELECT}),
            "contact_name": forms.TextInput(attrs={"class": INPUT}),
            "company_name": forms.TextInput(attrs={"class": INPUT}),
            "contact_phone": forms.TextInput(
                attrs={"class": INPUT, "inputmode": "numeric", "placeholder": "99XX-XXXX"}
            ),
            "contact_email": forms.EmailInput(
                attrs={"class": INPUT, "inputmode": "email", "placeholder": "you@example.com"}
            ),
            "city": forms.TextInput(attrs={"class": INPUT}),
            "district": forms.TextInput(attrs={"class": INPUT}),
            "address_line": forms.TextInput(attrs={"class": INPUT}),
            "preferred_branch": forms.Select(attrs={"class": SELECT}),
            "pickup_lat": forms.HiddenInput(),
            "pickup_lng": forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["preferred_branch"].queryset = Branch.objects.filter(is_active=True)
        self.fields["preferred_branch"].empty_label = "— Сонгоно уу —"
        self.fields["company_name"].required = False
        self.fields["contact_email"].required = False  # required only for guests (validated in view)

    def clean(self):
        data = super().clean()
        if data.get("customer_type") == IntakeRequest.CustomerType.COMPANY and not data.get(
            "company_name"
        ):
            self.add_error("company_name", "Компанийн нэрийг бөглөнө үү")
        return data


class DeviceItemForm(forms.ModelForm):
    """Step 1+2: device + condition (one item per submission for MVP)."""

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
        widgets = {
            "category": forms.Select(attrs={"class": SELECT}),
            "brand": forms.TextInput(attrs={"class": INPUT, "placeholder": "Apple, Samsung, ..."}),
            "model": forms.TextInput(attrs={"class": INPUT, "placeholder": "iPhone 12, Galaxy S21"}),
            "quantity": forms.NumberInput(attrs={"class": INPUT, "inputmode": "numeric", "min": 1}),
            "storage": forms.TextInput(attrs={"class": INPUT, "placeholder": "128GB"}),
            "color": forms.TextInput(attrs={"class": INPUT}),
            "imei_or_serial": forms.TextInput(
                attrs={"class": INPUT, "placeholder": "IMEI (заавал биш)"}
            ),
            "power_on_status": forms.Select(attrs={"class": SELECT}),
            "screen_status": forms.Select(attrs={"class": SELECT}),
            "battery_status": forms.Select(attrs={"class": SELECT}),
            "body_status": forms.Select(attrs={"class": SELECT}),
            "accessories": forms.TextInput(
                attrs={"class": INPUT, "placeholder": "Цэнэглэгч, хайрцаг г.м"}
            ),
            "issue_description": forms.Textarea(
                attrs={"class": INPUT, "rows": 3, "placeholder": "Нэмэлт мэдээлэл, тайлбар..."}
            ),
        }

    # Ажиллагаатай утасны флоу эдгээр талбарыг харуулдаггүй тул хоосон ирвэл
    # моделийн default утгыг онооно.
    CONDITION_DEFAULTS = {
        "power_on_status": DeviceItem.PowerStatus.UNKNOWN,
        "screen_status": DeviceItem.ScreenStatus.OK,
        "battery_status": DeviceItem.BatteryStatus.UNKNOWN,
        "body_status": DeviceItem.BodyStatus.OK,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = DeviceCategory.objects.filter(is_active=True)
        self.fields["category"].empty_label = "— Сонгоно уу —"
        self.fields["issue_description"].label = "Дэлгэрэнгүй"
        for name in self.CONDITION_DEFAULTS:
            self.fields[name].required = False

    def clean(self):
        data = super().clean()
        for name, default in self.CONDITION_DEFAULTS.items():
            if not data.get(name):
                data[name] = default
        return data


# Нэг хүсэлтээр олон төхөөрөмж зарах боломжтой — динамик formset.
DeviceItemFormSet = formset_factory(
    DeviceItemForm, extra=1, min_num=1, validate_min=True, can_delete=False
)


class TrackingTokenForm(forms.Form):
    token = forms.CharField(
        label="Tracking код",
        max_length=64,
        widget=forms.TextInput(
            attrs={"class": INPUT, "placeholder": "12345678-..."}
        ),
    )
