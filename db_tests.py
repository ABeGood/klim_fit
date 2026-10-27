"""Manual DB tool: create/drop tables and seed sample data (NOT a pytest suite).

    python db_tests.py              # interactive menu
    python db_tests.py reset-seed   # drop everything, recreate the schema, seed sample data (asks to confirm)
"""
import sys
import logging
from datetime import date, timedelta
from database_manager import DatabaseManager, init_database
from models import Account, Exercise, WorkoutTemplate, Comment

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def build_template(db, admin_id, name, description, duration, groups, ready=True):
    """groups = [(group_name, group_note, [(exercise, {target_*/rest_seconds/note}), ...]), ...]"""
    template = db.create_template(WorkoutTemplate(created_by=admin_id, name=name, description=description,
                                                  duration_minutes=duration))
    for group_name, group_note, sets in groups:
        group = db.create_group('templates', template.id)
        db.update_group('templates', group['id'], {'name': group_name, 'note': group_note})
        for exercise, values in sets:
            new_set = db.add_set('templates', group['id'], exercise.id)
            db.update_set('templates', new_set['id'], values)
    if ready:
        problems = db.validate_structure('templates', template.id)
        assert not problems, problems
        db.update_template(template.id, {'status': 'ready'})
    return template


def seed_sample_data():
    """Sample admin, clients, exercise library, templates and assigned workouts"""
    db = DatabaseManager()

    admin = db.create_account(Account(role='admin', name="Klimentij", surname="Lesniak",
                                      email="admin.smith@fitcoach.com"), password='124578')
    john = db.create_account(Account(name="John", surname="Doe", email="john.doe@email.com",
                                     age=30, weight_kg=75.5), password='123')
    jane = db.create_account(Account(name="Jane", surname="Smith", email="jane.smith@email.com",
                                     age=25, weight_kg=60.0), password='456')
    db.create_account(Account(name="Mike", surname="Johnson", email="mike.johnson@email.com",
                              age=35, weight_kg=85.2), password='789')

    ex = {}
    for name, description, flags in [
        ("Push-ups", "Upper body strength exercise targeting chest, shoulders, and triceps", ['reps']),
        ("Bench Press", "Barbell press for chest, shoulders and triceps", ['reps', 'weight_kg']),
        ("Pull-ups", "Bodyweight back and biceps exercise", ['reps']),
        ("Squats", "Lower body exercise targeting quadriceps, hamstrings, and glutes", ['reps', 'weight_kg']),
        ("Deadlifts", "Full-body compound exercise focusing on posterior chain", ['reps', 'weight_kg']),
        ("Plank", "Core stability exercise that strengthens abs and back", ['duration_s']),
        ("Running", "Cardiovascular exercise for endurance and fitness", ['duration_s', 'distance_m']),
    ]:
        ex[name] = db.create_exercise(Exercise(name=name, description=description, created_by=admin.id,
                                               **{'has_' + f: True for f in flags}))

    def sets(exercise, count, **values):
        return [(ex[exercise], values)] * count

    upper = build_template(db, admin.id, "Upper Body Strength", "Chest, shoulders, back", 45, [
        ("Bench press", "Slow on the way down", sets("Bench Press", 3, target_reps=10, target_weight_kg=60, rest_seconds=90)),
        ("Superset", "Alternate, no rest between", [
            (ex["Push-ups"], {'target_reps': 15, 'rest_seconds': 0}),
            (ex["Pull-ups"], {'target_reps': 8, 'rest_seconds': 60}),
        ] * 3),
    ])
    legs = build_template(db, admin.id, "Leg Day", "Lower body strength training", 60, [
        ("Squats", None, sets("Squats", 4, target_reps=8, target_weight_kg=70, rest_seconds=120)),
        ("Deadlifts", "Keep your back straight", sets("Deadlifts", 3, target_reps=5, target_weight_kg=90, rest_seconds=150)),
    ])
    build_template(db, admin.id, "Cardio & Core", "Work in progress", 30, [
        ("Run", None, [(ex["Running"], {'target_duration_s': 1200})]),  # distance missing -> stays a draft
        ("Core", None, sets("Plank", 3, target_duration_s=60, rest_seconds=30)),
    ], ready=False)

    # John: upper body yesterday (partly done, with chat); Jane: leg day tomorrow
    w1 = db.assign_template(upper.id, john.id, admin.id, date.today() - timedelta(days=1))
    db.assign_template(legs.id, jane.id, admin.id, date.today() + timedelta(days=1))
    first_group = db.get_structure('workouts', w1)[0]
    for s in first_group['sets'][:2]:
        db.record_set_result(s['id'], {'actual_reps': 10, 'actual_weight_kg': 60}, completed=True)
    db.add_comment(Comment(author_id=john.id, set_id=first_group['sets'][1]['id'], body="Last reps were tough"))
    db.add_comment(Comment(author_id=admin.id, set_id=first_group['sets'][1]['id'], body="Good — stay at 60 kg next time"))
    db.add_comment(Comment(author_id=john.id, workout_id=w1, body="Will finish the superset tonight"))

    logger.info("Sample data seeded successfully")


def reset_database():
    """Drop and recreate all tables (also drops the pre-v2 tables)"""
    db = DatabaseManager()
    db.drop_tables()
    print("✓ Tables dropped")
    db.create_tables()
    print("✓ Tables created")


def confirm_destructive() -> bool:
    db = DatabaseManager()
    host = db.database_url.split('@')[-1].split('/')[0]
    answer = input(f"This DELETES ALL DATA on {host}. Type 'yes' to continue: ")
    return answer.strip().lower() == 'yes'


def interactive_menu():
    """Interactive menu for database operations"""
    while True:
        print("\n=== Database Menu ===")
        print("1. Reset database and seed sample data")
        print("2. Reset database (empty)")
        print("3. Create tables only")
        print("4. Seed sample data (into empty tables)")
        print("5. Drop all tables")
        print("6. Exit")

        choice = input("\nEnter your choice (1-6): ").strip()

        try:
            if choice == '1' and confirm_destructive():
                reset_database()
                seed_sample_data()
            elif choice == '2' and confirm_destructive():
                reset_database()
            elif choice == '3':
                init_database()
                print("✓ Tables created")
            elif choice == '4':
                seed_sample_data()
            elif choice == '5' and confirm_destructive():
                DatabaseManager().drop_tables()
                print("✓ All tables dropped")
            elif choice == '6':
                print("Goodbye!")
                break
        except Exception as e:
            print(f"❌ Failed: {e}")


if __name__ == "__main__":
    if sys.argv[1:] == ['reset-seed']:
        if confirm_destructive():
            reset_database()
            seed_sample_data()
            print("✓ Database reset and seeded")
    else:
        interactive_menu()
