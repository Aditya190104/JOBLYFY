from django.conf import settings
from apps.accounts.models import Employer
from apps.jobs.locations import cities


def portal(request):
    return {
        "location_catalog": cities(),
        "sample_mode": settings.DEBUG
        and Employer.objects.filter(is_demo=True).exists(),
        "unread_notifications": request.user.notifications.filter(
            read_at__isnull=True
        ).count()
        if request.user.is_authenticated
        else 0,
    }
