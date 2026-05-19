import shutil
from datetime import datetime, time, timedelta
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from .models import AccessRequest, Appointment, AuditLog, Exam, FAQ, Notification, SecureMessage, User


class SmokeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User.objects.create_user(
            email="paciente@test.com",
            username="paciente",
            full_name="Paciente Teste",
            role=User.Role.PATIENT,
            password="Paciente123",
        )
        User.objects.create_user(
            email="clinica@test.com",
            username="clinica",
            full_name="Clinica Teste",
            role=User.Role.CLINIC,
            approval_status=User.ApprovalStatus.APPROVED,
            password="Clinica123",
        )
        User.objects.create_user(
            email="admin@test.com",
            username="admin",
            full_name="Admin Teste",
            role=User.Role.ADMIN,
            approval_status=User.ApprovalStatus.APPROVED,
            is_staff=True,
            password="Admin123",
        )

    def test_public_pages(self):
        client = Client()
        self.assertEqual(client.get("/").status_code, 200)
        self.assertEqual(client.get("/entrar/").status_code, 200)
        self.assertEqual(client.get("/faq/").status_code, 200)

    def test_role_dashboards(self):
        client = Client()
        self.assertTrue(client.login(email="paciente@test.com", password="Paciente123"))
        self.assertEqual(client.get("/paciente/").status_code, 200)

        client = Client()
        self.assertTrue(client.login(email="clinica@test.com", password="Clinica123"))
        self.assertEqual(client.get("/profissional/").status_code, 200)

        client = Client()
        self.assertTrue(client.login(email="admin@test.com", password="Admin123"))
        self.assertEqual(client.get("/gerenciador/").status_code, 200)

    def test_legacy_web_paths_redirect_to_canonical_routes(self):
        client = Client()

        mobile_response = client.get("/mobile/")
        self.assertEqual(mobile_response.status_code, 302)
        self.assertTrue(mobile_response.headers["Location"].endswith("/paciente/"))

        clinic_response = client.get("/clinica/")
        self.assertEqual(clinic_response.status_code, 302)
        self.assertTrue(clinic_response.headers["Location"].endswith("/profissional/"))

        register_response = client.get("/cadastro/clinica/")
        self.assertEqual(register_response.status_code, 302)
        self.assertTrue(register_response.headers["Location"].endswith("/cadastro/profissional/"))

    def test_admin_can_toggle_faq_status(self):
        faq = FAQ.objects.create(question="FAQ Toggle", answer="Resposta", is_active=True)
        client = Client()
        self.assertTrue(client.login(email="admin@test.com", password="Admin123"))
        response = client.post("/gerenciador/faq/", {"action": "toggle_status", "faq_id": faq.id}, follow=True)
        self.assertEqual(response.status_code, 200)
        faq.refresh_from_db()
        self.assertFalse(faq.is_active)

    def test_professional_can_cancel_scheduled_appointment(self):
        patient = User.objects.get(email="paciente@test.com")
        clinic = User.objects.get(email="clinica@test.com")
        appointment = Appointment.objects.create(
            patient=patient,
            clinic=clinic,
            specialist="Consulta escondida apos cancelamento",
            scheduled_for=timezone.make_aware(
                datetime.combine(timezone.localdate() + timedelta(days=2), time(hour=10))
            ),
        )

        client = Client()
        self.assertTrue(client.login(email="clinica@test.com", password="Clinica123"))
        response = client.post(
            "/profissional/consultas/",
            {"action": "cancel_appointment", "appointment_id": appointment.id},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, Appointment.Status.CANCELLED)
        self.assertNotIn(appointment.id, [item.id for item in response.context["appointments"]])
        self.assertNotContains(response, "Consulta escondida apos cancelamento")
        self.assertTrue(
            Notification.objects.filter(
                recipient=patient,
                type=Notification.Type.APPOINTMENT,
                message__icontains="cancelada",
            ).exists()
        )

    def test_admin_can_create_new_admin_account(self):
        client = Client()
        self.assertTrue(client.login(email="admin@test.com", password="Admin123"))

        response = client.post(
            "/gerenciador/contas/",
            {
                "action": "create_admin",
                "full_name": "Nova Administradora",
                "email": "nova-admin@test.com",
                "password1": "AdminNova123",
                "password2": "AdminNova123",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        new_admin = User.objects.get(email="nova-admin@test.com")
        self.assertEqual(new_admin.role, User.Role.ADMIN)
        self.assertTrue(new_admin.is_active)
        self.assertTrue(new_admin.is_staff)
        self.assertFalse(new_admin.is_superuser)
        self.assertTrue(
            AuditLog.objects.filter(
                action="Criação de administradora",
                target_user=new_admin,
            ).exists()
        )

    def test_admin_can_promote_existing_user_to_admin(self):
        target = User.objects.get(email="paciente@test.com")
        client = Client()
        self.assertTrue(client.login(email="admin@test.com", password="Admin123"))

        response = client.post(
            "/gerenciador/contas/",
            {"action": "promote_admin", "user_id": target.id},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        target.refresh_from_db()
        self.assertEqual(target.role, User.Role.ADMIN)
        self.assertTrue(target.is_active)
        self.assertTrue(target.is_staff)
        self.assertTrue(
            AuditLog.objects.filter(
                action="Promoção para administradora",
                target_user=target,
            ).exists()
        )

    def test_admin_can_suspend_reactivate_and_demote_other_admin(self):
        other_admin = User.objects.create_user(
            email="outra-admin@test.com",
            username="outra-admin",
            full_name="Outra Admin",
            role=User.Role.ADMIN,
            approval_status=User.ApprovalStatus.APPROVED,
            is_staff=True,
            password="OutraAdmin123",
        )
        client = Client()
        self.assertTrue(client.login(email="admin@test.com", password="Admin123"))

        suspend_response = client.post(
            "/gerenciador/contas/",
            {"action": "suspend_admin", "user_id": other_admin.id},
            follow=True,
        )
        self.assertEqual(suspend_response.status_code, 200)
        other_admin.refresh_from_db()
        self.assertFalse(other_admin.is_active)
        self.assertEqual(other_admin.approval_status, User.ApprovalStatus.SUSPENDED)

        reactivate_response = client.post(
            "/gerenciador/contas/",
            {"action": "reactivate_admin", "user_id": other_admin.id},
            follow=True,
        )
        self.assertEqual(reactivate_response.status_code, 200)
        other_admin.refresh_from_db()
        self.assertTrue(other_admin.is_active)
        self.assertEqual(other_admin.approval_status, User.ApprovalStatus.APPROVED)

        demote_response = client.post(
            "/gerenciador/contas/",
            {"action": "demote_admin", "user_id": other_admin.id, "target_role": User.Role.PATIENT},
            follow=True,
        )
        self.assertEqual(demote_response.status_code, 200)
        other_admin.refresh_from_db()
        self.assertEqual(other_admin.role, User.Role.PATIENT)
        self.assertFalse(other_admin.is_staff)
        self.assertFalse(other_admin.is_superuser)
        self.assertTrue(
            AuditLog.objects.filter(
                action="Rebaixamento de administradora",
                target_user=other_admin,
            ).exists()
        )

    def test_admin_cannot_suspend_own_account_from_management_screen(self):
        admin = User.objects.get(email="admin@test.com")
        client = Client()
        self.assertTrue(client.login(email="admin@test.com", password="Admin123"))

        response = client.post(
            "/gerenciador/contas/",
            {"action": "suspend_admin", "user_id": admin.id},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        admin.refresh_from_db()
        self.assertTrue(admin.is_active)
        self.assertEqual(admin.role, User.Role.ADMIN)


class ApiTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.patient = User.objects.create_user(
            email="api-paciente@test.com",
            username="api-paciente",
            full_name="Paciente API",
            role=User.Role.PATIENT,
            cpf="111.222.333-44",
            consent_accepted_at=timezone.now(),
            password="Paciente123",
        )
        cls.clinic = User.objects.create_user(
            email="api-clinica@test.com",
            username="api-clinica",
            full_name="Clinica API",
            role=User.Role.CLINIC,
            cnpj="11.222.333/0001-44",
            approval_status=User.ApprovalStatus.APPROVED,
            password="Clinica123",
        )
        cls.admin = User.objects.create_user(
            email="api-admin@test.com",
            username="api-admin",
            full_name="Admin API",
            role=User.Role.ADMIN,
            approval_status=User.ApprovalStatus.APPROVED,
            is_staff=True,
            password="Admin123",
        )
        FAQ.objects.create(question="FAQ Teste", answer="Resposta teste", is_active=True)
        AccessRequest.objects.create(clinic=cls.clinic, patient=cls.patient, status=AccessRequest.Status.PENDING)
        Appointment.objects.create(
            patient=cls.patient,
            clinic=cls.clinic,
            specialist="Ginecologia",
            scheduled_for=timezone.make_aware(datetime.combine(timezone.localdate() + timedelta(days=3), time(hour=14))),
        )

    def authenticate(self, email, password):
        response = self.client.post("/api/auth/token/", {"email": email, "password": password}, format="json")
        self.assertEqual(response.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {response.data['token']}")
        return response

    def test_public_api_endpoints(self):
        self.assertEqual(self.client.get("/api/health/").status_code, 200)
        faq_response = self.client.get("/api/faqs/")
        self.assertEqual(faq_response.status_code, 200)
        self.assertEqual(len(faq_response.data), 1)
        clinic_response = self.client.get("/api/clinics/")
        self.assertEqual(clinic_response.status_code, 200)
        self.assertEqual(len(clinic_response.data), 1)

    def test_patient_registration_api(self):
        response = self.client.post(
            "/api/auth/register/patient/",
            {
                "full_name": "Nova Paciente",
                "email": "nova-paciente@test.com",
                "password": "Paciente123",
                "cpf": "555.666.777-88",
                "phone_primary": "82999999999",
                "city": "Maceio",
                "state": "AL",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)

    def test_patient_api_flow(self):
        self.authenticate("api-paciente@test.com", "Paciente123")
        me_response = self.client.get("/api/me/")
        self.assertEqual(me_response.status_code, 200)
        dashboard_response = self.client.get("/api/patient/dashboard/")
        self.assertEqual(dashboard_response.status_code, 200)
        access_response = self.client.get("/api/patient/access-requests/")
        self.assertEqual(access_response.status_code, 200)
        self.assertEqual(len(access_response.data), 1)

    def test_patient_can_view_secure_messages(self):
        SecureMessage.objects.create(
            sender=self.clinic,
            recipient=self.patient,
            body="Seu exame foi analisado e esta tudo certo.",
        )

        self.authenticate("api-paciente@test.com", "Paciente123")
        response = self.client.get("/api/patient/messages/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["body"], "Seu exame foi analisado e esta tudo certo.")
        self.assertEqual(response.data[0]["sender"]["id"], self.clinic.id)

    def test_patient_cannot_schedule_appointment_via_api(self):
        self.authenticate("api-paciente@test.com", "Paciente123")
        existing_count = Appointment.objects.filter(patient=self.patient).count()

        response = self.client.post(
            "/api/patient/appointments/",
            {
                "professional_id": self.clinic.id,
                "specialist": "Retorno",
                "scheduled_for": (
                    timezone.make_aware(
                        datetime.combine(timezone.localdate() + timedelta(days=5), time(hour=10))
                    ).isoformat()
                ),
            },
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertIn("apenas pela profissional", response.data["detail"])
        self.assertEqual(Appointment.objects.filter(patient=self.patient).count(), existing_count)

    def test_patient_can_hide_cancelled_appointment_from_mobile_list(self):
        cancelled_appointment = Appointment.objects.create(
            patient=self.patient,
            clinic=self.clinic,
            specialist="Consulta cancelada",
            scheduled_for=timezone.make_aware(datetime.combine(timezone.localdate() + timedelta(days=7), time(hour=11))),
            status=Appointment.Status.CANCELLED,
        )

        self.authenticate("api-paciente@test.com", "Paciente123")

        initial_response = self.client.get("/api/patient/appointments/")
        self.assertEqual(initial_response.status_code, 200)
        self.assertIn(cancelled_appointment.id, [item["id"] for item in initial_response.data])

        delete_response = self.client.delete(f"/api/patient/appointments/{cancelled_appointment.id}/")
        self.assertEqual(delete_response.status_code, 204)

        cancelled_appointment.refresh_from_db()
        self.assertIsNotNone(cancelled_appointment.hidden_by_patient_at)

        second_response = self.client.get("/api/patient/appointments/")
        self.assertEqual(second_response.status_code, 200)
        self.assertNotIn(cancelled_appointment.id, [item["id"] for item in second_response.data])

    def test_patient_can_delete_only_read_notifications(self):
        read_notification = Notification.objects.create(
            recipient=self.patient,
            type=Notification.Type.ADMIN,
            message="Aviso ja lido",
            read_at=timezone.now(),
        )
        unread_notification = Notification.objects.create(
            recipient=self.patient,
            type=Notification.Type.ADMIN,
            message="Aviso ainda nao lido",
        )

        self.authenticate("api-paciente@test.com", "Paciente123")

        unread_delete_response = self.client.delete(f"/api/patient/notifications/{unread_notification.id}/")
        self.assertEqual(unread_delete_response.status_code, 400)
        self.assertTrue(Notification.objects.filter(pk=unread_notification.id).exists())

        read_delete_response = self.client.delete(f"/api/patient/notifications/{read_notification.id}/")
        self.assertEqual(read_delete_response.status_code, 204)
        self.assertFalse(Notification.objects.filter(pk=read_notification.id).exists())

    def test_patient_can_delete_exam_and_deleted_exam_leaves_listing(self):
        media_root = Path(__file__).resolve().parent.parent / "test_media_root"
        shutil.rmtree(media_root, ignore_errors=True)
        media_root.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(media_root, ignore_errors=True))

        with override_settings(MEDIA_ROOT=media_root):
            active_exam = Exam.objects.create(
                owner=self.patient,
                title="Ultrassom transvaginal",
                exam_type="Ultrassom",
                performed_at=timezone.localdate(),
                file=SimpleUploadedFile("ultrassom.pdf", b"%PDF-1.4 exame ativo", content_type="application/pdf"),
            )
            Exam.objects.create(
                owner=self.patient,
                title="Exame removido",
                exam_type="Mamografia",
                performed_at=timezone.localdate(),
                file=SimpleUploadedFile("mamografia.pdf", b"%PDF-1.4 exame removido", content_type="application/pdf"),
                status=Exam.Status.DELETED,
                deleted_at=timezone.now(),
            )

            stored_path = Path(active_exam.file.path)
            self.assertTrue(stored_path.exists())

            self.authenticate("api-paciente@test.com", "Paciente123")

            list_response = self.client.get("/api/patient/exams/")
            self.assertEqual(list_response.status_code, 200)
            self.assertEqual(len(list_response.data), 1)
            self.assertEqual(list_response.data[0]["id"], active_exam.id)

            delete_response = self.client.delete(f"/api/patient/exams/{active_exam.id}/")
            self.assertEqual(delete_response.status_code, 204)

            active_exam.refresh_from_db()
            self.assertEqual(active_exam.status, Exam.Status.DELETED)
            self.assertIsNotNone(active_exam.deleted_at)
            self.assertFalse(active_exam.file)
            self.assertFalse(stored_path.exists())

    def test_patient_exam_list_supports_date_filters_and_recent_upload_sort(self):
        media_root = Path(__file__).resolve().parent.parent / "test_media_root"
        shutil.rmtree(media_root, ignore_errors=True)
        media_root.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(media_root, ignore_errors=True))

        with override_settings(MEDIA_ROOT=media_root):
            older_exam = Exam.objects.create(
                owner=self.patient,
                title="Exame antigo",
                exam_type="Mamografia",
                performed_at=timezone.localdate() - timedelta(days=30),
                file=SimpleUploadedFile("antigo.pdf", b"%PDF-1.4 exame antigo", content_type="application/pdf"),
            )
            newer_exam = Exam.objects.create(
                owner=self.patient,
                title="Exame recente por data",
                exam_type="Ultrassom",
                performed_at=timezone.localdate() - timedelta(days=5),
                file=SimpleUploadedFile("recente-data.pdf", b"%PDF-1.4 exame recente", content_type="application/pdf"),
            )
            latest_upload_exam = Exam.objects.create(
                owner=self.patient,
                title="Upload mais recente",
                exam_type="Laboratorial",
                performed_at=timezone.localdate() - timedelta(days=20),
                file=SimpleUploadedFile("upload-recente.pdf", b"%PDF-1.4 upload recente", content_type="application/pdf"),
            )

            now = timezone.now()
            Exam.objects.filter(pk=older_exam.pk).update(uploaded_at=now - timedelta(days=3))
            Exam.objects.filter(pk=newer_exam.pk).update(uploaded_at=now - timedelta(days=2))
            Exam.objects.filter(pk=latest_upload_exam.pk).update(uploaded_at=now - timedelta(hours=1))

            self.authenticate("api-paciente@test.com", "Paciente123")

            response = self.client.get(
                "/api/patient/exams/",
                {
                    "performed_from": (timezone.localdate() - timedelta(days=25)).isoformat(),
                    "performed_to": (timezone.localdate() - timedelta(days=1)).isoformat(),
                    "sort": "recent_upload",
                },
            )

            self.assertEqual(response.status_code, 200)
            self.assertEqual([item["id"] for item in response.data], [latest_upload_exam.id, newer_exam.id])

    def test_patient_notifications_generate_three_day_and_weekly_reminders_once(self):
        self.authenticate("api-paciente@test.com", "Paciente123")
        first_response = self.client.get("/api/patient/notifications/")
        self.assertEqual(first_response.status_code, 200)
        self.assertGreaterEqual(len(first_response.data), 2)
        self.assertEqual(Notification.objects.filter(recipient=self.patient).count(), 2)
        messages = list(Notification.objects.filter(recipient=self.patient).values_list("message", flat=True))
        self.assertTrue(any("Faltam 3 dias" in message for message in messages))
        self.assertTrue(any("Viva Plena" in message or "app" in message.lower() for message in messages))

        second_response = self.client.get("/api/patient/notifications/")
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(Notification.objects.filter(recipient=self.patient).count(), 2)

    def test_patient_notifications_generate_same_day_reminder(self):
        Appointment.objects.create(
            patient=self.patient,
            clinic=self.clinic,
            specialist="Retorno",
            scheduled_for=timezone.make_aware(datetime.combine(timezone.localdate(), time(hour=9))),
        )
        self.authenticate("api-paciente@test.com", "Paciente123")
        response = self.client.get("/api/patient/notifications/")
        self.assertEqual(response.status_code, 200)

        same_day_notifications = Notification.objects.filter(recipient=self.patient, type=Notification.Type.APPOINTMENT, message__icontains="consulta é hoje")
        self.assertEqual(same_day_notifications.count(), 1)
        self.assertTrue(same_day_notifications.first().is_critical)

    def test_clinic_api_flow(self):
        self.authenticate("api-clinica@test.com", "Clinica123")
        dashboard_response = self.client.get("/api/clinic/dashboard/")
        self.assertEqual(dashboard_response.status_code, 200)
        requests_response = self.client.get("/api/clinic/access-requests/")
        self.assertEqual(requests_response.status_code, 200)

    def test_admin_api_flow(self):
        self.authenticate("api-admin@test.com", "Admin123")
        dashboard_response = self.client.get("/api/admin/dashboard/")
        self.assertEqual(dashboard_response.status_code, 200)
        logs_response = self.client.get("/api/admin/logs/")
        self.assertEqual(logs_response.status_code, 200)
