from django.contrib import admin
from .models import ServiceRequest, Appointment

@admin.register(ServiceRequest)
class ServiceRequestAdmin(admin.ModelAdmin):
    list_display = ['client', 'service', 'status', 'preferred_date', 'submitted_at']
    list_filter = ['status', 'service']

@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ['service_request', 'engineer', 'date', 'status']
    list_filter = ['status']