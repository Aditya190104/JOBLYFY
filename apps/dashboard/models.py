from django.conf import settings
from django.db import models
from django.urls import reverse


class Notification(models.Model):
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    application = models.ForeignKey(
        "jobs.Application",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications",
    )
    message = models.CharField(max_length=400)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        indexes = [
            models.Index(
                fields=["recipient", "read_at"], name="notification_recipient_idx"
            )
        ]

    def get_absolute_url(self):
        if self.application_id and self.recipient.is_employer:
            return reverse("dashboard:candidate_detail", args=[self.application_id])
        return reverse("dashboard:applications")
