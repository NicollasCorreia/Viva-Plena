from datetime import datetime, time, timedelta

from django.test import Client, TestCase
from django.utils import timezone
from rest_framework.test import APITestCase

from .models import AccessRequest, Appointment, FAQ, Notification, User


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
        self.assertEqual(client.get("/mobile/").status_code, 200)

        client = Client()
        self.assertTrue(client.login(email="clinica@test.com", password="Clinica123"))
        self.assertEqual(client.get("/clinica/").status_code, 200)

        client = Client()
        self.assertTrue(client.login(email="admin@test.com", password="Admin123"))
        self.assertEqual(client.get("/gerenciador/").status_code, 200)

    def test_admin_can_toggle_faq_status(self):
        faq = FAQ.objects.create(question="FAQ Toggle", answer="Resposta", is_active=True)
        client = Client()
        self.assertTrue(client.login(email="admin@test.com", password="Admin123"))
        response = client.post("/gerenciador/faq/", {"action": "toggle_status", "faq_id": faq.id}, follow=True)
        self.assertEqual(response.status_code, 200)
        faq.refresh_from_db()
        self.assertFalse(faq.is_active)


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

    def test_patient_notifications_generate_three_day_and_weekly_reminders_once(self):
        self.authenticate("api-paciente@test.com", "Paciente123")
        first_response = self.client.get("/api/patient/notifications/")
        self.assertEqual(first_response.status_code, 200)
        self.assertGreaterEqual(len(first_response.data), 2)
        self.assertEqual(Notification.objects.filter(recipient=self.patient).count(), 2)
        messages = list(Notification.objects.filter(recipient=self.patient).values_list("message", flat=True))
        self.assertTrue(any("Faltam 3 dias" in message for message in messages))
        self.assertTrue(any("Ciclo & Saude" in message or "app" in message.lower() for message in messages))

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

        same_day_notifications = Notification.objects.filter(recipient=self.patient, type=Notification.Type.APPOINTMENT, message__icontains="consulta e hoje")
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
