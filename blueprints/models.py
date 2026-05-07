from django.db import models
from appointments.models import ServiceRequest

class Blueprint(models.Model):
    APPROVAL_CHOICES = [
        ('draft', 'Draft'),
        ('submitted', 'Submitted for Review'),
        ('revision_needed', 'Revision Needed'),
        ('approved', 'Approved'),
    ]

    service_request = models.ForeignKey(ServiceRequest, on_delete=models.CASCADE, related_name='blueprints')
    title = models.CharField(max_length=255)
    version = models.PositiveIntegerField(default=1)
    file = models.FileField(upload_to='blueprints/%Y/%m/')
    status = models.CharField(max_length=20, choices=APPROVAL_CHOICES, default='draft')
    created_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, related_name='blueprints_created')
    reviewed_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='blueprints_reviewed')
    remarks = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['service_request', 'version']
        ordering = ['-version']

    def __str__(self):
        return f"{self.title} v{self.version} ({self.status})"