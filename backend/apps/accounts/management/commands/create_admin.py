import getpass

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from allauth.account.models import EmailAddress

User = get_user_model()


class Command(BaseCommand):
    help = "Create (or upgrade) a staff + superuser. The password is typed at a hidden prompt, never passed as an argument."

    def add_arguments(self, parser):
        parser.add_argument("email")

    def handle(self, *args, **options):
        email = options["email"].strip().lower()
        password = getpass.getpass("Password: ")
        if password != getpass.getpass("Password (again): "):
            raise CommandError("Passwords do not match.")
        try:
            validate_password(password, User(email=email))
        except ValidationError as exc:
            raise CommandError(" ".join(exc.messages))

        user = User.objects.filter(email__iexact=email).first()
        created = user is None
        if created:
            user = User.objects.create_superuser(email=email, password=password)
        else:
            user.set_password(password)
            user.is_staff = user.is_superuser = user.is_active = True
            user.save()
        EmailAddress.objects.update_or_create(user=user, email=user.email, defaults={"primary": True, "verified": True})
        self.stdout.write(self.style.SUCCESS(f"{'Created' if created else 'Upgraded'} admin {email}"))
