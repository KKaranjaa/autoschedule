import uuid
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.validators import MinValueValidator, MaxValueValidator


class Room(models.Model):
    """Physical space where a class can be held."""

    ROOM_TYPE_CHOICES = [
        ('lecture_hall', 'Lecture Hall'),
        ('computer_lab', 'Computer Lab'),
        ('physics_lab', 'Physics Lab'),
        ('chemistry_lab', 'Chemistry Lab'),
        ('biology_lab', 'Biology Lab'),
    ]

    name = models.CharField(max_length=100, unique=True)
    capacity = models.PositiveIntegerField(
        help_text='Maximum number of students the room can hold'
    )
    room_type = models.CharField(max_length=20, choices=ROOM_TYPE_CHOICES)
    is_available = models.BooleanField(
        default=True,
        help_text='Uncheck to exclude room from scheduling'
    )
    attributes = models.JSONField(
        default=dict,
        blank=True,
        help_text=(
            'Structured room attributes for smart classification. '
            'e.g. {"has_projector": true, "air_conditioned": true, '
            '"software": ["MATLAB", "AutoCAD"], "max_voltage": 240}'
        )
    )

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.get_room_type_display()})"

    @property
    def attribute_tags(self):
        """Returns a flat list of attribute labels for display."""
        if not isinstance(self.attributes, dict):
            return []
        tags = []
        for key, val in self.attributes.items():
            if isinstance(val, bool) and val:
                tags.append(key.replace('_', ' ').title())
            elif isinstance(val, list):
                tags.extend(val)
        return tags


class Lecturer(models.Model):
    """Academic staff member who teaches one or more units."""

    first_name = models.CharField(max_length=100, default='')
    last_name = models.CharField(max_length=100, default='')
    email = models.EmailField(unique=True)
    max_hours_per_week = models.PositiveIntegerField(
        default=20,
        help_text='Maximum teaching hours allowed per week (used as a hard constraint)'
    )
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, null=True, blank=True,
        related_name='lecturer_profile'
    )

    @property
    def name(self):
        return f"{self.first_name} {self.last_name}"

    class Meta:
        ordering = ['first_name', 'last_name']

    def __str__(self):
        return self.name


class Programme(models.Model):
    """Academic programme offered by the institution (e.g. BSc Computer Science)."""

    LEVEL_CHOICES = [
        ('degree',      'Degree'),
        ('diploma',     'Diploma'),
        ('certificate', 'Certificate'),
    ]

    # Domain category controls which lab types units in this programme may use.
    DOMAIN_CHOICES = [
        ('ict',         'ICT / Computing'),
        ('biology',     'Biology / Life Sciences'),
        ('chemistry',   'Chemistry'),
        ('physics',     'Physics / Electronics / Engineering'),
        ('general',     'General / Multi-discipline'),
    ]

    name = models.CharField(max_length=200)
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default='degree')
    domain_category = models.CharField(
        max_length=20,
        choices=DOMAIN_CHOICES,
        null=True,
        blank=True,
        help_text=(
            'Controls which lab types units in this programme may use. '
            'ICT = Computer Labs (+ Physics Lab for electronics); '
            'Biology = Biology Labs; Chemistry = Chemistry Labs; '
            'Physics = Physics Labs; General = any lab.'
        )
    )

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.get_level_display()})"

    @property
    def allowed_lab_types(self):
        """
        Returns allowed lab room_type values for this programme based on its domain.
        Used as the default lab routing when a unit has no preferred_lab_type set.
        """
        mapping = {
            'ict':       ['computer_lab', 'physics_lab'],   # physics_lab for electronics
            'biology':   ['biology_lab'],
            'chemistry': ['chemistry_lab'],
            'physics':   ['physics_lab'],
            'general':   ['computer_lab', 'physics_lab', 'chemistry_lab', 'biology_lab'],
        }
        return mapping.get(self.domain_category, [
            'computer_lab', 'physics_lab', 'chemistry_lab', 'biology_lab'
        ])


class Unit(models.Model):
    """An academic course/unit offered by the university."""

    LAB_TYPE_CHOICES = [
        ('computer_lab',   'Computer Lab'),
        ('physics_lab',    'Physics Lab'),
        ('chemistry_lab',  'Chemistry Lab'),
        ('biology_lab',    'Biology Lab'),
        ('any_lab',        'Any Lab (programme default)'),
    ]

    SESSION_TYPE_CHOICES = [
        ('theory',    'Theory Only — all sessions in lecture hall'),
        ('practical', 'Practical Only — all sessions in lab'),
        ('hybrid',    'Hybrid — split between lecture hall and lab'),
    ]

    code = models.CharField(max_length=20, unique=True, help_text='e.g. CS101')
    name = models.CharField(max_length=200)
    required_hours = models.PositiveIntegerField(
        default=3,
        help_text='Total contact hours per week for this unit'
    )
    session_type = models.CharField(
        max_length=10,
        choices=SESSION_TYPE_CHOICES,
        default='theory',
        help_text=(
            'Theory: only lecture halls. '
            'Practical: only labs. '
            'Hybrid: some sessions in hall, some in lab.'
        )
    )
    lab_hours_per_week = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text=(
            'For Hybrid units: how many hours per week are spent in a lab. '
            'The remaining hours go to a lecture hall. '
            'Leave blank for Theory/Practical units.'
        )
    )
    preferred_lab_type = models.CharField(
        max_length=20,
        choices=LAB_TYPE_CHOICES,
        null=True,
        blank=True,
        help_text=(
            'For Practical and Hybrid units. '
            'Leave as "Any Lab" to let the programme domain decide, '
            'or choose a specific lab type to override.'
        )
    )
    lecturer = models.ForeignKey(
        Lecturer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='units',
    )
    programme = models.ForeignKey(
        'Programme',
        on_delete=models.CASCADE,
        related_name='units',
        null=True,
    )

    class Meta:
        ordering = ['code']

    def __str__(self):
        return f"{self.code} — {self.name}"

    # ── Room routing helpers ──────────────────────────────────────────────────

    def _resolve_lab_types(self):
        """
        Returns the list of lab room_type values valid for this unit.
        Priority:  unit.preferred_lab_type  >  programme.domain_category  >  all labs.
        """
        if self.preferred_lab_type and self.preferred_lab_type != 'any_lab':
            return [self.preferred_lab_type]
        if self.programme and self.programme.domain_category:
            return self.programme.allowed_lab_types
        # Absolute fallback: all lab types
        return ['computer_lab', 'physics_lab', 'chemistry_lab', 'biology_lab']

    @property
    def theory_room_types(self):
        """Room types valid for the lecture (theory) portion of this unit."""
        if self.session_type == 'practical':
            return []
        return ['lecture_hall']

    @property
    def lab_room_types(self):
        """Room types valid for the lab (practical) portion of this unit."""
        if self.session_type == 'theory':
            return []
        return self._resolve_lab_types()

    @property
    def theory_hours(self):
        """Hours per week to schedule in lecture halls."""
        if self.session_type == 'theory':
            return self.required_hours
        if self.session_type == 'practical':
            return 0
        # hybrid
        lab_h = self.lab_hours_per_week or max(1, self.required_hours // 3)
        return max(1, self.required_hours - lab_h)

    @property
    def lab_hours(self):
        """Hours per week to schedule in labs."""
        if self.session_type == 'theory':
            return 0
        if self.session_type == 'practical':
            return self.required_hours
        # hybrid
        lab_h = self.lab_hours_per_week or max(1, self.required_hours // 3)
        return min(lab_h, self.required_hours - 1)  # at least 1 theory hour


class TimeSlot(models.Model):
    """A discrete block of time that can be allocated in the timetable."""

    DAY_CHOICES = [
        ('MON', 'Monday'),
        ('TUE', 'Tuesday'),
        ('WED', 'Wednesday'),
        ('THU', 'Thursday'),
        ('FRI', 'Friday'),
        ('SAT', 'Saturday'),
    ]

    day = models.CharField(max_length=3, choices=DAY_CHOICES)
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        ordering = ['day', 'start_time']
        unique_together = [['day', 'start_time', 'end_time']]

    def __str__(self):
        return (
            f"{self.get_day_display()} "
            f"{self.start_time.strftime('%H:%M')}–{self.end_time.strftime('%H:%M')}"
        )


class TimetableEntry(models.Model):
    """
    Core scheduling output table.
    Each row represents a single scheduled class session:
    a specific unit, delivered by a lecturer, in a room, at a timeslot.
    Consecutive slots belonging to the same session block share a session_group_id.
    """

    unit = models.ForeignKey(
        Unit, on_delete=models.CASCADE, related_name='timetable_entries'
    )
    room = models.ForeignKey(
        Room, on_delete=models.CASCADE, related_name='timetable_entries'
    )
    timeslot = models.ForeignKey(
        TimeSlot, on_delete=models.CASCADE, related_name='timetable_entries'
    )
    lecturer = models.ForeignKey(
        Lecturer, on_delete=models.CASCADE, related_name='timetable_entries'
    )
    session_group_id = models.UUIDField(default=uuid.uuid4, null=True, blank=True)

    class Meta:
        ordering = ['timeslot', 'room']
        unique_together = [['room', 'timeslot']]
        verbose_name = 'Timetable Entry'
        verbose_name_plural = 'Timetable Entries'

    def __str__(self):
        return f"{self.unit.code} | {self.room.name} | {self.timeslot}"


class LecturerPreference(models.Model):
    """
    Stores a lecturer's preference for a particular timeslot.
    Used as a soft constraint in the AI scheduling algorithm.
    Score: 1 (strongly disliked) → 5 (strongly preferred).
    """

    lecturer = models.ForeignKey(
        Lecturer, on_delete=models.CASCADE, related_name='preferences'
    )
    timeslot = models.ForeignKey(
        TimeSlot, on_delete=models.CASCADE, related_name='lecturer_preferences'
    )
    preference_score = models.IntegerField(
        default=3,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text='1 = strongly disliked, 5 = strongly preferred',
    )

    class Meta:
        ordering = ['lecturer', 'timeslot']
        unique_together = [['lecturer', 'timeslot']]
        verbose_name = 'Lecturer Preference'
        verbose_name_plural = 'Lecturer Preferences'

    def __str__(self):
        return (
            f"{self.lecturer.first_name} {self.lecturer.last_name} "
            f"→ {self.timeslot} (score: {self.preference_score})"
        )


class Profile(models.Model):
    """Extends the built-in User model to include roles."""

    ROLE_CHOICES = [
        ('admin',    'Administrator'),
        ('lecturer', 'Lecturer'),
        ('student',  'Student'),
    ]

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='profile'
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='student')
    must_change_password = models.BooleanField(default=False)

    # Student-specific fields
    registration_number = models.CharField(
        max_length=50, unique=True, null=True, blank=True
    )
    programme = models.ForeignKey(
        Programme, on_delete=models.CASCADE,
        related_name='students', null=True, blank=True
    )
    year_of_study = models.CharField(
        max_length=20,
        choices=[
            ('Year 1', 'Year 1'), ('Year 2', 'Year 2'),
            ('Year 3', 'Year 3'), ('Year 4', 'Year 4'),
        ],
        null=True, blank=True
    )

    def __str__(self):
        return f"{self.user.username} - {self.get_role_display()}"


# ── Signals ───────────────────────────────────────────────────────────────────
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()
    else:
        Profile.objects.create(user=instance)
