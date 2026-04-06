from pathlib import Path

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.validators import MinLengthValidator
from django.db import models
from django.utils import timezone


def exam_upload_path(instance, filename):
    extension = Path(filename).suffix.lower()
    safe_type = instance.exam_type.lower().replace(" ", "-")
    year = instance.performed_at.year if instance.performed_at else timezone.now().year
    return f"exams/{instance.owner_id}/{year}/{safe_type}-{timezone.now().strftime('%Y%m%d%H%M%S')}{extension}"


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("O e-mail é obrigatório.")
        email = self.normalize_email(email)
        username = extra_fields.get("username") or email.split("@")[0]
        extra_fields["username"] = username
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", User.Role.ADMIN)
        extra_fields.setdefault("approval_status", User.ApprovalStatus.APPROVED)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser precisa de is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser precisa de is_superuser=True.")
        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    class Role(models.TextChoices):
        PATIENT = "patient", "Usuária"
        CLINIC = "clinic", "Clínica"
        ADMIN = "admin", "Administrador"

    class ApprovalStatus(models.TextChoices):
        PENDING = "pending", "Pendente"
        APPROVED = "approved", "Aprovado"
        REJECTED = "rejected", "Recusado"
        SUSPENDED = "suspended", "Suspenso"

    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.PATIENT)
    full_name = models.CharField("nome completo", max_length=255)
    cpf = models.CharField(max_length=14, unique=True, blank=True, null=True)
    birth_date = models.DateField(blank=True, null=True)
    phone_primary = models.CharField(max_length=20, blank=True)
    phone_secondary = models.CharField(max_length=20, blank=True)
    secondary_email = models.EmailField(blank=True)
    cep = models.CharField(max_length=9, blank=True)
    street = models.CharField(max_length=255, blank=True)
    number = models.CharField(max_length=20, blank=True)
    neighborhood = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=2, blank=True)
    complement = models.CharField(max_length=255, blank=True)

    cnpj = models.CharField(max_length=18, unique=True, blank=True, null=True)
    company_name = models.CharField(max_length=255, blank=True)
    trade_name = models.CharField(max_length=255, blank=True)
    technical_manager = models.CharField(max_length=255, blank=True)
    crm = models.CharField(max_length=30, blank=True)

    consent_version = models.CharField(max_length=20, default="1.0")
    consent_accepted_at = models.DateTimeField(blank=True, null=True)
    approval_status = models.CharField(
        max_length=20,
        choices=ApprovalStatus.choices,
        default=ApprovalStatus.APPROVED,
    )
    blocked_until = models.DateTimeField(blank=True, null=True)
    invalid_login_attempts = models.PositiveSmallIntegerField(default=0)
    last_appointment_reminder_at = models.DateField(blank=True, null=True)
    last_engagement_reminder_at = models.DateField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    objects = UserManager()

    class Meta:
        ordering = ["full_name", "email"]

    def __str__(self):
        return self.full_name or self.email

    @property
    def is_patient(self):
        return self.role == self.Role.PATIENT

    @property
    def is_clinic(self):
        return self.role == self.Role.CLINIC

    @property
    def is_admin_portal(self):
        return self.role == self.Role.ADMIN

    @property
    def dashboard_label(self):
        return self.get_role_display()

    def approve(self):
        self.approval_status = self.ApprovalStatus.APPROVED
        self.is_active = True
        self.save(update_fields=["approval_status", "is_active", "updated_at"])

    def suspend(self):
        self.approval_status = self.ApprovalStatus.SUSPENDED
        self.is_active = False
        self.save(update_fields=["approval_status", "is_active", "updated_at"])


class AuditLog(models.Model):
    class Level(models.TextChoices):
        INFO = "info", "Informação"
        WARNING = "warning", "Alerta"
        CRITICAL = "critical", "Crítico"

    actor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="performed_logs",
    )
    target_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="target_logs",
    )
    action = models.CharField(max_length=120)
    details = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    level = models.CharField(max_length=10, choices=Level.choices, default=Level.INFO)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.action} - {self.created_at:%d/%m/%Y %H:%M}"


class FAQ(models.Model):
    question = models.CharField(max_length=255)
    answer = models.TextField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["question"]

    def __str__(self):
        return self.question


class Notification(models.Model):
    class Type(models.TextChoices):
        ACCESS = "access", "Solicitação de acesso"
        SECURITY = "security", "Segurança"
        CYCLE = "cycle", "Ciclo"
        APPOINTMENT = "appointment", "Consulta"
        EXAM = "exam", "Exame"
        ADMIN = "admin", "Administrativa"

    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    type = models.CharField(max_length=20, choices=Type.choices)
    message = models.CharField(max_length=255)
    is_critical = models.BooleanField(default=False)
    read_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def mark_as_read(self):
        self.read_at = timezone.now()
        self.save(update_fields=["read_at"])


class Exam(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Ativo"
        DELETED = "deleted", "Excluído"

    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="exams")
    title = models.CharField(max_length=120)
    exam_type = models.CharField(max_length=120)
    performed_at = models.DateField()
    file = models.FileField(upload_to=exam_upload_path)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    deleted_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-performed_at", "-uploaded_at"]

    def __str__(self):
        return f"{self.title} - {self.owner.full_name}"


class CycleRecord(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="cycles")
    start_date = models.DateField()
    end_date = models.DateField()
    symptoms = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-start_date"]

    def __str__(self):
        return f"Ciclo {self.owner.full_name} - {self.start_date:%d/%m/%Y}"


class MedicalHistory(models.Model):
    class InfoType(models.TextChoices):
        ALLERGY = "allergy", "Alergia"
        MEDICATION = "medication", "Medicamento"
        SURGERY = "surgery", "Cirurgia"
        DIAGNOSIS = "diagnosis", "Diagnóstico"

    patient = models.ForeignKey(User, on_delete=models.CASCADE, related_name="medical_histories")
    info_type = models.CharField(max_length=20, choices=InfoType.choices)
    description = models.CharField(max_length=255)
    record_date = models.DateField(default=timezone.localdate)
    observation = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-record_date", "-created_at"]

    def __str__(self):
        return f"{self.get_info_type_display()} - {self.patient.full_name}"


class AccessRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pendente"
        APPROVED = "approved", "Aprovado"
        REJECTED = "rejected", "Recusado"
        REVOKED = "revoked", "Revogado"

    clinic = models.ForeignKey(User, on_delete=models.CASCADE, related_name="clinic_requests")
    patient = models.ForeignKey(User, on_delete=models.CASCADE, related_name="patient_requests")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    request_note = models.CharField(max_length=255, blank=True)
    response_note = models.CharField(max_length=255, blank=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-requested_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["clinic", "patient"],
                condition=models.Q(status="pending"),
                name="unique_pending_access_request",
            )
        ]

    def __str__(self):
        return f"{self.clinic} -> {self.patient} ({self.get_status_display()})"


class Appointment(models.Model):
    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Agendada"
        CANCELLED = "cancelled", "Cancelada"
        COMPLETED = "completed", "Concluída"

    patient = models.ForeignKey(User, on_delete=models.CASCADE, related_name="appointments")
    clinic = models.ForeignKey(User, on_delete=models.CASCADE, related_name="clinic_appointments")
    specialist = models.CharField(max_length=120)
    scheduled_for = models.DateTimeField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SCHEDULED)
    three_day_reminder_sent_at = models.DateTimeField(blank=True, null=True)
    same_day_reminder_sent_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["scheduled_for"]

    def __str__(self):
        return f"{self.patient.full_name} - {self.scheduled_for:%d/%m/%Y %H:%M}"


class SecureMessage(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sent_messages")
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name="received_messages")
    body = models.TextField(validators=[MinLengthValidator(3)])
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.sender} -> {self.recipient}"
