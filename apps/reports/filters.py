import django_filters
from django import forms
from django_filters import rest_framework as drf  # noqa: F401

from apps.branches.models import Branch
from apps.intake.models import IntakeRequest


class IntakeRequestFilter(django_filters.FilterSet):
    q = django_filters.CharFilter(method="search", label="Хайх")
    status = django_filters.ChoiceFilter(
        choices=IntakeRequest.Status.choices,
        widget=forms.Select(attrs={"class": "rounded border px-2 py-1 text-sm"}),
    )
    preferred_branch = django_filters.ModelChoiceFilter(
        queryset=Branch.objects.filter(is_active=True),
        widget=forms.Select(attrs={"class": "rounded border px-2 py-1 text-sm"}),
    )
    created_at__gte = django_filters.DateFilter(
        field_name="created_at",
        lookup_expr="gte",
        widget=forms.DateInput(attrs={"type": "date", "class": "rounded border px-2 py-1 text-sm"}),
        label="Эхлэх огноо",
    )
    created_at__lte = django_filters.DateFilter(
        field_name="created_at",
        lookup_expr="lte",
        widget=forms.DateInput(attrs={"type": "date", "class": "rounded border px-2 py-1 text-sm"}),
        label="Дуусах огноо",
    )

    class Meta:
        model = IntakeRequest
        fields = ["status", "preferred_branch"]

    def search(self, queryset, name, value):
        from django.db.models import Q

        return queryset.filter(
            Q(request_code__icontains=value)
            | Q(contact_name__icontains=value)
            | Q(contact_phone__icontains=value)
            | Q(contact_email__icontains=value)
            | Q(company_name__icontains=value)
        )
