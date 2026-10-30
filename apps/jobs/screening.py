"""Deterministic self-reported screening; not qualification verification or hiring advice."""

import hashlib
import json
import re
import unicodedata
from decimal import Decimal, InvalidOperation
from django.core.exceptions import ValidationError
from django.utils import timezone
from .locations import normalize_location


def normalized(value):
    return " ".join(unicodedata.normalize("NFKC", str(value)).split()).casefold()


def split_items(value):
    result, seen = [], set()
    for part in re.split(r"[,;\n\r]+", value or ""):
        item = " ".join(part.split())
        if item and normalized(item) not in seen:
            result.append(item)
            seen.add(normalized(item))
    return result


def validate_items(values, limit=30):
    if (
        not isinstance(values, list)
        or len(values) > limit
        or any(not isinstance(v, str) or not v.strip() or len(v) > 120 for v in values)
    ):
        raise ValidationError(
            f"Use up to {limit} non-empty values, each at most 120 characters."
        )
    if len({normalized(v) for v in values}) != len(values):
        raise ValidationError("Values must be distinct (ignoring case and spacing).")


def question_snapshot(q):
    return {
        name: getattr(q, name)
        for name in (
            "id",
            "prompt",
            "kind",
            "options",
            "required",
            "position",
            "match_mode",
            "expected_answers",
            "is_blocking",
        )
    }


def job_snapshot(job, rules, questions):
    fields = (
        "id",
        "title",
        "description",
        "requirements",
        "responsibilities",
        "qualifications",
        "mandatory_skills",
        "preferred_skills",
        "min_experience",
        "max_experience",
        "salary",
        "salary_min",
        "salary_max",
        "location",
        "work_mode",
        "job_type",
        "deadline",
        "benefits",
        "application_instructions",
        "publication_status",
        "is_active",
        "is_demo",
        "demo_key",
        "screening_revision",
    )
    data = {name: getattr(job, name) for name in fields}
    data["company"] = job.employer.company_name
    data["rules"] = [
        {
            "kind": r.kind,
            "values": r.values,
            "is_blocking": r.is_blocking,
            "allow_relocation": r.allow_relocation,
        }
        for r in rules
    ]
    data["questions"] = [question_snapshot(q) for q in questions]
    return json.loads(json.dumps(data, default=str))


def fingerprint(snapshot):
    return hashlib.sha256(
        json.dumps(
            snapshot, sort_keys=True, ensure_ascii=False, separators=(",", ":")
        ).encode()
    ).hexdigest()


def assessment(rows, recommendations=None):
    automatic = [r for r in rows if r["state"] != "manual"]
    if any(r["is_blocking"] and r["state"] != "met" for r in automatic):
        result, label = "blocked", "Some blocking requirements need attention"
    elif any(r["state"] == "unknown" for r in automatic):
        result, label = "incomplete", "Information incomplete — recruiter review needed"
    elif any(r["state"] == "unmet" for r in automatic):
        result, label = "review", "Recruiter review needed"
    elif not automatic:
        result, label = "no_rules", "No automatic requirements configured"
    else:
        result, label = "met", "Configured requirements met"
    return {
        "outcome": result,
        "label": label,
        "can_continue": result != "blocked",
        "rows": rows,
        "recommendations": recommendations or [],
        "checked_at": timezone.now().isoformat(),
        "version": 1,
        "disclaimer": "Based only on your answers and the employer's configured rules. This is not a verification of qualifications or a hiring decision.",
    }


def evaluate_eligibility(job, rules, data):
    rows = []
    for rule in rules:
        state, reason, expected, provided = (
            "unknown",
            "Not provided. Correct or complete your answer to check this requirement.",
            "",
            "Not provided",
        )
        if rule.kind == "qualification":
            value = data.get("qualification", "")
            expected = "One of: " + ", ".join(rule.values)
            if value:
                provided = value
                state = (
                    "met"
                    if normalized(value) in {normalized(v) for v in rule.values}
                    else "unmet"
                )
                reason = (
                    "Your declared qualification matches an accepted qualification."
                    if state == "met"
                    else "Your answer does not exactly match an accepted qualification. Equivalencies are not inferred."
                )
        elif rule.kind == "experience":
            expected = job.experience_display
            value = data.get("years_experience")
            if value not in (None, ""):
                try:
                    years = Decimal(str(value))
                    if not years.is_finite() or years < 0 or years > 60:
                        raise InvalidOperation
                except (InvalidOperation, ValueError):
                    reason = "Enter a valid number of relevant years (0–60)."
                else:
                    provided = f"{years:g} years"
                    meets = (
                        job.min_experience is None or years >= job.min_experience
                    ) and (job.max_experience is None or years <= job.max_experience)
                    state = "met" if meets else "unmet"
                    reason = (
                        "Relevant experience is within the configured range."
                        if meets
                        else "Relevant experience is outside the configured range."
                    )
        elif rule.kind == "skills":
            needed = job.mandatory_skill_list
            expected = ", ".join(needed)
            value = data.get("skills", "")
            if value:
                provided = value
                missing = [
                    v
                    for v in needed
                    if normalized(v) not in {normalized(v) for v in split_items(value)}
                ]
                state = "unmet" if missing else "met"
                reason = (
                    "Missing from your declared skills: " + ", ".join(missing)
                    if missing
                    else "All mandatory skill names are included in your answer."
                )
        elif rule.kind == "location":
            expected = ", ".join(rule.values) + (
                "; relocation accepted" if rule.allow_relocation else ""
            )
            value, relocate = data.get("work_location", ""), data.get("relocate", "")
            if value:
                provided = normalize_location(value)
                if normalized(provided) in {
                    normalized(normalize_location(v)) for v in rule.values
                }:
                    state, reason = (
                        "met",
                        "Your work location matches an accepted location.",
                    )
                elif rule.allow_relocation and relocate == "yes":
                    state, reason = (
                        "met",
                        "You confirmed willingness to relocate to an accepted location.",
                    )
                    provided += "; willing to relocate"
                elif rule.allow_relocation and not relocate:
                    reason = "The location does not match. Answer the relocation question to finish this check."
                else:
                    state, reason = (
                        "unmet",
                        "Your declared work location does not match an accepted location.",
                    )
        elif rule.kind == "work_arrangement":
            expected = job.get_work_mode_display()
            value = data.get("work_arrangement", "")
            if value:
                provided = "Agreed" if value == "yes" else "Not agreed"
                state = "met" if value == "yes" else "unmet"
                reason = (
                    "You confirmed this work arrangement."
                    if state == "met"
                    else "You have not agreed to this work arrangement."
                )
        rows.append(
            {
                "kind": rule.kind,
                "label": rule.get_kind_display(),
                "state": state,
                "reason": reason,
                "expected": expected,
                "provided": provided,
                "is_blocking": rule.is_blocking,
            }
        )
    declared = {normalized(v) for v in split_items(data.get("skills", ""))}
    recommendations = [
        {"skill": v, "met": normalized(v) in declared} for v in job.preferred_skill_list
    ]
    return assessment(rows, recommendations)


def evaluate_questions(questions, answers):
    rows = []
    for q in questions:
        value = answers.get(f"question_{q.pk}", [] if q.kind == "multiple" else "")
        selected = value if isinstance(value, list) else ([value] if value else [])
        state, reason = (
            "manual",
            "For the recruiter to review. No automatic matching rule.",
        )
        if q.match_mode != "none":
            if not selected:
                state, reason = "unknown", "Not answered."
            else:
                actual, expected = (
                    {normalized(v) for v in selected},
                    {normalized(v) for v in q.expected_answers},
                )
                matches = (
                    expected.issubset(actual)
                    if q.match_mode == "all"
                    else bool(expected & actual)
                )
                state = "met" if matches else "unmet"
                reason = (
                    "Matches the recruiter's configured rule."
                    if matches
                    else "Does not match the recruiter's configured rule."
                )
        rows.append(
            {
                "question_id": q.pk,
                "label": q.prompt,
                "state": state,
                "reason": reason,
                "is_blocking": q.is_blocking,
                "answer": value,
                "provided": ", ".join(selected) or "Not answered",
                "expected": ", ".join(q.expected_answers),
                "question_snapshot": question_snapshot(q),
                "position": q.position,
            }
        )
    return assessment(rows)


def combined_assessment(eligibility, screening):
    return assessment(
        eligibility["rows"] + screening["rows"], eligibility["recommendations"]
    )
