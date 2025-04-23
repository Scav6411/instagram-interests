import os
import psycopg2
import argparse
from dotenv import load_dotenv
from tabulate import tabulate

def load_environment():
    """Load environment variables from .env file"""
    load_dotenv()
    return {
        'host': os.getenv('DB_HOST', 'localhost'),
        'database': os.getenv('DB_NAME'),
        'user': os.getenv('DB_USER'),
        'password': os.getenv('DB_PASSWORD'),
        'port': os.getenv('DB_PORT', '5432')
    }

def get_mutual_followers(username1, username2, db_config):
    """Find users who follow both specified users"""
    try:
        # Connect to the database
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()

        # Query to find mutual followers
        query = """
        SELECT m1.follower_username
        FROM mutual_follows m1
        JOIN mutual_follows m2 ON m1.follower_username = m2.follower_username
        WHERE m1.followee_username = %s AND m2.followee_username = %s
        ORDER BY m1.follower_username
        """
        
        cursor.execute(query, (username1, username2))
        mutual_followers = cursor.fetchall()
        
        # Close the database connection
        cursor.close()
        connection.close()
        
        return [follower[0] for follower in mutual_followers]
        
    except Exception as e:
        print(f"Database error: {e}")
        return []

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Find mutual followers between two Instagram users')
    parser.add_argument('username1', help='First Instagram username')
    parser.add_argument('username2', help='Second Instagram username')
    args = parser.parse_args()
    
    # Load database configuration
    db_config = load_environment()
    
    if not db_config['database'] or not db_config['user'] or not db_config['password']:
        print("Error: Missing database configuration. Please check your .env file.")
        return
    
    # Get mutual followers
    mutual_followers = get_mutual_followers(args.username1, args.username2, db_config)
    
    # Display results
    if mutual_followers:
        print(f"\nMutual followers of {args.username1} and {args.username2}:")
        print(f"Total: {len(mutual_followers)}")
        
        # Create a table with the results
        try:
            table_data = [[i+1, username] for i, username in enumerate(mutual_followers)]
            print(tabulate(table_data, headers=["#", "Username"], tablefmt="pretty"))
        except ImportError:
            # If tabulate is not installed, use simple format
            for i, username in enumerate(mutual_followers, 1):
                print(f"{i}. {username}")
    else:
        print(f"No mutual followers found between {args.username1} and {args.username2}")

if __name__ == "__main__":
    main()
