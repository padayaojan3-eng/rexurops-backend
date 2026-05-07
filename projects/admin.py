from django.contrib import admin
from .models import Project, ProjectUpdate

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ['name', 'manager', 'stage', 'start_date', 'target_completion']
    list_filter = ['stage']

admin.site.register(ProjectUpdate)