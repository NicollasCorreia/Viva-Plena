from django.urls import path

from . import api_views


urlpatterns = [
    path("health/", api_views.PublicHealthAPIView.as_view(), name="api_health"),
    path("faqs/", api_views.PublicFAQListAPIView.as_view(), name="api_faqs"),
    path("clinics/", api_views.PublicApprovedClinicListAPIView.as_view(), name="api_public_clinics"),
    path("auth/register/patient/", api_views.PatientRegistrationAPIView.as_view(), name="api_register_patient"),
    path("auth/register/clinic/", api_views.ClinicRegistrationAPIView.as_view(), name="api_register_clinic"),
    path("auth/token/", api_views.TokenLoginAPIView.as_view(), name="api_token_login"),
    path("auth/logout/", api_views.LogoutAPIView.as_view(), name="api_logout"),
    path("me/", api_views.MeAPIView.as_view(), name="api_me"),
    path("patient/dashboard/", api_views.PatientDashboardAPIView.as_view(), name="api_patient_dashboard"),
    path("patient/exams/", api_views.PatientExamListCreateAPIView.as_view(), name="api_patient_exams"),
    path("patient/cycles/", api_views.PatientCycleListCreateAPIView.as_view(), name="api_patient_cycles"),
    path("patient/histories/", api_views.PatientHistoryListCreateAPIView.as_view(), name="api_patient_histories"),
    path("patient/access-requests/", api_views.PatientAccessRequestListAPIView.as_view(), name="api_patient_access_requests"),
    path("patient/access-requests/<int:pk>/decision/", api_views.PatientAccessRequestDecisionAPIView.as_view(), name="api_patient_access_decision"),
    path("patient/appointments/", api_views.PatientAppointmentListCreateAPIView.as_view(), name="api_patient_appointments"),
    path("patient/notifications/", api_views.PatientNotificationListAPIView.as_view(), name="api_patient_notifications"),
    path("patient/notifications/mark-all-read/", api_views.PatientNotificationMarkAllReadAPIView.as_view(), name="api_patient_notifications_mark_all_read"),
    path("patient/messages/", api_views.PatientMessageListCreateAPIView.as_view(), name="api_patient_messages"),
    path("clinic/dashboard/", api_views.ClinicDashboardAPIView.as_view(), name="api_clinic_dashboard"),
    path("clinic/access-requests/", api_views.ClinicAccessRequestListCreateAPIView.as_view(), name="api_clinic_access_requests"),
    path("clinic/exams/", api_views.ClinicExamListAPIView.as_view(), name="api_clinic_exams"),
    path("clinic/messages/", api_views.ClinicMessageListCreateAPIView.as_view(), name="api_clinic_messages"),
    path("clinic/reports/", api_views.ClinicReportAPIView.as_view(), name="api_clinic_reports"),
    path("admin/dashboard/", api_views.AdminDashboardAPIView.as_view(), name="api_admin_dashboard"),
    path("admin/clinics/", api_views.AdminClinicListAPIView.as_view(), name="api_admin_clinics"),
    path("admin/clinics/<int:pk>/decision/", api_views.AdminClinicDecisionAPIView.as_view(), name="api_admin_clinic_decision"),
    path("admin/accounts/", api_views.AdminAccountListAPIView.as_view(), name="api_admin_accounts"),
    path("admin/accounts/<int:pk>/toggle/", api_views.AdminAccountToggleAPIView.as_view(), name="api_admin_account_toggle"),
    path("admin/logs/", api_views.AdminLogListAPIView.as_view(), name="api_admin_logs"),
    path("admin/faqs/", api_views.AdminFAQListCreateAPIView.as_view(), name="api_admin_faqs"),
    path("admin/reports/", api_views.AdminReportAPIView.as_view(), name="api_admin_reports"),
]
