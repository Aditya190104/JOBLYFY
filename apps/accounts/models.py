from django.db import models
from django.contrib.auth.models import AbstractUser
from django.urls import reverse
from .validators import validate_resume, validate_logo


class CustomUser(AbstractUser):
    is_employer = models.BooleanField(default=False)
    is_job_seeker = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def display_name(self):
        return self.get_full_name() or self.username

    @property
    def initials(self):
        return "".join(p[0] for p in self.display_name.split()[:2]).upper()


class Employer(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE)
    company_name = models.CharField(max_length=255)
    company_description = models.TextField(blank=True)
    company_website = models.URLField(blank=True)
    company_logo = models.ImageField(
        upload_to="company_logos/", blank=True, validators=[validate_logo]
    )
    location = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    industry = models.CharField(max_length=100, blank=True)
    is_demo = models.BooleanField(default=False, editable=False)

    def __str__(self):
        return self.company_name

    def get_absolute_url(self):
        return reverse("jobs:company_detail", args=[self.pk])

    @property
    def job_count(self):
        return self.jobs.open().count()

    @property
    def logo_available(self):
        return bool(
            self.company_logo
            and self.company_logo.storage.exists(self.company_logo.name)
        )

    @property
    def initials(self):
        return "".join(p[0] for p in self.company_name.split()[:2]).upper()


class JobSeeker(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE)
    resume = models.FileField(
        upload_to="resumes/", blank=True, validators=[validate_resume]
    )
    skills = models.TextField(blank=True)
    experience = models.TextField(blank=True)
    education = models.TextField(blank=True)
    headline = models.CharField(max_length=120, blank=True)
    bio = models.TextField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    location = models.CharField(max_length=100, blank=True)

    @property
    def skill_list(self):
        return [
            item.strip()
            for item in self.skills.replace("\n", ",").split(",")
            if item.strip()
        ][:20]

    @property
    def resume_available(self):
        return bool(self.resume and self.resume.storage.exists(self.resume.name))

    @property
    def completeness(self):
        values = [
            self.headline,
            self.location,
            self.skills,
            self.education,
            self.experience,
            self.resume_available,
        ]
        return round(sum(bool(v) for v in values) / len(values) * 100)

    def __str__(self):
        return self.user.username


class JobPreference(models.Model):
    job_seeker = models.OneToOneField(
        JobSeeker, on_delete=models.CASCADE, related_name="preferences"
    )
    keywords = models.CharField(max_length=150, blank=True)
    location = models.CharField(max_length=100, blank=True)
    job_type = models.CharField(max_length=20, blank=True)
    work_mode = models.CharField(max_length=20, blank=True)
    experience = models.CharField(max_length=20, blank=True)
    min_salary = models.PositiveIntegerField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def search_params(self):
        data = {
            name: getattr(self, name)
            for name in [
                "location",
                "job_type",
                "work_mode",
                "experience",
                "min_salary",
            ]
            if getattr(self, name)
        }
        if self.keywords:
            data["search"] = self.keywords
        return data
