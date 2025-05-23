import time
from random import randint
import os
import psycopg2
from selenium_driverless import webdriver
from selenium_driverless.types.by import By
from selenium_driverless.types.webelement import WebElement
from selenium_driverless.sync.webdriver import Chrome
import asyncio
from dotenv import load_dotenv, set_key
from instagram_login import InstagramLogin

def save_credentials(username, password):
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    set_key(env_path, 'INSTAGRAM_USERNAME', username)
    set_key(env_path, 'INSTAGRAM_PASSWORD', password)
    print("[Info] - Credentials saved to .env file")


def load_credentials():
    # Load variables from .env file
    load_dotenv()
    
    username = os.environ.get('INSTAGRAM_USERNAME')
    password = os.environ.get('INSTAGRAM_PASSWORD')
    
    if username and password:
        return username, password
    
    return None


def prompt_credentials():
    username = input("Enter your Instagram username: ")
    password = input("Enter your Instagram password: ")
    save_credentials(username, password)
    return username, password


async def wait_for_element(bot, by, selector, timeout=10):
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            element = await bot.find_element(by, selector)
            return element
        except Exception:
            await asyncio.sleep(0.5)
    raise TimeoutError(f"Element {selector} not found after {timeout} seconds")


def connect_to_database():
    connection_string = "postgresql://neondb_owner:npg_I4TLQtYq5kmH@ep-misty-bird-a40lry3r-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require"
    
    try:
        conn = psycopg2.connect(connection_string)
        print("[Info] - Connected to database successfully")
        return conn
    except Exception as e:
        print(f"[Error] - Database connection failed: {e}")
        return None


def check_username_exists(conn, username):
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, instagram_id FROM user_data WHERE instagram_id = %s", (username,))
        result = cursor.fetchone()
        cursor.close()
        return result
    except Exception as e:
        print(f"[Error] - Failed to check if username exists: {e}")
        return None


def get_existing_lists(conn, user_id):
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT followers_list, following_list FROM user_data WHERE id = %s", (user_id,))
        result = cursor.fetchone()
        cursor.close()
        return result
    except Exception as e:
        print(f"[Error] - Failed to get existing lists: {e}")
        return None, None


def update_user_lists(conn, user_id, followers_list, following_list):
    try:
        cursor = conn.cursor()
        
        # Get existing lists
        existing_lists = get_existing_lists(conn, user_id)
        
        if existing_lists:
            existing_followers, existing_following = existing_lists
            
            # Merge existing and new lists, keeping unique values
            if existing_followers:
                followers_list = list(set(existing_followers + followers_list))
            if existing_following:
                following_list = list(set(existing_following + following_list))
                
            print(f"[Info] - Updating existing user {user_id} with merged lists")
            cursor.execute(
                "UPDATE user_data SET followers_list = %s, following_list = %s WHERE id = %s",
                (followers_list, following_list, user_id)
            )
        else:
            print(f"[Info] - Inserting new lists for user {user_id}")
            cursor.execute(
                "UPDATE user_data SET followers_list = %s, following_list = %s WHERE id = %s",
                (followers_list, following_list, user_id)
            )
            
        conn.commit()
        cursor.close()
        print(f"[Info] - Successfully updated database for user {user_id}")
        return True
    except Exception as e:
        conn.rollback()
        print(f"[Error] - Failed to update user lists: {e}")
        return False


def insert_new_user(conn, username):
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO user_data (instagram_id) VALUES (%s) RETURNING id",
            (username,)
        )
        user_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        print(f"[Info] - Created new user in database with id {user_id}")
        return user_id
    except Exception as e:
        conn.rollback()
        print(f"[Error] - Failed to insert new user: {e}")
        return None


def fetch_pending_users(conn):
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, instagram_id FROM user_data WHERE scraping_status = 'pending'")
        users = cursor.fetchall()
        cursor.close()
        return users
    except Exception as e:
        print(f"[Error] - Failed to fetch pending users: {e}")
        return []


def update_scraping_status(conn, insta_id, status):
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE user_data SET scraping_status = %s WHERE instagram_id = %s", (status, insta_id))
        conn.commit()
        cursor.close()
        print(f"[Info] - Updated scraping status for user {insta_id} to {status}")
    except Exception as e:
        conn.rollback()
        print(f"[Error] - Failed to update scraping status for user {insta_id}: {e}")


async def scrape_following(bot, username, user_type='followers', count=None):
    await bot.get(f'https://www.instagram.com/{username}/')
    time.sleep(3.5)
    
    followers_link = await wait_for_element(bot, By.XPATH, f"//a[contains(@href, '/{user_type}')]", TIMEOUT)
    await followers_link.click()
    time.sleep(randint(2, 8))

    scroll_box = await bot.find_element(By.XPATH, '//div[@class="xyi19xy x1ccrb07 xtf3nb5 x1pc53ja x1lliihq x1iyjqo2 xs83m0k xz65tgg x1rife3k x1n2onr6"]')
    time.sleep(3)
    last_ht, ht = 0, 1
    
    users = set()
    
    while last_ht != ht:
        # Check if we've reached the requested count
        if count is not None and len(users) >= count:
            break
            
        last_ht = ht
        time.sleep(randint(5, 8))
        
        # Get current users before scrolling more
        following = await bot.find_elements(By.XPATH, "//a[contains(@href, '/')]")
        
        for i in following:
            href = await i.get_property('href')
            if href:
                parts = href.split("/")
                if len(parts) > 3 and parts[3]:
                    users.add(parts[3])
                    
        print(f"[Info] - Found {len(users)} {user_type} so far...")
                    
        # If we've reached the count, stop scrolling
        if count is not None and len(users) >= count:
            break
        
        ht = await bot.execute_script("""
                arguments[0].scrollTo(0, arguments[0].scrollHeight);
                return arguments[0].scrollHeight; """, scroll_box)
        time.sleep(randint(2, 4))
        
        # Simulate scrolling by focusing on the scroll box
        await scroll_box.click()
        time.sleep(2)

    # One final collection after scrolling completes
    following = await bot.find_elements(By.XPATH, "//a[contains(@href, '/')]")

    for i in following:
        href = await i.get_property('href')
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


async def scrape_async(use_proxy=False, proxy_info=None):
    instagram_login = InstagramLogin()
    credentials = instagram_login.load_credentials()

    if credentials is None:
        username, password = instagram_login.prompt_credentials()
    else:
        username, password = credentials

    # Connect to the database
    conn = connect_to_database()
    if not conn:
        print("[Error] - Database connection failed. Exiting.")
        return

    # Fetch pending users
    pending_users = fetch_pending_users(conn)
    if not pending_users:
        print("[Info] - No pending users to scrape.")
        conn.close()
        return

    # Create options dictionary for the driver
    options = webdriver.ChromeOptions()
    options.headless = False
    bot = await webdriver.Chrome(options=options)
    
    # Perform login before scraping
    try:
        print("[Info] - Logging in to Instagram...")
        await instagram_login.login(bot, username, password)
        print("[Info] - Login successful")
    except Exception as e:
        print(f"[Error] - Login failed: {e}")
        await bot.quit()
        conn.close()
        return

    for user_pk, username in pending_users:
        try:
            # Update status to 'in_progress'
            update_scraping_status(conn, username, 'in_progress')

            # Scrape followers and following
            followers = await scrape_following(bot, username, user_type='followers', count=None)
            time.sleep(randint(2, 8))
            following = await scrape_following(bot, username, user_type='following', count=None)

            # Update database with scraped data
            update_user_lists(conn, user_pk, followers, following)

            # Update status to 'done'
            update_scraping_status(conn, username, 'done')
        except Exception as e:
            print(f"[Error] - Scraping failed for user {username}: {e}")
            # Update status to 'failed'
            update_scraping_status(conn, username, 'failed')

    conn.close()
    await bot.quit()


def scrape(use_proxy=False, proxy_info=None):
    """Wrapper function to call the async scraper from synchronous code"""
    asyncio.run(scrape_async(use_proxy=use_proxy, proxy_info=proxy_info))


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