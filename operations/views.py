from django.shortcuts import render, redirect
from django.db.models import Q, Count, OuterRef, Subquery, F
from django.utils import timezone
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from appointments.models import ServiceRequest, Appointment
from blueprints.models import Blueprint, BlueprintFile
from operations.models import Task
from projects.models import Project, ProjectUpdate
from clients.models import Client
from accounts.models import UserProfile
from services.models import Service as ServiceModel
import json


def _fmt_date(dt):
    if not dt:
        return ''
    return f"{dt.month}/{dt.day}/{dt.year}"


def _fmt_datetime(dt):
    if not dt:
        return ''
    hour = dt.hour % 12 or 12
    ampm = 'AM' if dt.hour < 12 else 'PM'
    return f"{dt.month}/{dt.day}/{dt.year} at {hour}:{dt.minute:02d} {ampm}"


def _cors(response):
    response['Access-Control-Allow-Origin'] = '*'
    response['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response['Access-Control-Allow-Headers'] = 'Content-Type'
    return response


# ── Public API ────────────────────────────────────────────────────────────────

@csrf_exempt
def api_services(request):
    if request.method == 'OPTIONS':
        return _cors(JsonResponse({}))
    services = [
        {'value': s.name, 'label': s.get_name_display()}
        for s in ServiceModel.objects.filter(is_active=True).order_by('id')
    ]
    return _cors(JsonResponse({'services': services}))


@csrf_exempt
def api_submit_request(request):
    if request.method == 'OPTIONS':
        return _cors(JsonResponse({}))
    if request.method != 'POST':
        return _cors(JsonResponse({'error': 'Method not allowed'}, status=405))
    try:
        data = json.loads(request.body)
        full_name = data.get('full_name', '').strip()
        email = data.get('email', '').strip()
        phone = data.get('phone', '').strip()
        address = data.get('address', '').strip()
        service_name = data.get('service_type', '').strip()
        description = data.get('description', '').strip()
        preferred_date = data.get('preferred_date', '').strip()

        if not all([full_name, email, phone, address, service_name, description, preferred_date]):
            return _cors(JsonResponse({'error': 'All fields are required.'}, status=400))

        client, _ = Client.objects.get_or_create(
            email=email,
            defaults={'full_name': full_name, 'phone': phone, 'address': address},
        )

        service, _ = ServiceModel.objects.get_or_create(
            name=service_name,
            defaults={'description': '', 'is_active': True},
        )

        ServiceRequest.objects.create(
            client=client,
            service=service,
            description=description,
            preferred_date=preferred_date,
            status='pending',
        )

        return _cors(JsonResponse({
            'success': True,
            'message': 'Your service request has been submitted! Our team will get back to you within 24 hours.',
        }))
    except Exception as e:
        return _cors(JsonResponse({'error': str(e)}, status=400))


# ── Authentication ────────────────────────────────────────────────────────────

def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    ctx = {'signin_error': None, 'signup_error': None, 'signup_success': None, 'active_tab': 'signin'}

    if request.method == 'POST':
        form_type = request.POST.get('form_type')

        if form_type == 'signin':
            username = request.POST.get('username', '').strip()
            password = request.POST.get('password', '')
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                return redirect('dashboard')
            ctx['signin_error'] = 'Invalid username or password. Please try again.'

        elif form_type == 'signup':
            ctx['active_tab'] = 'signup'
            from django.contrib.auth.models import User as AuthUser
            admin_username = request.POST.get('admin_username', '').strip()
            admin_password = request.POST.get('admin_password', '')
            admin_user = authenticate(request, username=admin_username, password=admin_password)

            if admin_user is None:
                ctx['signup_error'] = 'Admin credentials are incorrect.'
            elif not (admin_user.is_staff or admin_user.is_superuser or
                      UserProfile.objects.filter(user=admin_user, role='admin').exists()):
                ctx['signup_error'] = 'The provided account does not have admin privileges.'
            else:
                full_name = request.POST.get('full_name', '').strip()
                new_username = request.POST.get('new_username', '').strip()
                new_email = request.POST.get('new_email', '').strip()
                new_password = request.POST.get('new_password', '')
                confirm_password = request.POST.get('confirm_password', '')
                role = request.POST.get('role', 'worker')

                if new_password != confirm_password:
                    ctx['signup_error'] = 'Passwords do not match.'
                elif AuthUser.objects.filter(username=new_username).exists():
                    ctx['signup_error'] = f'Username "{new_username}" is already taken.'
                elif AuthUser.objects.filter(email=new_email).exists():
                    ctx['signup_error'] = f'Email "{new_email}" is already registered.'
                else:
                    parts = full_name.split(' ', 1)
                    new_user = AuthUser.objects.create_user(
                        username=new_username,
                        email=new_email,
                        password=new_password,
                        first_name=parts[0],
                        last_name=parts[1] if len(parts) > 1 else '',
                    )
                    specialization = request.POST.get('specialization', '')
                    UserProfile.objects.create(user=new_user, role=role, specialization=specialization)
                    ctx['signup_success'] = f'Account "{new_username}" created successfully. They can now sign in.'

    return render(request, 'auth/login.html', ctx)


def logout_view(request):
    logout(request)
    return redirect('login')


# ── Dashboard ────────────────────────────────────────────────────────────────

@login_required
def dashboard(request):
    try:
        total_requests = ServiceRequest.objects.count()
        new_requests = ServiceRequest.objects.filter(status='pending').count()
    except Exception:
        total_requests = new_requests = 0

    try:
        total_appointments = Appointment.objects.count()
        upcoming_appointments = Appointment.objects.filter(
            status__in=['pending', 'confirmed']
        ).count()
    except Exception:
        total_appointments = upcoming_appointments = 0

    try:
        total_blueprints = Blueprint.objects.count()
        pending_blueprints = Blueprint.objects.filter(
            status__in=['submitted', 'revision_needed']
        ).count()
    except Exception:
        total_blueprints = pending_blueprints = 0

    try:
        total_projects = Project.objects.count()
        active_projects = Project.objects.filter(stage='ongoing').count()
    except Exception:
        total_projects = active_projects = 0

    try:
        total_tasks = Task.objects.count()
        active_tasks = Task.objects.filter(status='in_progress').count()
    except Exception:
        total_tasks = active_tasks = 0

    try:
        total_clients = Client.objects.count()
    except Exception:
        total_clients = 0

    overall_progress = 0
    try:
        ongoing = Project.objects.filter(stage='ongoing')
        if ongoing.exists():
            values = [p.progress for p in ongoing]
            overall_progress = int(sum(values) / len(values))
    except Exception:
        pass

    pending_requests = []
    try:
        pending_requests = list(
            ServiceRequest.objects.filter(status='pending')
            .select_related('client', 'service')
            .order_by('-submitted_at')[:5]
        )
    except Exception:
        pass

    active_projects_list = []
    try:
        for project in Project.objects.filter(stage='ongoing').select_related(
            'service_request', 'manager'
        )[:10]:
            bps = Blueprint.objects.filter(service_request=project.service_request)
            t = Task.objects.filter(blueprint__in=bps).count()
            c = Task.objects.filter(blueprint__in=bps, status='completed').count()
            progress = int((c / t * 100) if t > 0 else 0)
            workers = (
                Task.objects.filter(blueprint__in=bps)
                .exclude(assigned_to=None)
                .values('assigned_to')
                .distinct()
                .count()
            )
            active_projects_list.append({
                'project': project,
                'progress': progress,
                'worker_count': workers,
            })
    except Exception:
        pass

    activities = []
    try:
        for req in ServiceRequest.objects.select_related('client', 'service').order_by('-submitted_at')[:3]:
            activities.append({
                'title': 'New Service Request',
                'description': f'{req.service.get_name_display()} request from {req.client.full_name}',
                'timestamp': req.submitted_at,
                'color': 'blue',
                'icon': 'SR',
            })
    except Exception:
        pass

    try:
        for proj in Project.objects.select_related('service_request').order_by('-created_at')[:3]:
            activities.append({
                'title': 'Project Started',
                'description': f'{proj.name} project has begun',
                'timestamp': proj.created_at,
                'color': 'orange',
                'icon': 'PS',
            })
    except Exception:
        pass

    try:
        for bp in Blueprint.objects.filter(status='approved').order_by('-updated_at')[:3]:
            activities.append({
                'title': 'Blueprint Approved',
                'description': f'{bp.title} has been approved',
                'timestamp': bp.updated_at,
                'color': 'orange',
                'icon': 'BA',
            })
    except Exception:
        pass

    try:
        for task in (
            Task.objects.select_related('assigned_to')
            .filter(started_at__isnull=False)
            .order_by('-started_at')[:3]
        ):
            name = ''
            if task.assigned_to:
                name = task.assigned_to.get_full_name() or task.assigned_to.username
            activities.append({
                'title': 'Task Assigned',
                'description': f'{task.title} assigned to {name}',
                'timestamp': task.started_at,
                'color': 'blue',
                'icon': 'TA',
            })
    except Exception:
        pass

    try:
        for appt in Appointment.objects.select_related('service_request__client').order_by('-date')[:3]:
            activities.append({
                'title': 'Appointment Confirmed',
                'description': f'Appointment with {appt.service_request.client.full_name}',
                'timestamp': appt.date,
                'color': 'green',
                'icon': 'AC',
            })
    except Exception:
        pass

    activities.sort(key=lambda x: x['timestamp'], reverse=True)
    activities = activities[:5]

    context = {
        'active_nav': 'dashboard',
        'total_requests': total_requests,
        'new_requests': new_requests,
        'total_appointments': total_appointments,
        'upcoming_appointments': upcoming_appointments,
        'total_blueprints': total_blueprints,
        'pending_blueprints': pending_blueprints,
        'total_projects': total_projects,
        'active_projects': active_projects,
        'total_tasks': total_tasks,
        'active_tasks': active_tasks,
        'total_clients': total_clients,
        'overall_progress': overall_progress,
        'pending_requests': pending_requests,
        'active_projects_list': active_projects_list,
        'activities': activities,
    }
    return render(request, 'dashboard/index.html', context)


# ── Service Requests ─────────────────────────────────────────────────────────

@login_required
def service_requests(request):
    status_filter = request.GET.get('status', 'all')
    search_query = request.GET.get('search', '').strip()

    sr_list = []
    counts = {'all': 0, 'pending': 0, 'reviewed': 0, 'approved': 0, 'rejected': 0}

    show_archived = request.GET.get('archived') == '1'
    try:
        qs = ServiceRequest.objects.select_related('client', 'service').filter(is_archived=show_archived).order_by('-submitted_at')

        if status_filter and status_filter != 'all':
            qs = qs.filter(status=status_filter)

        if search_query:
            qs = qs.filter(
                Q(client__full_name__icontains=search_query) |
                Q(client__email__icontains=search_query) |
                Q(service__name__icontains=search_query) |
                Q(description__icontains=search_query)
            )

        sr_list = list(qs)
        counts = {
            'all': ServiceRequest.objects.filter(is_archived=show_archived).count(),
            'pending': ServiceRequest.objects.filter(status='pending', is_archived=show_archived).count(),
            'reviewed': ServiceRequest.objects.filter(status='reviewed', is_archived=show_archived).count(),
            'approved': ServiceRequest.objects.filter(status='approved', is_archived=show_archived).count(),
            'rejected': ServiceRequest.objects.filter(status='rejected', is_archived=show_archived).count(),
        }
    except Exception:
        pass

    modal_engineers = []
    try:
        modal_engineers = list(
            UserProfile.objects.select_related('user').filter(role='engineer').order_by('user__first_name')
        )
    except Exception:
        pass

    context = {
        'active_nav': 'service_requests',
        'sr_list': sr_list,
        'counts': counts,
        'status_filter': status_filter,
        'search_query': search_query,
        'request_count': len(sr_list),
        'modal_engineers': modal_engineers,
        'show_archived': show_archived,
    }
    return render(request, 'service_requests/index.html', context)


@login_required
def sr_mark_reviewed(request, sr_id):
    try:
        sr = ServiceRequest.objects.get(id=sr_id)
        sr.status = 'reviewed'
        sr.save()
    except Exception:
        pass
    return redirect('service_requests')


@login_required
def sr_reject(request, sr_id):
    try:
        sr = ServiceRequest.objects.get(id=sr_id)
        sr.status = 'rejected'
        sr.save()
    except Exception:
        pass
    return redirect('service_requests')


@login_required
def sr_schedule_appointment(request, sr_id):
    if request.method != 'POST':
        return redirect('service_requests')
    try:
        from datetime import datetime
        from django.contrib.auth.models import User
        from django.utils import timezone as tz
        sr = ServiceRequest.objects.get(id=sr_id)
        date_str = request.POST.get('appt_date', '')
        time_str = request.POST.get('appt_time', '')
        engineer_id = request.POST.get('engineer_id', '')
        location = request.POST.get('location', '').strip()
        notes = request.POST.get('notes', '').strip()
        engineer = User.objects.get(id=engineer_id) if engineer_id else None
        dt = datetime.strptime(f'{date_str} {time_str}', '%Y-%m-%d %H:%M')
        aware_dt = tz.make_aware(dt)
        existing = sr.appointments.first()
        if existing:
            existing.engineer = engineer
            existing.date = aware_dt
            existing.location = location
            existing.notes = notes
            existing.save()
        else:
            Appointment.objects.create(
                service_request=sr,
                engineer=engineer,
                date=aware_dt,
                location=location,
                notes=notes,
                status='pending',
            )
        sr.status = 'approved'
        sr.is_archived = True
        sr.save()
    except Exception:
        pass
    return redirect('service_requests')


# ── Appointments ─────────────────────────────────────────────────────────────

@login_required
def appointments_list(request):
    status_filter = request.GET.get('status', 'all')
    search_query = request.GET.get('search', '').strip()

    appts = []
    counts = {'all': 0, 'pending': 0, 'confirmed': 0, 'completed': 0, 'cancelled': 0}

    show_archived = request.GET.get('archived') == '1'
    try:
        qs = Appointment.objects.select_related(
            'service_request__client',
            'service_request__service',
            'engineer',
        ).filter(is_archived=show_archived).order_by('date')

        if status_filter and status_filter != 'all':
            qs = qs.filter(status=status_filter)

        if search_query:
            qs = qs.filter(
                Q(service_request__client__full_name__icontains=search_query) |
                Q(engineer__first_name__icontains=search_query) |
                Q(engineer__last_name__icontains=search_query) |
                Q(service_request__service__name__icontains=search_query)
            )

        appts = list(qs)
        counts = {
            'all': Appointment.objects.filter(is_archived=show_archived).count(),
            'pending': Appointment.objects.filter(status='pending', is_archived=show_archived).count(),
            'confirmed': Appointment.objects.filter(status='confirmed', is_archived=show_archived).count(),
            'completed': Appointment.objects.filter(status='completed', is_archived=show_archived).count(),
            'cancelled': Appointment.objects.filter(status='cancelled', is_archived=show_archived).count(),
        }
    except Exception:
        pass

    modal_engineers = []
    try:
        modal_engineers = list(
            UserProfile.objects.select_related('user').filter(role='engineer').order_by('user__first_name')
        )
    except Exception:
        pass

    context = {
        'active_nav': 'appointments',
        'appts': appts,
        'counts': counts,
        'status_filter': status_filter,
        'search_query': search_query,
        'appt_count': len(appts),
        'modal_engineers': modal_engineers,
        'show_archived': show_archived,
    }
    return render(request, 'appointments/index.html', context)


@login_required
def update_appointment_status(request, appt_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    try:
        appt = Appointment.objects.select_related(
            'service_request__client',
            'service_request__service',
        ).get(id=appt_id)
        new_status = request.POST.get('status', '')
        if new_status not in ('pending', 'confirmed', 'completed', 'cancelled'):
            return JsonResponse({'error': 'Invalid status'}, status=400)
        appt.status = new_status
        if new_status == 'completed':
            appt.is_archived = True
        appt.save()

        blueprint_created = False
        if new_status == 'completed':
            sr = appt.service_request
            if not Blueprint.objects.filter(service_request=sr).exists():
                remarks = (
                    f"Blueprint automatically generated from appointment scheduled on "
                    f"{_fmt_date(appt.date)}."
                )
                if appt.notes:
                    remarks += f" Purpose: {appt.notes}"
                Blueprint.objects.create(
                    service_request=sr,
                    title=f"{sr.client.full_name} - {sr.service.get_name_display()}",
                    version=1,
                    status='draft',
                    created_by=request.user,
                    summary="Initial blueprint created from completed appointment",
                    remarks=remarks,
                )
                blueprint_created = True

        return JsonResponse({'ok': True, 'status': new_status, 'blueprint_created': blueprint_created})
    except Appointment.DoesNotExist:
        return JsonResponse({'error': 'Appointment not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def edit_appointment(request, appt_id):
    if request.method != 'POST':
        return redirect('appointments_list')
    try:
        from datetime import datetime
        from django.contrib.auth.models import User
        from django.utils import timezone as tz
        appt = Appointment.objects.get(id=appt_id)
        date_str = request.POST.get('appt_date', '')
        time_str = request.POST.get('appt_time', '')
        engineer_id = request.POST.get('engineer_id', '')
        location = request.POST.get('location', '').strip()
        notes = request.POST.get('notes', '').strip()
        status = request.POST.get('status', appt.status)
        if date_str and time_str:
            dt = datetime.strptime(f'{date_str} {time_str}', '%Y-%m-%d %H:%M')
            appt.date = tz.make_aware(dt)
        appt.engineer = User.objects.get(id=engineer_id) if engineer_id else None
        appt.location = location
        appt.notes = notes
        appt.status = status
        appt.save()
    except Exception:
        pass
    return redirect('appointments_list')


# ── Blueprints ───────────────────────────────────────────────────────────────

@login_required
def blueprints_list(request):
    status_filter = request.GET.get('status', 'all')
    search_query = request.GET.get('search', '').strip()

    bp_data = []
    counts = {'all': 0, 'draft': 0, 'submitted': 0, 'approved': 0, 'revision_needed': 0}

    show_archived = request.GET.get('archived') == '1'
    try:
        qs = Blueprint.objects.select_related(
            'service_request__client',
            'created_by',
            'reviewed_by',
        ).filter(is_archived=show_archived).order_by('service_request_id', '-version')

        if search_query:
            qs = qs.filter(
                Q(title__icontains=search_query) |
                Q(service_request__client__full_name__icontains=search_query) |
                Q(created_by__first_name__icontains=search_query) |
                Q(created_by__last_name__icontains=search_query)
            )

        # Keep only the latest version per service_request
        seen_sr = set()
        latest_bps = []
        for bp in qs:
            if bp.service_request_id not in seen_sr:
                seen_sr.add(bp.service_request_id)
                latest_bps.append(bp)

        # Filter by status after grouping
        if status_filter and status_filter != 'all':
            latest_bps = [bp for bp in latest_bps if bp.status == status_filter]

        # File count = BlueprintFile records across all versions for same service_request
        for bp in latest_bps:
            all_version_ids = list(
                Blueprint.objects.filter(
                    service_request=bp.service_request,
                    title=bp.title,
                ).values_list('id', flat=True)
            )
            file_count = BlueprintFile.objects.filter(blueprint_id__in=all_version_ids).count()
            bp_data.append({'blueprint': bp, 'file_count': file_count})

        # Counts based on latest-version-per-sr (same archive filter)
        all_latest = []
        seen2 = set()
        for bp in Blueprint.objects.filter(is_archived=show_archived).order_by('service_request_id', '-version'):
            if bp.service_request_id not in seen2:
                seen2.add(bp.service_request_id)
                all_latest.append(bp)

        counts = {
            'all': len(all_latest),
            'draft': sum(1 for b in all_latest if b.status == 'draft'),
            'submitted': sum(1 for b in all_latest if b.status == 'submitted'),
            'approved': sum(1 for b in all_latest if b.status == 'approved'),
            'revision_needed': sum(1 for b in all_latest if b.status == 'revision_needed'),
        }
    except Exception:
        pass

    context = {
        'active_nav': 'blueprints',
        'bp_data': bp_data,
        'counts': counts,
        'status_filter': status_filter,
        'search_query': search_query,
        'show_archived': show_archived,
    }
    return render(request, 'blueprints/index.html', context)


@login_required
def create_blueprint(request):
    if request.method != 'POST':
        return redirect('blueprints_list')
    try:
        sr_id = request.POST.get('service_request_id')
        title = request.POST.get('title', '').strip()
        summary = request.POST.get('summary', '').strip()
        remarks = request.POST.get('remarks', '').strip()
        status = request.POST.get('status', 'draft')

        sr = ServiceRequest.objects.get(id=sr_id)
        latest = Blueprint.objects.filter(service_request=sr, title=title).order_by('-version').first()
        version = (latest.version + 1) if latest else 1

        Blueprint.objects.create(
            service_request=sr,
            title=title,
            version=version,
            status=status,
            created_by=request.user,
            summary=summary,
            remarks=remarks,
        )
    except Exception:
        pass
    return redirect('blueprints_list')


@login_required
def blueprint_detail(request, bp_id):
    try:
        bp = Blueprint.objects.select_related(
            'service_request__client',
            'service_request__service',
            'created_by',
            'reviewed_by',
        ).get(id=bp_id)

        # All versions for this blueprint (same service_request + title)
        revisions = list(
            Blueprint.objects.filter(
                service_request=bp.service_request,
                title=bp.title,
            ).select_related('created_by').order_by('version')
        )
        all_version_ids = [r.id for r in revisions]

        # All files across all versions
        files_qs = BlueprintFile.objects.filter(
            blueprint_id__in=all_version_ids
        ).select_related('uploaded_by').order_by('uploaded_at')

        files_data = [{
            'id': f.id,
            'name': f.original_name,
            'size': f.size_display(),
            'uploaded_by': (f.uploaded_by.get_full_name() or f.uploaded_by.username) if f.uploaded_by else '',
            'uploaded_at': _fmt_date(f.uploaded_at),
            'url': f.file.url if f.file else '',
        } for f in files_qs]

        revisions_data = [{
            'version': r.version,
            'created_by': ('Engr. ' + (r.created_by.get_full_name() or r.created_by.username)) if r.created_by else '—',
            'created_at': _fmt_datetime(r.created_at),
            'summary': r.summary,
            'notes': r.remarks,
            'file_count': BlueprintFile.objects.filter(blueprint=r).count(),
        } for r in revisions]

        data = {
            'id': bp.id,
            'title': bp.title,
            'client': bp.service_request.client.full_name,
            'status': bp.status,
            'current_version': bp.version,
            'created_by': ('Engr. ' + (bp.created_by.get_full_name() or bp.created_by.username)) if bp.created_by else '—',
            'created_at': _fmt_date(bp.created_at),
            'updated_at': _fmt_date(bp.updated_at),
            'approved_by': (bp.reviewed_by.get_full_name() or bp.reviewed_by.username) if bp.reviewed_by else '',
            'approved_at': _fmt_date(bp.approved_at) if bp.approved_at else '',
            'remarks': bp.remarks,
            'files': files_data,
            'revisions': revisions_data,
        }
        return JsonResponse(data)
    except Blueprint.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def create_blueprint_revision(request, bp_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    try:
        bp = Blueprint.objects.get(id=bp_id)
        summary = request.POST.get('summary', '').strip()
        remarks = request.POST.get('remarks', '').strip()
        new_bp = Blueprint.objects.create(
            service_request=bp.service_request,
            title=bp.title,
            version=bp.version + 1,
            status='submitted',
            created_by=request.user,
            summary=summary,
            remarks=remarks,
        )
        return JsonResponse({'ok': True, 'new_version': new_bp.version, 'new_id': new_bp.id})
    except Blueprint.DoesNotExist:
        return JsonResponse({'error': 'Blueprint not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def blueprint_approve(request, bp_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    try:
        bp = Blueprint.objects.select_related('service_request__client', 'service_request__service').get(id=bp_id)
        bp.status = 'approved'
        bp.reviewed_by = request.user
        bp.approved_at = timezone.now()
        bp.is_archived = True
        bp.save()

        sr = bp.service_request
        project_updated = False
        project_created = False

        try:
            project = sr.project
            project.name = bp.title
            if project.stage == 'pending':
                project.stage = 'ongoing'
            project.save()
            ProjectUpdate.objects.create(
                project=project,
                update_text=f"Blueprint v{bp.version} approved. Project updated from approved blueprint.",
                updated_by=request.user,
            )
            project_updated = True
        except Project.DoesNotExist:
            new_project = Project.objects.create(
                service_request=sr,
                name=bp.title,
                stage='ongoing',
                start_date=timezone.now().date(),
                manager=request.user,
            )
            ProjectUpdate.objects.create(
                project=new_project,
                update_text=f"Project created automatically when blueprint v{bp.version} was approved.",
                updated_by=request.user,
            )
            project_created = True

        return JsonResponse({'ok': True, 'project_updated': project_updated, 'project_created': project_created})
    except Blueprint.DoesNotExist:
        return JsonResponse({'error': 'Blueprint not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def blueprint_request_revision(request, bp_id):
    if request.method != 'POST':
        return redirect('blueprints_list')
    try:
        bp = Blueprint.objects.get(id=bp_id)
        bp.status = 'revision_needed'
        bp.save()
    except Exception:
        pass
    return redirect('blueprints_list')


@login_required
def blueprint_upload_file(request, bp_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    try:
        bp = Blueprint.objects.get(id=bp_id)
        uploaded = request.FILES.get('file')
        if not uploaded:
            return JsonResponse({'error': 'No file provided'}, status=400)
        bf = BlueprintFile.objects.create(
            blueprint=bp,
            file=uploaded,
            original_name=uploaded.name,
            file_size=uploaded.size,
            uploaded_by=request.user,
        )
        return JsonResponse({
            'id': bf.id,
            'name': bf.original_name,
            'size': bf.size_display(),
            'uploaded_by': request.user.get_full_name() or request.user.username,
            'uploaded_at': _fmt_date(bf.uploaded_at),
            'url': bf.file.url,
        })
    except Blueprint.DoesNotExist:
        return JsonResponse({'error': 'Blueprint not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def blueprint_delete_file(request, file_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    try:
        bf = BlueprintFile.objects.get(id=file_id)
        bf.file.delete(save=False)
        bf.delete()
        return JsonResponse({'ok': True})
    except BlueprintFile.DoesNotExist:
        return JsonResponse({'error': 'File not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ── Projects ──────────────────────────────────────────────────────────────────

@login_required
def projects_list(request):
    stage_filter = request.GET.get('stage', 'all')
    search_query = request.GET.get('search', '').strip()
    show_archived = request.GET.get('archived') == '1'

    proj_data = []
    counts = {'all': 0, 'pending': 0, 'ongoing': 0, 'on_hold': 0, 'completed': 0}

    try:
        qs = Project.objects.select_related(
            'service_request__client',
            'service_request__service',
            'manager',
        ).filter(is_archived=show_archived).order_by('-created_at')

        if stage_filter and stage_filter != 'all':
            qs = qs.filter(stage=stage_filter)

        if search_query:
            qs = qs.filter(
                Q(name__icontains=search_query) |
                Q(service_request__client__full_name__icontains=search_query) |
                Q(service_request__description__icontains=search_query)
            )

        for project in qs:
            assigned_ids = list(project.workers.values_list('id', flat=True))
            proj_data.append({
                'project': project,
                'progress': project.progress,
                'worker_count': len(assigned_ids),
                'assigned_worker_ids': assigned_ids,
            })

        counts = {
            'all': Project.objects.filter(is_archived=show_archived).count(),
            'pending': Project.objects.filter(stage='pending', is_archived=show_archived).count(),
            'ongoing': Project.objects.filter(stage='ongoing', is_archived=show_archived).count(),
            'on_hold': Project.objects.filter(stage='on_hold', is_archived=show_archived).count(),
            'completed': Project.objects.filter(stage='completed', is_archived=show_archived).count(),
        }
    except Exception:
        pass

    modal_clients = []
    modal_services = []
    modal_blueprints = []
    all_employees = []
    try:
        modal_clients = list(Client.objects.order_by('full_name'))
        modal_services = list(ServiceModel.objects.filter(is_active=True))
        latest_ver = Blueprint.objects.filter(
            service_request=OuterRef('service_request')
        ).order_by('-version').values('version')[:1]
        modal_blueprints = list(
            Blueprint.objects
            .annotate(latest_version=Subquery(latest_ver))
            .filter(version=F('latest_version'))
            .select_related('service_request__client')
            .order_by('-updated_at')[:50]
        )
        all_employees = list(
            UserProfile.objects.select_related('user')
            .filter(user__is_active=True)
            .order_by('user__first_name', 'user__last_name')
        )
    except Exception:
        pass

    context = {
        'active_nav': 'projects',
        'proj_data': proj_data,
        'counts': counts,
        'stage_filter': stage_filter,
        'search_query': search_query,
        'modal_clients': modal_clients,
        'modal_services': modal_services,
        'modal_blueprints': modal_blueprints,
        'all_employees': all_employees,
        'show_archived': show_archived,
    }
    return render(request, 'projects/index.html', context)


@login_required
def create_project(request):
    if request.method != 'POST':
        return redirect('projects_list')

    try:
        client_mode = request.POST.get('client_mode', 'existing')
        project_name = request.POST.get('project_name', '').strip()
        service_id = request.POST.get('service_id')
        description = request.POST.get('description', '').strip()
        start_date = request.POST.get('start_date') or None
        end_date = request.POST.get('end_date') or None

        service = Service.objects.get(id=service_id)

        if client_mode == 'new':
            client = Client.objects.create(
                full_name=request.POST.get('new_client_name', '').strip(),
                email=request.POST.get('new_client_email', '').strip(),
                phone=request.POST.get('new_client_phone', '').strip(),
                company=request.POST.get('new_client_company', '').strip(),
                address=request.POST.get('new_client_address', '').strip(),
            )
        else:
            client = Client.objects.get(id=request.POST.get('client_id'))

        service_request = ServiceRequest.objects.create(
            client=client,
            service=service,
            description=description,
            preferred_date=start_date or timezone.now().date(),
            status='approved',
        )

        Project.objects.create(
            service_request=service_request,
            name=project_name,
            stage='pending',
            start_date=start_date or None,
            target_completion=end_date or None,
        )
    except Exception:
        pass

    return redirect('projects_list')


@login_required
def assign_project_workers(request, project_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    try:
        from django.contrib.auth.models import User as AuthUser
        project = Project.objects.get(id=project_id)
        worker_ids = request.POST.getlist('worker_ids')
        project.workers.set(AuthUser.objects.filter(id__in=worker_ids))
        return JsonResponse({'ok': True, 'count': project.workers.count()})
    except Project.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def edit_project(request, project_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    try:
        project = Project.objects.get(id=project_id)
        project.name = request.POST.get('name', project.name).strip() or project.name
        project.description = request.POST.get('description', '').strip()
        project.stage = request.POST.get('stage', project.stage)
        if project.stage == 'completed':
            project.is_archived = True
        try:
            project.progress = max(0, min(100, int(request.POST.get('progress', project.progress))))
        except (ValueError, TypeError):
            pass
        start_date = request.POST.get('start_date') or None
        end_date = request.POST.get('end_date') or None
        project.start_date = start_date
        project.target_completion = end_date
        project.save()
        return JsonResponse({'ok': True})
    except Project.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def delete_project(request, project_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    try:
        Project.objects.filter(id=project_id).delete()
        return JsonResponse({'ok': True})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ── Tasks ─────────────────────────────────────────────────────────────────────

@login_required
def tasks_list(request):
    status_filter = request.GET.get('status', 'all')
    search_query = request.GET.get('search', '').strip()

    task_list = []
    counts = {'all': 0, 'pending': 0, 'in_progress': 0, 'completed': 0}

    try:
        qs = Task.objects.select_related(
            'blueprint__service_request__project',
            'assigned_to',
        ).order_by('due_date')

        if status_filter and status_filter != 'all':
            qs = qs.filter(status=status_filter)

        if search_query:
            qs = qs.filter(
                Q(title__icontains=search_query) |
                Q(blueprint__service_request__project__name__icontains=search_query) |
                Q(assigned_to__first_name__icontains=search_query) |
                Q(assigned_to__last_name__icontains=search_query)
            )

        task_list = list(qs)
        counts = {
            'all': Task.objects.count(),
            'pending': Task.objects.filter(status='pending').count(),
            'in_progress': Task.objects.filter(status='in_progress').count(),
            'completed': Task.objects.filter(status='completed').count(),
        }
    except Exception:
        pass

    modal_projects = []
    modal_workers = []
    try:
        modal_projects = list(Project.objects.select_related('service_request').order_by('name'))
        modal_workers = list(
            UserProfile.objects.select_related('user')
            .exclude(role='client')
            .order_by('user__first_name')
        )
    except Exception:
        pass

    context = {
        'active_nav': 'tasks',
        'task_list': task_list,
        'counts': counts,
        'status_filter': status_filter,
        'search_query': search_query,
        'modal_projects': modal_projects,
        'modal_workers': modal_workers,
    }
    return render(request, 'tasks/index.html', context)


@login_required
def create_task(request):
    if request.method != 'POST':
        return redirect('tasks_list')

    try:
        project_id = request.POST.get('project_id')
        title = request.POST.get('task_name', '').strip()
        description = request.POST.get('description', '').strip()
        assigned_to_id = request.POST.get('assigned_to_id') or None
        priority = request.POST.get('priority', 'medium')
        due_date = request.POST.get('due_date')

        project = Project.objects.select_related('service_request').get(id=project_id)
        blueprint = Blueprint.objects.filter(
            service_request=project.service_request
        ).order_by('-version').first()

        if blueprint:
            from django.contrib.auth.models import User
            assigned_user = User.objects.get(id=assigned_to_id) if assigned_to_id else None
            Task.objects.create(
                blueprint=blueprint,
                title=title,
                description=description,
                assigned_to=assigned_user,
                status='pending',
                priority=priority,
                due_date=due_date,
            )
    except Exception:
        pass

    return redirect('tasks_list')


@login_required
def task_update_status(request, task_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    try:
        task = Task.objects.get(id=task_id)
        new_status = request.POST.get('status', '').strip()
        if new_status not in {'pending', 'in_progress', 'completed', 'on_hold'}:
            return JsonResponse({'error': 'Invalid status'}, status=400)
        task.status = new_status
        if new_status == 'in_progress' and not task.started_at:
            task.started_at = timezone.now()
        elif new_status == 'completed':
            task.completed_at = timezone.now()
        task.save()
        return JsonResponse({'ok': True, 'status': new_status})
    except Task.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ── Clients ───────────────────────────────────────────────────────────────────

@login_required
def clients_list(request):
    search_query = request.GET.get('search', '').strip()

    client_data = []
    counts = {'total_clients': 0, 'active_clients': 0, 'total_requests': 0, 'total_projects': 0}

    try:
        qs = Client.objects.order_by('-created_at')

        if search_query:
            qs = qs.filter(
                Q(full_name__icontains=search_query) |
                Q(email__icontains=search_query) |
                Q(company__icontains=search_query)
            )

        for client in qs:
            requests = list(ServiceRequest.objects.filter(client=client).select_related('service').order_by('-submitted_at'))
            projects = list(Project.objects.filter(service_request__client=client).select_related('service_request__service').order_by('-created_at'))
            client_data.append({
                'client': client,
                'request_count': len(requests),
                'project_count': len(projects),
                'requests': requests,
                'projects': projects,
            })

        counts = {
            'total_clients': Client.objects.count(),
            'active_clients': Client.objects.count(),
            'total_requests': ServiceRequest.objects.count(),
            'total_projects': Project.objects.count(),
        }
    except Exception:
        pass

    context = {
        'active_nav': 'clients',
        'client_data': client_data,
        'counts': counts,
        'search_query': search_query,
        'client_count': len(client_data),
    }
    return render(request, 'clients/index.html', context)


@login_required
def create_client(request):
    if request.method != 'POST':
        return redirect('clients_list')

    try:
        Client.objects.create(
            full_name=request.POST.get('full_name', '').strip(),
            email=request.POST.get('email', '').strip(),
            phone=request.POST.get('phone', '').strip(),
            company=request.POST.get('company', '').strip(),
            address=request.POST.get('address', '').strip(),
        )
    except Exception:
        pass

    return redirect('clients_list')


@login_required
def edit_client(request, client_id):
    if request.method != 'POST':
        return redirect('clients_list')
    try:
        client = Client.objects.get(id=client_id)
        client.full_name = request.POST.get('full_name', '').strip()
        client.company   = request.POST.get('company', '').strip()
        client.email     = request.POST.get('email', '').strip()
        client.phone     = request.POST.get('phone', '').strip()
        client.address   = request.POST.get('address', '').strip()
        client.save()
    except Exception:
        pass
    return redirect('clients_list')


@login_required
def delete_client(request, client_id):
    try:
        Client.objects.get(id=client_id).delete()
    except Exception:
        pass
    return redirect('clients_list')


# ── Employees ─────────────────────────────────────────────────────────────────

@login_required
def employees_list(request):
    role_filter = request.GET.get('role', 'all')
    search_query = request.GET.get('search', '').strip()

    emp_data = []
    counts = {'all': 0, 'admin': 0, 'engineer': 0, 'worker': 0}
    ENGINEER_ROLES = ['mechanical_engineer', 'civil_engineer', 'architect']
    WORKER_ROLES = ['master_plumber', 'worker']

    try:
        qs = UserProfile.objects.select_related('user').exclude(role='client').order_by(
            'user__first_name', 'user__last_name'
        )

        if role_filter == 'engineer':
            qs = qs.filter(role__in=ENGINEER_ROLES)
        elif role_filter == 'worker':
            qs = qs.filter(role__in=WORKER_ROLES)
        elif role_filter and role_filter != 'all':
            qs = qs.filter(role=role_filter)

        if search_query:
            qs = qs.filter(
                Q(user__first_name__icontains=search_query) |
                Q(user__last_name__icontains=search_query) |
                Q(user__email__icontains=search_query) |
                Q(specialization__icontains=search_query)
            )

        try:
            all_projects = list(Project.objects.select_related('service_request__client', 'service_request__service').order_by('name'))
        except Exception:
            all_projects = []

        for profile in qs:
            task_count = Task.objects.filter(assigned_to=profile.user).count()
            proj_count = profile.user.assigned_projects.count()
            assigned_ids = list(profile.user.assigned_projects.values_list('id', flat=True))
            emp_data.append({
                'profile': profile,
                'task_count': task_count,
                'project_count': proj_count,
                'assigned_project_ids': assigned_ids,
            })

        counts = {
            'all': UserProfile.objects.exclude(role='client').count(),
            'admin': UserProfile.objects.filter(role='admin').count(),
            'engineer': UserProfile.objects.filter(role__in=ENGINEER_ROLES).count(),
            'worker': UserProfile.objects.filter(role__in=WORKER_ROLES).count(),
        }
    except Exception:
        all_projects = []

    context = {
        'active_nav': 'employees',
        'emp_data': emp_data,
        'counts': counts,
        'role_filter': role_filter,
        'search_query': search_query,
        'all_projects': all_projects,
    }
    return render(request, 'employees/index.html', context)


@login_required
def assign_projects(request, profile_id):
    if request.method != 'POST':
        return redirect('employees_list')
    try:
        profile = UserProfile.objects.get(id=profile_id)
        project_ids = request.POST.getlist('project_ids')
        profile.user.assigned_projects.set(Project.objects.filter(id__in=project_ids))
    except Exception:
        pass
    return redirect('employees_list')


@login_required
def edit_employee(request, profile_id):
    if request.method != 'POST':
        return redirect('employees_list')
    try:
        from django.contrib.auth.models import User as AuthUser
        profile = UserProfile.objects.get(id=profile_id)
        full_name = request.POST.get('full_name', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        role = request.POST.get('role', 'worker')
        specialization = request.POST.get('specialization', '').strip()
        is_active = request.POST.get('status', 'active') == 'active'

        parts = full_name.split(' ', 1)
        profile.user.first_name = parts[0]
        profile.user.last_name = parts[1] if len(parts) > 1 else ''
        profile.user.email = email
        profile.user.is_active = is_active
        profile.user.save()

        profile.phone = phone
        profile.role = role
        profile.specialization = specialization
        profile.save()
    except Exception:
        pass
    return redirect('employees_list')


@login_required
def delete_employee(request, profile_id):
    try:
        profile = UserProfile.objects.get(id=profile_id)
        profile.user.delete()
    except Exception:
        pass
    return redirect('employees_list')


@login_required
def create_employee(request):
    if request.method != 'POST':
        return redirect('employees_list')

    try:
        from django.contrib.auth.models import User
        full_name = request.POST.get('full_name', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        role = request.POST.get('role', 'worker')
        specialization = request.POST.get('specialization', '').strip()

        parts = full_name.split(' ', 1)
        first_name = parts[0]
        last_name = parts[1] if len(parts) > 1 else ''

        username = email.split('@')[0] if email else full_name.lower().replace(' ', '_')
        base = username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f'{base}{counter}'
            counter += 1

        import secrets
        user = User.objects.create_user(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            password=secrets.token_urlsafe(16),
        )
        UserProfile.objects.create(
            user=user,
            role=role,
            phone=phone,
            specialization=specialization,
        )
    except Exception:
        pass

    return redirect('employees_list')
