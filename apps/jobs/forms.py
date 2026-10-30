from django import forms
from django.conf import settings
from django.utils import timezone
from apps.accounts.models import Employer
from apps.accounts.validators import validate_resume
from .models import Job, Application, Category, CompanyReview
from .locations import normalize_location, resolve_city


class JobForm(forms.ModelForm):
    publication_status = forms.ChoiceField(
        choices=Job.PUBLICATION_CHOICES, required=False, label="Job status"
    )
    edit_revision = forms.IntegerField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = Job
        fields = [
            "title",
            "category",
            "description",
            "requirements",
            "location",
            "salary",
            "salary_min",
            "salary_max",
            "latitude",
            "longitude",
            "job_type",
            "experience_level",
            "work_mode",
            "deadline",
            "benefits",
            "publication_status",
            "responsibilities",
            "qualifications",
            "mandatory_skills",
            "preferred_skills",
            "min_experience",
            "max_experience",
            "application_instructions",
        ]
        widgets = {
            "deadline": forms.DateInput(attrs={"type": "date"}),
            **{
                key: forms.Textarea(attrs={"rows": 5})
                for key in (
                    "description",
                    "requirements",
                    "benefits",
                    "responsibilities",
                    "qualifications",
                    "application_instructions",
                )
            },
        }
        help_texts = {
            "salary": "Include currency and period, e.g. ₹6–9 LPA or ₹30,000/month.",
            "deadline": "Optional. Applications close after this date (India time).",
        }

    def clean_location(self):
        return normalize_location(self.cleaned_data["location"])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["publication_status"].initial = (
            self.instance.publication_status if self.instance.pk else "draft"
        )
        self.fields["edit_revision"].initial = (
            self.instance.screening_revision if self.instance.pk else 0
        )
        self.fields["requirements"].label = "Additional requirements"
        self.fields["qualifications"].label = "Required qualifications (description)"
        self.fields["min_experience"].label = "Minimum relevant experience (years)"
        self.fields["max_experience"].label = "Maximum relevant experience (years)"
        for name in ("mandatory_skills", "preferred_skills"):
            self.fields[name].widget = forms.Textarea(attrs={"rows": 2})
            self.fields[
                name
            ].help_text = "Comma-separated skill names, up to 30. Case and spacing are ignored; aliases are not inferred."
        self.fields[
            "preferred_skills"
        ].help_text += " Preferred skills never block applications."
        for name in ("description", "requirements", "benefits"):
            self.fields[name].widget.attrs["maxlength"] = 20000
        self.fields["salary"].label = "Salary description (optional)"
        self.fields[
            "salary"
        ].help_text = "Keep a free-text salary for other currencies or periods. Annual INR fields below enable salary filtering and take display priority."
        self.fields["salary_min"].label = "Minimum annual salary (INR)"
        self.fields["salary_max"].label = "Maximum annual salary (INR)"
        self.fields[
            "latitude"
        ].help_text = "Optional public workplace coordinate, not a home address. Enter both coordinates to enable a map."
        self.fields[
            "longitude"
        ].help_text = "Without coordinates, nearby search uses an approximate supported city center."
        self.fields["location"].widget.attrs.update(
            {"data-location-input": "", "autocomplete": "off"}
        )

    def clean_deadline(self):
        date = self.cleaned_data.get("deadline")
        keep_expired = (
            self.instance.pk
            and self.instance.deadline == date
            and self.data.get("publication_status") in {"paused", "closed", "draft"}
        )
        if date and date < timezone.localdate() and not keep_expired:
            raise forms.ValidationError("Choose today or a future date.")
        return date

    def clean_publication_status(self):
        return self.cleaned_data.get("publication_status") or (
            self.instance.publication_status if self.instance.pk else "draft"
        )

    def clean(self):
        from .screening import split_items, validate_items

        data = super().clean()
        for name in ("mandatory_skills", "preferred_skills"):
            try:
                validate_items(split_items(data.get(name, "")))
            except forms.ValidationError as error:
                self.add_error(name, error)
        for name in ("description", "requirements", "benefits"):
            if len(data.get(name, "")) > 20000:
                self.add_error(name, "Use at most 20,000 characters.")
        return data


# Keep the original import name, with one form for both GET and POST.
JobPostForm = JobForm


class JobSearchForm(forms.Form):
    search = forms.CharField(
        required=False,
        max_length=150,
        label="Keyword",
        widget=forms.TextInput(attrs={"placeholder": "Job title, skill or company"}),
    )
    location = forms.CharField(
        required=False,
        max_length=100,
        widget=forms.TextInput(
            attrs={
                "placeholder": "City, state or Remote",
                "data-location-input": "",
                "autocomplete": "off",
            }
        ),
    )
    category = forms.ModelChoiceField(
        queryset=Category.objects.order_by("name"),
        required=False,
        empty_label="All categories",
    )
    job_type = forms.ChoiceField(
        required=False, choices=[("", "All job types")] + Job.JOB_TYPE_CHOICES
    )
    experience = forms.ChoiceField(
        required=False, choices=[("", "Any experience")] + Job.EXPERIENCE_CHOICES
    )
    work_mode = forms.ChoiceField(
        required=False, choices=[("", "All work modes")] + Job.WORK_MODE_CHOICES
    )
    company = forms.ModelChoiceField(
        queryset=Employer.objects.filter(user__is_active=True).order_by("company_name"),
        required=False,
        empty_label="All companies",
    )
    sort = forms.ChoiceField(
        required=False,
        choices=[
            ("latest", "Newest first"),
            ("relevance", "Best match"),
            ("oldest", "Oldest first"),
            ("title", "Job title A–Z"),
            ("deadline", "Closing soon"),
        ],
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not settings.DEBUG:
            self.fields["company"].queryset = self.fields["company"].queryset.filter(
                is_demo=False
            )
        for field in self.fields.values():
            field.widget.attrs["form"] = "job-search"

    radius = forms.ChoiceField(
        required=False,
        label="Distance from city center",
        choices=[
            ("", "Exact location"),
            ("10", "Within about 10 km"),
            ("25", "Within about 25 km"),
            ("50", "Within about 50 km"),
            ("100", "Within about 100 km"),
        ],
    )
    min_salary = forms.IntegerField(
        required=False,
        min_value=0,
        max_value=100000000,
        label="Minimum annual salary (INR)",
        widget=forms.NumberInput(attrs={"placeholder": "e.g. 600000"}),
    )
    max_salary = forms.IntegerField(
        required=False,
        min_value=0,
        max_value=100000000,
        label="Maximum annual salary (INR)",
        widget=forms.NumberInput(attrs={"placeholder": "e.g. 1200000"}),
    )
    posted = forms.ChoiceField(
        required=False,
        label="Date posted",
        choices=[
            ("", "Any time"),
            ("1", "Last 24 hours"),
            ("3", "Last 3 days"),
            ("7", "Last 7 days"),
            ("30", "Last 30 days"),
        ],
    )

    def clean_search(self):
        value = " ".join(self.cleaned_data.get("search", "").split())
        if len(value.split()) > 12:
            raise forms.ValidationError(
                "Use up to 12 keywords for a more focused search."
            )
        return value

    def clean_location(self):
        return normalize_location(self.cleaned_data.get("location", ""))

    def clean(self):
        data = super().clean()
        if data.get("location", "").casefold() in {"remote", "work from home", "wfh"}:
            if data.get("work_mode") and data["work_mode"] != "remote":
                self.add_error(
                    "work_mode", "Choose Remote or clear the Remote location."
                )
            data["work_mode"] = "remote"
        if (
            data.get("radius")
            and data.get("work_mode") != "remote"
            and not resolve_city(data.get("location", ""))
        ):
            self.add_error(
                "radius",
                "Choose a supported city suggestion for distance filtering, or use Exact location.",
            )
        low, high = data.get("min_salary"), data.get("max_salary")
        if low is not None and high is not None and low > high:
            self.add_error("max_salary", "Maximum salary must be at least the minimum.")
        return data


class CompanyReviewForm(forms.ModelForm):
    rating = forms.TypedChoiceField(
        choices=[(i, f"{i} / 5") for i in range(1, 6)], coerce=int
    )
    consent = forms.BooleanField(
        label="This reflects my own experience. I have not included private contact details or confidential information."
    )

    class Meta:
        model = CompanyReview
        fields = ["rating", "relationship", "title", "body"]
        widgets = {
            "body": forms.Textarea(
                attrs={"rows": 6, "minlength": 50, "maxlength": 2000}
            )
        }
        help_texts = {
            "relationship": "Self-reported. JOBLYFY does not verify employment.",
            "body": "50–2,000 characters. Keep it relevant and respectful. Your account name is not displayed publicly.",
        }

    def clean_body(self):
        body = self.cleaned_data["body"].strip()
        if len(body) < 50:
            raise forms.ValidationError(
                "Share at least 50 characters about your experience."
            )
        return body


class JobApplicationForm(forms.ModelForm):
    resume = forms.FileField(
        required=False,
        validators=[validate_resume],
        widget=forms.FileInput(attrs={"accept": ".pdf"}),
        help_text="PDF, up to 5 MB. Leave blank to use your saved profile resume.",
    )

    class Meta:
        model = Application
        fields = ["cover_letter", "resume"]
        widgets = {
            "cover_letter": forms.Textarea(
                attrs={
                    "rows": 5,
                    "placeholder": "Tell the team why this opportunity interests you.",
                }
            )
        }

    def __init__(self, *args, seeker=None, **kwargs):
        self.seeker = seeker
        super().__init__(*args, **kwargs)

    def clean(self):
        data = super().clean()
        if not data.get("resume") and not (
            self.seeker and self.seeker.resume_available
        ):
            self.add_error(
                "resume",
                "Upload a resume here or add one to your profile before applying.",
            )
        return data


class CoverLetterForm(forms.ModelForm):
    class Meta:
        model = Application
        fields = ["cover_letter"]
        widgets = {"cover_letter": forms.Textarea(attrs={"rows": 8})}


class ApplicationStatusForm(forms.Form):
    status = forms.ChoiceField(
        choices=[c for c in Application.STATUS_CHOICES if c[0] != "withdrawn"]
    )


class ApplicationFilterForm(forms.Form):
    screening = forms.ChoiceField(
        required=False,
        choices=[("", "All screening results")] + Application.SCREENING_CHOICES,
    )

    status = forms.ChoiceField(
        required=False, choices=[("", "All statuses")] + Application.STATUS_CHOICES
    )
    search = forms.CharField(
        required=False, max_length=150, label="Search applications"
    )
    job = forms.ModelChoiceField(
        queryset=Job.objects.none(), required=False, empty_label="All jobs"
    )

    def __init__(self, *args, employer=None, **kwargs):
        super().__init__(*args, **kwargs)
        if employer:
            self.fields["job"].queryset = Job.objects.filter(employer=employer)
        else:
            self.fields.pop("job")
