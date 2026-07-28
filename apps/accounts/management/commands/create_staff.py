"""Create or update a staff user (ADMIN / MANAGER / OPERATOR) for the app/web.

Staff accounts cannot be created from the public app (registration always makes
a CUSTOMER), so use this command to provision dashboard/admin logins.

Example:
    python manage.py create_staff --email admin@ubpm.mn --pin 1234 --role ADMIN \
        --name "Админ"
"""

import re

from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import User

ROLES = {User.Role.ADMIN, User.Role.MANAGER, User.Role.OPERATOR}


class Command(BaseCommand):
    help = "Create or update a staff user (ADMIN/MANAGER/OPERATOR) with a 4-digit PIN."

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True)
        parser.add_argument("--pin", required=True, help="4 оронтой тоо (ж: 1234)")
        parser.add_argument(
            "--role", default=User.Role.ADMIN, choices=sorted(ROLES)
        )
        parser.add_argument("--name", default="", help="Бүтэн нэр (optional)")

    def handle(self, *args, **opts):
        email = opts["email"].lower().strip()
        pin = opts["pin"].strip()
        role = opts["role"]
        name = opts["name"].strip()

        if not re.fullmatch(r"\d{4}", pin):
            raise CommandError("PIN яг 4 оронтой тоо байх ёстой (ж: 1234).")

        user, created = User.objects.get_or_create(email=email)
        user.role = role
        user.is_staff = True  # access to /admin and marks an internal account
        if name:
            user.full_name = name
        user.set_password(pin)
        user.save()

        verb = "created" if created else "updated"
        # ASCII-only output: the Windows console (cp1252) cannot encode Cyrillic.
        self.stdout.write(
            self.style.SUCCESS(
                f"Staff {verb}: {email} (role={role}); sign in with the 4-digit PIN."
            )
        )
