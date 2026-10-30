from django.contrib import admin
from .models import (
    Job,
    Category,
    Application,
    SavedJob,
    EligibilityRule,
    ScreeningAnswer,
)


class OwnedHiringAdmin(admin.ModelAdmin):
    owner_lookup = "employer__user"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_employer:
            return qs.filter(**{self.owner_lookup: request.user})
        if request.user.is_job_seeker:
            return qs.none()
        return qs

    def has_change_permission(self, request, obj=None):
        return (
            super().has_change_permission(request, obj)
            and not request.user.is_job_seeker
            and (
                obj is None
                or not request.user.is_employer
                or self.get_queryset(request).filter(pk=obj.pk).exists()
            )
        )

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(
            request, obj
        ) and self.has_change_permission(request, obj)

    def has_add_permission(self, request):
        return super().has_add_permission(request) and not request.user.is_job_seeker


class ScreeningAnswerInline(admin.TabularInline):
    model = ScreeningAnswer
    extra = 0
    fields = ("question_snapshot", "answer", "result", "explanation")
    readonly_fields = fields
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Job)
class JobAdmin(OwnedHiringAdmin):
    list_display = (
        "title",
        "employer",
        "category",
        "location",
        "job_type",
        "posted_date",
        "is_active",
    )
    list_filter = (
        "publication_status",
        "is_active",
        "job_type",
        "category",
        "work_mode",
    )
    search_fields = ("title", "description", "location")
    date_hierarchy = "posted_date"
    list_select_related = ("employer", "category")
    readonly_fields = ("is_active", "screening_revision")

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "employer" and request.user.is_employer:
            from apps.accounts.models import Employer

            kwargs["queryset"] = Employer.objects.filter(user=request.user)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        obj.is_active = obj.publication_status == "published"
        obj.screening_revision += 1
        super().save_model(request, obj, form, change)
        for kind, enabled in [
            (
                "experience",
                obj.min_experience is not None or obj.max_experience is not None,
            ),
            ("skills", bool(obj.mandatory_skill_list)),
        ]:
            if enabled:
                EligibilityRule.objects.get_or_create(job=obj, kind=kind)
            else:
                obj.eligibility_rules.filter(kind=kind).delete()


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "icon")
    search_fields = ("name",)


@admin.register(Application)
class ApplicationAdmin(OwnedHiringAdmin):
    owner_lookup = "job__employer__user"
    readonly_fields = (
        "job",
        "job_seeker",
        "cover_letter",
        "candidate_snapshot",
        "job_snapshot",
        "eligibility_snapshot",
        "screening_outcome",
    )
    inlines = (ScreeningAnswerInline,)

    def has_add_permission(self, request):
        return False

    list_display = ("job", "job_seeker", "applied_date", "status")
    list_filter = ("status", "applied_date")
    search_fields = ("job__title", "job_seeker__user__username")
    date_hierarchy = "applied_date"
    list_select_related = ("job", "job_seeker__user")
    # Files are served through the authorized application routes, never raw media URLs.
    exclude = ("resume",)


@admin.register(SavedJob)
class SavedJobAdmin(admin.ModelAdmin):
    list_display = ("job", "job_seeker", "created_at")
    list_select_related = ("job", "job_seeker__user")


from django.utils import timezone
from .models import CompanyReview


@admin.register(CompanyReview)
class CompanyReviewAdmin(admin.ModelAdmin):
    list_display = ("title", "employer", "rating", "status", "created_at")
    list_filter = ("status", "rating")
    search_fields = ("title", "body", "employer__company_name")
    list_select_related = ("employer", "author__user")
    readonly_fields = (
        "employer",
        "author",
        "rating",
        "relationship",
        "title",
        "body",
        "created_at",
        "updated_at",
        "moderated_at",
    )
    actions = ("approve_reviews", "reject_reviews")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return (
            super().has_change_permission(request, obj) and not request.user.is_employer
        )

    def has_delete_permission(self, request, obj=None):
        return (
            super().has_delete_permission(request, obj) and not request.user.is_employer
        )

    def save_model(self, request, obj, form, change):
        obj.moderated_at = timezone.now() if obj.status != "pending" else None
        super().save_model(request, obj, form, change)

    @admin.action(description="Publish selected reviews", permissions=["change"])
    def approve_reviews(self, request, queryset):
        queryset.update(status="approved", moderated_at=timezone.now())

    @admin.action(description="Do not publish selected reviews", permissions=["change"])
    def reject_reviews(self, request, queryset):
        queryset.update(status="rejected", moderated_at=timezone.now())
