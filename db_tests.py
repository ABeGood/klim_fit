from database_manager import DatabaseManager, init_database
from models import User, Admin, Exercise
import logging

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

def interactive_menu():
    """Interactive menu for database operations"""
    while True:
        print("\n=== Database Test Menu ===")
        print("1. Test all database operations")
        print("2. Reset database (drop and recreate tables)")
        print("3. Setup database with sample data")
        print("4. Drop all tables")
        print("5. Create tables only")
        print("6. Exit")
        
        choice = input("\nEnter your choice (1-6): ").strip()
        
        if choice == '1':
            test_database_operations()
        elif choice == '2':
            confirm = input("Are you sure you want to reset the database? (yes/no): ")
            if confirm.lower() == 'yes':
                reset_database()
        elif choice == '3':
            setup_database_with_sample_data()
        elif choice == '4':
            confirm = input("Are you sure you want to drop all tables? (yes/no): ")
            if confirm.lower() == 'yes':
                try:
                    db = DatabaseManager()
                    db.drop_tables()
                    print("✓ All tables dropped")
                except Exception as e:
                    print(f"❌ Error dropping tables: {e}")
        elif choice == '5':
            try:
                init_database()
                print("✓ Tables created")
            except Exception as e:
                print(f"❌ Error creating tables: {e}")
        elif choice == '6':
            print("Goodbye!")
            break
        else:
            print("Invalid choice. Please enter 1-6.")

if __name__ == "__main__":
    interactive_menu()