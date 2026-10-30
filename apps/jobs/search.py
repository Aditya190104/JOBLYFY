"""Shared, paginated ORM search. No Python-side loading of the full jobs table."""

import math
from datetime import timedelta
from django.db.models import Q, Case, When, Value, IntegerField, FloatField, F
from django.db.models.functions import (
    ACos,
    Cos,
    Sin,
    Radians,
    Greatest,
    Least,
    Coalesce,
    Cast,
)
from django.utils import timezone
from .locations import cities, city_query, resolve_city, location_query


def search_jobs(queryset, data):
    jobs = queryset
    terms = data.get("search", "").split()[:12]
    score = Value(0, output_field=IntegerField())
    for word in terms:
        jobs = jobs.filter(
            Q(title__icontains=word)
            | Q(description__icontains=word)
            | Q(requirements__icontains=word)
            | Q(mandatory_skills__icontains=word)
            | Q(preferred_skills__icontains=word)
            | Q(qualifications__icontains=word)
            | Q(responsibilities__icontains=word)
            | Q(employer__company_name__icontains=word)
            | Q(category__name__icontains=word)
        )
        score += Case(When(title__icontains=word, then=Value(8)), default=Value(0))
        score += Case(
            When(employer__company_name__icontains=word, then=Value(4)),
            default=Value(0),
        )
        score += Case(
            When(requirements__icontains=word, then=Value(2)), default=Value(0)
        )
    for field, lookup in [
        ("category", "category"),
        ("job_type", "job_type"),
        ("experience", "experience_level"),
        ("work_mode", "work_mode"),
        ("company", "employer"),
    ]:
        if data.get(field):
            jobs = jobs.filter(**{lookup: data[field]})
    location, radius = data.get("location", ""), data.get("radius")
    if location and data.get("work_mode") != "remote":
        if radius and (center := resolve_city(location)):
            # Prefer explicit employer coordinates; otherwise use a clearly labelled city center.
            lat = Coalesce(
                Cast("latitude", FloatField()),
                Case(
                    *[When(city_query(c), then=Value(c["lat"])) for c in cities()],
                    default=Value(None),
                    output_field=FloatField(),
                ),
            )
            lon = Coalesce(
                Cast("longitude", FloatField()),
                Case(
                    *[When(city_query(c), then=Value(c["lon"])) for c in cities()],
                    default=Value(None),
                    output_field=FloatField(),
                ),
            )
            jobs = (
                jobs.annotate(search_lat=lat, search_lon=lon)
                .filter(search_lat__isnull=False, search_lon__isnull=False)
                .exclude(work_mode="remote")
            )
            cosine = Sin(Radians(F("search_lat"))) * math.sin(
                math.radians(center["lat"])
            ) + Cos(Radians(F("search_lat"))) * math.cos(
                math.radians(center["lat"])
            ) * Cos(Radians(F("search_lon") - center["lon"]))
            jobs = jobs.annotate(
                distance_km=6371.0088
                * ACos(Least(Value(1.0), Greatest(Value(-1.0), cosine)))
            ).filter(distance_km__lte=float(radius))
        else:
            jobs = jobs.filter(location_query(location))
    if data.get("posted"):
        jobs = jobs.filter(
            posted_date__gte=timezone.now() - timedelta(days=int(data["posted"]))
        )
    # Overlapping employer-provided annual INR bands, excluding undisclosed/unstructured salary.
    if data.get("min_salary") is not None:
        jobs = jobs.filter(salary_max__gte=data["min_salary"])
    if data.get("max_salary") is not None:
        jobs = jobs.filter(salary_min__lte=data["max_salary"])
    sort = data.get("sort", "latest")
    if sort == "relevance" and terms:
        return jobs.annotate(relevance=score).order_by(
            "-relevance", "-posted_date", "-pk"
        )
    if sort == "oldest":
        return jobs.order_by("posted_date", "pk")
    if sort == "title":
        return jobs.order_by("title", "pk")
    if sort == "deadline":
        return jobs.order_by(F("deadline").asc(nulls_last=True), "-posted_date", "-pk")
    return jobs.order_by("-posted_date", "-pk")
