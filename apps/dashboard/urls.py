from django.urls import path
from . import views

app_name = "dashboard"
urlpatterns = [
    path(
        "my-application/<int:application_id>/",
        views.application_detail,
        name="application_detail",
    ),
    path("notifications/", views.notifications, name="notifications"),
    path(
        "notifications/read-all/",
        views.read_all_notifications,
        name="read_all_notifications",
    ),
    path(
        "notifications/<int:pk>/read/",
        views.read_notification,
        name="read_notification",
    ),
    path("", views.home, name="home"),
    path("employer/", views.employer_dashboard, name="employer_dashboard"),
    path("jobseeker/", views.job_seeker_dashboard, name="jobseeker_dashboard"),
    path("jobs/", views.manage_jobs, name="manage_jobs"),
    path("applications/", views.applications, name="applications"),
    path(
        "employer/applications/",
        views.employer_applications,
        name="employer_applications",
    ),
    path("saved/", views.saved_jobs, name="saved_jobs"),
    path(
        "application/<int:application_id>/",
        views.candidate_detail,
        name="candidate_detail",
    ),
    path(
        "application/<int:application_id>/status/",
        views.manage_application,
        name="manage_application",
    ),
    path(
        "application/<int:application_id>/edit/",
        views.edit_application,
        name="edit_application",
    ),
    path(
        "application/<int:application_id>/withdraw/",
        views.withdraw_application,
        name="withdraw_application",
    ),
    path(
        "application/<int:application_id>/resume/",
        views.application_resume,
        name="application_resume",
    ),
]
