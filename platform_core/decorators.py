from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect


def role_required(*roles):
    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if request.user.role not in roles:
                messages.error(request, "Voce nao tem permissao para acessar esta area.")
                return redirect("dashboard_redirect")
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator
