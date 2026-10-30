from functools import wraps
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def role_required(role):
    """Require the role flag and corresponding existing profile."""

    def decorate(view):
        @login_required
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            flag = "is_employer" if role == "employer" else "is_job_seeker"
            profile = "employer" if role == "employer" else "jobseeker"
            if not getattr(request.user, flag, False) or not hasattr(
                request.user, profile
            ):
                raise PermissionDenied(
                    "This page requires a "
                    + role.replace("jobseeker", "job seeker")
                    + " account."
                )
            return view(request, *args, **kwargs)

        return wrapped

    return decorate
