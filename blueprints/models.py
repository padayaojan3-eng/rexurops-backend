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
    file = models.FileField(upload_to='blueprints/%Y/%m/', null=True, blank=True)
    status = models.CharField(max_length=20, choices=APPROVAL_CHOICES, default='draft')
    created_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, related_name='blueprints_created')
    reviewed_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='blueprints_reviewed')
    remarks = models.TextField(blank=True)
    summary = models.CharField(max_length=500, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['service_request', 'version']
        ordering = ['-version']

    def __str__(self):
        return f"{self.title} v{self.version} ({self.status})"


class BlueprintFile(models.Model):
    blueprint = models.ForeignKey(Blueprint, on_delete=models.CASCADE, related_name='files')
    file = models.FileField(upload_to='blueprints/files/%Y/%m/')
    original_name = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField(default=0)
    uploaded_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='blueprint_files')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def size_display(self):
        if self.file_size >= 1024 * 1024:
            return f"{self.file_size / (1024 * 1024):.2f} MB"
        if self.file_size >= 1024:
            return f"{self.file_size // 1024} KB"
        return f"{self.file_size} B"

    def __str__(self):
        return self.original_name
