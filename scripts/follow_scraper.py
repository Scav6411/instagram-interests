import time
from random import randint
import os
import psycopg2
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import NoSuchElementException
from dotenv import load_dotenv, set_key
from instagram_login import InstagramLogin

def connect_to_database():
    try:
        conn = psycopg2.connect(
            "postgresql://neondb_owner:npg_I4TLQtYq5kmH@ep-misty-bird-a40lry3r-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require"
        )
        print("[Info] - Connected to database successfully")
        return conn
    except Exception as e:
        print(f"[Error] - Database connection failed: {e}")
        return None


def check_username_exists(conn, username):
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT pk, username FROM user_data WHERE username = %s", (username,))
        result = cursor.fetchone()
        cursor.close()
        return result
    except Exception as e:
        print(f"[Error] - Failed to check if username exists: {e}")
        return None


def get_existing_lists(conn, user_pk):
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT followers_list, following_list FROM user_detail WHERE pk = %s", (user_pk,))
        result = cursor.fetchone()
        cursor.close()
        return result
    except Exception as e:
        print(f"[Error] - Failed to get existing lists: {e}")
        return None, None


def update_user_lists(conn, user_pk, followers_list, following_list):
    try:
        cursor = conn.cursor()
        
        # Get existing lists
        existing_lists = get_existing_lists(conn, user_pk)
        
        if existing_lists:
            existing_followers, existing_following = existing_lists
            
            # Merge existing and new lists, keeping unique values
            if existing_followers:
                followers_list = list(set(existing_followers + followers_list))
            if existing_following:
                following_list = list(set(existing_following + following_list))
                
            print(f"[Info] - Updating existing user {user_pk} with merged lists")
            cursor.execute(
                "UPDATE user_detail SET followers_list = %s, following_list = %s WHERE pk = %s",
                (followers_list, following_list, user_pk)
            )
        else:
            print(f"[Info] - Inserting new lists for user {user_pk}")
            cursor.execute(
                "INSERT INTO user_detail (pk, followers_list, following_list) VALUES (%s, %s, %s)",
                (user_pk, followers_list, following_list)
            )
            
        conn.commit()
        cursor.close()
        print(f"[Info] - Successfully updated database for user {user_pk}")
        return True
    except Exception as e:
        conn.rollback()
        print(f"[Error] - Failed to update user lists: {e}")
        return False


def insert_new_user(conn, username):
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO user_data (username) VALUES (%s) RETURNING pk",
            (username,)
        )
        user_pk = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        print(f"[Info] - Created new user in database with pk {user_pk}")
        return user_pk
    except Exception as e:
        conn.rollback()
        print(f"[Error] - Failed to insert new user: {e}")
        return None


def scrape_following(bot, username, user_type='followers', count=None):
    bot.get(f'https://www.instagram.com/{username}/')
    time.sleep(3.5)
    WebDriverWait(bot, TIMEOUT).until(ec.presence_of_element_located(
        (By.XPATH, f"//a[contains(@href, '/{user_type}')]"))).click()
    time.sleep(randint(2, 8))

    scroll_box = bot.find_element(By.XPATH, '//div[@class="xyi19xy x1ccrb07 xtf3nb5 x1pc53ja x1lliihq x1iyjqo2 xs83m0k xz65tgg x1rife3k x1n2onr6"]')
    actions = ActionChains(bot)
    time.sleep(5)
    last_ht, ht = 0, 1
    
    users = set()
    
    while last_ht != ht:
        # Check if we've reached the requested count
        if count is not None and len(users) >= count:
            break
            
        last_ht = ht
        time.sleep(randint(5, 8))
        
        # Get current users before scrolling more
        following = bot.find_elements(By.XPATH, "//a[contains(@href, '/')]")
        
        for i in following:
            href = i.get_attribute('href')
            if href:
                parts = href.split("/")
                if len(parts) > 3 and parts[3]:
                    users.add(parts[3])
                    
        print(f"[Info] - Found {len(users)} {user_type} so far...")
                    
        # If we've reached the count, stop scrolling
        if count is not None and len(users) >= count:
            break
        
        ht = bot.execute_script("""
                arguments[0].scrollTo(0, arguments[0].scrollHeight);
                return arguments[0].scrollHeight; """, scroll_box)
        time.sleep(randint(2, 4))
        actions.move_to_element(scroll_box).perform()
        time.sleep(2)

    # One final collection after scrolling completes
    following = bot.find_elements(By.XPATH, "//a[contains(@href, '/')]")

    for i in following:
        href = i.get_attribute('href')
        if href:
            parts = href.split("/")
            if len(parts) > 3 and parts[3]:
                users.add(parts[3])
                
    users = list(users)
    
    # Truncate to the requested count if necessary
    if count is not None and len(users) > count:
        users = users[:count]

    print(f"[Info] - Collected {len(users)} {user_type} for {username}")
    print(f"[Info] - Saving {user_type} for {username}...")
    with open(f'{username}_{user_type}.txt', 'a') as file:
        file.write('\n'.join(users) + "\n")
    
    return list(users)


def get_pending_users(conn):
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, instagram_id FROM user_data WHERE scraping_status = 'pending' LIMIT 10"
        )
        pending_users = cursor.fetchall()
        cursor.close()
        return pending_users
    except Exception as e:
        print(f"[Error] - Failed to fetch pending users: {e}")
        return []


def update_scraping_status(conn, user_id, status):
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE user_data SET scraping_status = %s WHERE id = %s",
            (status, user_id)
        )
        conn.commit()
        cursor.close()
        print(f"[Info] - Updated user {user_id} scraping status to {status}")
        return True
    except Exception as e:
        conn.rollback()
        print(f"[Error] - Failed to update scraping status: {e}")
        return False


def update_user_data(conn, user_id, followers_list, following_list):
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE user_data SET followers_list = %s, following_list = %s, scraping_status = 'done' WHERE id = %s",
            (followers_list, following_list, user_id)
        )
        conn.commit()
        cursor.close()
        print(f"[Info] - Successfully updated data for user {user_id}")
        return True
    except Exception as e:
        conn.rollback()
        print(f"[Error] - Failed to update user data: {e}")
        update_scraping_status(conn, user_id, 'fail')
        return False


def scrape(use_proxy=False, proxy_info=None):
    # Initialize the InstagramLogin class
    instagram_login = InstagramLogin()
    
    # Get credentials using the InstagramLogin methods
    credentials = instagram_login.load_credentials()

    if credentials is None:
        username, password = instagram_login.prompt_credentials()
    else:
        username, password = credentials

    # Connect to the database
    conn = connect_to_database()
    if not conn:
        print("[Error] - Database connection is required. Exiting.")
        return

    # Fetch pending users from the database
    pending_users = get_pending_users(conn)
    
    if not pending_users:
        print("[Info] - No pending users found for scraping.")
        conn.close()
        return
    
    print(f"[Info] - Found {len(pending_users)} pending users to scrape.")

    # Setup browser options
    options = webdriver.ChromeOptions()
    # options.add_argument('--headless')
    # options.add_argument('--blink-settings=imagesEnabled=false') 
    # mobile_emulation = {
    #     "userAgent": "Mozilla/5.0 (Linux; Android 10; SM-G970F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.106 Mobile Safari/537.36"}
    # options.add_experimental_option("mobileEmulation", mobile_emulation)
    
    # Configure proxy if enabled
    if use_proxy and proxy_info:
        if isinstance(proxy_info, dict):
            options.add_argument(f"--proxy-server={proxy_info['host']}:{proxy_info['port']}")
            print(f"[Info] - Using proxy: {proxy_info['host']}:{proxy_info['port']}")
        elif isinstance(proxy_info, str):
            # For simple proxy string format like "123.45.67.89:8080"
            options.add_argument(f"--proxy-server={proxy_info}")
            print(f"[Info] - Using proxy: {proxy_info}")

    bot = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()))
    
    # Use the InstagramLogin class for login
    instagram_login.login(bot, username, password)

    # Set to None to scrape all followers and following
    followers_count = None
    following_count = None
    
    print("[Info] - Set to scrape all followers and following for each user")

    for user_id, instagram_id in pending_users:
        try:
            # Update status to in_progress
            update_scraping_status(conn, user_id, 'in_progress')
            
            print(f"[Info] - Starting to scrape user {instagram_id}")
            followers = scrape_following(bot, instagram_id, user_type='followers', count=followers_count)
            time.sleep(randint(2, 8))
            following = scrape_following(bot, instagram_id, user_type='following', count=following_count)
            
            # Update user data with scraped information
            success = update_user_data(conn, user_id, followers, following)
            
            if not success:
                print(f"[Warning] - Failed to update database for user {instagram_id}. Marked as failed.")
                
            time.sleep(randint(5, 10))  # Wait between users to avoid being rate-limited
        except Exception as e:
            print(f"[Error] - Failed to scrape user {instagram_id}: {e}")
            update_scraping_status(conn, user_id, 'failed')

    if conn:
        conn.close()
        print("[Info] - Database connection closed")
    
    bot.quit()


if __name__ == '__main__':
    TIMEOUT = 15
    use_proxy = input("Do you want to use a proxy? (yes/no): ").lower() == 'yes'
    
    proxy_info = None
    if use_proxy:
        proxy_type = input("Enter proxy type (api/direct): ").lower()
        
        if proxy_type == "api":
            host = input("Enter proxy host: ")
            port = input("Enter proxy port: ")
            proxy_info = {"host": host, "port": port}
        else:
            proxy_info = input("Enter proxy in format 'host:port': ")
    
    scrape(use_proxy=use_proxy, proxy_info=proxy_info)
