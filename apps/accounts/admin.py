from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Employer, JobSeeker


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ("username", "email", "is_employer", "is_job_seeker", "is_staff")
    list_filter = ("is_employer", "is_job_seeker", "is_staff")
    fieldsets = UserAdmin.fieldsets + (
        ("User Type", {"fields": ("is_employer", "is_job_seeker")}),
    )


@admin.register(Employer)
class EmployerAdmin(admin.ModelAdmin):
    list_display = ("company_name", "industry", "location")
    search_fields = ("company_name",)


@admin.register(JobSeeker)
class JobSeekerAdmin(admin.ModelAdmin):
    list_display = ("user", "headline", "location")
    list_select_related = ("user",)
    exclude = ("resume",)
