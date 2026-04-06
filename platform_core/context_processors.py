from .models import FAQ


def global_ui_context(request):
    unread_notifications = 0
    if getattr(request, "user", None) and request.user.is_authenticated:
        unread_notifications = request.user.notifications.filter(read_at__isnull=True).count()

    return {
        "public_faq_count": FAQ.objects.filter(is_active=True).count(),
        "unread_notifications": unread_notifications,
    }
