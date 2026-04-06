from django.core.management.base import BaseCommand
from django.utils import timezone

from platform_core.models import AccessRequest, Appointment, AuditLog, CycleRecord, Exam, FAQ, MedicalHistory, User


class Command(BaseCommand):
    help = "Cria dados de demonstracao para o projeto Ciclo & Saude."

    def handle(self, *args, **options):
        admin_user, _ = User.objects.get_or_create(
            email="admin@ciclosaude.local",
            defaults={
                "username": "admin",
                "full_name": "Administradora Ciclo & Saude",
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
            },
        )
        patient.set_password("Paciente123")
        patient.save()

        clinic, _ = User.objects.get_or_create(
            email="clinica@demo.com",
            defaults={
                "username": "clinicademo",
                "full_name": "Clinica Ginecologica Parceira",
                "trade_name": "Clinica Ginecologica Parceira",
                "company_name": "Clinica Parceira LTDA",
                "role": User.Role.CLINIC,
                "cnpj": "12.345.678/0001-90",
                "phone_primary": "(82) 3333-0000",
                "technical_manager": "Dra. Helena Costa",
                "crm": "CRM-AL 1000",
                "city": "Maceio",
                "state": "AL",
                "approval_status": User.ApprovalStatus.APPROVED,
            },
        )
        clinic.set_password("Clinica123")
        clinic.save()

        FAQ.objects.get_or_create(
            question="Como compartilho meus exames com a clinica?",
            defaults={"answer": "Acesse a area de solicitacoes e aprove o pedido da clinica desejada.", "is_active": True},
        )
        FAQ.objects.get_or_create(
            question="Posso revogar o acesso depois?",
            defaults={"answer": "Sim. O acesso pode ser revogado imediatamente pela usuaria.", "is_active": True},
        )

        CycleRecord.objects.get_or_create(
            owner=patient,
            start_date=timezone.localdate() - timezone.timedelta(days=55),
            defaults={"end_date": timezone.localdate() - timezone.timedelta(days=50), "symptoms": "Colica leve"},
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
            action="Aprovacao de clinica",
            defaults={"details": "Clinica liberada para testes.", "level": AuditLog.Level.INFO},
        )

        self.stdout.write(self.style.SUCCESS("Dados demo criados com sucesso."))
