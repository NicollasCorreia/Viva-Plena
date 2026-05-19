from datetime import datetime, timedelta

from django.utils import timezone

from .models import Appointment, AuditLog, Notification


def get_client_ip(request):
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def log_action(actor, action, details="", target_user=None, request=None, level=AuditLog.Level.INFO):
    AuditLog.objects.create(
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        target_user=target_user,
        action=action,
        details=details,
        ip_address=get_client_ip(request) if request else None,
        level=level,
    )


def notify(recipient, notification_type, message, is_critical=False):
    Notification.objects.create(
        recipient=recipient,
        type=notification_type,
        message=message,
        is_critical=is_critical,
    )


def should_send_weekly_reminder(reference_date, current_date):
    return not reference_date or current_date >= reference_date + timedelta(days=7)


def ensure_patient_recurring_notifications(user):
    today = timezone.localdate()
    updated_fields = []

    if should_send_weekly_reminder(user.last_engagement_reminder_at, today):
        friendly_messages = [
            "Seu histórico está sempre por aqui. Abra o app quando quiser revisar seus exames, acessos e consultas.",
            "A Viva Plena continua ao seu lado. Aproveite para conferir seus exames e manter tudo em dia.",
            "Passando para lembrar que o app pode ajudar você a organizar consultas, exames e acessos em um só lugar.",
        ]
        notify(
            user,
            Notification.Type.ADMIN,
            friendly_messages[today.isocalendar().week % len(friendly_messages)],
        )
        user.last_engagement_reminder_at = today
        updated_fields.append("last_engagement_reminder_at")

    pending_updates = []
    appointments = (
        user.appointments.filter(
            status=Appointment.Status.SCHEDULED,
            scheduled_for__date__gte=today,
        )
        .select_related("clinic")
        .order_by("scheduled_for")
    )

    for appointment in appointments:
        appointment_local = timezone.localtime(appointment.scheduled_for)
        days_until = (appointment_local.date() - today).days

        if days_until == 3 and not appointment.three_day_reminder_sent_at:
            notify(
                user,
                Notification.Type.APPOINTMENT,
                (
                    f"Faltam 3 dias para sua consulta em {appointment_local:%d/%m às %H:%M} "
                    f"com {appointment.professional.full_name}. Se puder, organize seus exames com antecedência."
                ),
            )
            appointment.three_day_reminder_sent_at = timezone.now()
            pending_updates.append(appointment)

        if days_until == 0 and not appointment.same_day_reminder_sent_at:
            notify(
                user,
                Notification.Type.APPOINTMENT,
                (
                    f"Sua consulta é hoje, às {appointment_local:%H:%M}, com {appointment.professional.full_name}. "
                    "Se fizer sentido para você, revise seus exames antes de sair."
                ),
                is_critical=True,
            )
            appointment.same_day_reminder_sent_at = timezone.now()
            if appointment not in pending_updates:
                pending_updates.append(appointment)

    if updated_fields:
        user.save(update_fields=updated_fields)

    for appointment in pending_updates:
        fields = []
        if appointment.three_day_reminder_sent_at:
            fields.append("three_day_reminder_sent_at")
        if appointment.same_day_reminder_sent_at:
            fields.append("same_day_reminder_sent_at")
        appointment.save(update_fields=fields)


def estimate_next_cycle(cycle_queryset):
    records = list(cycle_queryset.order_by("-start_date")[:3])
    if len(records) < 2:
        return None

    intervals = []
    for index in range(len(records) - 1):
        current = records[index].start_date
        previous = records[index + 1].start_date
        intervals.append((current - previous).days)

    if not intervals:
        return None

    average_days = round(sum(intervals) / len(intervals))
    last_cycle = records[0].start_date
    return last_cycle + timedelta(days=average_days)


def should_block_login(user):
    return bool(user.blocked_until and user.blocked_until > timezone.now())


def parse_exam_filter_date(value):
    raw_value = str(value or "").strip()
    if not raw_value:
        return None

    for date_format in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw_value, date_format).date()
        except ValueError:
            continue

    return None


def apply_exam_filters(queryset, params, patient_param=None, default_sort=""):
    patient_id = str(params.get(patient_param, "")).strip() if patient_param else ""
    if patient_id:
        queryset = queryset.filter(owner_id=patient_id)

    performed_from = parse_exam_filter_date(params.get("performed_from"))
    if performed_from:
        queryset = queryset.filter(performed_at__gte=performed_from)

    performed_to = parse_exam_filter_date(params.get("performed_to"))
    if performed_to:
        queryset = queryset.filter(performed_at__lte=performed_to)

    sort = str(params.get("sort", "")).strip() or default_sort
    ordering_map = {
        "recent_upload": ("-uploaded_at", "-performed_at"),
        "recent_exam": ("-performed_at", "-uploaded_at"),
        "oldest_exam": ("performed_at", "uploaded_at"),
        "oldest_upload": ("uploaded_at", "performed_at"),
    }
    if sort in ordering_map:
        queryset = queryset.order_by(*ordering_map[sort])

    return queryset
