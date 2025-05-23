import psycopg2
from psycopg2 import OperationalError

def check_connection():
    connection_string = "postgresql://neondb_owner:npg_I4TLQtYq5kmH@ep-misty-bird-a40lry3r-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require"
    try:
        # Attempt to connect to the database
        connection = psycopg2.connect(connection_string)
        print("Connection successful!")
        connection.close()
    except OperationalError as e:
        print(f"Connection failed: {e}")

if __name__ == "__main__":
    check_connection()
