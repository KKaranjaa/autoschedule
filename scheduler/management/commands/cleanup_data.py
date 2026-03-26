from django.core.management.base import BaseCommand
from scheduler.models import Room, Unit, Programme

class Command(BaseCommand):
    help = 'Logically re-assign room attributes and unit session types.'

    def handle(self, *args, **options):
        self.stdout.write("--- Starting Logical Data Cleanup ---")

        # 1. Update Programmes
        prog_map = {
            'Computer Science': 'ict',
            'Information Technology': 'ict',
            'Business Information Technology': 'ict',
            'Physics': 'physics',
            'Biology': 'biology',
            'Applied Statistics': 'general',
            'Mathematics': 'general',
        }
        for p in Programme.objects.all():
            for key, domain in prog_map.items():
                if key in p.name:
                    p.domain_category = domain
                    p.save()
                    self.stdout.write(f"Updated Programme: {p.name} -> {domain}")
                    break

        # 2. Update Rooms
        rooms = Room.objects.all()
        for r in rooms:
            name_lower = r.name.lower()
            
            # Special case for Main Lab
            if "main lab" in name_lower:
                r.name = "Computer Lab 1 (Advanced)"
                r.room_type = "computer_lab"
            
            # Use name keyword to fix room_type if needed
            if "comp lab" in name_lower or "computer" in name_lower:
                r.room_type = "computer_lab"
            elif "phy" in name_lower and "lab" in name_lower:
                r.room_type = "physics_lab"
            elif "chem" in name_lower and "lab" in name_lower:
                r.room_type = "chemistry_lab"
            elif ("bio" in name_lower or "bot" in name_lower) and "lab" in name_lower:
                r.room_type = "biology_lab"
            elif r.capacity >= 30 and r.room_type not in ["computer_lab", "physics_lab", "chemistry_lab", "biology_lab"]:
                r.room_type = "lecture_hall"
            
            attrs = {}
            if r.room_type == 'lecture_hall':
                attrs = {'has_projector': True, 'has_whiteboard': True, 'air_conditioned': r.capacity > 50, 'wheelchair_accessible': True}
            elif r.room_type == 'computer_lab':
                attrs = {'has_projector': True, 'network_connected': True, 'software': ['Python', 'VS Code', 'MySQL', 'MATLAB'], 'air_conditioned': True}
            elif r.room_type == 'physics_lab':
                attrs = {'has_smartboard': True, 'equipment': ['Oscilloscope', 'Multimeters'], 'has_safety_shower': True}
            elif r.room_type == 'biology_lab':
                attrs = {'has_microscopes': True, 'equipment': ['Centrifuge'], 'has_safety_shower': True, 'has_fume_hood': True}
            elif r.room_type == 'chemistry_lab':
                attrs = {'has_fume_hood': True, 'has_safety_shower': True, 'equipment': ['Bunsen Burners']}
            
            r.attributes = attrs
            r.save()
            self.stdout.write(f"Updated Room: {r.name} ({r.room_type}) with attributes")

        # 3. Update Units
        theory_keywords = ['Calculus', 'Linear Algebra', 'Ethics', 'Communication', 'Management', 'Law', 'Introduction to', 'Statistics', 'Economics']
        hybrid_keywords = ['Programming', 'Database', 'Network', 'Web', 'Software Engineering', 'Structure', 'Electronics', 'Physics II', 'Microprocessor']
        practical_keywords = ['Practical', 'Workshop', 'Laboratory', 'Techniques']

        for u in Unit.objects.all():
            stype = 'theory'
            for k in practical_keywords:
                if k.lower() in u.name.lower():
                    stype = 'practical'; break
            if stype == 'theory':
                for k in hybrid_keywords:
                    if k.lower() in u.name.lower():
                        stype = 'hybrid'; break
            
            u.session_type = stype
            u.lab_hours_per_week = 1 if stype == 'hybrid' else None
            u.save()
            self.stdout.write(f"Updated Unit: {u.code} ({u.name}) -> {stype}")

        self.stdout.write(self.style.SUCCESS("--- Data Cleanup Finished Successfully ---"))
