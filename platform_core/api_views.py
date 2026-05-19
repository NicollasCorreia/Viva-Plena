from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .api_permissions import IsAdminRole, IsClinicRole, IsPatientRole
from .api_serializers import (
    AccessRequestSerializer,
    AppointmentSerializer,
    AuditLogSerializer,
    ClinicRegistrationSerializer,
    CycleRecordSerializer,
    ExamSerializer,
    FAQSerializer,
    MedicalHistorySerializer,
    NotificationSerializer,
    PatientRegistrationSerializer,
    SecureMessageSerializer,
    TokenLoginSerializer,
    UserSummarySerializer,
)
from .models import AccessRequest, Appointment, AuditLog, CycleRecord, Exam, FAQ, MedicalHistory, SecureMessage, User
from .services import apply_exam_filters, ensure_patient_recurring_notifications, estimate_next_cycle, log_action, notify, should_block_login


class PublicHealthAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        return Response({"status": "ok", "project": "Viva Plena"})


class PublicFAQListAPIView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = FAQSerializer
    queryset = FAQ.objects.filter(is_active=True)


class PublicApprovedClinicListAPIView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = UserSummarySerializer

    def get_queryset(self):
        return User.objects.filter(
            role=User.Role.CLINIC,
            approval_status=User.ApprovalStatus.APPROVED,
            institution_name__iexact="CESMAC",
        )


class PatientRegistrationAPIView(generics.CreateAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = PatientRegistrationSerializer

    def perform_create(self, serializer):
        user = serializer.save()
        log_action(user, "Cadastro via aplicativo", "Conta criada pelo aplicativo da paciente.", target_user=user, request=self.request)
        notify(user, "admin", "Sua conta foi criada com sucesso. Quando quiser, abra o app para acompanhar seus dados.")


class ClinicRegistrationAPIView(generics.CreateAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = ClinicRegistrationSerializer

    def perform_create(self, serializer):
        user = serializer.save()
        log_action(
            user,
            "Cadastro profissional via API",
            "Solicitação de acesso profissional vinculada ao CESMAC aguardando análise da administração.",
            target_user=user,
            request=self.request,
        )


class TokenLoginAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = TokenLoginSerializer(data=request.data, context={"request": request})
        email = request.data.get("email", "").strip().lower()
        user = User.objects.filter(email__iexact=email).first()

        if user and should_block_login(user):
            return Response(
                {"detail": "Seu acesso foi pausado por alguns minutos após várias tentativas seguidas. Tente novamente daqui a pouco."},
                status=status.HTTP_423_LOCKED,
            )

        if serializer.is_valid():
            user = serializer.validated_data["user"]
            token, _ = Token.objects.get_or_create(user=user)
            user.invalid_login_attempts = 0
            user.blocked_until = None
            user.save(update_fields=["invalid_login_attempts", "blocked_until", "updated_at"])
            log_action(user, "Login via token", "Acesso realizado com sucesso pelo aplicativo.", target_user=user, request=request)
            return Response({"token": token.key, "user": UserSummarySerializer(user).data})

        if user:
            user.invalid_login_attempts += 1
            if user.invalid_login_attempts >= 5:
                user.blocked_until = timezone.now() + timezone.timedelta(minutes=15)
            user.save(update_fields=["invalid_login_attempts", "blocked_until", "updated_at"])
            log_action(user, "Falha de login via API", "Tentativa de acesso com dados inválidos.", target_user=user, request=request, level=AuditLog.Level.WARNING)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LogoutAPIView(APIView):
    authentication_classes = [TokenAuthentication, SessionAuthentication]

    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        log_action(request.user, "Logout via API", "Token removido pela pessoa usuária.", target_user=request.user, request=request)
        return Response({"detail": "Você saiu do aplicativo com sucesso."})


class MeAPIView(APIView):
    authentication_classes = [TokenAuthentication, SessionAuthentication]

    def get(self, request):
        return Response(UserSummarySerializer(request.user).data)


class PatientDashboardAPIView(APIView):
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsPatientRole]

    def get(self, request):
        patient = request.user
        ensure_patient_recurring_notifications(patient)
        data = {
            "exam_count": patient.exams.filter(status=Exam.Status.ACTIVE).count(),
            "clinic_links": patient.patient_requests.filter(status=AccessRequest.Status.APPROVED).count(),
            "professional_links": patient.patient_requests.filter(status=AccessRequest.Status.APPROVED).count(),
            "medical_history_count": patient.medical_histories.filter(is_active=True).count(),
            "pending_requests": AccessRequestSerializer(patient.patient_requests.filter(status=AccessRequest.Status.PENDING), many=True).data,
            "next_cycle_date": estimate_next_cycle(patient.cycles.filter(is_active=True)),
        }
        if data["next_cycle_date"]:
            data["next_cycle_date"] = data["next_cycle_date"].isoformat()
        return Response(data)


class PatientExamListCreateAPIView(generics.ListCreateAPIView):
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsPatientRole]
    serializer_class = ExamSerializer
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        queryset = self.request.user.exams.filter(status=Exam.Status.ACTIVE)
        return apply_exam_filters(queryset, self.request.query_params)

    def perform_create(self, serializer):
        exam = serializer.save(owner=self.request.user)
        log_action(self.request.user, "Envio de exame via API", f"Exame enviado: {exam.title}", target_user=self.request.user, request=self.request)
        notify(self.request.user, "exam", f"Seu exame '{exam.title}' foi salvo com sucesso.")


class PatientExamDestroyAPIView(generics.DestroyAPIView):
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsPatientRole]
    serializer_class = ExamSerializer

    def get_queryset(self):
        return self.request.user.exams.filter(status=Exam.Status.ACTIVE)

    def perform_destroy(self, instance):
        exam_title = instance.title
        if instance.file:
            instance.file.delete(save=False)
        instance.status = Exam.Status.DELETED
        instance.deleted_at = timezone.now()
        instance.save(update_fields=["file", "status", "deleted_at"])
        log_action(self.request.user, "Remocao de exame via API", f"Exame removido: {exam_title}", target_user=self.request.user, request=self.request)
        notify(self.request.user, "exam", f"Seu exame '{exam_title}' foi removido.")


class PatientCycleListCreateAPIView(generics.ListCreateAPIView):
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsPatientRole]
    serializer_class = CycleRecordSerializer

    def get_queryset(self):
        return self.request.user.cycles.all()

    def perform_create(self, serializer):
        cycle = serializer.save(owner=self.request.user)
        log_action(self.request.user, "Registro de ciclo via API", "Novo ciclo menstrual registrado.", target_user=self.request.user, request=self.request)
        notify(self.request.user, "cycle", "Seu ciclo foi registrado com sucesso.")


class PatientHistoryListCreateAPIView(generics.ListCreateAPIView):
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsPatientRole]
    serializer_class = MedicalHistorySerializer

    def get_queryset(self):
        return self.request.user.medical_histories.filter(is_active=True)

    def perform_create(self, serializer):
        history = serializer.save(patient=self.request.user)
        log_action(self.request.user, "Histórico de saúde via API", f"Novo registro salvo: {history.description}", target_user=self.request.user, request=self.request)


class PatientAccessRequestListAPIView(generics.ListAPIView):
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsPatientRole]
    serializer_class = AccessRequestSerializer

    def get_queryset(self):
        return self.request.user.patient_requests.select_related("clinic", "patient")


class PatientAccessRequestDecisionAPIView(APIView):
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsPatientRole]

    def post(self, request, pk):
        access = generics.get_object_or_404(AccessRequest, pk=pk, patient=request.user)
        action = request.data.get("action")

        if action == "approve":
            access.status = AccessRequest.Status.APPROVED
            access.responded_at = timezone.now()
            access.save(update_fields=["status", "responded_at"])
            notify(access.professional, "access", f"A paciente {request.user.full_name} autorizou você a acessar os exames dela.")
            log_action(
                request.user,
                "Aprovação de acesso via API",
                f"Acesso individual liberado para {access.professional.full_name}",
                target_user=access.professional,
                request=request,
            )
        elif action == "reject":
            access.status = AccessRequest.Status.REJECTED
            access.responded_at = timezone.now()
            access.save(update_fields=["status", "responded_at"])
            notify(access.professional, "access", f"A paciente {request.user.full_name} não autorizou o acesso aos exames dela.")
            log_action(
                request.user,
                "Recusa de acesso via API",
                f"Acesso recusado para {access.professional.full_name}",
                target_user=access.professional,
                request=request,
                level=AuditLog.Level.WARNING,
            )
        elif action == "revoke":
            access.status = AccessRequest.Status.REVOKED
            access.responded_at = timezone.now()
            access.save(update_fields=["status", "responded_at"])
            notify(access.professional, "security", f"A paciente {request.user.full_name} encerrou seu acesso aos exames dela.", is_critical=True)
            log_action(
                request.user,
                "Revogação de acesso via API",
                f"Acesso encerrado para {access.professional.full_name}",
                target_user=access.professional,
                request=request,
                level=AuditLog.Level.WARNING,
            )
        else:
            return Response({"detail": "A ação informada não é válida."}, status=status.HTTP_400_BAD_REQUEST)

        return Response(AccessRequestSerializer(access).data)


class PatientAppointmentListCreateAPIView(generics.ListCreateAPIView):
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsPatientRole]
    serializer_class = AppointmentSerializer

    def get_queryset(self):
        return self.request.user.appointments.filter(hidden_by_patient_at__isnull=True).select_related("clinic")

    def create(self, request, *args, **kwargs):
        return Response(
            {
                "detail": (
                    "As consultas são agendadas apenas pela profissional. "
                    "No aplicativo, você pode apenas acompanhar os horários já marcados."
                )
            },
            status=status.HTTP_403_FORBIDDEN,
        )


class PatientAppointmentDestroyAPIView(generics.DestroyAPIView):
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsPatientRole]
    serializer_class = AppointmentSerializer

    def get_queryset(self):
        return self.request.user.appointments.select_related("clinic")

    def delete(self, request, *args, **kwargs):
        appointment = self.get_object()
        if appointment.status != Appointment.Status.CANCELLED:
            return Response(
                {"detail": "Somente consultas canceladas podem ser removidas da sua lista."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not appointment.hidden_by_patient_at:
            appointment.hidden_by_patient_at = timezone.now()
            appointment.save(update_fields=["hidden_by_patient_at"])
            log_action(
                request.user,
                "Ocultacao de consulta cancelada via API",
                f"Consulta cancelada removida da lista: {appointment.specialist}",
                target_user=request.user,
                request=request,
            )

        return Response(status=status.HTTP_204_NO_CONTENT)


class PatientNotificationListAPIView(generics.ListAPIView):
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsPatientRole]
    serializer_class = NotificationSerializer

    def get_queryset(self):
        ensure_patient_recurring_notifications(self.request.user)
        return self.request.user.notifications.all()


class PatientNotificationMarkAllReadAPIView(APIView):
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsPatientRole]

    def post(self, request):
        updated = request.user.notifications.filter(read_at__isnull=True).update(read_at=timezone.now())
        return Response({"detail": "Seus avisos foram marcados como lidos.", "updated": updated})


class PatientNotificationDestroyAPIView(generics.DestroyAPIView):
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsPatientRole]
    serializer_class = NotificationSerializer

    def get_queryset(self):
        return self.request.user.notifications.all()

    def delete(self, request, *args, **kwargs):
        notification = self.get_object()
        if not notification.read_at:
            return Response(
                {"detail": "Marque o aviso como lido antes de apagar esse item."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        message = notification.message
        notification.delete()
        log_action(
            request.user,
            "Exclusao de aviso via API",
            f"Aviso removido: {message}",
            target_user=request.user,
            request=request,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class PatientMessageListCreateAPIView(generics.ListCreateAPIView):
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsPatientRole]
    serializer_class = SecureMessageSerializer

    def get_queryset(self):
        return SecureMessage.objects.filter(Q(sender=self.request.user) | Q(recipient=self.request.user)).select_related("sender", "recipient")

    def perform_create(self, serializer):
        message = serializer.save(sender=self.request.user)
        notify(message.recipient, "admin", f"Você recebeu uma nova mensagem segura de {self.request.user.full_name}.")
        log_action(self.request.user, "Mensagem segura via API", f"Mensagem enviada para {message.recipient.full_name}", target_user=message.recipient, request=self.request)


class ClinicDashboardAPIView(APIView):
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsClinicRole]

    def get(self, request):
        clinic = request.user
        if clinic.approval_status != User.ApprovalStatus.APPROVED:
            return Response({"pending_approval": True, "detail": "Seu acesso profissional ainda está em análise pela administração."})

        approved_patient_ids = clinic.clinic_requests.filter(status=AccessRequest.Status.APPROVED).values_list("patient_id", flat=True)
        data = {
            "pending_approval": False,
            "approved_count": clinic.clinic_requests.filter(status=AccessRequest.Status.APPROVED).count(),
            "pending_count": clinic.clinic_requests.filter(status=AccessRequest.Status.PENDING).count(),
            "exam_count": Exam.objects.filter(owner_id__in=approved_patient_ids, status=Exam.Status.ACTIVE).count(),
            "recent_requests": AccessRequestSerializer(clinic.clinic_requests.select_related("patient", "clinic")[:5], many=True).data,
        }
        return Response(data)


class ClinicAccessRequestListCreateAPIView(generics.ListCreateAPIView):
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsClinicRole]
    serializer_class = AccessRequestSerializer

    def get_queryset(self):
        return self.request.user.clinic_requests.select_related("clinic", "patient")

    def perform_create(self, serializer):
        if self.request.user.approval_status != User.ApprovalStatus.APPROVED:
            raise PermissionDenied("Seu acesso profissional ainda está em análise e não pode enviar pedidos de acesso por enquanto.")
        access = serializer.save()
        notify(
            access.patient,
            "access",
            f"{self.request.user.full_name}, profissional do CESMAC, pediu acesso aos seus exames. Só ela poderá visualizar esse conteúdo se você aprovar.",
            is_critical=True,
        )
        log_action(self.request.user, "Solicitação de acesso via API", f"Pedido enviado para {access.patient.full_name}", target_user=access.patient, request=self.request)


class ClinicExamListAPIView(generics.ListAPIView):
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsClinicRole]
    serializer_class = ExamSerializer

    def get_queryset(self):
        if self.request.user.approval_status != User.ApprovalStatus.APPROVED:
            return Exam.objects.none()
        approved_ids = self.request.user.clinic_requests.filter(status=AccessRequest.Status.APPROVED).values_list("patient_id", flat=True)
        queryset = Exam.objects.filter(owner_id__in=approved_ids, status=Exam.Status.ACTIVE).select_related("owner")
        return apply_exam_filters(queryset, self.request.query_params, patient_param="patient_id")

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        response = super().list(request, *args, **kwargs)
        log_action(
            request.user,
            "Consulta de exames via API",
            f"Profissional consultou {queryset.count()} exame(s) dentro dos acessos aprovados.",
            request=request,
        )
        return response


class ClinicMessageListCreateAPIView(generics.ListCreateAPIView):
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsClinicRole]
    serializer_class = SecureMessageSerializer

    def get_queryset(self):
        return SecureMessage.objects.filter(Q(sender=self.request.user) | Q(recipient=self.request.user)).select_related("sender", "recipient")

    def perform_create(self, serializer):
        message = serializer.save(sender=self.request.user)
        notify(message.recipient, "admin", f"Você recebeu uma nova mensagem segura de {self.request.user.full_name}.")
        log_action(self.request.user, "Mensagem segura via API", f"Mensagem enviada para {message.recipient.full_name}", target_user=message.recipient, request=self.request)


class ClinicReportAPIView(APIView):
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsClinicRole]

    def get(self, request):
        approved_requests = request.user.clinic_requests.filter(status=AccessRequest.Status.APPROVED)
        exams_count = Exam.objects.filter(owner_id__in=approved_requests.values_list("patient_id", flat=True), status=Exam.Status.ACTIVE).count()
        appointments_count = request.user.clinic_appointments.count()
        return Response(
            {
                "approved_count": approved_requests.count(),
                "exams_count": exams_count,
                "appointments_count": appointments_count,
                "institution_name": "CESMAC",
            }
        )


class AdminDashboardAPIView(APIView):
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAdminRole]

    def get(self, request):
        data = {
            "patient_count": User.objects.filter(role=User.Role.PATIENT).count(),
            "clinic_count": User.objects.filter(role=User.Role.CLINIC).count(),
            "professional_count": User.objects.filter(role=User.Role.CLINIC).count(),
            "exam_count": Exam.objects.filter(status=Exam.Status.ACTIVE).count(),
            "pending_clinics": UserSummarySerializer(
                User.objects.filter(role=User.Role.CLINIC, approval_status=User.ApprovalStatus.PENDING),
                many=True,
            ).data,
            "pending_professionals": UserSummarySerializer(
                User.objects.filter(role=User.Role.CLINIC, approval_status=User.ApprovalStatus.PENDING),
                many=True,
            ).data,
            "recent_logs": AuditLogSerializer(AuditLog.objects.select_related("actor", "target_user")[:10], many=True).data,
            "request_summary": list(AccessRequest.objects.values("status").annotate(total=Count("id"))),
        }
        return Response(data)


class AdminClinicListAPIView(generics.ListAPIView):
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAdminRole]
    serializer_class = UserSummarySerializer

    def get_queryset(self):
        return User.objects.filter(role=User.Role.CLINIC)


class AdminClinicDecisionAPIView(APIView):
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAdminRole]

    def post(self, request, pk):
        clinic = generics.get_object_or_404(User, pk=pk, role=User.Role.CLINIC)
        action = request.data.get("action")

        if action == "approve":
            clinic.approval_status = User.ApprovalStatus.APPROVED
            clinic.is_active = True
            clinic.save(update_fields=["approval_status", "is_active", "updated_at"])
            notify(clinic, "admin", "Seu acesso profissional foi aprovado e já pode ser usado no ambiente do CESMAC.")
            log_action(request.user, "Aprovação profissional via API", f"Profissional aprovada: {clinic.full_name}", target_user=clinic, request=request)
        elif action == "reject":
            clinic.approval_status = User.ApprovalStatus.REJECTED
            clinic.save(update_fields=["approval_status", "updated_at"])
            notify(clinic, "admin", "Seu cadastro profissional não foi aprovado.", is_critical=True)
            log_action(request.user, "Recusa profissional via API", f"Profissional recusada: {clinic.full_name}", target_user=clinic, request=request, level=AuditLog.Level.WARNING)
        elif action == "suspend":
            clinic.approval_status = User.ApprovalStatus.SUSPENDED
            clinic.is_active = False
            clinic.save(update_fields=["approval_status", "is_active", "updated_at"])
            notify(clinic, "security", "Seu acesso profissional foi suspenso pela administração.", is_critical=True)
            log_action(request.user, "Suspensão profissional via API", f"Profissional suspensa: {clinic.full_name}", target_user=clinic, request=request, level=AuditLog.Level.WARNING)
        else:
            return Response({"detail": "A ação informada não é válida."}, status=status.HTTP_400_BAD_REQUEST)

        return Response(UserSummarySerializer(clinic).data)


class AdminAccountListAPIView(generics.ListAPIView):
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAdminRole]
    serializer_class = UserSummarySerializer

    def get_queryset(self):
        return User.objects.exclude(role=User.Role.ADMIN).order_by("role", "full_name")


class AdminAccountToggleAPIView(APIView):
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAdminRole]

    def post(self, request, pk):
        target = generics.get_object_or_404(User, pk=pk)
        target.is_active = not target.is_active
        if not target.is_active:
            target.approval_status = User.ApprovalStatus.SUSPENDED
        else:
            target.approval_status = User.ApprovalStatus.APPROVED
        target.save(update_fields=["is_active", "approval_status", "updated_at"])
        log_action(request.user, "Alteração de status via API", f"Conta atualizada: {target.full_name}", target_user=target, request=request)
        return Response(UserSummarySerializer(target).data)


class AdminLogListAPIView(generics.ListAPIView):
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAdminRole]
    serializer_class = AuditLogSerializer

    def get_queryset(self):
        queryset = AuditLog.objects.select_related("actor", "target_user")
        level = self.request.query_params.get("level")
        if level:
            queryset = queryset.filter(level=level)
        return queryset


class AdminFAQListCreateAPIView(generics.ListCreateAPIView):
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAdminRole]
    serializer_class = FAQSerializer
    queryset = FAQ.objects.all()

    def perform_create(self, serializer):
        faq = serializer.save()
        log_action(self.request.user, "FAQ via API", f"Pergunta salva: {faq.question}", request=self.request)


class AdminReportAPIView(APIView):
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAdminRole]

    def get(self, request):
        summary = {
            "users": User.objects.count(),
            "patients": User.objects.filter(role=User.Role.PATIENT).count(),
            "clinics": User.objects.filter(role=User.Role.CLINIC).count(),
            "professionals": User.objects.filter(role=User.Role.CLINIC).count(),
            "approved_clinics": User.objects.filter(role=User.Role.CLINIC, approval_status=User.ApprovalStatus.APPROVED).count(),
            "approved_professionals": User.objects.filter(role=User.Role.CLINIC, approval_status=User.ApprovalStatus.APPROVED).count(),
            "exams": Exam.objects.filter(status=Exam.Status.ACTIVE).count(),
            "appointments": Appointment.objects.count(),
            "logs": AuditLog.objects.count(),
        }
        return Response(summary)
