# AutoSchedule

A Django-based timetable scheduling application.

## Setup Instructions

1. Clone the repository
```bash
git clone https://github.com/KKaranjaa/autoschedule.git
cd autoschedule
```

2. Create and activate virtual environment
```bash
python -m venv venv
venv\Scripts\activate
```

3. Install dependencies
```bash
pip install -r requirements.txt
```

4. Set up environment variables
- Create a `.env` file (copy from `.env.example`)
- Add your SECRET_KEY and other settings

5. Run migrations
```bash
python manage.py migrate
```

6. Start the development server
```bash
python manage.py runserver
```
