import os
import mysql.connector
from dotenv import load_dotenv

def test_connection():
    load_dotenv()
    
    user = os.getenv('MYSQL_USER')
    password = os.getenv('MYSQL_PASSWORD')
    host = os.getenv('MYSQL_HOST', 'localhost')
    database = os.getenv('MYSQL_DATABASE', 'luna_db')

    print("🔍 LUNA Database Diagnostic")
    print(f"User: {user}")
    print(f"Host: {host}")
    print(f"Database: {database}")
    print(f"Password provided: {'YES' if password and password != 'your_password_here' else 'NO (or still using placeholder)'}")

    if password == 'your_password_here':
        print("\n❌ ERROR: You are still using the placeholder 'your_password_here' in .env")
        return

    try:
        conn = mysql.connector.connect(
            user=user,
            password=password,
            host=host,
            database=database
        )
        print("\n✅ SUCCESS: Connection established!")
        conn.close()
    except mysql.connector.Error as err:
        print(f"\n❌ FAILED: {err}")
        if err.errno == 1045:
            print("💡 TIP: Access Denied. Double-check your MySQL root password.")
        elif err.errno == 1049:
            print("💡 TIP: Database 'luna_db' not found. Run 'CREATE DATABASE luna_db;' in MySQL.")

if __name__ == "__main__":
    test_connection()
