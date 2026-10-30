from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("apps.accounts.urls")),
    path("dashboard/", include("apps.dashboard.urls")),
    path("", include("apps.jobs.urls")),
]
# Intentionally no catch-all MEDIA_URL route. Resumes must remain private.
admin.site.site_header = "JOBLYFY administration"
admin.site.site_title = "JOBLYFY admin"
admin.site.index_title = "Platform management"
