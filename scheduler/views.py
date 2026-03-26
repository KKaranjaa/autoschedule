from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from functools import wraps
from .models import User, Lecturer, Unit, Room, TimeSlot, LecturerPreference, Programme, TimetableEntry, Profile
from .forms import LecturerForm, ProgrammeForm, UnitForm, VenueForm, LabForm, PreferenceForm


# ── Room attribute helper ─────────────────────────────────────────────────────
# Predefined attribute keys for smart classification.
# Boolean attributes are submitted as checkboxes; list attributes as comma-separated text.

VENUE_BOOL_ATTRS = [
    'has_projector', 'has_whiteboard', 'has_smartboard',
    'air_conditioned', 'has_microphone', 'has_camera',
    'wheelchair_accessible',
]

LAB_BOOL_ATTRS = [
    'air_conditioned', 'has_projector', 'has_smartboard',
    'wheelchair_accessible', 'has_fume_hood', 'has_safety_shower',
    'has_microscopes', 'network_connected',
]

LAB_LIST_ATTRS = ['software', 'equipment']


def _parse_room_attributes(post_data, room_category='venue'):
    """
    Build the attributes JSON dict from POST form data.
    Checkboxes → bool values.
    Comma-separated text fields → list values.
    """
    attrs = {}
    bool_keys = VENUE_BOOL_ATTRS if room_category == 'venue' else LAB_BOOL_ATTRS
    for key in bool_keys:
        attrs[key] = (f'attr_{key}' in post_data)

    if room_category == 'lab':
        for key in LAB_LIST_ATTRS:
            raw = post_data.get(f'attr_{key}', '')
            items = [x.strip() for x in raw.split(',') if x.strip()]
            if items:
                attrs[key] = items

    # Remove all-False bool entries to keep attrs compact
    attrs = {k: v for k, v in attrs.items() if v is not False and v != []}
    return attrs
# ─────────────────────────────────────────────────────────────────────────────



def admin_required(view_func):
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if hasattr(request.user, 'profile') and request.user.profile.role == 'admin':
            return view_func(request, *args, **kwargs)
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        messages.error(request, "Access denied. Admin privileges required.")
        return redirect('login')
    return _wrapped_view

def lecturer_required(view_func):
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if hasattr(request.user, 'profile') and request.user.profile.role == 'lecturer':
            return view_func(request, *args, **kwargs)
        messages.error(request, "Access denied. Lecturer privileges required.")
        return redirect('login')
    return _wrapped_view

def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            try:
                role = user.profile.role
                if role == 'lecturer' and user.profile.must_change_password:
                    return redirect('change_password')
                
                if role == 'admin':
                    return redirect('admin_dashboard')
                elif role == 'lecturer':
                    return redirect('lecturer_dashboard')
                else:
                    return redirect('student_dashboard')
            except AttributeError:
                if user.is_superuser:
                    return redirect('admin_dashboard')
                return redirect('login')
        else:
            messages.error(request, 'Invalid username or password')
            
    return render(request, 'scheduler/login.html')

def logout_view(request):
    logout(request)
    return redirect('login')

def register_view(request):
    if request.method == 'POST':
        full_name = request.POST.get('full_name')
        reg_no = request.POST.get('reg_no')
        programme_id = request.POST.get('programme')
        year = request.POST.get('year')
        email = request.POST.get('email')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')

        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
        elif User.objects.filter(email=email).exists():
            messages.error(request, "Email already in use.")
        elif Student.objects.filter(registration_number=reg_no).exists():
            messages.error(request, "Registration number already exists.")
        elif not reg_no or len(reg_no) < 4:
            messages.error(request, "Invalid registration number.")
        else:
            try:
                first_name = full_name.split()[0] if ' ' in full_name else full_name
                last_name = " ".join(full_name.split()[1:]) if ' ' in full_name else ""
                
                user = User.objects.create_user(
                    username=reg_no,
                    email=email,
                    password=password,
                    first_name=first_name,
                    last_name=last_name
                )
                user.profile.role = 'student'
                user.profile.registration_number = reg_no
                user.profile.programme = get_object_or_404(Programme, id=programme_id)
                user.profile.year_of_study = year
                user.profile.save()

                login(request, user)
                messages.success(request, f"Welcome, {full_name}! Your account has been created.")
                return redirect('student_dashboard')
            except Exception as e:
                messages.error(request, f"Error during registration: {str(e)}")

    programmes = Programme.objects.all()
    return render(request, 'scheduler/register.html', {'programmes': programmes})

@admin_required
def admin_dashboard(request):
    lecturer_count = Lecturer.objects.count()
    unit_count = Unit.objects.count()
    student_count = User.objects.filter(profile__role='student').count()
    venue_count = Room.objects.filter(room_type='lecture_hall').count()
    lab_types = ['computer_lab', 'physics_lab', 'chemistry_lab', 'biology_lab']
    lab_count = Room.objects.filter(room_type__in=lab_types).count()

    context = {
        'lecturer_count': lecturer_count,
        'unit_count': unit_count,
        'student_count': student_count,
        'venue_count': venue_count,
        'lab_count': lab_count,
    }
    return render(request, 'scheduler/admin_dashboard.html', context)

# --- Management Views ---

@admin_required
def manage_lecturers(request):
    if request.method == 'POST':
        form = LecturerForm(request.POST)
        if form.is_valid():
            # Create linked User account first
            email = form.cleaned_data['email']
            first_name = form.cleaned_data['first_name']
            last_name = form.cleaned_data['last_name']
            username = email.split('@')[0]
            
            user, created = User.objects.get_or_create(username=username, email=email)
            user.first_name = first_name
            user.last_name = last_name
            if created:
                user.set_password('lecturer123')
            user.save()
            
            # Ensure profile role is lecturer and must change password
            user.profile.role = 'lecturer'
            user.profile.must_change_password = True
            user.profile.save()
            
            # Create/Update Lecturer record linked to User
            lecturer = form.save(commit=False)
            lecturer.user = user
            lecturer.save()
            
            messages.success(request, f"Lecturer {lecturer.first_name} {lecturer.last_name} created and linked to user account.")
            return redirect('manage_lecturers')
    else:
        form = LecturerForm()
    
    lecturers = Lecturer.objects.all()
    return render(request, 'scheduler/manage_lecturers.html', {'form': form, 'lecturers': lecturers})

@admin_required
def manage_programmes(request):
    if request.method == 'POST':
        form = ProgrammeForm(request.POST)
        if form.is_valid():
            programme = form.save()
            messages.success(request, f"Programme {programme.name} added successfully.")
            return redirect('manage_programmes')
    else:
        form = ProgrammeForm()
    
    programmes = Programme.objects.all()
    return render(request, 'scheduler/manage_programmes.html', {'form': form, 'programmes': programmes})

@admin_required
def manage_units(request):
    if request.method == 'POST':
        form = UnitForm(request.POST)
        if form.is_valid():
            unit = form.save()
            messages.success(request, f"Unit {unit.code} added successfully.")
            return redirect('manage_units')
    else:
        form = UnitForm()
    
    units = Unit.objects.all()
    return render(request, 'scheduler/manage_units.html', {'form': form, 'units': units})

@admin_required
def manage_venues(request):
    if request.method == 'POST':
        form = VenueForm(request.POST)
        if form.is_valid():
            venue = form.save(commit=False)
            venue.room_type = 'lecture_hall'
            venue.attributes = _parse_room_attributes(request.POST, 'venue')
            venue.save()
            messages.success(request, f"Venue {venue.name} added successfully.")
            return redirect('manage_venues')
    else:
        form = VenueForm()

    venues = Room.objects.filter(room_type='lecture_hall')
    return render(request, 'scheduler/manage_venues.html', {'form': form, 'venues': venues})

def manage_labs(request):
    if request.method == 'POST':
        form = LabForm(request.POST)
        if form.is_valid():
            lab = form.save(commit=False)
            lab.attributes = _parse_room_attributes(request.POST, 'lab')
            lab.save()
            messages.success(request, f"Laboratory {lab.name} added successfully.")
            return redirect('manage_labs')
    else:
        form = LabForm()

    lab_types = ['computer_lab', 'physics_lab', 'chemistry_lab', 'biology_lab']
    labs = Room.objects.filter(room_type__in=lab_types)
    return render(request, 'scheduler/manage_labs.html', {'form': form, 'labs': labs})

@admin_required
def lecturer_preferences(request):
    if request.method == 'POST':
        form = PreferenceForm(request.POST)
        if form.is_valid():
            pref = form.save()
            messages.success(request, f"Preference for {pref.lecturer.first_name} {pref.lecturer.last_name} updated.")
            return redirect('lecturer_preferences')
    else:
        form = PreferenceForm()
    
    preferences = LecturerPreference.objects.all()
    return render(request, 'scheduler/lecturer_preferences.html', {'form': form, 'preferences': preferences})

@admin_required
def generate_timetable(request):
    from .scheduler_engine import generate_timetable as run_engine
    
    results = None
    if request.method == 'POST':
        if 'clear' in request.POST:
            TimetableEntry.objects.all().delete()
            messages.success(request, "Timetable cleared successfully.")
            return redirect('generate_timetable')
        else:
            results = run_engine()
    
    context = {
        'results': results,
        'unit_count': Unit.objects.count(),
        'room_count': Room.objects.filter(is_available=True).count(),
        'lecturer_count': Lecturer.objects.count(),
        'timeslot_count': TimeSlot.objects.count(),
        'entry_count': TimetableEntry.objects.count(),
    }
    return render(request, 'scheduler/generate_timetable.html', context)

def get_year_from_unit_code(code):
    import re
    numbers = re.findall(r'\d+', code)
    if numbers:
        num = int(numbers[0])
        if 100 <= num <= 199: return 1
        if 200 <= num <= 299: return 2
        if 300 <= num <= 399: return 3
        if 400 <= num <= 499: return 4
        if num >= 500: return 'PG'
    return 1

def get_slot_number(start_time):
    # slot 1 = 07:00, slot 2 = 08:00, ..., slot 13 = 19:00
    return start_time.hour - 6

@admin_required
def view_timetables(request):
    programme_id = request.GET.get('programme')
    lecturer_id = request.GET.get('lecturer')

    # Load ALL entries for the grid -- filters applied via JS row visibility
    all_entries = TimetableEntry.objects.select_related(
        'unit', 'unit__programme', 'room', 'lecturer', 'timeslot'
    ).all()

    DAY_CODES = ['MON', 'TUE', 'WED', 'THU', 'FRI']
    DAY_LABELS = {'MON': 'Monday', 'TUE': 'Tuesday', 'WED': 'Wednesday',
                  'THU': 'Thursday', 'FRI': 'Friday'}
    SLOT_NUMBERS = list(range(1, 14))  # 1-13 = 07:00-19:00

    grid = {}
    row_meta = {}

    COLOURS = [
        '#dbeafe', '#dcfce7', '#fef9c3', '#fce7f3', '#ede9fe',
        '#ffedd5', '#e0f2fe', '#d1fae5', '#fef3c7', '#f3e8ff',
    ]
    prog_colour_map = {}
    colour_idx = 0

    for entry in all_entries:
        if not entry.unit.programme:
            continue
        prog_name = entry.unit.programme.name
        prog_id = entry.unit.programme_id
        year = get_year_from_unit_code(entry.unit.code)
        row_key = f"{prog_id}_Y{year}"
        day = entry.timeslot.day
        slot_num = get_slot_number(entry.timeslot.start_time)

        if row_key not in grid:
            grid[row_key] = {d: {} for d in DAY_CODES}
            short_map = {
                'BSc Information Technology': 'BSc IT',
                'Bachelor of Business in Information Technology': 'BBIT',
                'BSc Computer Science': 'BSc CS',
                'BSc Cybersecurity': 'BSc CySec',
                'MSc Information Technology': 'MSc IT',
                'MSc Computer Science': 'MSc CS',
                'PhD Information Technology': 'PhD IT',
            }
            short = short_map.get(prog_name, prog_name[:10])
            year_label = 'PG' if year == 'PG' else f"Y{year}"
            row_meta[row_key] = {
                'label': f"{prog_name} - Year {year}" if year != 'PG' else f"{prog_name} - Postgrad",
                'short_label': f"{short} - {year_label}",
                'programme_id': prog_id,
                'programme_name': prog_name,
                'year': year,
            }
            if prog_id not in prog_colour_map:
                prog_colour_map[prog_id] = COLOURS[colour_idx % len(COLOURS)]
                colour_idx += 1

        room_type_class_map = {
            'lecture_hall': 'rt-lecture',
            'computer_lab': 'rt-computer',
            'physics_lab': 'rt-physics',
            'chemistry_lab': 'rt-chemistry',
            'biology_lab': 'rt-biology',
        }
        room_type = entry.room.room_type if entry.room else 'lecture_hall'
        rt_class = room_type_class_map.get(room_type, 'rt-lecture')

        grid[row_key][day][slot_num] = {
            'unit_code': entry.unit.code,
            'unit_name': entry.unit.name,
            'room': entry.room.name if entry.room else '---',
            'room_type': room_type,
            'room_type_class': rt_class,
            'room_capacity': entry.room.capacity if entry.room else 0,
            'lecturer': f"Dr. {entry.lecturer.last_name}" if entry.lecturer else '---',
            'lecturer_full': (f"{entry.lecturer.first_name} {entry.lecturer.last_name}"
                              if entry.lecturer else '---'),
            'lecturer_id': entry.lecturer_id,
            'programme_id': prog_id,
            'programme_name': prog_name,
            'year': year,
            'session_group_id': str(entry.session_group_id) if entry.session_group_id else None,
            'start_time': entry.timeslot.start_time.strftime('%H:%M'),
            'end_time': entry.timeslot.end_time.strftime('%H:%M'),
            'day_label': DAY_LABELS.get(day, day),
            'colspan': 1,
            'skip': False,
            'session_hours': 1,
        }

    # Post-process: compute colspan for session groups
    for rk in grid:
        for day in DAY_CODES:
            day_grid = grid[rk][day]
            processed = set()
            for sn in SLOT_NUMBERS:
                cell = day_grid.get(sn)
                if cell is None or cell.get('skip') or sn in processed:
                    continue
                sgid = cell.get('session_group_id')
                if not sgid:
                    continue
                span = 1
                for la in range(1, 4):
                    nc = day_grid.get(sn + la)
                    if (nc and nc.get('session_group_id') == sgid
                            and nc.get('unit_code') == cell['unit_code']):
                        span += 1
                    else:
                        break
                if span > 1:
                    cell['colspan'] = span
                    cell['session_hours'] = span
                    last_cell = day_grid.get(sn + span - 1)
                    if last_cell:
                        cell['end_time'] = last_cell['end_time']
                    for cont in range(1, span):
                        cont_cell = day_grid.get(sn + cont)
                        if cont_cell:
                            cont_cell['skip'] = True
                    processed.update(range(sn, sn + span))

    # Sort rows: by programme name then year
    def sort_key(k):
        meta = row_meta[k]
        yr = meta['year']
        return (meta['programme_name'], 0 if yr == 'PG' else yr)

    ordered_rows = sorted(grid.keys(), key=sort_key)

    rows = []
    for rk in ordered_rows:
        meta = row_meta[rk]
        colour = prog_colour_map.get(meta['programme_id'], '#e0f2fe')
        day_data = []
        for d in DAY_CODES:
            slots = []
            for sn in SLOT_NUMBERS:
                cell = grid[rk][d].get(sn)
                if cell and cell.get('skip'):
                    slots.append({'skip': True})
                else:
                    slots.append(cell)
            day_data.append({'day': d, 'day_label': DAY_LABELS[d], 'slots': slots})
        rows.append({
            'key': rk,
            'label': meta['label'],
            'short_label': meta['short_label'],
            'programme_id': meta['programme_id'],
            'year': meta['year'],
            'colour': colour,
            'days': day_data,
        })

    slot_labels = [f"{6 + i:02d}:00" for i in SLOT_NUMBERS]

    room_type_legend = [
        {'label': 'Lecture Hall',   'css_class': 'rt-lecture'},
        {'label': 'Computer Lab',   'css_class': 'rt-computer'},
        {'label': 'Physics Lab',    'css_class': 'rt-physics'},
        {'label': 'Chemistry Lab',  'css_class': 'rt-chemistry'},
        {'label': 'Biology Lab',    'css_class': 'rt-biology'},
    ]

    programmes = Programme.objects.all()
    for p in programmes:
        p.is_selected = (str(p.id) == programme_id)

    lecturers = Lecturer.objects.all()
    for l in lecturers:
        l.is_selected = (str(l.id) == lecturer_id)

    from datetime import datetime
    context = {
        'rows': rows,
        'slot_labels': slot_labels,
        'slot_numbers': SLOT_NUMBERS,
        'day_codes': DAY_CODES,
        'day_labels': DAY_LABELS,
        'programmes': programmes,
        'lecturers': lecturers,
        'selected_programme': programme_id or '',
        'selected_lecturer': lecturer_id or '',
        'has_entries': bool(grid),
        'generated_date': datetime.now().strftime('%d %B %Y, %H:%M'),
        'room_type_legend': room_type_legend,
    }
    return render(request, 'scheduler/view_timetables.html', context)

@admin_required
def manage_students(request):
    query = request.GET.get('q', '')
    students = User.objects.filter(profile__role='student')
    
    if query:
        from django.db.models import Q
        students = students.filter(
            Q(first_name__icontains=query) | 
            Q(last_name__icontains=query) | 
            Q(profile__registration_number__icontains=query)
        )
    
    if request.method == 'POST' and 'delete_id' in request.POST:
        user_to_delete = get_object_or_404(User, id=request.POST.get('delete_id'))
        user_name = user_to_delete.get_full_name()
        user_to_delete.delete()
        messages.success(request, f"Student {user_name} has been removed.")
        return redirect('manage_students')

    student_count = students.count()
    return render(request, 'scheduler/manage_students.html', {
        'students': students,
        'student_count': student_count,
        'query': query
    })

@admin_required
def manage_timeslots(request):
    if request.method == 'POST':
        if 'auto_generate' in request.POST:
            # Delete existing slots first to avoid conflicts and ensure new range is clean
            TimeSlot.objects.all().delete()
            
            days = ['MON', 'TUE', 'WED', 'THU', 'FRI']
            created_count = 0
            from datetime import time, timedelta, datetime
            
            for day_code in days:
                current_time = datetime.strptime("07:00", "%H:%M")
                end_of_day = datetime.strptime("20:00", "%H:%M") # New end time: 8:00 PM
                
                while current_time < end_of_day:
                    slot_start = current_time.time()
                    slot_end = (current_time + timedelta(hours=1)).time()
                    
                    TimeSlot.objects.create(
                        day=day_code,
                        start_time=slot_start,
                        end_time=slot_end
                    )
                    created_count += 1
                    current_time += timedelta(hours=1)
            
            messages.success(request, f"Successfully regenerated {created_count} time slots (7 AM – 8 PM).")
            return redirect('manage_timeslots')
        else:
            from .forms import TimeSlotForm
            form = TimeSlotForm(request.POST)
            if form.is_valid():
                form.save()
                messages.success(request, "Time slot added successfully.")
                return redirect('manage_timeslots')
    else:
        from .forms import TimeSlotForm
        form = TimeSlotForm()
    
    timeslots = TimeSlot.objects.all().order_by('day', 'start_time')
    # Grouping logic for template if needed, or just pass flat
    return render(request, 'scheduler/manage_timeslots.html', {'form': form, 'timeslots': timeslots})

@admin_required
def room_availability(request):
    rooms = Room.objects.all()
    return render(request, 'scheduler/room_availability.html', {'rooms': rooms})

@lecturer_required
def lecturer_dashboard(request):
    # Ensure a Lecturer profile exists for this user
    lecturer, created = Lecturer.objects.get_or_create(
        user=request.user,
        defaults={
            'first_name': request.user.first_name,
            'last_name': request.user.last_name,
            'email': request.user.email,
        }
    )

    if request.method == 'POST':
        # Handle saving multiple preferences at once
        saved_count = 0
        for key, value in request.POST.items():
            if key.startswith('pref_'):
                try:
                    timeslot_id = int(key.split('_')[1])
                    score = int(value)
                    timeslot = TimeSlot.objects.get(id=timeslot_id)
                    
                    LecturerPreference.objects.update_or_create(
                        lecturer=lecturer,
                        timeslot=timeslot,
                        defaults={'preference_score': score}
                    )
                    saved_count += 1
                except (ValueError, TimeSlot.DoesNotExist):
                    continue
        
        if saved_count > 0:
            messages.success(request, f"Successfully saved {saved_count} preferences.")
        return redirect('lecturer_dashboard')

    # Get all timeslots grouped by day for the form
    timeslots = TimeSlot.objects.all().order_by('day', 'start_time')
    
    # Get existing preferences for this lecturer
    existing_prefs = {p.timeslot_id: p.preference_score for p in lecturer.preferences.all()}
    
    # Attach preference score to each timeslot for easier template access
    for slot in timeslots:
        pref = existing_prefs.get(slot.id, 3) # Default to 3 (Neutral)
        slot.current_preference = pref
        slot.sel_1 = (pref == 1)
        slot.sel_2 = (pref == 2)
        slot.sel_3 = (pref == 3)
        slot.sel_4 = (pref == 4)
        slot.sel_5 = (pref == 5)
    
    context = {
        'lecturer': lecturer,
        'timeslots': timeslots,
    }
    return render(request, 'scheduler/lecturer_dashboard.html', context)

@login_required
def change_password(request):
    if request.method == 'POST':
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        
        if new_password != confirm_password:
            messages.error(request, "Passwords do not match.")
        else:
            request.user.set_password(new_password)
            request.user.save()
            from django.contrib.auth import update_session_auth_hash
            update_session_auth_hash(request, request.user)
            
            # Update profile flag
            request.user.profile.must_change_password = False
            request.user.profile.save()
            
            messages.success(request, "Password updated successfully. Welcome!")
            return redirect('lecturer_dashboard')
            
    return render(request, 'scheduler/change_password.html')

@login_required
def student_dashboard(request):
    if not hasattr(request.user, 'profile') or request.user.profile.role != 'student':
        messages.error(request, "Access denied. Student dashboard is for students only.")
        return redirect('admin_dashboard' if request.user.is_superuser else 'login')
    
    profile = request.user.profile
    programme = profile.programme
    
    # Section 1: Timetable
    from .models import TimetableEntry
    timetable_entries = TimetableEntry.objects.filter(unit__programme=programme)
    timetable_data = {entry.timeslot_id: entry for entry in timetable_entries}
        
    days = [
        ('MON', 'Monday'),
        ('TUE', 'Tuesday'),
        ('WED', 'Wednesday'),
        ('THU', 'Thursday'),
        ('FRI', 'Friday'),
    ]

    # Unique times regardless of day
    unique_times = []
    seen_times = set()
    for ts in TimeSlot.objects.all().order_by('start_time'):
        time_str = f"{ts.start_time.strftime('%H:%M')}–{ts.end_time.strftime('%H:%M')}"
        if time_str not in seen_times:
            # For each time, get all day slots and attach entries if they exist
            time_row = {
                'label': time_str,
                'day_slots': []
            }
            for day_code, _ in days:
                # Find the slot for this specific time and day
                slot = TimeSlot.objects.filter(day=day_code, start_time=ts.start_time, end_time=ts.end_time).first()
                if slot:
                    slot.entry = timetable_data.get(slot.id)
                time_row['day_slots'].append(slot)
            
            unique_times.append(time_row)
            seen_times.add(time_str)

    # Section 2: Room Availability
    from datetime import datetime
    now = datetime.now()
    current_day_code = now.strftime('%a').upper()[:3] # MON, TUE...
    current_time = now.time()
    
    # Find current timeslot
    current_slot = TimeSlot.objects.filter(
        day=current_day_code,
        start_time__lte=current_time,
        end_time__gt=current_time
    ).first()
    
    rooms = Room.objects.all()
    room_status = []
    
    # Filter by room type if requested
    room_type_filter = request.GET.get('room_type', 'All')
    if room_type_filter != 'All':
        rooms = rooms.filter(room_type=room_type_filter)

    for room in rooms:
        is_occupied = False
        if current_slot:
            is_occupied = TimetableEntry.objects.filter(room=room, timeslot=current_slot).exists()
        
        room_status.append({
            'name': room.name,
            'room_type': room.get_room_type_display(),
            'capacity': room.capacity,
            'status': 'Occupied' if is_occupied else 'Available',
            'status_class': 'status-occupied' if is_occupied else 'status-available'
        })

    # Pre-calculate room type selection flags for template
    room_types = [
        ('All', 'All Rooms'),
        ('lecture_hall', 'Lecture Hall'),
        ('computer_lab', 'Computer Lab'),
        ('physics_lab', 'Physics Lab'),
        ('chemistry_lab', 'Chemistry Lab'),
        ('biology_lab', 'Biology Lab'),
    ]
    formatted_room_types = []
    for val, label in room_types:
        formatted_room_types.append({
            'value': val,
            'label': label,
            'is_selected': (val == room_type_filter)
        })

    context = {
        'user': request.user,
        'profile': profile,
        'days': days,
        'unique_times': unique_times,
        'timetable_data': timetable_data,
        'room_status': room_status,
        'room_types': formatted_room_types,
        'current_filter': room_type_filter,
        'has_entries': timetable_entries.exists(),
    }
    return render(request, 'scheduler/student_dashboard.html', context)
