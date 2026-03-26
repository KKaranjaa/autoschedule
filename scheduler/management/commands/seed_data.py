from django.core.management.base import BaseCommand
from scheduler.models import Programme, Room, Lecturer, Unit

class Command(BaseCommand):
    help = 'Seeds the database with initial programme, room, lecturer, and unit data.'

    def handle(self, *args, **options):
        # 1. PROGRAMMES
        programmes_data = [
            ("BSc Information Technology", "degree"),
            ("Bachelor of Business in Information Technology", "degree"),
            ("BSc Computer Science", "degree"),
            ("BSc Cybersecurity", "degree"),
            ("MSc Information Technology", "postgraduate"),
            ("MSc Computer Science", "postgraduate"),
            ("PhD Information Technology", "postgraduate"),
        ]
        
        programmes_dict = {}
        for name, level in programmes_data:
            prog, created = Programme.objects.get_or_create(name=name, defaults={'level': level})
            programmes_dict[name] = prog

        # 2. ROOMS - Lecture Halls
        lecture_halls = [
            ("TB 310", 250), ("TB 311", 150), ("TB 312", 150), ("TB 208", 150),
            ("TB 104", 150), ("TB 102", 150), ("TB 111", 150), ("TB 388", 150),
            ("TB 106", 60), ("TB 001", 60), ("TB 002", 60), ("TB 003", 120),
            ("TB 007", 150), ("TB 008", 150), ("TB 009", 250), ("TB 010", 250),
            ("TB 011", 150), ("LT 03", 324), ("LT 04", 432), ("CH", 300),
            ("ASH 04", 60), ("ASH 11", 60),
        ]
        for name, cap in lecture_halls:
            Room.objects.get_or_create(name=name, defaults={'capacity': cap, 'room_type': 'lecture_hall', 'is_available': True})

        # Rooms - Labs
        labs = [
            ("Comp Lab 1", 60, 'computer_lab'), ("Comp Lab 2", 60, 'computer_lab'),
            ("Comp Lab 3", 60, 'computer_lab'), ("Comp Lab 4", 60, 'computer_lab'),
            ("Phy Lab A", 60, 'physics_lab'), ("Phy Lab B", 60, 'physics_lab'),
            ("Chem Lab A", 60, 'chemistry_lab'), ("Chem Lab B", 60, 'chemistry_lab'),
            ("Bot Lab", 60, 'biology_lab'), ("Microbio Lab", 60, 'biology_lab'),
        ]
        for name, cap, rtype in labs:
            Room.objects.get_or_create(name=name, defaults={'capacity': cap, 'room_type': rtype, 'is_available': True})

        # 3. LECTURERS
        lecturers_data = [
            ("Dr. James Mwangi", "j.mwangi@embuni.ac.ke", 20),
            ("Dr. Faith Kamau", "f.kamau@embuni.ac.ke", 20),
            ("Dr. Peter Otieno", "p.otieno@embuni.ac.ke", 18),
            ("Dr. Alice Njeri", "a.njeri@embuni.ac.ke", 20),
            ("Dr. Samuel Kariuki", "s.kariuki@embuni.ac.ke", 16),
            ("Dr. Grace Wambui", "g.wambui@embuni.ac.ke", 18),
            ("Dr. David Mugo", "d.mugo@embuni.ac.ke", 20),
            ("Dr. Sarah Mutua", "s.mutua@embuni.ac.ke", 18),
            ("Dr. John Kimani", "j.kimani@embuni.ac.ke", 20),
            ("Dr. Mary Wanjiku", "m.wanjiku@embuni.ac.ke", 16),
        ]
        lecturers_dict = {}
        for full_name, email, hours in lecturers_data:
            first = full_name.split(' ')[0] + ' ' + full_name.split(' ')[1]
            last = full_name.split(' ')[2] if len(full_name.split(' ')) > 2 else ""
            lect, created = Lecturer.objects.get_or_create(
                email=email,
                defaults={'first_name': first, 'last_name': last, 'max_hours_per_week': hours}
            )
            lecturers_dict[full_name] = lect

        # 4. UNITS
        units_data = [
            # BSc IT Year 1
            ("BSc Information Technology", "SIT 126", "Systems Analysis", "Dr. James Mwangi"),
            ("BSc Information Technology", "SIT 127", "Programming Fundamentals", "Dr. Faith Kamau"),
            ("BSc Information Technology", "SIT 121", "Introduction to IT", "Dr. Peter Otieno"),
            ("BSc Information Technology", "SIT 122", "Web Technologies", "Dr. Alice Njeri"),
            ("BSc Information Technology", "CSC 124", "Discrete Mathematics", "Dr. Samuel Kariuki"),
            ("BSc Information Technology", "CSC 125", "Computer Architecture", "Dr. Grace Wambui"),
            ("BSc Information Technology", "CSC 123", "Database Systems", "Dr. James Mwangi"),
            ("BSc Information Technology", "CCS 104A", "Common Computing Skills", "Dr. David Mugo"),
            # BSc IT Year 2
            ("BSc Information Technology", "SIT 221", "Operating Systems", "Dr. Peter Otieno"),
            ("BSc Information Technology", "SIT 223", "Software Engineering", "Dr. Faith Kamau"),
            ("BSc Information Technology", "SIT 226", "Networks and Communications", "Dr. Alice Njeri"),
            ("BSc Information Technology", "SIT 227", "Object Oriented Programming", "Dr. James Mwangi"),
            ("BSc Information Technology", "CSC 221", "Algorithms and Data Structures", "Dr. Samuel Kariuki"),
            ("BSc Information Technology", "CSC 224", "Human Computer Interaction", "Dr. Grace Wambui"),
            ("BSc Information Technology", "SIT 222", "Systems Programming", "Dr. David Mugo"),
            ("BSc Information Technology", "CSC 225", "Theory of Computation", "Dr. Sarah Mutua"),
            # BSc IT Year 3
            ("BSc Information Technology", "SIT 322", "Mobile Application Development", "Dr. Faith Kamau"),
            ("BSc Information Technology", "SIT 323", "Information Security", "Dr. James Mwangi"),
            ("BSc Information Technology", "SIT 324", "Cloud Computing", "Dr. Alice Njeri"),
            ("BSc Information Technology", "SIT 325", "IT Project Management", "Dr. Peter Otieno"),
            ("BSc Information Technology", "CSC 321", "Artificial Intelligence", "Dr. Samuel Kariuki"),
            # BSc IT Year 4
            ("BSc Information Technology", "SIT 421", "Advanced Systems Design", "Dr. Peter Otieno"),
            ("BSc Information Technology", "SIT 422", "Enterprise Systems", "Dr. James Mwangi"),
            ("BSc Information Technology", "SIT 423", "IT Research Methods", "Dr. Faith Kamau"),
            ("BSc Information Technology", "SIT 424", "Final Year Project", "Dr. Alice Njeri"),
            ("BSc Information Technology", "SIT 415", "Distributed Systems", "Dr. Grace Wambui"),
            ("BSc Information Technology", "CSC 454", "Advanced Topics in Computing", "Dr. Samuel Kariuki"),
            
            # BBIT Year 1
            ("Bachelor of Business in Information Technology", "SIT 122P", "Web Technologies Practical", "Dr. Grace Wambui"),
            ("Bachelor of Business in Information Technology", "CCS 104B", "Common Computing Skills B", "Dr. David Mugo"),
            ("Bachelor of Business in Information Technology", "SIT 127B", "Programming Fundamentals B", "Dr. Faith Kamau"),
            ("Bachelor of Business in Information Technology", "CSC 123B", "Database Systems B", "Dr. John Kimani"),
            # BBIT Year 2
            ("Bachelor of Business in Information Technology", "SIT 227B", "Object Oriented Programming B", "Dr. James Mwangi"),
            ("Bachelor of Business in Information Technology", "CSC 225B", "Theory of Computation B", "Dr. Sarah Mutua"),
            ("Bachelor of Business in Information Technology", "SIT 221B", "Operating Systems B", "Dr. Peter Otieno"),
            ("Bachelor of Business in Information Technology", "SIT 225", "Business Information Systems", "Dr. Mary Wanjiku"),
            ("Bachelor of Business in Information Technology", "SIT 222B", "Systems Programming B", "Dr. David Mugo"),
            # BBIT Year 3
            ("Bachelor of Business in Information Technology", "DFI 303", "Digital Finance", "Dr. Faith Kamau"),
            ("Bachelor of Business in Information Technology", "SIT 322B", "Mobile Development B", "Dr. Grace Wambui"),
            ("Bachelor of Business in Information Technology", "SIT 323B", "Information Security B", "Dr. James Mwangi"),
            ("Bachelor of Business in Information Technology", "SIT 325B", "IT Project Management B", "Dr. Peter Otieno"),
            ("Bachelor of Business in Information Technology", "CSC 321B", "Artificial Intelligence B", "Dr. Samuel Kariuki"),
            # BBIT Year 4
            ("Bachelor of Business in Information Technology", "SIT 415B", "Distributed Systems B", "Dr. Alice Njeri"),
            ("Bachelor of Business in Information Technology", "SIT 417", "IT Governance", "Dr. John Kimani"),
            ("Bachelor of Business in Information Technology", "SIT 424B", "Final Year Project B", "Dr. Faith Kamau"),

            # BSc CS Year 1
            ("BSc Computer Science", "CSC 121", "Introduction to Programming", "Dr. Samuel Kariuki"),
            ("BSc Computer Science", "CSC 126", "Logic and Set Theory", "Dr. Grace Wambui"),
            ("BSc Computer Science", "CSC 124B", "Discrete Mathematics B", "Dr. David Mugo"),
            ("BSc Computer Science", "CCS 104B", "Common Computing Skills", "Dr. Mary Wanjiku"),
            # BSc CS Year 2
            ("BSc Computer Science", "CSC 221B", "Algorithms and Data Structures B", "Dr. Samuel Kariuki"),
            ("BSc Computer Science", "CSC 222", "Compiler Construction", "Dr. John Kimani"),
            ("BSc Computer Science", "CSC 223", "Operating Systems B", "Dr. Peter Otieno"),
            ("BSc Computer Science", "CSC 224B", "Human Computer Interaction B", "Dr. Grace Wambui"),
            ("BSc Computer Science", "CSC 225C", "Theory of Computation C", "Dr. Sarah Mutua"),
            ("BSc Computer Science", "CSC 226", "Numerical Methods", "Dr. David Mugo"),
            ("BSc Computer Science", "CSC 227", "Computer Graphics", "Dr. Mary Wanjiku"),
            # BSc CS Year 3
            ("BSc Computer Science", "CSC 321B", "Artificial Intelligence B", "Dr. Samuel Kariuki"),
            ("BSc Computer Science", "CSC 322", "Compiler Design", "Dr. John Kimani"),
            ("BSc Computer Science", "CSC 323", "Distributed Computing", "Dr. Peter Otieno"),
            ("BSc Computer Science", "CSC 324", "Information Retrieval", "Dr. Grace Wambui"),
            ("BSc Computer Science", "CSC 325", "Cryptography", "Dr. Alice Njeri"),
            ("BSc Computer Science", "CSC 326", "Software Testing", "Dr. Faith Kamau"),
            # BSc CS Year 4
            ("BSc Computer Science", "CSC 418", "Advanced Algorithms", "Dr. Samuel Kariuki"),
            ("BSc Computer Science", "CSC 432", "Machine Learning", "Dr. John Kimani"),
            ("BSc Computer Science", "CSC 441", "Computer Vision", "Dr. Peter Otieno"),
            ("BSc Computer Science", "CSC 452", "Advanced Database Systems", "Dr. Grace Wambui"),
            ("BSc Computer Science", "CSC 463", "Natural Language Processing", "Dr. Alice Njeri"),
            ("BSc Computer Science", "CSC 481", "Research Project", "Dr. James Mwangi"),

            # BSc Cybersecurity Year 1
            ("BSc Cybersecurity", "SCS 125", "Introduction to Cybersecurity", "Dr. Sarah Mutua"),
            ("BSc Cybersecurity", "CSC 121B", "Introduction to Programming B", "Dr. Samuel Kariuki"),
            ("BSc Cybersecurity", "CSC 124C", "Discrete Mathematics C", "Dr. David Mugo"),
            ("BSc Cybersecurity", "SMA 218", "Mathematics for Computing", "Dr. Mary Wanjiku"),

            # MSc IT Year 1
            ("MSc Information Technology", "SIT 701", "Advanced Networking", "Dr. Faith Kamau"),
            ("MSc Information Technology", "SIT 702", "IT Management", "Dr. Peter Otieno"),
            ("MSc Information Technology", "SIT 703", "Advanced Software Engineering", "Dr. Alice Njeri"),
            ("MSc Information Technology", "SIT 704", "Research Methodology", "Dr. James Mwangi"),
            ("MSc Information Technology", "SIT 705", "Advanced Database Systems", "Dr. Samuel Kariuki"),
            ("MSc Information Technology", "SIT 706", "Knowledge Management", "Dr. Grace Wambui"),
            ("MSc Information Technology", "SIT 707", "Advanced Research Methods", "Dr. James Mwangi"),
            ("MSc Information Technology", "SIT 708", "IT Strategy", "Dr. John Kimani"),
            ("MSc Information Technology", "SIT 709", "Advanced Networks", "Dr. Faith Kamau"),
            ("MSc Information Technology", "SIT 710", "Emerging Technologies", "Dr. Sarah Mutua"),
            ("MSc Information Technology", "SIT 711", "Data Science", "Dr. David Mugo"),

            # MSc CS Year 1
            ("MSc Computer Science", "SCS 703", "Advanced Algorithms", "Dr. Samuel Kariuki"),
            ("MSc Computer Science", "SCS 704", "Advanced AI", "Dr. John Kimani"),
            ("MSc Computer Science", "SCS 705", "Advanced Software Engineering", "Dr. Peter Otieno"),
            ("MSc Computer Science", "SCS 706", "Advanced Computer Networks", "Dr. Alice Njeri"),
            ("MSc Computer Science", "SCS 707", "Advanced Database Systems", "Dr. Grace Wambui"),
            ("MSc Computer Science", "SCS 708", "Research Methods in CS", "Dr. Faith Kamau"),
            ("MSc Computer Science", "SCS 709", "Advanced Operating Systems", "Dr. James Mwangi"),
            ("MSc Computer Science", "SCI 701", "Scientific Computing", "Dr. Sarah Mutua"),

            # PhD IT Year 1
            ("PhD Information Technology", "SIT 803", "Doctoral Research Seminar", "Dr. James Mwangi"),
            ("PhD Information Technology", "SIT 805", "Advanced Topics in IT", "Dr. Alice Njeri"),
        ]

        for prog_name, code, unit_name, lect_name in units_data:
            prog = programmes_dict.get(prog_name)
            lect = lecturers_dict.get(lect_name)
            Unit.objects.get_or_create(
                code=code,
                defaults={
                    'name': unit_name,
                    'required_hours': 3,
                    'lecturer': lect,
                    'programme': prog
                }
            )

        # Summary Output
        self.stdout.write(self.style.SUCCESS(f"✓ Programmes created: {Programme.objects.count()}"))
        self.stdout.write(self.style.SUCCESS(f"✓ Rooms created: {Room.objects.count()}"))
        self.stdout.write(self.style.SUCCESS(f"✓ Lecturers created: {Lecturer.objects.count()}"))
        self.stdout.write(self.style.SUCCESS(f"✓ Units created: {Unit.objects.count()}"))
        self.stdout.write(self.style.SUCCESS(f"✓ Time slots :Already exist, not modified"))
        self.stdout.write(self.style.SUCCESS(f"✓ Seed data complete! Ready for scheduling engine."))
