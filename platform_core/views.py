import csv

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .decorators import role_required
from .forms import (
    AccessRequestForm,
    AppointmentForm,
    ClinicRegistrationForm,
    CycleRecordForm,
    EmailAuthenticationForm,
    ExamForm,
    FAQForm,
    MedicalHistoryForm,
    PatientRegistrationForm,
    SecureMessageForm,
)
from .models import AccessRequest, Appointment, AuditLog, CycleRecord, Exam, FAQ, MedicalHistory, SecureMessage, User
from .services import estimate_next_cycle, log_action, notify, should_block_login


def home(request):
    faqs = FAQ.objects.filter(is_active=True)[:4]
    approved_clinics = User.objects.filter(
        role=User.Role.CLINIC,
        approval_status=User.ApprovalStatus.APPROVED,
    ).count()
    context = {
        "faqs": faqs,
        "approved_clinics": approved_clinics,
        "patient_count": User.objects.filter(role=User.Role.PATIENT).count(),
        "exam_count": Exam.objects.filter(status=Exam.Status.ACTIVE).count(),
    }
    return render(request, "public/home.html", context)


def faq_public(request):
    return render(request, "public/faq.html", {"faqs": FAQ.objects.filter(is_active=True)})


def register_patient(request):
    form = PatientRegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        log_action(user, "Cadastro de usuária", "Nova conta criada pelo portal mobile.", target_user=user, request=request)
        notify(user, "admin", "Seu cadastro foi concluido com sucesso.", is_critical=False)
        login(request, user)
        messages.success(request, "Cadastro realizado com sucesso.")
        return redirect("patient_dashboard")
    return render(request, "public/register_patient.html", {"form": form})


def register_clinic(request):
    form = ClinicRegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        log_action(user, "Cadastro de clínica", "Clínica aguardando aprovação administrativa.", target_user=user, request=request)
        messages.success(request, "Cadastro enviado. A liberação será feita pela administração.")
        return redirect("login")
    return render(request, "public/register_clinic.html", {"form": form})


def login_view(request):
    form = EmailAuthenticationForm(request, data=request.POST or None)

    if request.method == "POST":
        email = request.POST.get("username", "").strip().lower()
        user = User.objects.filter(email__iexact=email).first()

        if user and should_block_login(user):
            messages.error(request, "Acesso bloqueado temporariamente por excesso de tentativas.")
            return render(request, "public/login.html", {"form": form})

        if form.is_valid():
            user = form.get_user()
            if user.role == User.Role.CLINIC and user.approval_status == User.ApprovalStatus.PENDING:
                messages.warning(request, "Sua clínica ainda aguarda aprovação administrativa.")
            user.invalid_login_attempts = 0
            user.blocked_until = None
            user.save(update_fields=["invalid_login_attempts", "blocked_until", "updated_at"])
            login(request, user)
            log_action(user, "Login", "Acesso realizado com sucesso.", target_user=user, request=request)
            return redirect("dashboard_redirect")

        if user:
            user.invalid_login_attempts += 1
            if user.invalid_login_attempts >= 5:
                user.blocked_until = timezone.now() + timezone.timedelta(minutes=15)
            user.save(update_fields=["invalid_login_attempts", "blocked_until", "updated_at"])
            log_action(user, "Falha de login", "Credenciais invalidas.", target_user=user, request=request, level=AuditLog.Level.WARNING)
        messages.error(request, "Não foi possível autenticar com os dados informados.")

    return render(request, "public/login.html", {"form": form})


@login_required
def dashboard_redirect(request):
    if request.user.role == User.Role.PATIENT:
        return redirect("patient_dashboard")
    if request.user.role == User.Role.CLINIC:
        return redirect("clinic_dashboard")
    return redirect("admin_dashboard")


@login_required
def logout_view(request):
    log_action(request.user, "Logout", "Sessao encerrada pelo usuario.", target_user=request.user, request=request)
    logout(request)
    messages.success(request, "Sessao encerrada com sucesso.")
    return redirect("home")


@role_required(User.Role.PATIENT)
def patient_dashboard(request):
    recent_exams = request.user.exams.filter(status=Exam.Status.ACTIVE)[:4]
    recent_cycles = request.user.cycles.filter(is_active=True)[:3]
    pending_requests = request.user.patient_requests.filter(status=AccessRequest.Status.PENDING)
    appointments = request.user.appointments.exclude(status=Appointment.Status.CANCELLED)[:5]
    context = {
        "recent_exams": recent_exams,
        "recent_cycles": recent_cycles,
        "pending_requests": pending_requests,
        "appointments": appointments,
        "exam_count": request.user.exams.filter(status=Exam.Status.ACTIVE).count(),
        "clinic_links": request.user.patient_requests.filter(status=AccessRequest.Status.APPROVED).count(),
        "medical_history_count": request.user.medical_histories.filter(is_active=True).count(),
        "next_cycle_date": estimate_next_cycle(request.user.cycles.filter(is_active=True)),
    }
    return render(request, "patient/dashboard.html", context)


@role_required(User.Role.PATIENT)
def patient_exams(request):
    form = ExamForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        exam = form.save(commit=False)
        exam.owner = request.user
        exam.save()
        log_action(request.user, "Upload de exame", f"Exame enviado: {exam.title}", target_user=request.user, request=request)
        notify(request.user, "exam", f"O exame '{exam.title}' foi salvo com sucesso.")
        messages.success(request, "Exame enviado com sucesso.")
        return redirect("patient_exams")

    exams = request.user.exams.all()
    return render(request, "patient/exams.html", {"form": form, "exams": exams})


@role_required(User.Role.PATIENT)
def patient_cycles(request):
    form = CycleRecordForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        cycle = form.save(commit=False)
        cycle.owner = request.user
        cycle.save()
        log_action(request.user, "Registro de ciclo", "Ciclo menstrual adicionado.", target_user=request.user, request=request)
        notify(request.user, "cycle", "Seu ciclo foi registrado com sucesso.")
        messages.success(request, "Ciclo registrado com sucesso.")
        return redirect("patient_cycles")

    cycles = request.user.cycles.all()
    prediction = estimate_next_cycle(request.user.cycles.filter(is_active=True))
    return render(request, "patient/cycles.html", {"form": form, "cycles": cycles, "prediction": prediction})


@role_required(User.Role.PATIENT)
def patient_histories(request):
    form = MedicalHistoryForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        history = form.save(commit=False)
        history.patient = request.user
        history.save()
        log_action(request.user, "Historico medico", f"Registro medico adicionado: {history.get_info_type_display()}", target_user=request.user, request=request)
        messages.success(request, "Registro medico salvo com sucesso.")
        return redirect("patient_histories")

    histories = request.user.medical_histories.filter(is_active=True)
    return render(request, "patient/histories.html", {"form": form, "histories": histories})


@role_required(User.Role.PATIENT)
def patient_access(request):
    if request.method == "POST":
        access = get_object_or_404(AccessRequest, pk=request.POST.get("access_id"), patient=request.user)
        action = request.POST.get("action")

        if action == "approve":
            access.status = AccessRequest.Status.APPROVED
            access.responded_at = timezone.now()
            access.save(update_fields=["status", "responded_at"])
            notify(access.clinic, "access", f"A paciente {request.user.full_name} aprovou o acesso.")
            log_action(request.user, "Aprovação de acesso", f"Acesso aprovado para {access.clinic.full_name}", target_user=access.clinic, request=request)
            messages.success(request, "Acesso aprovado com sucesso.")
        elif action == "reject":
            access.status = AccessRequest.Status.REJECTED
            access.responded_at = timezone.now()
            access.save(update_fields=["status", "responded_at"])
            notify(access.clinic, "access", f"A paciente {request.user.full_name} recusou o acesso.")
            log_action(request.user, "Recusa de acesso", f"Acesso recusado para {access.clinic.full_name}", target_user=access.clinic, request=request, level=AuditLog.Level.WARNING)
            messages.warning(request, "Solicitação recusada.")
        elif action == "revoke":
            access.status = AccessRequest.Status.REVOKED
            access.responded_at = timezone.now()
            access.save(update_fields=["status", "responded_at"])
            notify(access.clinic, "security", f"O acesso da clínica à paciente {request.user.full_name} foi revogado.", is_critical=True)
            log_action(request.user, "Revogação de acesso", f"Acesso revogado para {access.clinic.full_name}", target_user=access.clinic, request=request, level=AuditLog.Level.WARNING)
            messages.warning(request, "Acesso revogado imediatamente.")
        return redirect("patient_access")

    requests_list = request.user.patient_requests.select_related("clinic")
    return render(request, "patient/access.html", {"requests_list": requests_list})


@role_required(User.Role.PATIENT)
def patient_appointments(request):
    form = AppointmentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        appointment = form.save(commit=False)
        appointment.patient = request.user
        appointment.save()
        notify(request.user, "appointment", "Sua consulta foi agendada com sucesso.")
        notify(appointment.clinic, "appointment", f"Nova consulta agendada por {request.user.full_name}.")
        log_action(request.user, "Agendamento de consulta", f"Consulta com {appointment.clinic.full_name}", target_user=appointment.clinic, request=request)
        messages.success(request, "Consulta agendada com sucesso.")
        return redirect("patient_appointments")

    appointments = request.user.appointments.select_related("clinic")
    return render(request, "patient/appointments.html", {"form": form, "appointments": appointments})


@role_required(User.Role.PATIENT)
def patient_messages(request):
    allowed_recipients = User.objects.filter(
        id__in=request.user.patient_requests.filter(status=AccessRequest.Status.APPROVED).values_list("clinic_id", flat=True)
    )
    form = SecureMessageForm(request.POST or None, allowed_recipients=allowed_recipients)
    if request.method == "POST" and form.is_valid():
        message = form.save(commit=False)
        message.sender = request.user
        message.save()
        notify(message.recipient, "admin", f"Nova mensagem segura de {request.user.full_name}.")
        log_action(request.user, "Mensagem segura", f"Mensagem enviada para {message.recipient.full_name}", target_user=message.recipient, request=request)
        messages.success(request, "Mensagem enviada com sucesso.")
        return redirect("patient_messages")

    inbox = SecureMessage.objects.filter(Q(sender=request.user) | Q(recipient=request.user)).select_related("sender", "recipient")
    return render(request, "patient/messages.html", {"form": form, "messages_list": inbox})


@role_required(User.Role.PATIENT)
def patient_notifications(request):
    if request.method == "POST":
        request.user.notifications.filter(read_at__isnull=True).update(read_at=timezone.now())
        messages.success(request, "Notificações marcadas como lidas.")
        return redirect("patient_notifications")

    notifications = request.user.notifications.all()
    return render(request, "patient/notifications.html", {"notifications": notifications})


@role_required(User.Role.CLINIC)
def clinic_dashboard(request):
    if request.user.approval_status != User.ApprovalStatus.APPROVED:
        return render(request, "clinic/dashboard.html", {"pending_approval": True})

    requests_list = request.user.clinic_requests.select_related("patient")[:5]
    appointments = request.user.clinic_appointments.select_related("patient")[:5]
    approved_patient_ids = request.user.clinic_requests.filter(status=AccessRequest.Status.APPROVED).values_list("patient_id", flat=True)
    context = {
        "pending_approval": False,
        "requests_list": requests_list,
        "appointments": appointments,
        "approved_count": request.user.clinic_requests.filter(status=AccessRequest.Status.APPROVED).count(),
        "pending_count": request.user.clinic_requests.filter(status=AccessRequest.Status.PENDING).count(),
        "exam_count": Exam.objects.filter(owner_id__in=approved_patient_ids, status=Exam.Status.ACTIVE).count(),
    }
    return render(request, "clinic/dashboard.html", context)


@role_required(User.Role.CLINIC)
def clinic_requests(request):
    form = AccessRequestForm(request.POST or None)

    if request.method == "POST":
        if request.user.approval_status != User.ApprovalStatus.APPROVED:
            messages.error(request, "Sua clínica ainda não foi aprovada.")
            return redirect("clinic_requests")
        if form.is_valid():
            patient = User.objects.filter(cpf=form.cleaned_data["patient_cpf"], role=User.Role.PATIENT).first()
            if not patient:
                messages.error(request, "Paciente não encontrada com esse CPF.")
            else:
                access, created = AccessRequest.objects.get_or_create(
                    clinic=request.user,
                    patient=patient,
                    defaults={"request_note": form.cleaned_data["request_note"]},
                )
                if created or access.status in {AccessRequest.Status.REJECTED, AccessRequest.Status.REVOKED}:
                    if not created:
                        access.status = AccessRequest.Status.PENDING
                        access.request_note = form.cleaned_data["request_note"]
                        access.responded_at = None
                        access.save(update_fields=["status", "request_note", "responded_at"])
                    notify(patient, "access", f"A clínica {request.user.full_name} solicitou acesso aos seus exames.", is_critical=True)
                    log_action(request.user, "Solicitação de acesso", f"Acesso solicitado para {patient.full_name}", target_user=patient, request=request)
                    messages.success(request, "Solicitação enviada com sucesso.")
                else:
                    messages.warning(request, "Já existe uma solicitação ativa para essa paciente.")
            return redirect("clinic_requests")

    requests_list = request.user.clinic_requests.select_related("patient")
    return render(request, "clinic/requests.html", {"form": form, "requests_list": requests_list})


@role_required(User.Role.CLINIC)
def clinic_exams(request):
    approved_requests = request.user.clinic_requests.filter(status=AccessRequest.Status.APPROVED).select_related("patient")
    patient_ids = approved_requests.values_list("patient_id", flat=True)
    selected_patient_id = request.GET.get("patient")
    exams = Exam.objects.filter(owner_id__in=patient_ids, status=Exam.Status.ACTIVE).select_related("owner")
    if selected_patient_id:
        exams = exams.filter(owner_id=selected_patient_id)

    for exam in exams[:20]:
        log_action(request.user, "Visualização de exame", f"Exame visualizado: {exam.title}", target_user=exam.owner, request=request)

    return render(
        request,
        "clinic/exams.html",
        {"approved_requests": approved_requests, "exams": exams, "selected_patient_id": str(selected_patient_id or "")},
    )


@role_required(User.Role.CLINIC)
def clinic_messages(request):
    allowed_recipients = User.objects.filter(
        id__in=request.user.clinic_requests.filter(status=AccessRequest.Status.APPROVED).values_list("patient_id", flat=True)
    )
    form = SecureMessageForm(request.POST or None, allowed_recipients=allowed_recipients)
    if request.method == "POST" and form.is_valid():
        message = form.save(commit=False)
        message.sender = request.user
        message.save()
        notify(message.recipient, "admin", f"Nova mensagem segura de {request.user.full_name}.")
        log_action(request.user, "Mensagem segura", f"Mensagem enviada para {message.recipient.full_name}", target_user=message.recipient, request=request)
        messages.success(request, "Mensagem enviada com sucesso.")
        return redirect("clinic_messages")

    messages_list = SecureMessage.objects.filter(Q(sender=request.user) | Q(recipient=request.user)).select_related("sender", "recipient")
    return render(request, "clinic/messages.html", {"form": form, "messages_list": messages_list})


@role_required(User.Role.CLINIC)
def clinic_reports(request):
    approved_requests = request.user.clinic_requests.filter(status=AccessRequest.Status.APPROVED)
    exams_count = Exam.objects.filter(owner_id__in=approved_requests.values_list("patient_id", flat=True), status=Exam.Status.ACTIVE).count()
    appointments_count = request.user.clinic_appointments.count()
    if request.GET.get("export") == "csv":
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="relatorio_clinica.csv"'
        writer = csv.writer(response)
        writer.writerow(["Indicador", "Valor"])
        writer.writerow(["Pacientes com acesso aprovado", approved_requests.count()])
        writer.writerow(["Exames acessiveis", exams_count])
        writer.writerow(["Consultas", appointments_count])
        return response

    return render(
        request,
        "clinic/reports.html",
        {
            "approved_count": approved_requests.count(),
            "exams_count": exams_count,
            "appointments_count": appointments_count,
        },
    )


@role_required(User.Role.ADMIN)
def admin_dashboard(request):
    context = {
        "patient_count": User.objects.filter(role=User.Role.PATIENT).count(),
        "clinic_count": User.objects.filter(role=User.Role.CLINIC).count(),
        "pending_clinics": User.objects.filter(role=User.Role.CLINIC, approval_status=User.ApprovalStatus.PENDING),
        "exam_count": Exam.objects.filter(status=Exam.Status.ACTIVE).count(),
        "recent_logs": AuditLog.objects.select_related("actor", "target_user")[:10],
        "request_summary": AccessRequest.objects.values("status").annotate(total=Count("id")),
    }
    return render(request, "admin_portal/dashboard.html", context)


@role_required(User.Role.ADMIN)
def admin_clinics(request):
    if request.method == "POST":
        clinic = get_object_or_404(User, pk=request.POST.get("user_id"), role=User.Role.CLINIC)
        action = request.POST.get("action")

        if action == "approve":
            clinic.approval_status = User.ApprovalStatus.APPROVED
            clinic.is_active = True
            clinic.save(update_fields=["approval_status", "is_active", "updated_at"])
            notify(clinic, "admin", "Sua clínica foi aprovada e já pode acessar o sistema.")
            log_action(request.user, "Aprovação de clínica", f"Clínica aprovada: {clinic.full_name}", target_user=clinic, request=request)
            messages.success(request, "Clínica aprovada com sucesso.")
        elif action == "reject":
            clinic.approval_status = User.ApprovalStatus.REJECTED
            clinic.save(update_fields=["approval_status", "updated_at"])
            notify(clinic, "admin", "Sua solicitação de cadastro foi recusada.", is_critical=True)
            log_action(request.user, "Recusa de clínica", f"Clínica recusada: {clinic.full_name}", target_user=clinic, request=request, level=AuditLog.Level.WARNING)
            messages.warning(request, "Clínica recusada.")
        elif action == "suspend":
            clinic.approval_status = User.ApprovalStatus.SUSPENDED
            clinic.is_active = False
            clinic.save(update_fields=["approval_status", "is_active", "updated_at"])
            notify(clinic, "security", "Sua conta foi suspensa pelo administrador.", is_critical=True)
            log_action(request.user, "Suspensão de clínica", f"Clínica suspensa: {clinic.full_name}", target_user=clinic, request=request, level=AuditLog.Level.WARNING)
            messages.warning(request, "Clínica suspensa.")
        return redirect("admin_clinics")

    clinics = User.objects.filter(role=User.Role.CLINIC)
    return render(request, "admin_portal/clinics.html", {"clinics": clinics})


@role_required(User.Role.ADMIN)
def admin_accounts(request):
    if request.method == "POST":
        target = get_object_or_404(User, pk=request.POST.get("user_id"))
        action = request.POST.get("action")
        if action == "toggle":
            target.is_active = not target.is_active
            if not target.is_active:
                target.approval_status = User.ApprovalStatus.SUSPENDED
            elif target.role == User.Role.CLINIC:
                target.approval_status = User.ApprovalStatus.APPROVED
            else:
                target.approval_status = User.ApprovalStatus.APPROVED
            target.save(update_fields=["is_active", "approval_status", "updated_at"])
            log_action(request.user, "Alteração de status", f"Conta atualizada: {target.full_name}", target_user=target, request=request)
            messages.success(request, "Status da conta atualizado.")
        return redirect("admin_accounts")

    users = User.objects.exclude(role=User.Role.ADMIN).order_by("role", "full_name")
    return render(request, "admin_portal/accounts.html", {"users": users})


@role_required(User.Role.ADMIN)
def admin_logs(request):
    level = request.GET.get("level")
    logs = AuditLog.objects.select_related("actor", "target_user")
    if level:
        logs = logs.filter(level=level)
    return render(request, "admin_portal/logs.html", {"logs": logs[:300], "level": level or ""})


@role_required(User.Role.ADMIN)
def admin_faq(request):
    if request.method == "POST" and request.POST.get("action") == "toggle_status":
        faq = get_object_or_404(FAQ, pk=request.POST.get("faq_id"))
        faq.is_active = not faq.is_active
        faq.save(update_fields=["is_active", "updated_at"])
        state_label = "ativada" if faq.is_active else "desativada"
        log_action(request.user, "Status de FAQ alterado", f"FAQ {state_label}: {faq.question}", request=request)
        messages.success(request, f"FAQ {state_label} com sucesso.")
        return redirect("admin_faq")

    form = FAQForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        faq = form.save()
        log_action(request.user, "FAQ atualizada", f"Pergunta criada/atualizada: {faq.question}", request=request)
        messages.success(request, "FAQ salva com sucesso.")
        return redirect("admin_faq")

    faqs = FAQ.objects.all()
    return render(request, "admin_portal/faq.html", {"form": form, "faqs": faqs})


@role_required(User.Role.ADMIN)
def admin_reports(request):
    summary = [
        ("Usuarios", User.objects.count()),
        ("Pacientes", User.objects.filter(role=User.Role.PATIENT).count()),
        ("Clinicas", User.objects.filter(role=User.Role.CLINIC).count()),
        ("Clinicas aprovadas", User.objects.filter(role=User.Role.CLINIC, approval_status=User.ApprovalStatus.APPROVED).count()),
        ("Exames", Exam.objects.filter(status=Exam.Status.ACTIVE).count()),
        ("Consultas", Appointment.objects.count()),
        ("Logs", AuditLog.objects.count()),
    ]

    if request.GET.get("export") == "csv":
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="relatorio_admin.csv"'
        writer = csv.writer(response)
        writer.writerow(["Indicador", "Valor"])
        for label, value in summary:
            writer.writerow([label, value])
        return response

    return render(request, "admin_portal/reports.html", {"summary": summary})
