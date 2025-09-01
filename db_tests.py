from database_manager import DatabaseManager, init_database
from models import User, Admin, Exercise, Workout, ExerciseSet
import logging
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def seed_sample_data():
    """Add some sample data for testing"""
    try:
        db = DatabaseManager()
        
        # Add sample users
        user1 = User(name="John", surname="Doe", email="john.doe@email.com", age=30, weight_kg=75.5)
        user2 = User(name="Jane", surname="Smith", email="jane.smith@email.com", age=25, weight_kg=60.0)
        user3 = User(name="Mike", surname="Johnson", email="mike.johnson@email.com", age=35, weight_kg=85.2)
        
        user1 = db.create_user(user1, password='123')
        user2 = db.create_user(user2, password='456')
        user3 = db.create_user(user3, password='789')
        
        # Add sample exercises with parameters
        exercise1 = Exercise(name="Push-ups", description="Upper body strength exercise targeting chest, shoulders, and triceps", has_reps=True)
        exercise2 = Exercise(name="Squats", description="Lower body exercise targeting quadriceps, hamstrings, and glutes", has_reps=True, has_weight_kg=True)
        exercise3 = Exercise(name="Plank", description="Core stability exercise that strengthens abs and back", has_duration_s=True)
        exercise4 = Exercise(name="Running", description="Cardiovascular exercise for endurance and fitness", has_duration_s=True, has_distance_m=True)
        exercise5 = Exercise(name="Deadlifts", description="Full-body compound exercise focusing on posterior chain", has_reps=True, has_weight_kg=True)
        
        db.create_exercise(exercise1)
        db.create_exercise(exercise2)
        db.create_exercise(exercise3)
        db.create_exercise(exercise4)
        db.create_exercise(exercise5)
        
        # Add sample admins
        admin1 = Admin(name="Klimentij", surname="Lesniak", email="admin.smith@fitcoach.com")
        db.create_admin(admin1, password='124578')
        
        # Add sample workouts
        workout1 = Workout(
            user_id=user1.id,
            name="Upper Body Strength",
            description="Focus on chest, shoulders, and triceps",
            workout_date=datetime.now() - timedelta(days=2),
            duration_minutes=45,
            completed=True
        )
        workout2 = Workout(
            user_id=user1.id,
            name="Leg Day",
            description="Lower body strength training",
            workout_date=datetime.now() - timedelta(days=1),
            duration_minutes=60,
            completed=False
        )
        workout3 = Workout(
            user_id=user2.id,
            name="Cardio & Core",
            description="Cardiovascular endurance and core stability",
            workout_date=datetime.now(),
            duration_minutes=30,
            completed=False
        )
        
        created_workout1 = db.create_workout(workout1)
        created_workout2 = db.create_workout(workout2)
        created_workout3 = db.create_workout(workout3)
        
        # Add sample exercise sets
        # For workout1 (Upper Body Strength)
        set1 = ExerciseSet(
            workout_id=created_workout1.id,
            exercise_id=1,  # Push-ups (assuming it gets ID 1)
            set_order=1,
            reps=15,
            completed=True
        )
        set2 = ExerciseSet(
            workout_id=created_workout1.id,
            exercise_id=1,  # Push-ups
            set_order=2,
            reps=12,
            completed=True
        )
        set3 = ExerciseSet(
            workout_id=created_workout1.id,
            exercise_id=5,  # Deadlifts
            set_order=3,
            reps=8,
            weight_kg=80.0,
            completed=True
        )
        
        # For workout2 (Leg Day)
        set4 = ExerciseSet(
            workout_id=created_workout2.id,
            exercise_id=2,  # Squats
            set_order=1,
            reps=12,
            weight_kg=60.0,
            completed=False
        )
        set5 = ExerciseSet(
            workout_id=created_workout2.id,
            exercise_id=2,  # Squats
            set_order=2,
            reps=10,
            weight_kg=65.0,
            completed=False
        )
        
        # For workout3 (Cardio & Core)
        set6 = ExerciseSet(
            workout_id=created_workout3.id,
            exercise_id=4,  # Running
            set_order=1,
            duration_s=1200,  # 20 minutes
            distance_m=3000,  # 3km
            completed=False
        )
        set7 = ExerciseSet(
            workout_id=created_workout3.id,
            exercise_id=3,  # Plank
            set_order=2,
            duration_s=60,  # 1 minute
            completed=False
        )
        
        db.create_exercise_set(set1)
        db.create_exercise_set(set2)
        db.create_exercise_set(set3)
        db.create_exercise_set(set4)
        db.create_exercise_set(set5)
        db.create_exercise_set(set6)
        db.create_exercise_set(set7)
        
        logger.info("Sample data seeded successfully")
        return True
    except Exception as e:
        logger.error(f"Error seeding sample data: {e}")
        return False

def test_database_operations():
    """Test all database operations"""
    try:
        db = DatabaseManager()
        
        print("=== Testing Database Operations ===")
        
        # Test table creation
        print("\n1. Creating tables...")
        init_database()
        print("✓ Tables created successfully")
        
        # Test user operations
        print("\n2. Testing User operations...")
        test_user = User(name="Test", surname="User", email="test@example.com", age=25, weight_kg=70.5)
        created_user = db.create_user(test_user)
        print(f"✓ Created user with ID: {created_user.id}")
        
        user = db.get_user(created_user.id)
        print(f"✓ Retrieved user: {user.name} {user.surname}")
        
        user.weight_kg = 72.0
        updated = db.update_user(user)
        print(f"✓ Updated user weight: {updated}")
        
        user_by_email = db.get_user_by_email("test@example.com")
        print(f"✓ Found user by email: {user_by_email.name}")
        
        # Test exercise operations
        print("\n3. Testing Exercise operations...")
        test_exercise = Exercise(name="Test Exercise", description="A test exercise description", has_reps=True, has_weight_kg=True)
        created_exercise = db.create_exercise(test_exercise)
        print(f"✓ Created exercise with ID: {created_exercise.id}")
        
        exercise = db.get_exercise(created_exercise.id)
        print(f"✓ Retrieved exercise: {exercise.name} with parameters: {exercise.parameter_summary}")
        
        # Test parameter updates
        exercise.has_duration_s = True
        updated = db.update_exercise(exercise)
        print(f"✓ Updated exercise parameters: {updated}")
        
        exercises = db.search_exercises("Test")
        print(f"✓ Found {len(exercises)} exercises matching 'Test'")
        
        # Test parameter-based searches
        weight_exercises = db.get_exercises_with_parameter("has_weight_kg")
        print(f"✓ Found {len(weight_exercises)} exercises with weight parameter")
        
        rep_exercises = db.search_exercises_by_parameters({"has_reps": True})
        print(f"✓ Found {len(rep_exercises)} exercises requiring reps")
        
        # Test admin operations
        print("\n4. Testing Admin operations...")
        test_admin = Admin(name="Test", surname="Admin", email="testadmin@fitcoach.com")
        created_admin = db.create_admin(test_admin)
        print(f"✓ Created admin with ID: {created_admin.id}")
        
        admin = db.get_admin(created_admin.id)
        print(f"✓ Retrieved admin: {admin.name} {admin.surname}")
        
        admin_by_email = db.get_admin_by_email("testadmin@fitcoach.com")
        print(f"✓ Found admin by email: {admin_by_email.name}")
        
        # Test counts
        print("\n5. Testing count operations...")
        user_count = db.get_user_count()
        exercise_count = db.get_exercise_count()
        admin_count = db.get_admin_count()
        print(f"✓ Users: {user_count}, Exercises: {exercise_count}, Admins: {admin_count}")
        
        # Test getting all records
        print("\n6. Testing get all operations...")
        all_users = db.get_all_users()
        all_exercises = db.get_all_exercises()
        all_admins = db.get_all_admins()
        print(f"✓ Retrieved {len(all_users)} users, {len(all_exercises)} exercises, {len(all_admins)} admins")
        
        # Test workout operations
        print("\n7. Testing Workout operations...")
        test_workout = Workout(
            user_id=created_user.id,
            name="Test Workout",
            description="A test workout",
            workout_date=datetime.now(),
            duration_minutes=30,
            completed=False
        )
        created_workout = db.create_workout(test_workout)
        print(f"✓ Created workout with ID: {created_workout.id}")
        
        workout = db.get_workout(created_workout.id)
        print(f"✓ Retrieved workout: {workout.name}")
        
        user_workouts = db.get_workouts_by_user(created_user.id)
        print(f"✓ Found {len(user_workouts)} workouts for user")
        
        # Test exercise set operations
        print("\n8. Testing Exercise Set operations...")
        test_exercise_set = ExerciseSet(
            workout_id=created_workout.id,
            exercise_id=created_exercise.id,
            set_order=1,
            reps=10,
            weight_kg=50.0,
            completed=False
        )
        created_set = db.create_exercise_set(test_exercise_set)
        print(f"✓ Created exercise set with ID: {created_set.id}")
        
        workout_sets = db.get_exercise_sets_by_workout(created_workout.id)
        print(f"✓ Found {len(workout_sets)} exercise sets in workout")
        
        # Test workout progress
        progress = db.get_workout_progress(created_workout.id)
        print(f"✓ Workout progress: {progress['completed_sets']}/{progress['total_sets']} ({progress['completion_percentage']}%)")
        
        # Test user workout stats
        stats = db.get_user_workout_stats(created_user.id)
        print(f"✓ User workout stats: {stats['completed_workouts']}/{stats['total_workouts']} workouts completed")
        
        print("\n=== All tests completed successfully! ===")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        logger.error(f"Database test error: {e}")

def reset_database():
    """Drop and recreate all tables"""
    try:
        db = DatabaseManager()
        
        print("Dropping all tables...")
        db.drop_tables()
        print("✓ Tables dropped successfully")
        
        print("Creating tables...")
        db.create_tables()
        print("✓ Tables created successfully")
        
        print("Database reset complete!")
        
    except Exception as e:
        print(f"❌ Database reset failed: {e}")
        logger.error(f"Database reset error: {e}")

def setup_database_with_sample_data():
    """Initialize database and add sample data"""
    try:
        print("Setting up database with sample data...")
        
        # Initialize tables
        init_database()
        print("✓ Database initialized")
        
        # Add sample data
        seed_sample_data()
        print("✓ Sample data added")
        
        print("Database setup complete!")
        
    except Exception as e:
        print(f"❌ Database setup failed: {e}")
        logger.error(f"Database setup error: {e}")

def test_workout_functionality():
    """Test workout and exercise set functionality specifically"""
    try:
        db = DatabaseManager()
        
        print("=== Testing Workout Functionality ===")
        
        # Ensure tables exist
        print("\n1. Ensuring tables exist...")
        init_database()
        print("✓ Tables ready")
        
        # Get or create test data
        print("\n2. Setting up test data...")
        users = db.get_all_users()
        exercises = db.get_all_exercises()
        
        if not users:
            print("No users found. Creating test user...")
            test_user = User(name="Test", surname="User", email="test@example.com", age=25, weight_kg=70.0)
            test_user = db.create_user(test_user, password="test123")
        else:
            test_user = users[0]
            print(f"Using existing user: {test_user.full_name}")
        
        if not exercises:
            print("No exercises found. Creating test exercises...")
            exercise1 = Exercise(name="Push-ups", description="Upper body exercise", has_reps=True)
            exercise2 = Exercise(name="Squats", description="Lower body exercise", has_reps=True, has_weight_kg=True)
            db.create_exercise(exercise1)
            db.create_exercise(exercise2)
            exercises = db.get_all_exercises()
        
        print(f"✓ Using user ID {test_user.id} with {len(exercises)} available exercises")
        
        # Test workout creation
        print("\n3. Testing workout creation...")
        workout = Workout(
            user_id=test_user.id,
            name="Test Workout Session",
            description="Testing workout creation and management",
            workout_date=datetime.now(),
            duration_minutes=45,
            completed=False
        )
        created_workout = db.create_workout(workout)
        print(f"✓ Created workout: {created_workout.name} (ID: {created_workout.id})")
        
        # Test exercise set creation
        print("\n4. Testing exercise set creation...")
        for i, exercise in enumerate(exercises[:2], 1):  # Use first 2 exercises
            exercise_set = ExerciseSet(
                workout_id=created_workout.id,
                exercise_id=exercise.id,
                set_order=i,
                reps=10 + i*2,
                weight_kg=50.0 if exercise.has_weight_kg else None,
                completed=False
            )
            created_set = db.create_exercise_set(exercise_set)
            print(f"✓ Added {exercise.name} as set {i} (ID: {created_set.id})")
        
        # Test retrieving workout data
        print("\n5. Testing data retrieval...")
        user_workouts = db.get_workouts_by_user(test_user.id)
        print(f"✓ User has {len(user_workouts)} workouts")
        
        workout_sets = db.get_exercise_sets_by_workout(created_workout.id)
        print(f"✓ Workout has {len(workout_sets)} exercise sets")
        
        # Test workout progress
        progress = db.get_workout_progress(created_workout.id)
        print(f"✓ Workout progress: {progress['completed_sets']}/{progress['total_sets']} sets completed")
        
        # Test API-compatible methods
        print("\n6. Testing API-compatible methods...")
        api_users = db.get_all_users()
        api_workouts = db.get_workouts_by_user(test_user.id)
        api_sets = db.get_exercise_sets_by_workout(created_workout.id)
        api_exercises = db.get_all_exercises()
        
        print(f"✓ API methods return: {len(api_users)} users, {len(api_workouts)} workouts, {len(api_sets)} sets, {len(api_exercises)} exercises")
        
        print("\n=== Workout functionality test completed successfully! ===")
        
    except Exception as e:
        print(f"❌ Workout test failed: {e}")
        logger.error(f"Workout test error: {e}")

def interactive_menu():
    """Interactive menu for database operations"""
    while True:
        print("\n=== Database Test Menu ===")
        print("1. Test all database operations")
        print("2. Reset database (drop and recreate tables)")
        print("3. Setup database with sample data")
        print("4. Test workout functionality specifically")
        print("5. Drop all tables")
        print("6. Create tables only")
        print("7. Exit")
        
        choice = input("\nEnter your choice (1-7): ").strip()
        
        if choice == '1':
            test_database_operations()
        elif choice == '2':
            confirm = input("Are you sure you want to reset the database? (yes/no): ")
            if confirm.lower() == 'yes':
                reset_database()
        elif choice == '3':
            setup_database_with_sample_data()
        elif choice == '4':
            test_workout_functionality()
        elif choice == '5':
            confirm = input("Are you sure you want to drop all tables? (yes/no): ")
            if confirm.lower() == 'yes':
                try:
                    db = DatabaseManager()
                    db.drop_tables()
                    print("✓ All tables dropped")
                except Exception as e:
                    print(f"❌ Error dropping tables: {e}")
        elif choice == '6':
            try:
                init_database()
                print("✓ Tables created")
            except Exception as e:
                print(f"❌ Error creating tables: {e}")
        elif choice == '7':
            print("Goodbye!")
            break
        else:
            print("Invalid choice. Please enter 1-7.")

if __name__ == "__main__":
    interactive_menu()