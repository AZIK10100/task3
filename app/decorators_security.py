import json
from functools import wraps

from django.contrib.auth import get_user_model
from django.http import JsonResponse

from .security import get_user_secret, verify_hash


def verify_request_signature(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        signature = request.headers.get("request-sign")
        if not signature:
            return JsonResponse({"detail": "request-sign header is required"}, status=400)

        user = request.user if getattr(request, "user", None) and request.user.is_authenticated else None
        if not user:
            username = request.headers.get("x-username")
            if not username:
                try:
                    username = json.loads(request.body.decode("utf-8") or "{}").get("username")
                except json.JSONDecodeError:
                    username = None
            if username:
                User = get_user_model()
                try:
                    user = User.objects.get(username=username)
                except User.DoesNotExist:
                    user = None

        secret = get_user_secret(user) if user else ""
        if not user or not secret:
            return JsonResponse({"detail": "Valid user secret is required"}, status=401)

        if not verify_hash(request.body.decode("utf-8"), secret, signature):
            return JsonResponse({"detail": "Invalid request signature"}, status=403)

        return view_func(request, *args, **kwargs)

    return wrapper
