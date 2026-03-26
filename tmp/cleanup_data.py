import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'autoschedule.settings')
django.setup()

from scheduler.models import Room, Unit, Programme

def run():
    print("--- Starting Logical Data Cleanup ---")

    # 1. Update Programmes (Domain Categories)
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
                print(f"Update Programme: {p.name} -> {domain}")
                break

    # 2. Update Rooms (Names & Attributes)
    rooms = Room.objects.all()
    for r in rooms:
        # Rename Main lab50
        if "Main lab50" in r.name:
            r.name = "Computer Lab 1 (Advanced)"
            r.room_type = "computer_lab"
        
        # Set logical attributes based on type
        attrs = {}
        if r.room_type == 'lecture_hall':
            attrs = {
                'has_projector': True,
                'has_whiteboard': True,
                'air_conditioned': r.capacity > 50,
                'wheelchair_accessible': True
            }
        elif r.room_type == 'computer_lab':
            attrs = {
                'has_projector': True,
                'network_connected': True,
                'software': ['Python', 'VS Code', 'Microsoft Office', 'MySQL', 'MATLAB'],
                'air_conditioned': True
            }
        elif r.room_type == 'physics_lab':
            attrs = {
                'has_smartboard': True,
                'equipment': ['Oscilloscope', 'Multimeters', 'Power Supplies', 'Logic Probes'],
                'has_safety_shower': True
            }
        elif r.room_type == 'biology_lab':
            attrs = {
                'has_microscopes': True,
                'equipment': ['Centrifuge', 'Incubator', 'Petri Dishes'],
                'has_safety_shower': True,
                'has_fume_hood': True
            }
        elif r.room_type == 'chemistry_lab':
            attrs = {
                'has_fume_hood': True,
                'has_safety_shower': True,
                'equipment': ['Bunsen Burners', 'Flasks', 'Spectrometer']
            }
        
        r.attributes = attrs
        r.save()
        print(f"Update Room: {r.name} ({r.room_type}) with attributes")

    # 3. Update Units (Session Types & Lab Hours)
    # Theory Patterns
    theory_keywords = ['Calculus', 'Linear Algebra', 'Ethics', 'Communication', 'Management', 'Law', 'Introduction to', 'Entrepreneurship', 'Statistics', 'Economics']
    # Hybrid Patterns
    hybrid_keywords = ['Programming', 'Database', 'Network', 'Web', 'System', 'OS', 'Software Engineering', 'Structure', 'Electronics', 'Physics II', 'Microprocessor', 'Circuits']
    # Practical Patterns
    practical_keywords = ['Practical', 'Workshop', 'Laboratory', 'Techniques']

    for u in Unit.objects.all():
        # Determine logical type
        stype = 'theory' # default
        for k in practical_keywords:
            if k.lower() in u.name.lower():
                stype = 'practical'
                break
        if stype == 'theory':
            for k in hybrid_keywords:
                if k.lower() in u.name.lower():
                    stype = 'hybrid'
                    break
        
        u.session_type = stype
        
        # Set lab hours for hybrids
        if stype == 'hybrid':
            # Default: 1 hour lab for most, 2 for some
            u.lab_hours_per_week = 1 
            if u.required_hours > 3:
                u.lab_hours_per_week = 2
        else:
            u.lab_hours_per_week = None

        u.save()
        print(f"Update Unit: {u.code} ({u.name}) -> {stype}")

    print("--- Cleanup Done ---")

if __name__ == "__main__":
    run()
