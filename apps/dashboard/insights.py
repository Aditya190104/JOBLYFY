"""Current application distribution, scoped by the caller's owned queryset."""
from django.db.models import Count, Q
from apps.jobs.models import Application


def application_insights(applications):
    stats = applications.aggregate(
        total=Count("id"),
        **{status: Count("id", filter=Q(status=status))
           for status, _label in Application.STATUS_CHOICES},
    )
    rows = [
        {"status": status, "label": label, "count": stats[status],
         "percent": round(100 * stats[status] / stats["total"], 2) if stats["total"] else 0}
        for status, label in Application.STATUS_CHOICES
    ]
    other = stats["total"] - sum(row["count"] for row in rows)
    if other:
        rows.append({"status": "other", "label": "Other / legacy", "count": other,
                     "percent": round(100 * other / stats["total"], 2)})
    return stats, rows
