from django.contrib import admin
from .models import Blueprint

@admin.register(Blueprint)
class BlueprintAdmin(admin.ModelAdmin):
    list_display = ['title', 'version', 'status', 'created_by', 'reviewed_by', 'created_at']
    list_filter = ['status']