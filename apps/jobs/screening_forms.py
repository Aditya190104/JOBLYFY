"""Server-validated recruiter rules and candidate answers."""

from django import forms
from django.core.exceptions import ValidationError
from django.forms import BaseInlineFormSet, inlineformset_factory
from apps.accounts.validators import validate_resume
from .models import Job, EligibilityRule, ScreeningQuestion
from .screening import split_items, validate_items
from .locations import normalize_location


class EligibilitySettingsForm(forms.Form):
    accepted_qualifications = forms.CharField(
        required=False,
        max_length=2000,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Optional automatic check. Comma-separated exact accepted qualifications and equivalencies, for example B.Tech, B.E. Blank means human review only.",
    )
    block_qualification = forms.BooleanField(
        required=False,
        label="Block submission when qualification is missing or does not match",
    )
    block_experience = forms.BooleanField(
        required=False, label="Block submission when the experience range is not met"
    )
    block_skills = forms.BooleanField(
        required=False, label="Block submission when mandatory skills are missing"
    )
    allowed_locations = forms.CharField(
        required=False,
        max_length=2000,
        widget=forms.Textarea(attrs={"rows": 2}),
        help_text="Optional eligibility restriction, including for remote roles. Comma-separated city names. Blank means no location restriction; this is separate from the job's display location.",
    )
    allow_relocation = forms.BooleanField(
        required=False, label="Accept willingness to relocate to an allowed location"
    )
    block_location = forms.BooleanField(
        required=False, label="Block submission when the location rule is not met"
    )
    check_work_arrangement = forms.BooleanField(
        required=False, label="Ask candidates to confirm the job's work arrangement"
    )
    block_work_arrangement = forms.BooleanField(
        required=False,
        label="Block submission when the work arrangement is not accepted",
    )

    def __init__(self, *args, job=None, **kwargs):
        initial = {}
        if job and job.pk:
            for rule in job.eligibility_rules.all():
                initial["block_" + rule.kind] = rule.is_blocking
                if rule.kind == "qualification":
                    initial["accepted_qualifications"] = ", ".join(rule.values)
                if rule.kind == "location":
                    initial["allowed_locations"] = ", ".join(rule.values)
                    initial["allow_relocation"] = rule.allow_relocation
                if rule.kind == "work_arrangement":
                    initial["check_work_arrangement"] = True
        kwargs.setdefault("initial", initial)
        super().__init__(*args, **kwargs)

    def clean(self):
        data = super().clean()
        for name in ("accepted_qualifications", "allowed_locations"):
            items = split_items(data.get(name, ""))
            try:
                validate_items(items)
            except ValidationError as error:
                self.add_error(name, error)
            data[name] = items
        if data.get("block_qualification") and not data.get("accepted_qualifications"):
            self.add_error(
                "accepted_qualifications",
                "Add accepted qualifications before enabling this block.",
            )
        if (
            data.get("block_location") or data.get("allow_relocation")
        ) and not data.get("allowed_locations"):
            self.add_error("allowed_locations", "Add allowed locations for this rule.")
        if data.get("block_work_arrangement") and not data.get(
            "check_work_arrangement"
        ):
            self.add_error(
                "check_work_arrangement", "Enable this check before making it blocking."
            )
        return data

    def validate_job(self, job):
        if (
            self.cleaned_data.get("block_experience")
            and job.min_experience is None
            and job.max_experience is None
        ):
            self.add_error(
                "block_experience",
                "Set an experience bound before enabling this block.",
            )
        if self.cleaned_data.get("block_skills") and not job.mandatory_skill_list:
            self.add_error(
                "block_skills", "Add mandatory skills before enabling this block."
            )
        return not self.errors

    def save(self, job):
        data = self.cleaned_data
        enabled = {
            "qualification": bool(data["accepted_qualifications"]),
            "experience": job.min_experience is not None
            or job.max_experience is not None,
            "skills": bool(job.mandatory_skill_list),
            "location": bool(data["allowed_locations"]),
            "work_arrangement": data["check_work_arrangement"],
        }
        for kind, active in enabled.items():
            if not active:
                job.eligibility_rules.filter(kind=kind).delete()
                continue
            values = (
                data["accepted_qualifications"]
                if kind == "qualification"
                else data["allowed_locations"]
                if kind == "location"
                else []
            )
            if kind == "location":
                values = list(dict.fromkeys(normalize_location(v) for v in values))
            EligibilityRule.objects.update_or_create(
                job=job,
                kind=kind,
                defaults={
                    "values": values,
                    "is_blocking": data["block_" + kind],
                    "allow_relocation": kind == "location" and data["allow_relocation"],
                },
            )


class ScreeningQuestionForm(forms.ModelForm):
    options = forms.CharField(
        required=False,
        max_length=2500,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Single/multiple select: 2–20 choices, one per line. Blank for Yes / No and short text.",
    )
    expected_answers = forms.CharField(
        required=False,
        max_length=2500,
        widget=forms.Textarea(attrs={"rows": 2}),
        help_text="One accepted answer per line, exactly matching a choice. For Yes / No use yes or no. Blank for manual review.",
    )

    class Meta:
        model = ScreeningQuestion
        fields = [
            "prompt",
            "kind",
            "options",
            "required",
            "position",
            "match_mode",
            "expected_answers",
            "is_blocking",
        ]
        labels = {
            "prompt": "Question",
            "kind": "Answer type",
            "position": "Display order",
            "match_mode": "Screening rule",
            "is_blocking": "Block submission if this rule is not met",
            "required": "Answer required",
        }
        widgets = {"prompt": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("options", "expected_answers"):
            self.initial[name] = "\n".join(getattr(self.instance, name, []) or [])

    def clean_options(self):
        items = [
            v.strip() for v in self.cleaned_data["options"].splitlines() if v.strip()
        ]
        validate_items(items, limit=20)
        return items

    def clean_expected_answers(self):
        items = [
            v.strip()
            for v in self.cleaned_data["expected_answers"].splitlines()
            if v.strip()
        ]
        validate_items(items, limit=20)
        return items


class OwnedQuestionFormSet(BaseInlineFormSet):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        next_position = max((q.position for q in self.get_queryset()), default=0) + 1
        for index, form in enumerate(self.extra_forms):
            form.initial["position"] = next_position + index

    def clean(self):
        super().clean()
        if any(self.errors):
            return
        owned_ids = set(self.queryset.values_list("pk", flat=True))
        submitted_ids, positions = set(), set()
        for form in self.forms:
            data = form.cleaned_data
            if not data:
                continue
            obj = data.get("id")
            if obj:
                if obj.pk not in owned_ids or obj.pk in submitted_ids:
                    raise forms.ValidationError(
                        "Invalid or repeated question. Reload this job's questions."
                    )
                submitted_ids.add(obj.pk)
            if data.get("DELETE"):
                continue
            if data.get("position") in positions:
                raise forms.ValidationError(
                    "Each question needs a different display order."
                )
            positions.add(data.get("position"))
        if submitted_ids != owned_ids:
            raise forms.ValidationError(
                "The question list changed or some questions are missing. Reload before saving."
            )


ScreeningQuestionFormSet = inlineformset_factory(
    Job,
    ScreeningQuestion,
    form=ScreeningQuestionForm,
    formset=OwnedQuestionFormSet,
    extra=1,
    can_delete=True,
    max_num=20,
    validate_max=True,
    absolute_max=40,
)


class CandidateEligibilityForm(forms.Form):
    def __init__(self, *args, job, rules, **kwargs):
        super().__init__(*args, **kwargs)
        kinds = {r.kind: r for r in rules}
        if "qualification" in kinds:
            self.fields["qualification"] = forms.CharField(
                required=False,
                max_length=200,
                label="Your relevant qualification",
                help_text="Accepted names: "
                + ", ".join(kinds["qualification"].values)
                + ". Enter your actual qualification; equivalents are not guessed.",
            )
        if "experience" in kinds:
            self.fields["years_experience"] = forms.DecimalField(
                required=False,
                min_value=0,
                max_value=60,
                max_digits=4,
                decimal_places=2,
                label="Years of relevant experience",
                help_text="Relevant experience only. Enter 0 for no experience.",
            )
        if "skills" in kinds or job.preferred_skills:
            self.fields["skills"] = forms.CharField(
                required=False,
                max_length=2000,
                widget=forms.Textarea(attrs={"rows": 3}),
                label="Your relevant skills",
                help_text="Comma-separated skill names. Matching ignores case and spacing, but does not infer aliases or proficiency.",
            )
        if "location" in kinds:
            self.fields["work_location"] = forms.CharField(
                required=False,
                max_length=100,
                label="City you can work from",
                widget=forms.TextInput(
                    attrs={"data-location-input": "", "autocomplete": "off"}
                ),
            )
            if kinds["location"].allow_relocation:
                self.fields["relocate"] = forms.ChoiceField(
                    required=False,
                    choices=[("", "Not answered"), ("yes", "Yes"), ("no", "No")],
                    label="Willing to relocate to an accepted location?",
                )
        if "work_arrangement" in kinds:
            self.fields["work_arrangement"] = forms.ChoiceField(
                required=False,
                choices=[("", "Not answered"), ("yes", "Yes"), ("no", "No")],
                label=f"Can you work {job.get_work_mode_display().lower()} as described in this job?",
            )

    def clean_skills(self):
        value = self.cleaned_data["skills"]
        validate_items(split_items(value))
        return value

    def clean_work_location(self):
        return normalize_location(self.cleaned_data["work_location"])


class CandidateScreeningForm(forms.Form):
    def __init__(self, *args, questions, **kwargs):
        super().__init__(*args, **kwargs)
        for q in questions:
            common = {
                "label": q.prompt,
                "required": q.required,
                "help_text": "Blocks submission if the configured rule is not met."
                if q.is_blocking
                else "For recruiter review; a non-matching answer does not automatically reject you.",
            }
            if q.kind == "yes_no":
                field = forms.ChoiceField(
                    choices=[("", "Choose an answer"), ("yes", "Yes"), ("no", "No")],
                    **common,
                )
            elif q.kind == "single":
                field = forms.ChoiceField(
                    choices=[("", "Choose an answer")] + [(v, v) for v in q.options],
                    **common,
                )
            elif q.kind == "multiple":
                field = forms.MultipleChoiceField(
                    choices=[(v, v) for v in q.options],
                    widget=forms.CheckboxSelectMultiple,
                    **common,
                )
            else:
                field = forms.CharField(
                    max_length=2000,
                    widget=forms.Textarea(attrs={"rows": 4, "maxlength": 2000}),
                    **common,
                )
            self.fields[f"question_{q.pk}"] = field


class ApplicationResumeForm(forms.Form):
    resume_source = forms.ChoiceField(label="Resume to submit")
    resume = forms.FileField(
        required=False,
        validators=[validate_resume],
        widget=forms.FileInput(attrs={"accept": ".pdf"}),
        help_text="For new uploads: readable, unencrypted PDF, 1–30 pages, at most 5 MB.",
    )
    cover_letter = forms.CharField(
        required=False,
        max_length=6000,
        widget=forms.Textarea(attrs={"rows": 6}),
        help_text="Optional, up to 6,000 characters.",
    )

    def __init__(self, *args, seeker, draft, **kwargs):
        super().__init__(*args, **kwargs)
        choices = []
        if draft.resume_available:
            choices.append(
                ("keep", "Keep the resume already selected for this application")
            )
        if seeker.resume_available:
            choices.append(("profile", "Use my saved profile resume"))
        choices.append(("upload", "Upload a new PDF"))
        self.fields["resume_source"].choices = choices
        self.fields["resume_source"].initial = choices[0][0]

    def clean(self):
        data = super().clean()
        if data.get("resume_source") == "upload" and not data.get("resume"):
            self.add_error(
                "resume", "Upload a resume PDF or select an available saved resume."
            )
        elif data.get("resume") and data.get("resume_source") != "upload":
            self.add_error(
                "resume_source", "Choose Upload a new PDF to use the file you selected."
            )
        return data


class FinalSubmissionForm(forms.Form):
    review_token = forms.CharField(widget=forms.HiddenInput, max_length=1000)
    consent = forms.BooleanField(
        label="I confirm these answers are accurate and agree to share this application and resume with this employer."
    )
