from django.core.management.base import BaseCommand
from django.utils import timezone

from platform_core.models import AccessRequest, Appointment, AuditLog, CycleRecord, Exam, FAQ, MedicalHistory, User


class Command(BaseCommand):
    help = "Cria dados de demonstração para o projeto Viva Plena."

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
                "city": "Maceió",
                "state": "AL",
                "approval_status": User.ApprovalStatus.APPROVED,
                "consent_accepted_at": timezone.now(),
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
                "city": "Maceió",
                "state": "AL",
                "approval_status": User.ApprovalStatus.APPROVED,
            },
        )
        clinic.set_password("Clinica123")
        clinic.save()

        FAQ.objects.get_or_create(
            question="Como libero meus exames para uma profissional?",
            defaults={"answer": "Abra a área de privacidade e autorize o pedido da profissional do CESMAC que você deseja liberar.", "is_active": True},
        )
        FAQ.objects.get_or_create(
            question="Posso encerrar esse acesso depois?",
            defaults={"answer": "Sim. Você pode encerrar o acesso a qualquer momento, com efeito imediato.", "is_active": True},
        )

        CycleRecord.objects.get_or_create(
            owner=patient,
            start_date=timezone.localdate() - timezone.timedelta(days=55),
            defaults={"end_date": timezone.localdate() - timezone.timedelta(days=50), "symptoms": "Cólica leve"},
        )
        CycleRecord.objects.get_or_create(
            owner=patient,
            start_date=timezone.localdate() - timezone.timedelta(days=28),
            defaults={"end_date": timezone.localdate() - timezone.timedelta(days=24), "symptoms": "Fluxo moderado"},
        )

        MedicalHistory.objects.get_or_create(
            patient=patient,
            info_type=MedicalHistory.InfoType.ALLERGY,
            description="Alergia a dipirona",
            defaults={"record_date": timezone.localdate()},
        )

        AccessRequest.objects.get_or_create(
            clinic=clinic,
            patient=patient,
            defaults={"status": AccessRequest.Status.APPROVED, "responded_at": timezone.now()},
        )

        Appointment.objects.get_or_create(
            patient=patient,
            clinic=clinic,
            specialist="Dra. Helena Costa",
            scheduled_for=timezone.now() + timezone.timedelta(days=3),
            defaults={"status": Appointment.Status.SCHEDULED},
        )

        AuditLog.objects.get_or_create(
            actor=admin_user,
            target_user=clinic,
            action="Aprovação profissional",
            defaults={"details": "Profissional liberada para testes.", "level": AuditLog.Level.INFO},
        )

        self.stdout.write(self.style.SUCCESS("Dados de demonstração criados com sucesso."))
