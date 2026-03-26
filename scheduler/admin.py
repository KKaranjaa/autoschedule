from django.contrib import admin
from .models import (
    Room,
    Lecturer,
    Unit,
    Programme,
    TimeSlot,
    TimetableEntry,
    LecturerPreference,
    Profile,
)

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'must_change_password')
    list_filter = ('role', 'must_change_password')
    search_fields = ('user__username', 'user__email')

@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('name', 'room_type', 'capacity', 'is_available')
    list_filter = ('room_type', 'is_available')
    search_fields = ('name',)

@admin.register(Lecturer)
class LecturerAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'max_hours_per_week')
    search_fields = ('name', 'email')

@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'required_hours', 'lecturer')
    list_filter = ('lecturer',)
    search_fields = ('code', 'name')

@admin.register(Programme)
class ProgrammeAdmin(admin.ModelAdmin):
    list_display = ('name', 'level')
    list_filter = ('level',)
    search_fields = ('name',)

@admin.register(TimeSlot)
class TimeSlotAdmin(admin.ModelAdmin):
    list_display = ('day', 'start_time', 'end_time')
    list_filter = ('day',)
    ordering = ('day', 'start_time')

@admin.register(TimetableEntry)
class TimetableEntryAdmin(admin.ModelAdmin):
    list_display = ('unit', 'lecturer', 'room', 'timeslot')
    list_filter = ('timeslot__day', 'room', 'lecturer')
    search_fields = ('unit__code', 'unit__name', 'lecturer__name')

@admin.register(LecturerPreference)
class LecturerPreferenceAdmin(admin.ModelAdmin):
    list_display = ('lecturer', 'timeslot', 'preference_score')
    list_filter = ('lecturer', 'preference_score')
    search_fields = ('lecturer__name',)
