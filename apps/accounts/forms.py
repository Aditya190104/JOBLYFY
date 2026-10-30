from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import UserCreationForm
from django.db import transaction
from .models import CustomUser, Employer, JobSeeker
from .validators import validate_resume, validate_logo


class LoginForm(forms.Form):
    username_or_email = forms.CharField(
        label="Username or email",
        max_length=254,
        widget=forms.TextInput(attrs={"autocomplete": "username", "autofocus": True}),
    )
    password = forms.CharField(
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )
    remember = forms.BooleanField(
        required=False,
        label="Keep me signed in",
        help_text="Stay signed in for 14 days on this device. Leave unchecked on a shared computer.",
    )

    def __init__(self, *args, request=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.request = request
        self.user = None

    def clean(self):
        data = super().clean()
        identity, password = data.get("username_or_email", ""), data.get("password")
        if not password:
            return data
        user = CustomUser.objects.filter(username=identity).first()
        if user is None:
            names = list(CustomUser.objects.filter(username__iexact=identity)[:2])
            user = names[0] if len(names) == 1 else None
        if user is None:
            matches = list(CustomUser.objects.filter(email__iexact=identity)[:2])
            user = matches[0] if len(matches) == 1 else None
        # Always use the password hasher, including for an unknown identity.
        self.user = authenticate(
            self.request,
            username=user.username if user else identity,
            password=password,
        )
        if self.user is None:
            raise forms.ValidationError(
                "Unable to sign in. Check your username/email and password. If your email is shared by older accounts, use your username."
            )
        return data


class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)

    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = (
            "username",
            "first_name",
            "last_name",
            "email",
            "password1",
            "password2",
        )

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if CustomUser.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                "This email is already in use. Sign in or reset your password."
            )
        return email

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if CustomUser.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("This username is already in use.")
        return username

    def recheck_identity(self):
        """Called inside the existing SQLite IMMEDIATE save transaction.

        Keep legacy duplicate identities intact; new registrations must be unique.
        Validation outside this transaction alone would allow concurrent signups.
        """
        for field, clean in (
            ("email", self.clean_email),
            ("username", self.clean_username),
        ):
            try:
                clean()
            except forms.ValidationError as error:
                raise forms.ValidationError({field: error.messages}) from error


class EmployerSignUpForm(SignUpForm):
    company_name = forms.CharField(max_length=255)
    company_description = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}), required=False
    )
    company_website = forms.URLField(required=False, assume_scheme="https")
    company_logo = forms.ImageField(
        required=False,
        validators=[validate_logo],
        help_text="PNG, JPG or WebP, up to 2 MB.",
    )

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_employer, user.is_job_seeker = True, False
        if commit:
            self.recheck_identity()
            user.save()
            Employer.objects.create(
                user=user,
                **{
                    key: self.cleaned_data[key]
                    for key in (
                        "company_name",
                        "company_description",
                        "company_website",
                        "company_logo",
                    )
                },
            )
        return user


class JobSeekerSignUpForm(SignUpForm):
    skills = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 2}),
        required=False,
        help_text="Separate skills with commas.",
    )
    resume = forms.FileField(
        required=False,
        validators=[validate_resume],
        help_text="PDF, up to 5 MB and 30 pages. You can add this later.",
    )
    experience = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}), required=False
    )
    education = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}), required=False
    )

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_job_seeker, user.is_employer = True, False
        if commit:
            self.recheck_identity()
            user.save()
            JobSeeker.objects.create(
                user=user,
                **{
                    key: self.cleaned_data[key]
                    for key in ("skills", "resume", "experience", "education")
                },
            )
        return user


class UserProfileForm(forms.ModelForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = CustomUser
        fields = ("first_name", "last_name", "email")

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        # Preserve existing duplicate addresses until their owners voluntarily change them.
        if (
            email.casefold() != self.instance.email.strip().casefold()
            and CustomUser.objects.filter(email__iexact=email)
            .exclude(pk=self.instance.pk)
            .exists()
        ):
            raise forms.ValidationError("This email is already in use.")
        return email


class JobSeekerProfileForm(forms.ModelForm):
    class Meta:
        model = JobSeeker
        fields = (
            "headline",
            "location",
            "phone",
            "bio",
            "skills",
            "education",
            "experience",
            "resume",
        )
        widgets = {
            "location": forms.TextInput(
                attrs={"data-location-input": "", "autocomplete": "off"}
            ),
            **{
                key: forms.Textarea(attrs={"rows": 3})
                for key in ("bio", "skills", "education", "experience")
            },
            "resume": forms.FileInput(attrs={"accept": ".pdf"}),
        }
        help_texts = {
            "resume": "Upload a PDF up to 5 MB to replace your current resume. Earlier applications keep their submitted copy.",
            "skills": "Separate skills with commas.",
        }


class EmployerProfileForm(forms.ModelForm):
    company_website = forms.URLField(required=False, assume_scheme="https")

    class Meta:
        model = Employer
        fields = (
            "company_name",
            "company_description",
            "company_website",
            "company_logo",
            "location",
            "phone",
            "industry",
        )
        widgets = {
            "company_description": forms.Textarea(attrs={"rows": 6}),
            "location": forms.TextInput(
                attrs={"data-location-input": "", "autocomplete": "off"}
            ),
            "company_logo": forms.FileInput(attrs={"accept": ".png,.jpg,.jpeg,.webp"}),
        }
        help_texts = {"company_logo": "PNG, JPG or WebP, up to 2 MB."}


class JobPreferenceForm(forms.ModelForm):
    class Meta:
        from .models import JobPreference

        model = JobPreference
        fields = [
            "keywords",
            "location",
            "job_type",
            "work_mode",
            "experience",
            "min_salary",
        ]
        labels = {"min_salary": "Minimum annual salary (INR)"}
        help_texts = {
            "keywords": "All words must match a job title, description, requirements, company or category.",
            "min_salary": "Optional. Only jobs with a stated annual INR range can match this filter.",
        }

    def __init__(self, *args, **kwargs):
        from apps.jobs.models import Job

        super().__init__(*args, **kwargs)
        self.fields["min_salary"] = forms.IntegerField(
            required=False,
            min_value=0,
            max_value=100000000,
            label="Minimum annual salary (INR)",
            help_text="Optional; only stated annual INR ranges can match.",
        )
        for name, choices in [
            ("job_type", Job.JOB_TYPE_CHOICES),
            ("work_mode", Job.WORK_MODE_CHOICES),
            ("experience", Job.EXPERIENCE_CHOICES),
        ]:
            self.fields[name] = forms.ChoiceField(
                required=False,
                choices=[("", "Any")] + choices,
                label=name.replace("_", " ").title(),
            )
        self.fields["location"].widget.attrs.update(
            {"data-location-input": "", "autocomplete": "off"}
        )

    def clean_keywords(self):
        value = " ".join(self.cleaned_data.get("keywords", "").split())
        if len(value.split()) > 12:
            raise forms.ValidationError(
                "Use up to 12 keywords for a more focused search."
            )
        return value

    def clean_location(self):
        from apps.jobs.locations import normalize_location

        return normalize_location(self.cleaned_data["location"])

    def clean(self):
        data = super().clean()
        if data.get("location", "").casefold() in {"remote", "work from home", "wfh"}:
            data["work_mode"] = "remote"
            data["location"] = ""
        return data
