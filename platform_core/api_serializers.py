from pathlib import Path

from django.contrib.auth import authenticate
from django.utils import timezone
from rest_framework import serializers

from .models import AccessRequest, Appointment, AuditLog, CycleRecord, Exam, FAQ, MedicalHistory, Notification, SecureMessage, User


class UserSummarySerializer(serializers.ModelSerializer):
    role_label = serializers.CharField(source="get_role_display", read_only=True)
    approval_status_label = serializers.CharField(source="get_approval_status_display", read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "full_name",
            "email",
            "role",
            "role_label",
            "approval_status",
            "approval_status_label",
            "cpf",
            "cnpj",
            "trade_name",
            "company_name",
        ]


class FAQSerializer(serializers.ModelSerializer):
    class Meta:
        model = FAQ
        fields = ["id", "question", "answer", "is_active", "created_at", "updated_at"]


class NotificationSerializer(serializers.ModelSerializer):
    type_label = serializers.CharField(source="get_type_display", read_only=True)

    class Meta:
        model = Notification
        fields = ["id", "type", "type_label", "message", "is_critical", "read_at", "created_at"]


class ExamSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()
    owner = UserSummarySerializer(read_only=True)

    class Meta:
        model = Exam
        fields = [
            "id",
            "owner",
            "title",
            "exam_type",
            "performed_at",
            "file",
            "file_url",
            "notes",
            "status",
            "uploaded_at",
        ]
        read_only_fields = ["status", "uploaded_at"]

    def get_file_url(self, obj):
        request = self.context.get("request")
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        if obj.file:
            return obj.file.url
        return None

    def validate_file(self, file):
        extension = Path(file.name).suffix.lower()
        if extension not in {".jpg", ".jpeg", ".png", ".pdf"}:
            raise serializers.ValidationError("Envie apenas arquivos JPG, PNG ou PDF.")
        if file.size > 10 * 1024 * 1024:
            raise serializers.ValidationError("O arquivo nao pode ultrapassar 10 MB.")
        return file


class CycleRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = CycleRecord
        fields = ["id", "start_date", "end_date", "symptoms", "notes", "is_active", "created_at"]
        read_only_fields = ["is_active", "created_at"]

    def validate(self, attrs):
        if attrs["end_date"] < attrs["start_date"]:
            raise serializers.ValidationError("A data final nao pode ser anterior a data inicial.")
        return attrs


class MedicalHistorySerializer(serializers.ModelSerializer):
    info_type_label = serializers.CharField(source="get_info_type_display", read_only=True)

    class Meta:
        model = MedicalHistory
        fields = ["id", "info_type", "info_type_label", "description", "record_date", "observation", "is_active", "created_at"]
        read_only_fields = ["is_active", "created_at"]


class AccessRequestSerializer(serializers.ModelSerializer):
    clinic = UserSummarySerializer(read_only=True)
    patient = UserSummarySerializer(read_only=True)
    patient_cpf = serializers.CharField(write_only=True, required=False)
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = AccessRequest
        fields = [
            "id",
            "clinic",
            "patient",
            "patient_cpf",
            "status",
            "status_label",
            "request_note",
            "response_note",
            "requested_at",
            "responded_at",
        ]
        read_only_fields = ["status", "requested_at", "responded_at", "response_note"]

    def validate_patient_cpf(self, value):
        patient = User.objects.filter(cpf=value, role=User.Role.PATIENT).first()
        if not patient:
            raise serializers.ValidationError("Paciente nao encontrada com esse CPF.")
        return value

    def create(self, validated_data):
        patient_cpf = validated_data.pop("patient_cpf")
        clinic = self.context["request"].user
        patient = User.objects.get(cpf=patient_cpf, role=User.Role.PATIENT)

        existing = AccessRequest.objects.filter(
            clinic=clinic,
            patient=patient,
            status=AccessRequest.Status.PENDING,
        ).first()
        if existing:
            raise serializers.ValidationError({"detail": "Ja existe uma solicitacao pendente para essa paciente."})

        return AccessRequest.objects.create(clinic=clinic, patient=patient, **validated_data)


class AppointmentSerializer(serializers.ModelSerializer):
    clinic = UserSummarySerializer(read_only=True)
    clinic_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role=User.Role.CLINIC, approval_status=User.ApprovalStatus.APPROVED),
        source="clinic",
        write_only=True,
    )
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Appointment
        fields = ["id", "clinic", "clinic_id", "specialist", "scheduled_for", "status", "status_label", "created_at"]
        read_only_fields = ["status", "created_at"]

    def validate_scheduled_for(self, value):
        if value <= timezone.now():
            raise serializers.ValidationError("Escolha uma data futura para o agendamento.")
        return value


class SecureMessageSerializer(serializers.ModelSerializer):
    sender = UserSummarySerializer(read_only=True)
    recipient = UserSummarySerializer(read_only=True)
    recipient_id = serializers.PrimaryKeyRelatedField(queryset=User.objects.none(), source="recipient", write_only=True)

    class Meta:
        model = SecureMessage
        fields = ["id", "sender", "recipient", "recipient_id", "body", "is_read", "created_at"]
        read_only_fields = ["is_read", "created_at"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            user = request.user
            if user.role == User.Role.PATIENT:
                allowed_ids = user.patient_requests.filter(status=AccessRequest.Status.APPROVED).values_list("clinic_id", flat=True)
            elif user.role == User.Role.CLINIC:
                allowed_ids = user.clinic_requests.filter(status=AccessRequest.Status.APPROVED).values_list("patient_id", flat=True)
            else:
                allowed_ids = User.objects.exclude(id=user.id).values_list("id", flat=True)
            self.fields["recipient_id"].queryset = User.objects.filter(id__in=allowed_ids)


class AuditLogSerializer(serializers.ModelSerializer):
    actor = UserSummarySerializer(read_only=True)
    target_user = UserSummarySerializer(read_only=True)
    level_label = serializers.CharField(source="get_level_display", read_only=True)

    class Meta:
        model = AuditLog
        fields = ["id", "action", "details", "level", "level_label", "created_at", "actor", "target_user", "ip_address"]


class TokenLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(style={"input_type": "password"}, trim_whitespace=False)

    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")
        request = self.context.get("request")
        user = authenticate(request=request, email=email, password=password)
        if not user:
            raise serializers.ValidationError("Credenciais invalidas.", code="authorization")
        attrs["user"] = user
        return attrs


class PatientRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = [
            "full_name",
            "email",
            "password",
            "cpf",
            "birth_date",
            "phone_primary",
            "cep",
            "street",
            "number",
            "neighborhood",
            "city",
            "state",
            "complement",
        ]

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(
            username=validated_data["email"],
            role=User.Role.PATIENT,
            approval_status=User.ApprovalStatus.APPROVED,
            consent_accepted_at=timezone.now(),
            **validated_data,
        )
        user.set_password(password)
        user.save()
        return user


class ClinicRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = [
            "trade_name",
            "company_name",
            "email",
            "password",
            "cnpj",
            "phone_primary",
            "technical_manager",
            "crm",
            "city",
            "state",
        ]

    def create(self, validated_data):
        password = validated_data.pop("password")
        trade_name = validated_data.get("trade_name")
        user = User(
            username=validated_data["email"],
            role=User.Role.CLINIC,
            full_name=trade_name,
            approval_status=User.ApprovalStatus.PENDING,
            is_active=True,
            **validated_data,
        )
        user.set_password(password)
        user.save()
        return user
