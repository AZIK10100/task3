import json

from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import JsonResponse

from .security import get_user_secret, verify_hash


class RequestSignatureMiddleware:
    """
    Validates request body HMAC from the `request-sign` header.

    Client:
        sign = HMAC_SHA256(raw_request_body, user.secret)
        headers["request-sign"] = sign
        headers["x-username"] = username
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.exempt_prefixes = tuple(
            getattr(
                settings,
                "REQUEST_SIGNATURE_EXEMPT_PREFIXES",
                ("/admin/", "/static/", "/media/"),
            )
        )

    def __call__(self, request):
        if not self._is_exempt(request):
            error = self._validate(request)
            if error:
                return error
        return self.get_response(request)

    def _is_exempt(self, request):
        if request.method == "OPTIONS":
            return True
        return request.path.startswith(self.exempt_prefixes)

    def _validate(self, request):
        signature = request.headers.get("request-sign")
        if not signature:
            return JsonResponse({"detail": "request-sign header is required"}, status=400)

        user = self._get_user(request)
        if not user:
            return JsonResponse({"detail": "Valid user is required for request signature"}, status=401)

        secret = get_user_secret(user)
        if not secret:
            return JsonResponse({"detail": "User secret is not configured"}, status=403)

        payload = request.body.decode("utf-8")
        if not verify_hash(payload, secret, signature):
            return JsonResponse({"detail": "Invalid request signature"}, status=403)
        return None

    def _get_user(self, request):
        if getattr(request, "user", None) and request.user.is_authenticated:
            return request.user

        username = request.headers.get("x-username")
        if not username:
            try:
                username = json.loads(request.body.decode("utf-8") or "{}").get("username")
            except json.JSONDecodeError:
                username = None

        if not username:
            return None

        User = get_user_model()
        try:
            return User.objects.get(username=username)
        except User.DoesNotExist:
            return None


class AdminIPRestrictionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.allowed_ips = set(getattr(settings, "ADMIN_ALLOWED_IPS", []))

    def __call__(self, request):
        if request.path.startswith("/admin/") and self.allowed_ips:
            ip_address = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
            ip_address = ip_address or request.META.get("REMOTE_ADDR")
            if ip_address not in self.allowed_ips:
                return JsonResponse({"detail": "Admin access denied"}, status=403)
        return self.get_response(request)
