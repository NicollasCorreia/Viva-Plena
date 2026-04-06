from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import AccessRequest, Appointment, AuditLog, CycleRecord, Exam, FAQ, MedicalHistory, Notification, SecureMessage, User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    model = User
    list_display = ("email", "full_name", "role", "approval_status", "is_active")
    list_filter = ("role", "approval_status", "is_active")
    ordering = ("email",)
    search_fields = ("email", "full_name", "cpf", "cnpj")
    fieldsets = (
        (None, {"fields": ("email", "username", "password")}),
        ("Perfil", {"fields": ("full_name", "role", "approval_status", "consent_version", "consent_accepted_at")}),
        ("Contato", {"fields": ("phone_primary", "phone_secondary", "secondary_email")}),
        ("Usuaria", {"fields": ("cpf", "birth_date", "cep", "street", "number", "neighborhood", "city", "state", "complement")}),
        ("Clinica", {"fields": ("cnpj", "company_name", "trade_name", "technical_manager", "crm")}),
        ("Permissoes", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Seguranca", {"fields": ("invalid_login_attempts", "blocked_until", "last_login")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "username", "full_name", "role", "password1", "password2"),
            },
        ),
    )


admin.site.register(AuditLog)
admin.site.register(FAQ)
admin.site.register(Notification)
admin.site.register(Exam)
admin.site.register(CycleRecord)
admin.site.register(MedicalHistory)
admin.site.register(AccessRequest)
admin.site.register(Appointment)
admin.site.register(SecureMessage)
