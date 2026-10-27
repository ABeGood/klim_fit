import os
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
import logging
import bcrypt
from typing import Dict, List, Optional, Any
from datetime import date
from dotenv import load_dotenv
from models import PARAMS, Account, Exercise, WorkoutTemplate, Workout, Group, Set, Comment

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Templates and client workouts share the same group -> set structure in parallel tables.
# Table/column names below are fixed constants (never user input), so formatting them into SQL is safe;
# values always go through %s parameters.
KINDS = {
    'templates': {'owner': 'workout_templates', 'groups': 'template_groups', 'sets': 'template_sets',
                  'parent': 'template_id'},
    'workouts': {'owner': 'workouts', 'groups': 'workout_groups', 'sets': 'workout_sets',
                 'parent': 'workout_id'},
}

TARGET_COLUMNS = ['target_' + p for p in PARAMS]
ACTUAL_COLUMNS = ['actual_' + p for p in PARAMS]

# Columns an API caller may change, per object
TEMPLATE_FIELDS = ('name', 'description', 'duration_minutes', 'note', 'status')
WORKOUT_FIELDS = ('name', 'description', 'duration_minutes', 'note', 'scheduled_date')
GROUP_FIELDS = ('name', 'note')
SET_FIELDS = tuple(TARGET_COLUMNS) + ('rest_seconds', 'note')
RESULT_FIELDS = tuple(ACTUAL_COLUMNS)


class DatabaseManager:
    def __init__(self):
        self.database_url = os.getenv('DATABASE_URL')
        if not self.database_url:
            raise ValueError('DATABASE_URL not defined.')

        # Railway PostgreSQL often provides URLs starting with postgres://
        # but psycopg2 requires postgresql://
        if self.database_url.startswith('postgres://'):
            self.database_url = self.database_url.replace('postgres://', 'postgresql://', 1)

    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = None
        try:
            conn = psycopg2.connect(self.database_url)
            yield conn
        except psycopg2.Error as e:
            logger.error(f"Database connection error: {e}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                conn.close()

    # ---------- Query helpers (one connection + commit per call) ----------
    def _fetchone(self, sql: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(sql, params)
                    row = cursor.fetchone()
                    conn.commit()
                    return dict(row) if row else None
        except Exception as e:
            logger.error(f"Query failed: {e}")
            raise

    def _fetchall(self, sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(sql, params)
                    rows = cursor.fetchall()
                    conn.commit()
                    return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Query failed: {e}")
            raise

    def _execute(self, sql: str, params: tuple = ()) -> int:
        """Run a write; returns affected row count"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(sql, params)
                    conn.commit()
                    return cursor.rowcount
        except Exception as e:
            logger.error(f"Query failed: {e}")
            raise

    def _count(self, sql: str, params: tuple = ()) -> int:
        return self._fetchone(sql, params)['count']

    @staticmethod
    def _update_sql(table: str, changes: Dict[str, Any], allowed: tuple):
        """Build 'UPDATE table SET a = %s, b = %s WHERE id = %s' for the allowed keys present in changes"""
        cols = [c for c in allowed if c in changes]
        if not cols:
            return None, ()
        assignments = ', '.join(f"{c} = %s" for c in cols)
        return f"UPDATE {table} SET {assignments} WHERE id = %s", tuple(changes[c] for c in cols)

    # ---------- Passwords ----------
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using bcrypt"""
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')

    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        """Verify a password against its hash"""
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

    # ---------- Schema ----------
    TABLES = ['accounts', 'exercises', 'workout_templates', 'template_groups', 'template_sets',
              'workouts', 'workout_groups', 'workout_sets', 'comments']

    def create_tables(self):
        """Create all required tables (the canonical schema)"""
        param_columns = """
            target_reps INTEGER CHECK (target_reps > 0),
            target_weight_kg DECIMAL(6,2) CHECK (target_weight_kg > 0),
            target_duration_s INTEGER CHECK (target_duration_s > 0),
            target_distance_m DECIMAL(10,2) CHECK (target_distance_m > 0),
            rest_seconds INTEGER CHECK (rest_seconds >= 0),
            note TEXT,"""

        create_tables_sql = f"""
        CREATE TABLE IF NOT EXISTS accounts (
            id SERIAL PRIMARY KEY,
            role TEXT NOT NULL CHECK (role IN ('admin', 'client')),
            name VARCHAR(100) NOT NULL,
            surname VARCHAR(100) NOT NULL,
            email VARCHAR(255) NOT NULL,
            password_hash VARCHAR(255),
            google_id VARCHAR(255) UNIQUE,
            profile_picture TEXT,
            age INTEGER CHECK (age > 0 AND age < 150),
            weight_kg DECIMAL(5,2) CHECK (weight_kg > 0),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_accounts_email ON accounts (lower(email));

        CREATE TABLE IF NOT EXISTS exercises (
            id SERIAL PRIMARY KEY,
            name VARCHAR(200) NOT NULL UNIQUE,
            description TEXT,
            has_reps BOOLEAN NOT NULL DEFAULT FALSE,
            has_weight_kg BOOLEAN NOT NULL DEFAULT FALSE,
            has_duration_s BOOLEAN NOT NULL DEFAULT FALSE,
            has_distance_m BOOLEAN NOT NULL DEFAULT FALSE,
            archived_at TIMESTAMP,
            created_by INTEGER REFERENCES accounts(id) ON DELETE SET NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CHECK (has_reps OR has_weight_kg OR has_duration_s OR has_distance_m)
        );

        -- Template side: the coach's reusable plans
        CREATE TABLE IF NOT EXISTS workout_templates (
            id SERIAL PRIMARY KEY,
            created_by INTEGER REFERENCES accounts(id) ON DELETE SET NULL,
            name VARCHAR(200) NOT NULL,
            description TEXT,
            duration_minutes INTEGER CHECK (duration_minutes > 0),
            note TEXT,
            status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'ready')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS template_groups (
            id SERIAL PRIMARY KEY,
            template_id INTEGER NOT NULL REFERENCES workout_templates(id) ON DELETE CASCADE,
            position INTEGER NOT NULL CHECK (position > 0),
            name VARCHAR(200),
            note TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (template_id, position) DEFERRABLE INITIALLY DEFERRED
        );

        CREATE TABLE IF NOT EXISTS template_sets (
            id SERIAL PRIMARY KEY,
            group_id INTEGER NOT NULL REFERENCES template_groups(id) ON DELETE CASCADE,
            position INTEGER NOT NULL CHECK (position > 0),
            exercise_id INTEGER NOT NULL REFERENCES exercises(id) ON DELETE RESTRICT,
            {param_columns}
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (group_id, position) DEFERRABLE INITIALLY DEFERRED
        );

        -- Client side: copies of templates, owned by one client
        CREATE TABLE IF NOT EXISTS workouts (
            id SERIAL PRIMARY KEY,
            client_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
            template_id INTEGER REFERENCES workout_templates(id) ON DELETE SET NULL,
            assigned_by INTEGER REFERENCES accounts(id) ON DELETE SET NULL,
            name VARCHAR(200) NOT NULL,
            description TEXT,
            duration_minutes INTEGER CHECK (duration_minutes > 0),
            note TEXT,
            scheduled_date DATE,
            completed_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS workout_groups (
            id SERIAL PRIMARY KEY,
            workout_id INTEGER NOT NULL REFERENCES workouts(id) ON DELETE CASCADE,
            position INTEGER NOT NULL CHECK (position > 0),
            name VARCHAR(200),
            note TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (workout_id, position) DEFERRABLE INITIALLY DEFERRED
        );

        CREATE TABLE IF NOT EXISTS workout_sets (
            id SERIAL PRIMARY KEY,
            group_id INTEGER NOT NULL REFERENCES workout_groups(id) ON DELETE CASCADE,
            position INTEGER NOT NULL CHECK (position > 0),
            exercise_id INTEGER NOT NULL REFERENCES exercises(id) ON DELETE RESTRICT,
            {param_columns}
            actual_reps INTEGER CHECK (actual_reps > 0),
            actual_weight_kg DECIMAL(6,2) CHECK (actual_weight_kg > 0),
            actual_duration_s INTEGER CHECK (actual_duration_s > 0),
            actual_distance_m DECIMAL(10,2) CHECK (actual_distance_m > 0),
            completed_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (group_id, position) DEFERRABLE INITIALLY DEFERRED
        );

        -- Coach <-> client chat, attached to exactly one workout, group or set
        CREATE TABLE IF NOT EXISTS comments (
            id SERIAL PRIMARY KEY,
            author_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
            workout_id INTEGER REFERENCES workouts(id) ON DELETE CASCADE,
            group_id INTEGER REFERENCES workout_groups(id) ON DELETE CASCADE,
            set_id INTEGER REFERENCES workout_sets(id) ON DELETE CASCADE,
            body TEXT NOT NULL CHECK (length(trim(body)) > 0),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            edited_at TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CHECK (num_nonnulls(workout_id, group_id, set_id) = 1)
        );

        CREATE INDEX IF NOT EXISTS idx_workout_templates_status ON workout_templates(status);
        CREATE INDEX IF NOT EXISTS idx_template_sets_exercise_id ON template_sets(exercise_id);
        CREATE INDEX IF NOT EXISTS idx_workouts_client_id ON workouts(client_id);
        CREATE INDEX IF NOT EXISTS idx_workouts_template_id ON workouts(template_id);
        CREATE INDEX IF NOT EXISTS idx_workout_sets_exercise_id ON workout_sets(exercise_id);
        CREATE INDEX IF NOT EXISTS idx_comments_workout_id ON comments(workout_id);
        CREATE INDEX IF NOT EXISTS idx_comments_group_id ON comments(group_id);
        CREATE INDEX IF NOT EXISTS idx_comments_set_id ON comments(set_id);

        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$ language 'plpgsql';
        """

        for table in self.TABLES:
            create_tables_sql += f"""
        DROP TRIGGER IF EXISTS update_{table}_updated_at ON {table};
        CREATE TRIGGER update_{table}_updated_at
            BEFORE UPDATE ON {table}
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
        """

        self._execute(create_tables_sql)
        logger.info("Tables created successfully")

    def drop_tables(self):
        """Drop all tables, including the pre-v2 ones (use with caution)"""
        legacy = ['exercise_sets', 'workout_sets', 'workouts', 'users', 'admins']
        tables = list(dict.fromkeys(list(reversed(self.TABLES)) + legacy))
        drop_sql = ''.join(f"DROP TABLE IF EXISTS {t} CASCADE;\n" for t in tables)
        drop_sql += "DROP FUNCTION IF EXISTS update_updated_at_column() CASCADE;"
        self._execute(drop_sql)
        logger.info("Tables dropped successfully")

    # ---------- Accounts ----------
    def create_account(self, account: Account, password: Optional[str] = None) -> Account:
        """Create an account; password is optional (Google-only accounts have none)"""
        account.password_hash = self.hash_password(password) if password else None
        row = self._fetchone("""
            INSERT INTO accounts (role, name, surname, email, password_hash, google_id, profile_picture, age, weight_kg)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, created_at, updated_at;
            """, (account.role, account.name, account.surname, account.email, account.password_hash,
                  account.google_id, account.profile_picture, account.age, account.weight_kg))
        account.id, account.created_at, account.updated_at = row['id'], row['created_at'], row['updated_at']
        logger.info(f"Account created with ID: {account.id} ({account.role})")
        return account

    def get_account(self, account_id: int) -> Optional[Account]:
        row = self._fetchone("SELECT * FROM accounts WHERE id = %s;", (account_id,))
        return Account.from_dict(row) if row else None

    def get_account_by_email(self, email: str) -> Optional[Account]:
        row = self._fetchone("SELECT * FROM accounts WHERE lower(email) = lower(%s);", (email.strip(),))
        return Account.from_dict(row) if row else None

    def get_account_by_google_id(self, google_id: str) -> Optional[Account]:
        row = self._fetchone("SELECT * FROM accounts WHERE google_id = %s;", (google_id,))
        return Account.from_dict(row) if row else None

    def get_clients(self) -> List[Account]:
        rows = self._fetchall("SELECT * FROM accounts WHERE role = 'client' ORDER BY surname, name;")
        return [Account.from_dict(row) for row in rows]

    def get_recent_clients(self, limit: int = 5) -> List[Account]:
        rows = self._fetchall("SELECT * FROM accounts WHERE role = 'client' ORDER BY created_at DESC LIMIT %s;",
                              (limit,))
        return [Account.from_dict(row) for row in rows]

    def count_clients(self) -> int:
        return self._count("SELECT COUNT(*) FROM accounts WHERE role = 'client';")

    def get_clients_overview(self) -> List[Dict[str, Any]]:
        """Every client with their current workout (the earliest-scheduled unfinished one), progress and
        last activity (latest completed set or message they wrote) -- the coach's clients table"""
        clients = self.get_clients()
        workouts = [self._workout_list_row(row) for row in self._fetchall(self.WORKOUT_LIST_SQL + """
            WHERE w.completed_at IS NULL
            ORDER BY w.scheduled_date ASC NULLS LAST, w.created_at ASC;
            """)]
        activity = {row['id']: row for row in self._fetchall("""
            SELECT a.id,
                   (SELECT MAX(s.completed_at) FROM workout_sets s
                      JOIN workout_groups g ON g.id = s.group_id JOIN workouts w ON w.id = g.workout_id
                     WHERE w.client_id = a.id) AS last_set_at,
                   (SELECT MAX(c.created_at) FROM comments c WHERE c.author_id = a.id) AS last_message_at
            FROM accounts a WHERE a.role = 'client';
            """)}
        result = []
        for client in clients:
            current = next((w for w in workouts if w['client_id'] == client.id), None)
            act = activity.get(client.id, {})
            result.append(dict(client.to_public_dict(), current_workout=current,
                               last_set_at=act.get('last_set_at'), last_message_at=act.get('last_message_at')))
        return result

    def get_attention_items(self) -> Dict[str, List[Dict[str, Any]]]:
        """What the coach should look at: chat threads whose latest message is from the client (unanswered),
        unfinished workouts scheduled before today, and clients with no unfinished workout"""
        unanswered = self._fetchall("""
            WITH c2 AS (
                SELECT c.*, COALESCE(c.workout_id, g.workout_id, sg.workout_id) AS wid
                FROM comments c
                LEFT JOIN workout_groups g ON g.id = c.group_id
                LEFT JOIN workout_sets s ON s.id = c.set_id
                LEFT JOIN workout_groups sg ON sg.id = s.group_id
            ), latest AS (
                SELECT DISTINCT ON (wid, workout_id, group_id, set_id) *
                FROM c2 ORDER BY wid, workout_id, group_id, set_id, created_at DESC, id DESC
            )
            SELECT l.id, l.wid AS workout_id, l.group_id, l.set_id, l.body, l.created_at,
                   a.name || ' ' || a.surname AS client_name, w.name AS workout_name,
                   COALESCE(g.name, 'Group ' || g.position) AS group_label,
                   e.name AS exercise_name, s.position AS set_position
            FROM latest l
            JOIN accounts a ON a.id = l.author_id AND a.role = 'client'
            JOIN workouts w ON w.id = l.wid
            LEFT JOIN workout_groups g ON g.id = l.group_id
            LEFT JOIN workout_sets s ON s.id = l.set_id
            LEFT JOIN exercises e ON e.id = s.exercise_id
            ORDER BY l.created_at DESC;
            """)
        for item in unanswered:
            item['context'] = (f"{item['exercise_name']} · set {item['set_position']}" if item['set_id']
                               else item['group_label'] if item['group_id'] else 'the workout')
        overdue = [self._workout_list_row(row) for row in self._fetchall(self.WORKOUT_LIST_SQL + """
            WHERE w.completed_at IS NULL AND w.scheduled_date < CURRENT_DATE
            ORDER BY w.scheduled_date;
            """)]
        no_plan = [Account.from_dict(row).to_public_dict() for row in self._fetchall("""
            SELECT * FROM accounts a WHERE a.role = 'client'
              AND NOT EXISTS (SELECT 1 FROM workouts w WHERE w.client_id = a.id AND w.completed_at IS NULL)
            ORDER BY a.surname, a.name;
            """)]
        return {'unanswered': unanswered, 'overdue': overdue, 'no_plan': no_plan}

    def update_account_google_info(self, account_id: int, google_id: str, profile_picture: str = None) -> bool:
        return self._execute("UPDATE accounts SET google_id = %s, profile_picture = %s WHERE id = %s;",
                             (google_id, profile_picture, account_id)) > 0

    def authenticate(self, email: str, password: str) -> Optional[Account]:
        """Return the account if the email/password pair is valid"""
        account = self.get_account_by_email(email)
        if account and account.password_hash and self.verify_password(password, account.password_hash):
            return account
        return None

    def change_password(self, account_id: int, new_password: str) -> bool:
        return self._execute("UPDATE accounts SET password_hash = %s WHERE id = %s;",
                             (self.hash_password(new_password), account_id)) > 0

    # ---------- Exercises (library) ----------
    def create_exercise(self, exercise: Exercise) -> Exercise:
        row = self._fetchone("""
            INSERT INTO exercises (name, description, has_reps, has_weight_kg, has_duration_s, has_distance_m, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id, created_at, updated_at;
            """, (exercise.name, exercise.description, exercise.has_reps, exercise.has_weight_kg,
                  exercise.has_duration_s, exercise.has_distance_m, exercise.created_by))
        exercise.id, exercise.created_at, exercise.updated_at = row['id'], row['created_at'], row['updated_at']
        logger.info(f"Exercise created with ID: {exercise.id}")
        return exercise

    def get_exercise(self, exercise_id: int) -> Optional[Exercise]:
        row = self._fetchone("SELECT * FROM exercises WHERE id = %s;", (exercise_id,))
        return Exercise.from_dict(row) if row else None

    def get_exercises(self, include_archived: bool = False) -> List[Exercise]:
        """Library exercises; archived ones are hidden unless asked for"""
        where = "" if include_archived else "WHERE archived_at IS NULL"
        rows = self._fetchall(f"SELECT * FROM exercises {where} ORDER BY name;")
        return [Exercise.from_dict(row) for row in rows]

    def get_exercises_with_usage(self) -> List[Dict[str, Any]]:
        """All exercises incl. archived, with how many template/workout sets use each (library page)"""
        rows = self._fetchall("""
            SELECT e.*,
                   (SELECT COUNT(*) FROM template_sets t WHERE t.exercise_id = e.id)
                 + (SELECT COUNT(*) FROM workout_sets w WHERE w.exercise_id = e.id) AS usage_count
            FROM exercises e ORDER BY e.archived_at IS NOT NULL, e.name;
            """)
        return [dict(Exercise.from_dict(row).to_dict(), usage_count=row['usage_count']) for row in rows]

    def restore_exercise(self, exercise_id: int) -> bool:
        """Bring an archived exercise back into the library"""
        return self._execute("UPDATE exercises SET archived_at = NULL WHERE id = %s;", (exercise_id,)) > 0

    def count_exercises(self) -> int:
        return self._count("SELECT COUNT(*) FROM exercises WHERE archived_at IS NULL;")

    def archive_exercise(self, exercise_id: int) -> bool:
        """Hide an exercise from the library; sets that use it keep it"""
        return self._execute("UPDATE exercises SET archived_at = CURRENT_TIMESTAMP WHERE id = %s;",
                             (exercise_id,)) > 0

    def get_exercise_usage(self, exercise_id: int) -> int:
        """How many template + workout sets use an exercise (0 = safe to delete)"""
        return self._count("""
            SELECT (SELECT COUNT(*) FROM template_sets WHERE exercise_id = %s)
                 + (SELECT COUNT(*) FROM workout_sets WHERE exercise_id = %s) AS count;
            """, (exercise_id, exercise_id))

    def delete_exercise(self, exercise_id: int) -> bool:
        """Delete an exercise; raises (RESTRICT) if any template or workout set uses it -- archive instead"""
        return self._execute("DELETE FROM exercises WHERE id = %s;", (exercise_id,)) > 0

    # ---------- Templates ----------
    def create_template(self, template: WorkoutTemplate) -> WorkoutTemplate:
        row = self._fetchone("""
            INSERT INTO workout_templates (created_by, name, description, duration_minutes, note, status)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING *;
            """, (template.created_by, template.name, template.description, template.duration_minutes,
                  template.note, template.status))
        logger.info(f"Template created with ID: {row['id']}")
        return WorkoutTemplate.from_dict(row)

    def get_template(self, template_id: int) -> Optional[WorkoutTemplate]:
        row = self._fetchone("SELECT * FROM workout_templates WHERE id = %s;", (template_id,))
        return WorkoutTemplate.from_dict(row) if row else None

    def get_templates(self) -> List[Dict[str, Any]]:
        """All templates, newest first, with group/set counts and how often each was assigned"""
        rows = self._fetchall("""
            SELECT t.*,
                   (SELECT COUNT(*) FROM template_groups g WHERE g.template_id = t.id) AS group_count,
                   (SELECT COUNT(*) FROM template_sets s JOIN template_groups g ON g.id = s.group_id
                     WHERE g.template_id = t.id) AS set_count,
                   (SELECT COUNT(*) FROM workouts w WHERE w.template_id = t.id) AS assigned_count
            FROM workout_templates t
            ORDER BY t.updated_at DESC;
            """)
        return [dict(WorkoutTemplate.from_dict(row).to_dict(), group_count=row['group_count'],
                     set_count=row['set_count'], assigned_count=row['assigned_count']) for row in rows]

    def count_templates(self) -> int:
        return self._count("SELECT COUNT(*) FROM workout_templates;")

    def update_template(self, template_id: int, changes: Dict[str, Any]) -> Optional[WorkoutTemplate]:
        sql, params = self._update_sql('workout_templates', changes, TEMPLATE_FIELDS)
        if sql:
            self._execute(sql, params + (template_id,))
        return self.get_template(template_id)

    def delete_template(self, template_id: int) -> bool:
        """Delete a template (cascades to its groups/sets); assigned workouts keep existing"""
        return self._execute("DELETE FROM workout_templates WHERE id = %s;", (template_id,)) > 0

    # ---------- Workouts (client side) ----------
    def get_workout(self, workout_id: int) -> Optional[Workout]:
        row = self._fetchone("SELECT * FROM workouts WHERE id = %s;", (workout_id,))
        return Workout.from_dict(row) if row else None

    WORKOUT_LIST_SQL = """
        SELECT w.*, a.name || ' ' || a.surname AS client_name,
               (SELECT COUNT(*) FROM workout_sets s JOIN workout_groups g ON g.id = s.group_id
                 WHERE g.workout_id = w.id) AS set_count,
               (SELECT COUNT(*) FROM workout_sets s JOIN workout_groups g ON g.id = s.group_id
                 WHERE g.workout_id = w.id AND s.completed_at IS NOT NULL) AS completed_set_count,
               (SELECT COUNT(*) FROM workout_groups g WHERE g.workout_id = w.id) AS group_count,
               (SELECT c.body FROM comments c
                  JOIN accounts ca ON ca.id = c.author_id AND ca.role = 'admin'
                  LEFT JOIN workout_groups cg ON cg.id = c.group_id
                  LEFT JOIN workout_sets cs ON cs.id = c.set_id
                  LEFT JOIN workout_groups csg ON csg.id = cs.group_id
                 WHERE COALESCE(c.workout_id, cg.workout_id, csg.workout_id) = w.id
                 ORDER BY c.created_at DESC LIMIT 1) AS last_coach_message
        FROM workouts w JOIN accounts a ON a.id = w.client_id
        """

    @staticmethod
    def _workout_list_row(row: Dict[str, Any]) -> Dict[str, Any]:
        workout = Workout.from_dict(row)
        return dict(workout.to_dict(), completed=workout.completed, client_name=row['client_name'],
                    set_count=row['set_count'], completed_set_count=row['completed_set_count'],
                    group_count=row['group_count'], last_coach_message=row['last_coach_message'])

    def get_client_workouts(self, client_id: int) -> List[Dict[str, Any]]:
        """A client's workouts with progress counts: undated first, then by date (newest first)"""
        rows = self._fetchall(self.WORKOUT_LIST_SQL + """
            WHERE w.client_id = %s
            ORDER BY w.scheduled_date DESC NULLS FIRST, w.created_at DESC;
            """, (client_id,))
        return [self._workout_list_row(row) for row in rows]

    def get_recent_workouts(self, limit: int = 5) -> List[Dict[str, Any]]:
        rows = self._fetchall(self.WORKOUT_LIST_SQL + " ORDER BY w.created_at DESC LIMIT %s;", (limit,))
        return [self._workout_list_row(row) for row in rows]

    def count_workouts(self) -> int:
        return self._count("SELECT COUNT(*) FROM workouts;")

    def update_workout(self, workout_id: int, changes: Dict[str, Any]) -> Optional[Workout]:
        sql, params = self._update_sql('workouts', changes, WORKOUT_FIELDS)
        if sql:
            self._execute(sql, params + (workout_id,))
        return self.get_workout(workout_id)

    def delete_workout(self, workout_id: int) -> bool:
        return self._execute("DELETE FROM workouts WHERE id = %s;", (workout_id,)) > 0

    def assign_template(self, template_id: int, client_id: int, assigned_by: int,
                        scheduled_date: Optional[date] = None) -> int:
        """Deep-copy a template (groups + sets) into a new workout for a client; returns the workout id.
        Copies are snapshots: later template edits don't touch them."""
        set_cols = ', '.join(['exercise_id', 'position'] + TARGET_COLUMNS + ['rest_seconds', 'note'])
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO workouts (client_id, template_id, assigned_by, name, description,
                                              duration_minutes, note, scheduled_date)
                        SELECT %s, id, %s, name, description, duration_minutes, note, %s
                        FROM workout_templates WHERE id = %s
                        RETURNING id;
                        """, (client_id, assigned_by, scheduled_date, template_id))
                    row = cursor.fetchone()
                    if not row:
                        raise ValueError(f"Template {template_id} not found")
                    workout_id = row[0]

                    cursor.execute("SELECT id, position, name, note FROM template_groups WHERE template_id = %s "
                                   "ORDER BY position;", (template_id,))
                    for old_group_id, position, name, note in cursor.fetchall():
                        cursor.execute("""
                            INSERT INTO workout_groups (workout_id, position, name, note)
                            VALUES (%s, %s, %s, %s) RETURNING id;
                            """, (workout_id, position, name, note))
                        new_group_id = cursor.fetchone()[0]
                        cursor.execute(f"""
                            INSERT INTO workout_sets (group_id, {set_cols})
                            SELECT %s, {set_cols} FROM template_sets WHERE group_id = %s;
                            """, (new_group_id, old_group_id))
                    conn.commit()
                    logger.info(f"Template {template_id} assigned to client {client_id} as workout {workout_id}")
                    return workout_id
        except Exception as e:
            logger.error(f"Error assigning template: {e}")
            raise

    # ---------- Groups & sets (shared by templates and workouts via `kind`) ----------
    @staticmethod
    def _group_dict(row: Dict[str, Any], parent_col: str) -> Dict[str, Any]:
        group = Group.from_dict(dict(row, parent_id=row[parent_col]))
        return dict(group.to_dict(), sets=[])

    @staticmethod
    def _set_dict(row: Dict[str, Any]) -> Dict[str, Any]:
        """Set fields + the exercise info the UI needs to render it"""
        return dict(Set.from_dict(row).to_dict(),
                    exercise_name=row['exercise_name'],
                    exercise_description=row['exercise_description'],
                    **{'has_' + p: row['has_' + p] for p in PARAMS})

    def _set_select_sql(self, kind: str) -> str:
        t = KINDS[kind]
        return f"""
            SELECT s.*, e.name AS exercise_name, e.description AS exercise_description,
                   e.has_reps, e.has_weight_kg, e.has_duration_s, e.has_distance_m
            FROM {t['sets']} s
            JOIN exercises e ON e.id = s.exercise_id
            """

    def get_structure(self, kind: str, owner_id: int) -> List[Dict[str, Any]]:
        """Groups of a template/workout, ordered, each with its ordered `sets`"""
        t = KINDS[kind]
        groups = [self._group_dict(row, t['parent']) for row in self._fetchall(
            f"SELECT * FROM {t['groups']} WHERE {t['parent']} = %s ORDER BY position;", (owner_id,))]
        sets = self._fetchall(self._set_select_sql(kind) + f"""
            JOIN {t['groups']} g ON g.id = s.group_id
            WHERE g.{t['parent']} = %s
            ORDER BY s.group_id, s.position;
            """, (owner_id,))
        by_group = {g['id']: g for g in groups}
        for row in sets:
            by_group[row['group_id']]['sets'].append(self._set_dict(row))
        return groups

    def get_group(self, kind: str, group_id: int) -> Optional[Dict[str, Any]]:
        t = KINDS[kind]
        row = self._fetchone(f"SELECT * FROM {t['groups']} WHERE id = %s;", (group_id,))
        return self._group_dict(row, t['parent']) if row else None

    def get_set(self, kind: str, set_id: int) -> Optional[Dict[str, Any]]:
        row = self._fetchone(self._set_select_sql(kind) + " WHERE s.id = %s;", (set_id,))
        return self._set_dict(row) if row else None

    def get_owner_id(self, kind: str, group_id: Optional[int] = None, set_id: Optional[int] = None) -> Optional[int]:
        """The template/workout id a group or set belongs to (None if it doesn't exist)"""
        t = KINDS[kind]
        if set_id is not None:
            row = self._fetchone(f"""SELECT g.{t['parent']} AS owner_id FROM {t['sets']} s
                                     JOIN {t['groups']} g ON g.id = s.group_id WHERE s.id = %s;""", (set_id,))
        else:
            row = self._fetchone(f"SELECT {t['parent']} AS owner_id FROM {t['groups']} WHERE id = %s;", (group_id,))
        return row['owner_id'] if row else None

    def create_group(self, kind: str, owner_id: int) -> Dict[str, Any]:
        """Append an empty group at the end"""
        t = KINDS[kind]
        row = self._fetchone(f"""
            INSERT INTO {t['groups']} ({t['parent']}, position)
            VALUES (%s, COALESCE((SELECT MAX(position) FROM {t['groups']} WHERE {t['parent']} = %s), 0) + 1)
            RETURNING *;
            """, (owner_id, owner_id))
        return self._group_dict(row, t['parent'])

    def update_group(self, kind: str, group_id: int, changes: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        sql, params = self._update_sql(KINDS[kind]['groups'], changes, GROUP_FIELDS)
        if sql:
            self._execute(sql, params + (group_id,))
        return self.get_group(kind, group_id)

    def delete_group(self, kind: str, group_id: int) -> bool:
        return self._execute(f"DELETE FROM {KINDS[kind]['groups']} WHERE id = %s;", (group_id,)) > 0

    def add_set(self, kind: str, group_id: int, exercise_id: int) -> Optional[Dict[str, Any]]:
        """Append a set of an exercise to a group"""
        t = KINDS[kind]
        row = self._fetchone(f"""
            INSERT INTO {t['sets']} (group_id, exercise_id, position)
            SELECT g.id, %s, COALESCE((SELECT MAX(position) FROM {t['sets']} WHERE group_id = g.id), 0) + 1
            FROM {t['groups']} g WHERE g.id = %s
            RETURNING id;
            """, (exercise_id, group_id))
        return self.get_set(kind, row['id']) if row else None

    def update_set(self, kind: str, set_id: int, changes: Dict[str, Any],
                   allowed: tuple = SET_FIELDS) -> Optional[Dict[str, Any]]:
        sql, params = self._update_sql(KINDS[kind]['sets'], changes, allowed)
        if sql:
            self._execute(sql, params + (set_id,))
        return self.get_set(kind, set_id)

    def delete_set(self, kind: str, set_id: int) -> bool:
        return self._execute(f"DELETE FROM {KINDS[kind]['sets']} WHERE id = %s;", (set_id,)) > 0

    def duplicate_group(self, kind: str, group_id: int) -> Optional[Dict[str, Any]]:
        """Copy a group with its sets (targets, rest, notes -- never results) right after the original"""
        t = KINDS[kind]
        set_cols = ', '.join(['exercise_id', 'position'] + TARGET_COLUMNS + ['rest_seconds', 'note'])
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(f"SELECT * FROM {t['groups']} WHERE id = %s;", (group_id,))
                    orig = cursor.fetchone()
                    if not orig:
                        return None
                    owner_id = orig[t['parent']]
                    cursor.execute(f"UPDATE {t['groups']} SET position = position + 1 "
                                   f"WHERE {t['parent']} = %s AND position > %s;", (owner_id, orig['position']))
                    cursor.execute(f"""
                        INSERT INTO {t['groups']} ({t['parent']}, position, name, note)
                        VALUES (%s, %s, %s, %s) RETURNING id;
                        """, (owner_id, orig['position'] + 1, orig['name'], orig['note']))
                    new_id = cursor.fetchone()['id']
                    cursor.execute(f"""
                        INSERT INTO {t['sets']} (group_id, {set_cols})
                        SELECT %s, {set_cols} FROM {t['sets']} WHERE group_id = %s;
                        """, (new_id, group_id))
                    conn.commit()
        except Exception as e:
            logger.error(f"Error duplicating group: {e}")
            raise
        group = self.get_group(kind, new_id)
        group['sets'] = [s for g in self.get_structure(kind, owner_id) if g['id'] == new_id for s in g['sets']]
        return group

    def duplicate_set(self, kind: str, set_id: int) -> Optional[Dict[str, Any]]:
        """Copy a set (targets, rest, note -- never results) right after the original within its group"""
        t = KINDS[kind]
        copy_cols = ', '.join(['exercise_id'] + TARGET_COLUMNS + ['rest_seconds', 'note'])
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(f"SELECT group_id, position FROM {t['sets']} WHERE id = %s;", (set_id,))
                    orig = cursor.fetchone()
                    if not orig:
                        return None
                    cursor.execute(f"UPDATE {t['sets']} SET position = position + 1 "
                                   f"WHERE group_id = %s AND position > %s;", (orig['group_id'], orig['position']))
                    cursor.execute(f"""
                        INSERT INTO {t['sets']} (group_id, position, {copy_cols})
                        SELECT group_id, %s, {copy_cols} FROM {t['sets']} WHERE id = %s
                        RETURNING id;
                        """, (orig['position'] + 1, set_id))
                    new_id = cursor.fetchone()['id']
                    conn.commit()
        except Exception as e:
            logger.error(f"Error duplicating set: {e}")
            raise
        return self.get_set(kind, new_id)

    def _reorder(self, table: str, parent_col: str, parent_id: int, ordered_ids: List[int]):
        """Rewrite positions 1..n in the given order. ordered_ids must be exactly the parent's children;
        the deferred UNIQUE(parent, position) constraint lets positions swap within the transaction."""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(f"SELECT id FROM {table} WHERE {parent_col} = %s;", (parent_id,))
                    existing = {r[0] for r in cursor.fetchall()}
                    if existing != set(ordered_ids) or len(ordered_ids) != len(existing):
                        raise ValueError("Order must list every item exactly once")
                    cursor.execute(f"""
                        UPDATE {table} AS x SET position = t.ord
                        FROM unnest(%s::int[]) WITH ORDINALITY AS t(id, ord)
                        WHERE x.id = t.id;
                        """, (ordered_ids,))
                    conn.commit()
        except Exception as e:
            logger.error(f"Error reordering {table}: {e}")
            raise

    def reorder_groups(self, kind: str, owner_id: int, ordered_ids: List[int]):
        t = KINDS[kind]
        self._reorder(t['groups'], t['parent'], owner_id, ordered_ids)

    def reorder_sets(self, kind: str, group_id: int, ordered_ids: List[int]):
        self._reorder(KINDS[kind]['sets'], 'group_id', group_id, ordered_ids)

    def validate_structure(self, kind: str, owner_id: int) -> List[str]:
        """Problems that block marking a template ready / assigning it (empty list = OK)"""
        groups = self.get_structure(kind, owner_id)
        if not groups:
            return ['it has no groups']
        problems = []
        for gi, group in enumerate(groups, 1):
            if not group['sets']:
                problems.append(f'group {gi} is empty')
            for si, s in enumerate(group['sets'], 1):
                missing = [p for p in PARAMS if s['has_' + p] and s['target_' + p] is None]
                if missing:
                    problems.append(f"group {gi}, set {si} ({s['exercise_name']}): {', '.join(missing)} missing")
        return problems

    # ---------- Client results ----------
    def record_set_result(self, set_id: int, changes: Dict[str, Any], completed: Optional[bool]) -> Dict[str, Any]:
        """Save a client's actual values and/or tick/untick the set, then refresh the workout's completed_at
        (set when every set is done, cleared again if one is unticked)"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    sql, params = self._update_sql('workout_sets', changes, RESULT_FIELDS)
                    if sql:
                        cursor.execute(sql, params + (set_id,))
                    if completed is not None:
                        cursor.execute("""UPDATE workout_sets
                                          SET completed_at = CASE WHEN %s THEN COALESCE(completed_at, CURRENT_TIMESTAMP) END
                                          WHERE id = %s;""", (completed, set_id))
                    cursor.execute("""
                        UPDATE workouts w SET completed_at = CASE
                            WHEN NOT EXISTS (SELECT 1 FROM workout_sets s JOIN workout_groups g ON g.id = s.group_id
                                             WHERE g.workout_id = w.id AND s.completed_at IS NULL)
                             AND EXISTS (SELECT 1 FROM workout_groups g WHERE g.workout_id = w.id)
                            THEN COALESCE(w.completed_at, CURRENT_TIMESTAMP) END
                        WHERE w.id = (SELECT g.workout_id FROM workout_sets s JOIN workout_groups g ON g.id = s.group_id
                                      WHERE s.id = %s);
                        """, (set_id,))
                    conn.commit()
        except Exception as e:
            logger.error(f"Error recording set result: {e}")
            raise
        return self.get_set('workouts', set_id)

    # ---------- Comments (chat) ----------
    def add_comment(self, comment: Comment) -> Dict[str, Any]:
        row = self._fetchone("""
            INSERT INTO comments (author_id, workout_id, group_id, set_id, body)
            VALUES (%s, %s, %s, %s, %s) RETURNING id;
            """, (comment.author_id, comment.workout_id, comment.group_id, comment.set_id, comment.body.strip()))
        return self.get_comment(row['id'])

    COMMENT_SELECT_SQL = """
        SELECT c.*, a.name || ' ' || a.surname AS author_name, a.role AS author_role
        FROM comments c JOIN accounts a ON a.id = c.author_id
        """

    @staticmethod
    def _comment_dict(row: Dict[str, Any]) -> Dict[str, Any]:
        return dict(Comment.from_dict(row).to_dict(), author_name=row['author_name'], author_role=row['author_role'])

    def get_comment(self, comment_id: int) -> Optional[Dict[str, Any]]:
        row = self._fetchone(self.COMMENT_SELECT_SQL + " WHERE c.id = %s;", (comment_id,))
        return self._comment_dict(row) if row else None

    def get_workout_comments(self, workout_id: int) -> List[Dict[str, Any]]:
        """All chat in a workout -- on the workout itself, its groups and its sets -- oldest first"""
        rows = self._fetchall(self.COMMENT_SELECT_SQL + """
            WHERE c.workout_id = %s
               OR c.group_id IN (SELECT id FROM workout_groups WHERE workout_id = %s)
               OR c.set_id IN (SELECT s.id FROM workout_sets s JOIN workout_groups g ON g.id = s.group_id
                               WHERE g.workout_id = %s)
            ORDER BY c.created_at, c.id;
            """, (workout_id, workout_id, workout_id))
        return [self._comment_dict(row) for row in rows]


# Initialize database manager
db = DatabaseManager()

# Convenience functions for easy import
def init_database():
    """Initialize database tables"""
    db.create_tables()

def drop_all_tables():
    """Drop all tables (use with caution)"""
    db.drop_tables()
