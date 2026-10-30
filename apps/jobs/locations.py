"""Offline city names/approximate centers. No network call or API key is required."""

import json
import re
from functools import lru_cache
from pathlib import Path
from django.conf import settings
from django.db.models import Q


@lru_cache(maxsize=1)
def cities():
    return json.loads(
        (Path(settings.BASE_DIR) / "static/data/locations.json").read_text()
    )


def key(value):
    return re.sub(r"[^\w\s]", "", " ".join(value.casefold().split()))


def resolve_city(value):
    value = key(value)
    for city in cities():
        for alias in city["aliases"]:
            if value in {
                key(alias),
                key(f"{alias}, {city['state']}"),
                key(f"{alias}, India"),
                key(f"{alias}, {city['state']}, India"),
            }:
                return city
    return None


def normalize_location(value):
    value = " ".join(value.strip().split())
    city = resolve_city(value)
    return city["name"] if city else value


def city_query(city, field="location"):
    query = Q(pk__in=[])
    for alias in city["aliases"]:
        # Exact city or conventional city, state / city - area records; do not match a different city containing this name.
        query |= (
            Q(**{field + "__iexact": alias})
            | Q(**{field + "__istartswith": alias + ","})
            | Q(**{field + "__istartswith": alias + " -"})
        )
    return query


def location_query(value, field="location"):
    if field == "location" and key(value) in {
        "remote",
        "remote india",
        "work from home",
        "work from home in india",
        "wfh",
    }:
        return Q(work_mode="remote")
    city = resolve_city(value)
    if city:
        return city_query(city, field)
    query = Q(**{field + "__icontains": value})
    for city in cities():
        if key(value) == key(city["state"]):
            query |= city_query(city, field)
    return query
