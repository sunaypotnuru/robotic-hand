"""
LUNA Database Migration Tool - Add login_history table
File: migrate_db.py
"""
import sqlite3
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

def migrate():
    db_url = os.getenv('DATABASE_URL', 'sqlite:///instance/luna_robot.db')
    print("Inspecting Target Database for schema synchronization...")
    
    if db_url.startswith('sqlite:///'):
        db_path = db_url.replace('sqlite:///', '')
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)
            
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='login_history';")
        if not cursor.fetchone():
            print("SQLite: Table 'login_history' is missing. Deploying schema definition...")
            cursor.execute('''
                CREATE TABLE login_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    ip_address VARCHAR(45) NOT NULL,
                    user_agent VARCHAR(255) NOT NULL,
                    login_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    success BOOLEAN DEFAULT 1,
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                );
            ''')
            conn.commit()
            print("SQLite: Table 'login_history' successfully created!")
        else:
            print("SQLite: Table 'login_history' is already synchronized.")
        conn.close()
        
    elif db_url.startswith('postgresql://') or db_url.startswith('postgres://'):
        # Parse connection details or connect directly via psycopg2
        try:
            conn = psycopg2.connect(db_url)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'login_history'
                );
            """)
            exists = cursor.fetchone()[0]
            if not exists:
                print("Postgres: Table 'login_history' is missing. Deploying schema definition...")
                cursor.execute("""
                    CREATE TABLE login_history (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                        ip_address VARCHAR(45) NOT NULL,
                        user_agent VARCHAR(255) NOT NULL,
                        login_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        success BOOLEAN DEFAULT TRUE
                    );
                """)
                conn.commit()
                print("Postgres: Table 'login_history' successfully created!")
            else:
                print("Postgres: Table 'login_history' is already synchronized.")
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"Postgres Connection Error: {e}")

if __name__ == '__main__':
    migrate()
