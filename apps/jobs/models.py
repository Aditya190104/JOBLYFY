from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from urllib.parse import urlencode
from apps.accounts.models import Employer, JobSeeker
from apps.accounts.validators import validate_resume
from django.db.models import Q
from django.utils import timezone
from django.urls import reverse


class Category(models.Model):
    name = models.CharField(max_length=100)
    icon = models.CharField(
        max_length=50, help_text="FontAwesome icon class (e.g., 'fas fa-code')"
    )

    def __str__(self):
        return self.name

    @property
    def job_count(self):
        return self.job_set.open().count()


class JobQuerySet(models.QuerySet):
    def open(self):
        qs = self if settings.DEBUG else self.filter(is_demo=False)
        return qs.filter(
            is_active=True,
            publication_status="published",
            employer__user__is_active=True,
        ).filter(Q(deadline__isnull=True) | Q(deadline__gte=timezone.localdate()))


class Job(models.Model):
    PUBLICATION_CHOICES = [
        ("draft", "Draft"),
        ("published", "Published"),
        ("paused", "Paused"),
        ("closed", "Closed"),
    ]

    JOB_TYPE_CHOICES = [
        ("full_time", "Full Time"),
        ("part_time", "Part Time"),
        ("contract", "Contract"),
        ("internship", "Internship"),
    ]

    EXPERIENCE_CHOICES = [
        ("entry", "Entry Level"),
        ("mid", "Mid Level"),
        ("senior", "Senior Level"),
    ]
    WORK_MODE_CHOICES = [
        ("onsite", "On-site"),
        ("hybrid", "Hybrid"),
        ("remote", "Remote"),
    ]
    title = models.CharField(max_length=255)
    employer = models.ForeignKey(
        Employer, on_delete=models.CASCADE, related_name="jobs"
    )
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True)
    description = models.TextField()
    requirements = models.TextField()
    location = models.CharField(max_length=255)
    salary = models.CharField(max_length=100, blank=True)
    job_type = models.CharField(max_length=20, choices=JOB_TYPE_CHOICES)
    posted_date = models.DateTimeField(auto_now_add=True)
    deadline = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    experience_level = models.CharField(
        max_length=20, choices=EXPERIENCE_CHOICES, default="entry"
    )
    work_mode = models.CharField(
        max_length=20, choices=WORK_MODE_CHOICES, default="onsite"
    )
    benefits = models.TextField(blank=True)
    publication_status = models.CharField(
        max_length=12, choices=PUBLICATION_CHOICES, default="published", db_index=True
    )
    responsibilities = models.TextField(blank=True, max_length=12000)
    qualifications = models.TextField(blank=True, max_length=6000)
    mandatory_skills = models.TextField(blank=True, max_length=2000)
    preferred_skills = models.TextField(blank=True, max_length=2000)
    min_experience = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(60)],
    )
    max_experience = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(60)],
    )
    application_instructions = models.TextField(blank=True, max_length=4000)
    screening_revision = models.PositiveIntegerField(default=1, editable=False)
    salary_min = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Annual INR, before tax. Optional; enter both ends of the range.",
    )
    salary_max = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )
    is_featured = models.BooleanField(
        default=False,
        help_text="Editorial selection, managed by the platform administrator.",
    )
    is_demo = models.BooleanField(default=False, editable=False)
    demo_key = models.CharField(
        max_length=80, blank=True, null=True, unique=True, editable=False
    )
    objects = JobQuerySet.as_manager()

    class Meta:
        ordering = ["-posted_date", "-pk"]
        constraints = [
            models.CheckConstraint(
                condition=Q(
                    publication_status__in=["draft", "published", "paused", "closed"]
                ),
                name="job_publication_valid",
            ),
            models.CheckConstraint(
                condition=(
                    Q(min_experience__isnull=True)
                    | Q(min_experience__gte=0, min_experience__lte=60)
                )
                & (
                    Q(max_experience__isnull=True)
                    | Q(max_experience__gte=0, max_experience__lte=60)
                )
                & (
                    Q(min_experience__isnull=True)
                    | Q(max_experience__isnull=True)
                    | Q(max_experience__gte=models.F("min_experience"))
                ),
                name="job_experience_range_valid",
            ),
            models.CheckConstraint(
                condition=(
                    Q(salary_min__isnull=True, salary_max__isnull=True)
                    | Q(
                        salary_min__isnull=False,
                        salary_max__isnull=False,
                        salary_min__gte=0,
                        salary_max__gte=models.F("salary_min"),
                    )
                ),
                name="job_salary_range_valid",
            ),
            models.CheckConstraint(
                condition=(
                    Q(latitude__isnull=True, longitude__isnull=True)
                    | Q(
                        latitude__isnull=False,
                        longitude__isnull=False,
                        latitude__gte=-90,
                        latitude__lte=90,
                        longitude__gte=-180,
                        longitude__lte=180,
                    )
                ),
                name="job_coordinates_valid",
            ),
        ]
        indexes = [
            models.Index(
                fields=["is_active", "-posted_date"], name="job_active_posted_idx"
            )
        ]

    def clean(self):
        super().clean()
        if (
            self.min_experience is not None
            and self.max_experience is not None
            and self.min_experience > self.max_experience
        ):
            raise ValidationError(
                {"max_experience": "Maximum experience must be at least the minimum."}
            )
        if (self.salary_min is None) != (self.salary_max is None):
            raise ValidationError(
                "Enter both minimum and maximum annual salary, or leave both blank."
            )
        if (
            self.salary_min is not None
            and self.salary_max is not None
            and self.salary_min > self.salary_max
        ):
            raise ValidationError(
                {"salary_max": "Maximum salary must be at least the minimum."}
            )
        if (self.latitude is None) != (self.longitude is None):
            raise ValidationError(
                "Enter both latitude and longitude, or leave both blank."
            )

    @property
    def salary_display(self):
        if self.salary_min is not None and self.salary_max is not None:
            if self.is_practice_demo and self.job_type == "internship":
                return f"₹{self.salary_min / 12:,.0f}–₹{self.salary_max / 12:,.0f} / month (sample stipend)"
            low, high = self.salary_min / 100000, self.salary_max / 100000
            return f"₹{low:,.2f}–{high:,.2f} lakh / year"
        return self.salary or "Salary not disclosed"

    @property
    def map_embed_url(self):
        if (
            self.latitude is None
            or self.longitude is None
            or self.work_mode == "remote"
        ):
            return ""
        lat, lon = float(self.latitude), float(self.longitude)
        bbox = f"{max(-180, lon - 0.025)},{max(-90, lat - 0.018)},{min(180, lon + 0.025)},{min(90, lat + 0.018)}"
        return "https://www.openstreetmap.org/export/embed.html?" + urlencode(
            {"bbox": bbox, "layer": "mapnik", "marker": f"{lat},{lon}"}
        )

    @property
    def map_link(self):
        if not self.map_embed_url:
            return ""
        return f"https://www.openstreetmap.org/?mlat={self.latitude}&mlon={self.longitude}#map=14/{self.latitude}/{self.longitude}"

    def __str__(self):
        return self.title

    @property
    def is_practice_demo(self):
        from .demo_catalog import DEMO_PREFIX

        return (
            self.is_demo
            and bool(self.demo_key and self.demo_key.startswith(DEMO_PREFIX))
            and self.employer.is_demo
        )

    @property
    def accepts_demo_applications(self):
        return settings.DEBUG and self.is_practice_demo

    @property
    def card_description(self):
        first, separator, body = self.description.partition("\n\n")
        if (
            self.is_practice_demo
            and separator
            and first.startswith("DEVELOPMENT SAMPLE —")
        ):
            return body
        return self.description

    @property
    def is_open(self):
        return (
            self.is_active
            and self.publication_status == "published"
            and (settings.DEBUG or not self.is_demo)
            and self.employer.user.is_active
            and (not self.deadline or self.deadline >= timezone.localdate())
        )

    @property
    def status_label(self):
        if self.publication_status == "published":
            if not self.is_active:
                return "Paused"
            if self.deadline and self.deadline < timezone.localdate():
                return "Expired"
        return self.get_publication_status_display()

    @property
    def experience_display(self):
        if self.min_experience is not None and self.max_experience is not None:
            return f"{self.min_experience:g}–{self.max_experience:g} years"
        if self.min_experience is not None:
            return f"At least {self.min_experience:g} years"
        if self.max_experience is not None:
            return f"Up to {self.max_experience:g} years"
        return self.get_experience_level_display()

    @property
    def mandatory_skill_list(self):
        from .screening import split_items

        return split_items(self.mandatory_skills)

    @property
    def preferred_skill_list(self):
        from .screening import split_items

        return split_items(self.preferred_skills)

    def get_absolute_url(self):
        return reverse("jobs:job_detail", args=[self.pk])


class Application(models.Model):
    SCREENING_CHOICES = [
        ("legacy", "Not assessed (older application)"),
        ("no_rules", "No automatic rules"),
        ("met", "Configured rules met"),
        ("review", "Recruiter review needed"),
        ("incomplete", "Information incomplete"),
    ]
    candidate_snapshot = models.JSONField(default=dict, blank=True, editable=False)
    job_snapshot = models.JSONField(default=dict, blank=True, editable=False)
    eligibility_snapshot = models.JSONField(default=dict, blank=True, editable=False)
    screening_outcome = models.CharField(
        max_length=12,
        choices=SCREENING_CHOICES,
        default="legacy",
        editable=False,
        db_index=True,
    )

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("reviewing", "Reviewing"),
        ("shortlisted", "Shortlisted"),
        ("interview", "Interview"),
        ("accepted", "Accepted"),
        ("rejected", "Rejected"),
        ("withdrawn", "Withdrawn"),
    ]

    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="applications")
    job_seeker = models.ForeignKey(
        JobSeeker, on_delete=models.CASCADE, related_name="applications"
    )
    cover_letter = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    applied_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)
    resume = models.FileField(
        upload_to="application_resumes/", blank=True, validators=[validate_resume]
    )

    class Meta:
        unique_together = ("job", "job_seeker")
        ordering = ["-applied_date", "-pk"]

    def __str__(self):
        return f"{self.job_seeker.user.username} - {self.job.title}"

    @property
    def resume_available(self):
        file = self.resume or self.job_seeker.resume
        return bool(file and file.storage.exists(file.name))

    @property
    def can_edit(self):
        return self.status == "pending" and self.job.is_open

    @property
    def can_withdraw(self):
        return self.status in {"pending", "reviewing", "shortlisted", "interview"}


class SavedJob(models.Model):
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="saves")
    job_seeker = models.ForeignKey(
        JobSeeker, on_delete=models.CASCADE, related_name="saved_jobs"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["job", "job_seeker"], name="unique_saved_job"
            )
        ]
        ordering = ["-created_at"]


class CompanyReview(models.Model):
    RELATIONSHIPS = [
        ("current", "Current employee"),
        ("former", "Former employee"),
        ("interview", "Interview candidate"),
    ]
    STATUSES = [
        ("pending", "Pending moderation"),
        ("approved", "Published"),
        ("rejected", "Not published"),
    ]
    employer = models.ForeignKey(
        Employer, on_delete=models.CASCADE, related_name="reviews"
    )
    author = models.ForeignKey(
        JobSeeker, on_delete=models.CASCADE, related_name="company_reviews"
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    relationship = models.CharField(max_length=12, choices=RELATIONSHIPS)
    title = models.CharField(max_length=100)
    body = models.TextField(max_length=2000)
    status = models.CharField(max_length=10, choices=STATUSES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    moderated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["employer", "author"], name="one_review_per_company_author"
            ),
            models.CheckConstraint(
                condition=Q(rating__gte=1, rating__lte=5), name="review_rating_valid"
            ),
        ]

    def __str__(self):
        return f"{self.employer}: {self.title}"


class EligibilityRule(models.Model):
    KINDS = [
        ("qualification", "Qualification"),
        ("experience", "Relevant experience"),
        ("skills", "Mandatory skills"),
        ("location", "Work location"),
        ("work_arrangement", "Work arrangement"),
    ]
    job = models.ForeignKey(
        Job, on_delete=models.CASCADE, related_name="eligibility_rules"
    )
    kind = models.CharField(max_length=20, choices=KINDS)
    values = models.JSONField(default=list, blank=True)
    is_blocking = models.BooleanField(default=False)
    allow_relocation = models.BooleanField(default=False)

    class Meta:
        ordering = ["kind"]
        constraints = [
            models.UniqueConstraint(
                fields=["job", "kind"], name="one_eligibility_rule_kind"
            )
        ]

    def clean(self):
        from .screening import validate_items

        validate_items(self.values)
        if self.kind in {"qualification", "location"} and not self.values:
            raise ValidationError({"values": "Provide at least one accepted value."})
        if self.kind != "location" and self.allow_relocation:
            raise ValidationError(
                {"allow_relocation": "Relocation applies only to location rules."}
            )

    def __str__(self):
        return f"{self.job}: {self.get_kind_display()}"


class ScreeningQuestion(models.Model):
    KINDS = [
        ("yes_no", "Yes / No"),
        ("single", "Single select"),
        ("multiple", "Multiple choice (select all that apply)"),
        ("text", "Short text"),
    ]
    MATCH_MODES = [
        ("none", "Manual review only"),
        ("any", "At least one accepted answer"),
        ("all", "All specified answers (multiple choice)"),
    ]
    job = models.ForeignKey(
        Job, on_delete=models.CASCADE, related_name="screening_questions"
    )
    prompt = models.CharField(max_length=400)
    kind = models.CharField(max_length=12, choices=KINDS)
    options = models.JSONField(default=list, blank=True)
    required = models.BooleanField(default=True)
    position = models.PositiveSmallIntegerField(
        default=1, validators=[MinValueValidator(1), MaxValueValidator(999)]
    )
    match_mode = models.CharField(max_length=8, choices=MATCH_MODES, default="none")
    expected_answers = models.JSONField(default=list, blank=True)
    is_blocking = models.BooleanField(default=False)

    class Meta:
        ordering = ["position", "pk"]

    def clean(self):
        from .screening import validate_items, normalized

        validate_items(self.options, limit=20)
        validate_items(self.expected_answers, limit=20)
        if self.kind in {"single", "multiple"} and len(self.options) < 2:
            raise ValidationError(
                {"options": "Provide 2–20 distinct options, one per line."}
            )
        if self.kind not in {"single", "multiple"} and self.options:
            raise ValidationError(
                {"options": "Only select questions use answer options."}
            )
        choices = ["yes", "no"] if self.kind == "yes_no" else self.options
        if self.match_mode != "none":
            if self.kind == "text":
                raise ValidationError(
                    {
                        "match_mode": "Short text needs human review; automatic text rejection is not supported."
                    }
                )
            if not self.expected_answers or any(
                normalized(v) not in {normalized(c) for c in choices}
                for v in self.expected_answers
            ):
                raise ValidationError(
                    {
                        "expected_answers": "Accepted answers must match the available choices (yes or no for Yes / No)."
                    }
                )
            if self.match_mode == "all" and self.kind != "multiple":
                raise ValidationError(
                    {
                        "match_mode": "All specified answers is only valid for multiple choice."
                    }
                )
        elif self.expected_answers or self.is_blocking:
            raise ValidationError(
                "Choose a matching rule before setting accepted answers or blocking submission."
            )
        if self.is_blocking and not self.required:
            raise ValidationError(
                {"required": "A blocking question must also be required."}
            )

    def __str__(self):
        return self.prompt


class ApplicationDraft(models.Model):
    job = models.ForeignKey(
        Job, on_delete=models.CASCADE, related_name="application_drafts"
    )
    job_seeker = models.ForeignKey(
        JobSeeker, on_delete=models.CASCADE, related_name="application_drafts"
    )
    candidate_data = models.JSONField(default=dict, blank=True)
    answers_data = models.JSONField(default=dict, blank=True)
    cover_letter = models.TextField(blank=True, max_length=6000)
    resume = models.FileField(
        upload_to="draft_resumes/", blank=True, validators=[validate_resume]
    )
    resume_label = models.CharField(max_length=150, blank=True)
    stage = models.PositiveSmallIntegerField(default=1)
    version = models.PositiveIntegerField(default=1)
    rules_fingerprint = models.CharField(max_length=64, blank=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["job", "job_seeker"], name="one_application_draft"
            ),
            models.CheckConstraint(
                condition=Q(stage__gte=1, stage__lte=4), name="draft_stage_valid"
            ),
        ]

    @property
    def resume_available(self):
        return bool(self.resume and self.resume.storage.exists(self.resume.name))


class ScreeningAnswer(models.Model):
    application = models.ForeignKey(
        Application, on_delete=models.CASCADE, related_name="screening_answers"
    )
    question = models.ForeignKey(
        ScreeningQuestion, null=True, blank=True, on_delete=models.SET_NULL
    )
    question_snapshot = models.JSONField(default=dict)
    answer = models.JSONField(default=str, blank=True)
    result = models.CharField(max_length=12)
    explanation = models.CharField(max_length=1000, blank=True)
    position = models.PositiveSmallIntegerField(default=1)

    class Meta:
        ordering = ["position", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["application", "question"], name="one_answer_per_question"
            )
        ]

    def clean(self):
        if (
            self.question_id
            and self.application_id
            and self.question.job_id != self.application.job_id
        ):
            raise ValidationError(
                "The screening question must belong to this application's job."
            )

    @property
    def display_answer(self):
        if isinstance(self.answer, list):
            return ", ".join(self.answer) or "Not answered"
        if self.question_snapshot.get("kind") == "yes_no":
            return {"yes": "Yes", "no": "No"}.get(self.answer, "Not answered")
        return self.answer or "Not answered"
