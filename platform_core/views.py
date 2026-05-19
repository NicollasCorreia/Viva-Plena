import csv

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .decorators import role_required
from .forms import (
    AdminCreationForm,
    AccessRequestForm,
    ClinicAppointmentForm,
    ClinicRegistrationForm,
    EmailAuthenticationForm,
    FAQForm,
    SecureMessageForm,
)
from .models import AccessRequest, Appointment, AuditLog, CycleRecord, Exam, FAQ, MedicalHistory, SecureMessage, User
from .services import apply_exam_filters, estimate_next_cycle, log_action, notify, should_block_login


def home(request):
    faqs = FAQ.objects.filter(is_active=True)[:4]
    approved_professionals = User.objects.filter(
        role=User.Role.CLINIC,
        approval_status=User.ApprovalStatus.APPROVED,
        institution_name__iexact="CESMAC",
    ).count()
    context = {
        "faqs": faqs,
        "approved_professionals": approved_professionals,
        "patient_count": User.objects.filter(role=User.Role.PATIENT).count(),
        "exam_count": Exam.objects.filter(status=Exam.Status.ACTIVE).count(),
    }
    return render(request, "public/home.html", context)


def faq_public(request):
    return render(request, "public/faq.html", {"faqs": FAQ.objects.filter(is_active=True)})


def register_clinic(request):
    form = ClinicRegistrationForm(request.POST or None)
    if request.method == "POST":
        user = form.save()
        log_action(user, "Cadastro profissional", "Cadastro web recebido e aguardando análise da administração.", target_user=user, request=request)
        messages.success(request, "Recebemos seu cadastro profissional. Nossa equipe vai analisar e liberar o acesso em breve.")
        return redirect("login")
    return render(request, "public/register_clinic.html", {"form": form})


def login_view(request):
    form = EmailAuthenticationForm(request, data=request.POST or None)

    if request.method == "POST":
        email = request.POST.get("username", "").strip().lower()
        user = User.objects.filter(email__iexact=email).first()

        if user and should_block_login(user):
            messages.error(request, "Seu acesso foi pausado por alguns minutos após várias tentativas seguidas. Tente novamente daqui a pouco.")
            return render(request, "public/login.html", {"form": form})

        if form.is_valid():
            user = form.get_user()
            if user.role == User.Role.PATIENT:
                messages.warning(request, "O acesso para pacientes é exclusivo pelo aplicativo móvel.")
                return render(request, "public/login.html", {"form": form})

            if user.role == User.Role.CLINIC and user.approval_status == User.ApprovalStatus.PENDING:
                messages.warning(request, "Recebemos seu cadastro profissional. O acesso completo será liberado assim que a análise terminar.")
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
            log_action(user, "Falha de login", "Tentativa de acesso com dados inválidos.", target_user=user, request=request, level=AuditLog.Level.WARNING)
        messages.error(request, "Não conseguimos entrar com esse e-mail e senha. Confira os dados e tente novamente.")

    return render(request, "public/login.html", {"form": form})


@login_required
def dashboard_redirect(request):
    if request.user.role == User.Role.PATIENT:
        return redirect("patient_access")
    if request.user.role == User.Role.CLINIC:
        return redirect("professional_dashboard")
    return redirect("admin_dashboard")


@login_required
def logout_view(request):
    log_action(request.user, "Logout", "Sessão encerrada pela pessoa usuária.", target_user=request.user, request=request)
    logout(request)
    messages.success(request, "Você saiu da sua conta com segurança.")
    return redirect("home")



@role_required(User.Role.PATIENT)
def patient_access(request):
    return render(request, "patient/access.html")


@role_required(User.Role.CLINIC)
def clinic_dashboard(request):
    if request.user.approval_status != User.ApprovalStatus.APPROVED:
        return render(request, "clinic/dashboard.html", {"pending_approval": True})

    requests_list = request.user.clinic_requests.select_related("patient")[:5]
    appointments = (
        request.user.clinic_appointments.filter(
            status=Appointment.Status.SCHEDULED,
            scheduled_for__gte=timezone.now(),
        )
        .select_related("patient")
        .order_by("scheduled_for")[:5]
    )
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
            messages.error(request, "Seu acesso profissional ainda está em análise e não pode enviar pedidos por enquanto.")
            return redirect("professional_requests")
        if form.is_valid():
            patient = User.objects.filter(cpf=form.cleaned_data["patient_cpf"], role=User.Role.PATIENT).first()
            if not patient:
                messages.error(request, "Não encontramos uma paciente com esse CPF.")
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
                    notify(patient, "access", f"{request.user.full_name}, profissional do CESMAC, pediu acesso aos seus exames. Só ela poderá visualizar esse conteúdo se você aprovar.", is_critical=True)
                    log_action(request.user, "Solicitação de acesso", f"Pedido enviado para {patient.full_name}", target_user=patient, request=request)
                    messages.success(request, "Pedido enviado com sucesso. A paciente receberá um aviso.")
                else:
                    messages.warning(request, "Já existe um pedido em andamento para essa paciente.")
            return redirect("professional_requests")

    requests_list = request.user.clinic_requests.select_related("patient")
    return render(request, "clinic/requests.html", {"form": form, "requests_list": requests_list})


@role_required(User.Role.CLINIC)
def clinic_appointments(request):
    form = ClinicAppointmentForm(request.POST or None, clinic=request.user)
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "cancel_appointment":
            appointment = get_object_or_404(
                Appointment,
                pk=request.POST.get("appointment_id"),
                clinic=request.user,
            )
            if appointment.status != Appointment.Status.SCHEDULED:
                messages.warning(request, "Essa consulta já não está disponível para cancelamento.")
                return redirect("professional_appointments")

            appointment.status = Appointment.Status.CANCELLED
            appointment.save(update_fields=["status"])
            appointment_local = timezone.localtime(appointment.scheduled_for)
            notify(
                appointment.patient,
                "appointment",
                (
                    f"A consulta marcada para {appointment_local:%d/%m às %H:%M} "
                    f"com {request.user.full_name} foi cancelada."
                ),
                is_critical=True,
            )
            log_action(
                request.user,
                "Cancelamento de consulta",
                f"Consulta cancelada para {appointment.patient.full_name}",
                target_user=appointment.patient,
                request=request,
                level=AuditLog.Level.WARNING,
            )
            messages.success(request, "Consulta cancelada com sucesso.")
            return redirect("professional_appointments")

        if form.is_valid():
            appointment = form.save(commit=False)
            appointment.clinic = request.user
            appointment.save()
            notify(appointment.patient, "appointment", f"A profissional {request.user.full_name} agendou uma consulta para você.")
            log_action(request.user, "Agendamento de consulta", f"Consulta marcada para {appointment.patient.full_name}", target_user=appointment.patient, request=request)
            messages.success(request, "Consulta agendada com sucesso.")
            return redirect("professional_appointments")

    appointments = (
        request.user.clinic_appointments.exclude(status=Appointment.Status.CANCELLED)
        .select_related("patient")
        .order_by("scheduled_for")
    )
    return render(request, "clinic/appointments.html", {"form": form, "appointments": appointments})


@role_required(User.Role.CLINIC)
def clinic_exams(request):
    approved_requests = request.user.clinic_requests.filter(status=AccessRequest.Status.APPROVED).select_related("patient")
    patient_ids = approved_requests.values_list("patient_id", flat=True)
    selected_patient_id = request.GET.get("patient")
    performed_from = str(request.GET.get("performed_from", "")).strip()
    performed_to = str(request.GET.get("performed_to", "")).strip()
    selected_sort = str(request.GET.get("sort", "recent_upload")).strip() or "recent_upload"
    exams = Exam.objects.filter(owner_id__in=patient_ids, status=Exam.Status.ACTIVE).select_related("owner")
    exams = apply_exam_filters(exams, request.GET, patient_param="patient", default_sort=selected_sort)

    for exam in exams[:20]:
        log_action(request.user, "Visualização de exame", f"Exame visualizado: {exam.title}", target_user=exam.owner, request=request)

    return render(
        request,
        "clinic/exams.html",
        {
            "approved_requests": approved_requests,
            "exams": exams,
            "selected_patient_id": str(selected_patient_id or ""),
            "performed_from": performed_from,
            "performed_to": performed_to,
            "selected_sort": selected_sort,
        },
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
        notify(message.recipient, "admin", f"Você recebeu uma nova mensagem segura de {request.user.full_name}.")
        log_action(request.user, "Mensagem segura", f"Mensagem enviada para {message.recipient.full_name}", target_user=message.recipient, request=request)
        messages.success(request, "Sua mensagem foi enviada com sucesso.")
        return redirect("professional_messages")

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
        writer.writerow(["Exames liberados", exams_count])
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
            notify(clinic, "admin", "Seu acesso profissional foi aprovado e já pode ser usado no ambiente web do CESMAC.")
            log_action(request.user, "Aprovação profissional", f"Profissional aprovada: {clinic.full_name}", target_user=clinic, request=request)
            messages.success(request, "O acesso profissional foi aprovado com sucesso.")
        elif action == "reject":
            clinic.approval_status = User.ApprovalStatus.REJECTED
            clinic.save(update_fields=["approval_status", "updated_at"])
            notify(clinic, "admin", "Seu cadastro profissional não foi aprovado.", is_critical=True)
            log_action(request.user, "Recusa profissional", f"Profissional recusada: {clinic.full_name}", target_user=clinic, request=request, level=AuditLog.Level.WARNING)
            messages.warning(request, "O cadastro profissional foi recusado.")
        elif action == "suspend":
            clinic.approval_status = User.ApprovalStatus.SUSPENDED
            clinic.is_active = False
            clinic.save(update_fields=["approval_status", "is_active", "updated_at"])
            notify(clinic, "security", "Seu acesso profissional foi suspenso pela administração.", is_critical=True)
            log_action(request.user, "Suspensão profissional", f"Profissional suspensa: {clinic.full_name}", target_user=clinic, request=request, level=AuditLog.Level.WARNING)
            messages.warning(request, "O acesso profissional foi suspenso.")
        return redirect("admin_clinics")

    clinics = User.objects.filter(role=User.Role.CLINIC)
    return render(request, "admin_portal/clinics.html", {"clinics": clinics})


@role_required(User.Role.ADMIN)
def admin_accounts(request):
    admin_form = AdminCreationForm()

    def active_admins_queryset():
        return User.objects.filter(role=User.Role.ADMIN)

    def block_self_admin_change(target, action_label):
        if target.pk == request.user.pk:
            messages.error(request, f"Por segurança, você não pode {action_label} a sua própria conta por esta tela.")
            return True
        return False

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "create_admin":
            admin_form = AdminCreationForm(request.POST)
            if admin_form.is_valid():
                target = admin_form.save()
                notify(target, "admin", "Seu acesso administrativo foi criado e já pode ser usado na Viva Plena.")
                log_action(
                    request.user,
                    "Criação de administradora",
                    f"Nova conta administrativa criada: {target.full_name}",
                    target_user=target,
                    request=request,
                )
                messages.success(request, "A nova conta administrativa foi criada com sucesso.")
                return redirect("admin_accounts")
            messages.error(request, "Não foi possível criar a nova administradora. Revise os dados do formulário.")

        elif action == "promote_admin":
            target = get_object_or_404(User.objects.exclude(role=User.Role.ADMIN), pk=request.POST.get("user_id"))
            previous_role = target.get_role_display()
            target.role = User.Role.ADMIN
            target.approval_status = User.ApprovalStatus.APPROVED
            target.is_active = True
            target.is_staff = True
            target.is_superuser = False
            target.save(update_fields=["role", "approval_status", "is_active", "is_staff", "is_superuser", "updated_at"])
            notify(target, "admin", "Seu perfil agora também possui acesso administrativo na Viva Plena.")
            log_action(
                request.user,
                "Promoção para administradora",
                f"Conta promovida de {previous_role} para administradora: {target.full_name}",
                target_user=target,
                request=request,
            )
            messages.success(request, "A conta foi promovida para administradora com sucesso.")
            return redirect("admin_accounts")

        elif action == "toggle":
            target = get_object_or_404(User.objects.exclude(role=User.Role.ADMIN), pk=request.POST.get("user_id"))
            target.is_active = not target.is_active
            if not target.is_active:
                target.approval_status = User.ApprovalStatus.SUSPENDED
            elif target.role == User.Role.CLINIC:
                target.approval_status = User.ApprovalStatus.APPROVED
            else:
                target.approval_status = User.ApprovalStatus.APPROVED
            target.save(update_fields=["is_active", "approval_status", "updated_at"])
            log_action(request.user, "Alteração de status", f"Conta atualizada: {target.full_name}", target_user=target, request=request)
            messages.success(request, "O status da conta foi atualizado com sucesso.")
            return redirect("admin_accounts")

        elif action == "suspend_admin":
            target = get_object_or_404(active_admins_queryset(), pk=request.POST.get("user_id"))
            if block_self_admin_change(target, "suspender"):
                return redirect("admin_accounts")

            target.is_active = False
            target.approval_status = User.ApprovalStatus.SUSPENDED
            target.save(update_fields=["is_active", "approval_status", "updated_at"])
            notify(target, "security", "Seu acesso administrativo foi suspenso pela administração.", is_critical=True)
            log_action(
                request.user,
                "Suspensão de administradora",
                f"Conta administrativa suspensa: {target.full_name}",
                target_user=target,
                request=request,
                level=AuditLog.Level.WARNING,
            )
            messages.success(request, "A administradora foi suspensa com sucesso.")
            return redirect("admin_accounts")

        elif action == "reactivate_admin":
            target = get_object_or_404(active_admins_queryset(), pk=request.POST.get("user_id"))
            target.is_active = True
            target.approval_status = User.ApprovalStatus.APPROVED
            target.is_staff = True
            target.save(update_fields=["is_active", "approval_status", "is_staff", "updated_at"])
            notify(target, "admin", "Seu acesso administrativo foi reativado.")
            log_action(
                request.user,
                "Reativação de administradora",
                f"Conta administrativa reativada: {target.full_name}",
                target_user=target,
                request=request,
            )
            messages.success(request, "A administradora foi reativada com sucesso.")
            return redirect("admin_accounts")

        elif action == "demote_admin":
            target = get_object_or_404(active_admins_queryset(), pk=request.POST.get("user_id"))
            if block_self_admin_change(target, "rebaixar"):
                return redirect("admin_accounts")

            new_role = request.POST.get("target_role")
            if new_role not in {User.Role.PATIENT, User.Role.CLINIC}:
                messages.error(request, "Escolha um perfil válido para rebaixar a conta administrativa.")
                return redirect("admin_accounts")

            previous_role = target.get_role_display()
            target.role = new_role
            target.approval_status = User.ApprovalStatus.APPROVED
            target.is_active = True
            target.is_staff = False
            target.is_superuser = False
            if new_role == User.Role.CLINIC and not target.institution_name:
                target.institution_name = "CESMAC"
            target.save(update_fields=["role", "approval_status", "is_active", "is_staff", "is_superuser", "institution_name", "updated_at"])
            notify(target, "admin", f"Seu acesso administrativo foi removido. Seu novo perfil é {target.get_role_display().lower()}.")
            log_action(
                request.user,
                "Rebaixamento de administradora",
                f"Conta rebaixada de {previous_role} para {target.get_role_display()}: {target.full_name}",
                target_user=target,
                request=request,
                level=AuditLog.Level.WARNING,
            )
            messages.success(request, "A administradora foi rebaixada com sucesso.")
            return redirect("admin_accounts")

    admins = active_admins_queryset().order_by("full_name", "email")
    users = User.objects.exclude(role=User.Role.ADMIN).order_by("role", "full_name")
    return render(
        request,
        "admin_portal/accounts.html",
        {
            "admin_form": admin_form,
            "admins": admins,
            "users": users,
        },
    )


@role_required(User.Role.ADMIN)
def admin_logs(request):
    level = request.GET.get("level")
    logs = AuditLog.objects.select_related("actor", "target_user")
    if level:
        logs = logs.filter(level=level)
    return render(request, "admin_portal/logs.html", {"logs": logs[:300], "level": level or ""})


@role_required(User.Role.ADMIN)
def admin_faq(request):
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "delete":
            faq = get_object_or_404(FAQ, pk=request.POST.get("faq_id"))
            question = faq.question
            faq.delete()
            log_action(request.user, "Ajuda excluída", f"Pergunta removida: {question}", request=request)
            messages.success(request, "A pergunta foi excluída com sucesso.")
            return redirect("admin_faq")
            
        elif action == "toggle_status":
            faq = get_object_or_404(FAQ, pk=request.POST.get("faq_id"))
            faq.is_active = not faq.is_active
            faq.save(update_fields=["is_active", "updated_at"])
            state_label = "ativada" if faq.is_active else "desativada"
            log_action(request.user, "Status da ajuda alterado", f"Pergunta {state_label}: {faq.question}", request=request)
            messages.success(request, f"A pergunta foi {state_label} com sucesso.")
            return redirect("admin_faq")

    form = FAQForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        faq = form.save()
        log_action(request.user, "FAQ atualizada", f"Pergunta salva: {faq.question}", request=request)
        messages.success(request, "A pergunta foi salva com sucesso.")
        return redirect("admin_faq")

    faqs = FAQ.objects.all()
    return render(request, "admin_portal/faq.html", {"form": form, "faqs": faqs})


@role_required(User.Role.ADMIN)
def admin_reports(request):
    summary = [
        ("Usuários", User.objects.count()),
        ("Pacientes", User.objects.filter(role=User.Role.PATIENT).count()),
        ("Clínicas", User.objects.filter(role=User.Role.CLINIC).count()),
        ("Clínicas aprovadas", User.objects.filter(role=User.Role.CLINIC, approval_status=User.ApprovalStatus.APPROVED).count()),
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
