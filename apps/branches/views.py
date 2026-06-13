from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from apps.accounts.views import staff_required

from .models import Branch, PartnerLocation


def _to_decimal(value):
    """Parse a coordinate string to a value the DecimalField accepts, else None."""
    if value in (None, ""):
        return None
    try:
        return round(float(value), 6)
    except (TypeError, ValueError):
        return None


def branch_list(request):
    branches = Branch.objects.filter(is_active=True).prefetch_related("gallery")
    partners = PartnerLocation.objects.filter(is_active=True)
    return render(
        request,
        "public/branches.html",
        {"branches": branches, "partners": partners},
    )


def branch_detail(request, code):
    branch = get_object_or_404(Branch.objects.prefetch_related("gallery"), code=code)
    return render(request, "public/branch_detail.html", {"branch": branch})


@staff_required
@require_POST
def branch_edit(request, code):
    """Inline edit of a branch from the public branches page (staff only)."""
    branch = get_object_or_404(Branch, code=code)

    branch.name = request.POST.get("name", branch.name).strip() or branch.name
    branch.address_line = request.POST.get("address_line", branch.address_line).strip()
    branch.district = request.POST.get("district", branch.district).strip()
    branch.working_hours = request.POST.get("working_hours", branch.working_hours).strip()
    branch.description = request.POST.get("description", branch.description).strip()

    phones_raw = request.POST.get("phones", "")
    branch.phones = [p.strip() for p in phones_raw.split(",") if p.strip()]

    branch.is_active = request.POST.get("is_active") == "1"

    branch.latitude = _to_decimal(request.POST.get("latitude"))
    branch.longitude = _to_decimal(request.POST.get("longitude"))

    if request.FILES.get("cover_image"):
        branch.cover_image = request.FILES["cover_image"]

    branch.save()
    messages.success(request, f"«{branch.name}» салбар шинэчлэгдлээ.")
    nxt = request.POST.get("next", "")
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
        return redirect(nxt)
    return redirect("branches:list")
