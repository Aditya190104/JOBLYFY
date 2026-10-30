class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if not request.path.startswith("/admin/"):
            response["Content-Security-Policy"] = (
                "default-src 'self'; img-src 'self' data:; style-src 'self'; "
                "script-src 'self'; font-src 'self'; object-src 'none'; "
                "base-uri 'self'; frame-ancestors 'none'; form-action 'self'; frame-src https://www.openstreetmap.org"
            )
        response["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(self)"
        if request.user.is_authenticated:
            response["Cache-Control"] = "private, no-store"
        return response
