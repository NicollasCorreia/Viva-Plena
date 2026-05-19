from django.core.management.base import BaseCommand
from django.utils import timezone

from platform_core.models import User


class Command(BaseCommand):
    help = "Cria apenas as contas demo principais do projeto Viva Plena."

    def handle(self, *args, **options):
        admin_user, _ = User.objects.get_or_create(
            email="admin@vivaplena.local",
            defaults={
                "username": "admin",
                "full_name": "Administradora Viva Plena",
                "role": User.Role.ADMIN,
                "approval_status": User.ApprovalStatus.APPROVED,
                "is_staff": True,
                "is_superuser": True,
            },
        )
        admin_user.set_password("Admin12345")
        admin_user.save()

        patient, _ = User.objects.get_or_create(
            email="maria@demo.com",
            defaults={
                "username": "maria",
                "full_name": "Maria Eduarda Lima",
                "role": User.Role.PATIENT,
                "cpf": "123.456.789-00",
                "phone_primary": "(82) 99999-0000",
                "city": "Maceio",
                "state": "AL",
                "approval_status": User.ApprovalStatus.APPROVED,
                "consent_accepted_at": timezone.now(),
                "institution_name": "CESMAC",
            },
        )
        patient.set_password("Paciente123")
        patient.save()

        clinic, _ = User.objects.get_or_create(
            email="helena@demo.com",
            defaults={
                "username": "helenacosta",
                "full_name": "Dra. Helena Costa",
                "trade_name": "Dra. Helena Costa",
                "company_name": "CESMAC",
                "role": User.Role.CLINIC,
                "phone_primary": "(82) 3333-0000",
                "crm": "CRM-AL 1000",
                "specialty": "Ginecologia",
                "institution_name": "CESMAC",
                "city": "Maceio",
                "state": "AL",
                "approval_status": User.ApprovalStatus.APPROVED,
            },
        )
        clinic.set_password("Clinica123")
        clinic.save()

        self.stdout.write(
            self.style.SUCCESS(
                "Contas demo criadas com sucesso, sem exames, ciclos, mensagens ou outros dados preenchidos."
            )
        )
