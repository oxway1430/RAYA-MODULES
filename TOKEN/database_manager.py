import sqlite3

class RayaDB:
    def __init__(self, db_name="emergency_system.db"):
        self.db_name = db_name
        self._create_tables()
        self._seed_initial_users() 

    def _get_connection(self):
        return sqlite3.connect(self.db_name)

    def _create_tables(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS patients (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE,
                    age INTEGER,
                    sex TEXT,
                    mobile TEXT
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tokens (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT,
                    sub_token TEXT,
                    department TEXT,
                    patient_name TEXT
                )
            ''')
            conn.commit()

    def _seed_initial_users(self):
        """Pre-populates the database with the 4 specific users if they don't exist."""
        users = [
            ("Ayushman", 20, "Male", "9000000001"),
            ("Kamlesh", 21, "Male", "9000000002"),
            ("Devansh", 20, "Male", "9000000003"),
            ("Aditya", 22, "Male", "9000000004")
        ]
        with self._get_connection() as conn:
            cursor = conn.cursor()
            for name, age, sex, mobile in users:
                # INSERT OR IGNORE prevents errors if the names already exist
                cursor.execute('''
                    INSERT OR IGNORE INTO patients (name, age, sex, mobile) 
                    VALUES (?, ?, ?, ?)
                ''', (name, age, sex, mobile))
            conn.commit()

    def find_patient(self, name):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name, age, sex, mobile FROM patients WHERE LOWER(name) = ?", (name.lower(),))
            return cursor.fetchone()

    def add_patient(self, name, age, sex, mobile):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO patients (name, age, sex, mobile) VALUES (?, ?, ?, ?)", 
                           (name, age, sex, mobile))
            conn.commit()

    def get_counts(self, date, dept):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM tokens WHERE date = ?", (date,))
            total = cursor.fetchone()[0] + 1
            cursor.execute("SELECT COUNT(*) FROM tokens WHERE date = ? AND department = ?", (date, dept))
            dept_total = cursor.fetchone()[0] + 1
            return total, dept_total

    def save_token(self, date, sub_token, dept, name):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO tokens (date, sub_token, department, patient_name) VALUES (?, ?, ?, ?)",
                           (date, sub_token, dept, name))
            conn.commit()