from django.urls import path

from . import views


urlpatterns = [
    path("", views.home, name="home"),
    path("faq/", views.faq_public, name="faq_public"),
    path("entrar/", views.login_view, name="login"),
    path("sair/", views.logout_view, name="logout"),
    path("cadastro/usuaria/", views.register_patient, name="register_patient"),
    path("cadastro/clinica/", views.register_clinic, name="register_clinic"),
    path("dashboard/", views.dashboard_redirect, name="dashboard_redirect"),
    path("mobile/", views.patient_dashboard, name="patient_dashboard"),
    path("mobile/exames/", views.patient_exams, name="patient_exams"),
    path("mobile/ciclos/", views.patient_cycles, name="patient_cycles"),
    path("mobile/historico/", views.patient_histories, name="patient_histories"),
    path("mobile/acessos/", views.patient_access, name="patient_access"),
    path("mobile/consultas/", views.patient_appointments, name="patient_appointments"),
    path("mobile/mensagens/", views.patient_messages, name="patient_messages"),
    path("mobile/notificacoes/", views.patient_notifications, name="patient_notifications"),
    path("clinica/", views.clinic_dashboard, name="clinic_dashboard"),
    path("clinica/solicitacoes/", views.clinic_requests, name="clinic_requests"),
    path("clinica/exames/", views.clinic_exams, name="clinic_exams"),
    path("clinica/mensagens/", views.clinic_messages, name="clinic_messages"),
    path("clinica/relatorios/", views.clinic_reports, name="clinic_reports"),
    path("gerenciador/", views.admin_dashboard, name="admin_dashboard"),
    path("gerenciador/clinicas/", views.admin_clinics, name="admin_clinics"),
    path("gerenciador/contas/", views.admin_accounts, name="admin_accounts"),
    path("gerenciador/logs/", views.admin_logs, name="admin_logs"),
    path("gerenciador/faq/", views.admin_faq, name="admin_faq"),
    path("gerenciador/relatorios/", views.admin_reports, name="admin_reports"),
]
