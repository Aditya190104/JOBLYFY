from django.urls import path, reverse_lazy
from django.contrib.auth import views as auth_views
from . import views

app_name = "accounts"
urlpatterns = [
    path("preferences/", views.job_preferences, name="job_preferences"),
    path(
        "settings/",
        auth_views.PasswordChangeView.as_view(
            template_name="accounts/settings.html",
            success_url=reverse_lazy("accounts:password_change_done"),
        ),
        name="settings",
    ),
    path(
        "settings/password/done/",
        auth_views.PasswordChangeDoneView.as_view(
            template_name="accounts/password_change_done.html"
        ),
        name="password_change_done",
    ),
    path("signup/", views.signup_view, name="signup"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("signup/employer/", views.employer_signup, name="employer_signup"),
    path("signup/jobseeker/", views.jobseeker_signup, name="jobseeker_signup"),
    path("profile/", views.user_profile, name="user_profile"),
    path("profile/edit/", views.user_profile, name="edit_profile"),
    path("profile/resume/", views.own_resume, name="own_resume"),
    path("employer/profile/", views.employer_profile, name="employer_profile"),
    path(
        "employer/profile/edit/", views.employer_profile, name="edit_employer_profile"
    ),
    path("company/<int:pk>/logo/", views.company_logo, name="company_logo"),
    path("password_reset/", views.PasswordResetView.as_view(), name="password_reset"),
    path(
        "password_reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="accounts/password_reset_done.html"
        ),
        name="password_reset_done",
    ),
    path(
        "reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="accounts/password_reset_confirm.html",
            success_url=reverse_lazy("accounts:password_reset_complete"),
        ),
        name="password_reset_confirm",
    ),
    path(
        "reset/done/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="accounts/password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),
]
