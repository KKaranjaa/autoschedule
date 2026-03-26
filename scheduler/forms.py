from django import forms
from .models import Lecturer, Programme, Unit, Room, TimeSlot, LecturerPreference


class LecturerForm(forms.ModelForm):
    class Meta:
        model = Lecturer
        fields = ['first_name', 'last_name', 'email', 'max_hours_per_week']


class ProgrammeForm(forms.ModelForm):
    class Meta:
        model = Programme
        fields = ['name', 'level', 'domain_category']
        help_texts = {
            'domain_category': (
                'Controls lab assignment for units in this programme. '
                'ICT → Computer / Physics Labs; Biology → Biology Labs; '
                'Chemistry → Chemistry Labs; Physics → Physics Labs; '
                'General → any lab.'
            )
        }


class UnitForm(forms.ModelForm):
    class Meta:
        model = Unit
        fields = [
            'code', 'name', 'required_hours',
            'session_type', 'lab_hours_per_week', 'preferred_lab_type',
            'lecturer', 'programme',
        ]
        widgets = {
            'session_type':       forms.Select(attrs={'id': 'id_session_type'}),
            'lab_hours_per_week': forms.NumberInput(attrs={'id': 'id_lab_hours_per_week', 'min': 1}),
            'preferred_lab_type': forms.Select(attrs={'id': 'id_preferred_lab_type'}),
        }
        help_texts = {
            'session_type':       'Theory: lecture hall only. Practical: lab only. Hybrid: both.',
            'lab_hours_per_week': 'Hybrid only: how many hours per week are in a lab.',
            'preferred_lab_type': 'Optional override. Leave blank to use programme domain.',
        }

    def clean(self):
        cleaned = super().clean()
        stype = cleaned.get('session_type')
        if stype == 'theory':
            cleaned['lab_hours_per_week'] = None
            cleaned['preferred_lab_type'] = None
        elif stype == 'practical':
            cleaned['lab_hours_per_week'] = None  # engine uses required_hours
        return cleaned


class VenueForm(forms.ModelForm):
    class Meta:
        model = Room
        fields = ['name', 'capacity', 'is_available']


class LabForm(forms.ModelForm):
    class Meta:
        model = Room
        fields = ['name', 'capacity', 'room_type', 'is_available']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        lab_choices = [
            ('computer_lab',  'Computer Lab'),
            ('physics_lab',   'Physics Lab'),
            ('chemistry_lab', 'Chemistry Lab'),
            ('biology_lab',   'Biology Lab'),
        ]
        self.fields['room_type'].choices = lab_choices


class PreferenceForm(forms.ModelForm):
    class Meta:
        model = LecturerPreference
        fields = ['lecturer', 'timeslot', 'preference_score']

    preference_score = forms.IntegerField(min_value=1, max_value=5)


class TimeSlotForm(forms.ModelForm):
    class Meta:
        model = TimeSlot
        fields = ['day', 'start_time', 'end_time']
        widgets = {
            'start_time': forms.TimeInput(attrs={'type': 'time'}),
            'end_time':   forms.TimeInput(attrs={'type': 'time'}),
        }
