from django.urls import path
from django.views.generic import RedirectView

from . import views


urlpatterns = [
    path("", views.home, name="home"),
    path("faq/", views.faq_public, name="faq_public"),
    path("entrar/", views.login_view, name="login"),
    path("sair/", views.logout_view, name="logout"),
    path("cadastro/profissional/", views.register_clinic, name="register_professional"),
    path("cadastro/clinica/", RedirectView.as_view(pattern_name="register_professional", permanent=False)),
    path("dashboard/", views.dashboard_redirect, name="dashboard_redirect"),
    path("paciente/", views.patient_access, name="patient_access"),
    path("profissional/", views.clinic_dashboard, name="professional_dashboard"),
    path("profissional/consultas/", views.clinic_appointments, name="professional_appointments"),
    path("profissional/solicitacoes/", views.clinic_requests, name="professional_requests"),
    path("profissional/exames/", views.clinic_exams, name="professional_exams"),
    path("profissional/mensagens/", views.clinic_messages, name="professional_messages"),
    path("profissional/relatorios/", views.clinic_reports, name="professional_reports"),
    path("mobile/", RedirectView.as_view(pattern_name="patient_access", permanent=False)),
    path("clinica/", RedirectView.as_view(pattern_name="professional_dashboard", permanent=False)),
    path("clinica/solicitacoes/", RedirectView.as_view(pattern_name="professional_requests", permanent=False)),
    path("clinica/exames/", RedirectView.as_view(pattern_name="professional_exams", permanent=False)),
    path("clinica/mensagens/", RedirectView.as_view(pattern_name="professional_messages", permanent=False)),
    path("clinica/relatorios/", RedirectView.as_view(pattern_name="professional_reports", permanent=False)),
    path("gerenciador/", views.admin_dashboard, name="admin_dashboard"),
    path("gerenciador/clinicas/", views.admin_clinics, name="admin_clinics"),
    path("gerenciador/contas/", views.admin_accounts, name="admin_accounts"),
    path("gerenciador/logs/", views.admin_logs, name="admin_logs"),
    path("gerenciador/faq/", views.admin_faq, name="admin_faq"),
    path("gerenciador/relatorios/", views.admin_reports, name="admin_reports"),
]
