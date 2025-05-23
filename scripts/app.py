import time
from random import randint
import os
import codecs
import psycopg2
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from dotenv import load_dotenv, set_key
from instagram_login import InstagramLogin
from instagram_post import InstagramPostScraper
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
from typing import Optional
import tempfile
import shutil

class InstagramScraper:
    def __init__(self, driver):
        self.bot = driver
        self.TIMEOUT = 15

    def decode_unicode_string(self, raw_string):
        try:
            return codecs.decode(raw_string, 'unicode_escape').encode('utf-16', 'surrogatepass').decode('utf-16')
        except Exception:
            return raw_string

    def scrape_followers_following(self, username, user_type='followers', count=None):
        self.bot.get(f'https://www.instagram.com/{username}/')
        time.sleep(3.5)
        WebDriverWait(self.bot, self.TIMEOUT).until(ec.presence_of_element_located(
            (By.XPATH, f"//a[contains(@href, '/{user_type}')]"))).click()
        time.sleep(randint(2, 8))

        scroll_box = self.bot.find_element(By.XPATH, '//div[@class="xyi19xy x1ccrb07 xtf3nb5 x1pc53ja x1lliihq x1iyjqo2 xs83m0k xz65tgg x1rife3k x1n2onr6"]')
        actions = ActionChains(self.bot)
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
            following = self.bot.find_elements(By.XPATH, "//a[contains(@href, '/')]")
            
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
            
            ht = self.bot.execute_script("""
                    arguments[0].scrollTo(0, arguments[0].scrollHeight);
                    return arguments[0].scrollHeight; """, scroll_box)
            time.sleep(randint(2, 4))
            actions.move_to_element(scroll_box).perform()
            time.sleep(2)

        # One final collection after scrolling completes
        following = self.bot.find_elements(By.XPATH, "//a[contains(@href, '/')]")

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

        # print(f"[Info] - Collected {len(users)} {user_type} for {username}")
        # print(f"[Info] - Saving {user_type} for {username}...")
        # with open(f'{username}_{user_type}.txt', 'a') as file:
        #     file.write('\n'.join(users) + "\n")
        
        return list(users)

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

def update_user_data(conn, user_id, followers_list, following_list, db_ready_posts):
    try:
        # Extract data from db_ready_posts
        captions = db_ready_posts.get("captions", [])
        post_urls = db_ready_posts.get("post_urls", [])
        likes = db_ready_posts.get("likes", [])
        
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE user_data 
            SET 
                followers_list = %s, 
                following_list = %s, 
                captions = %s, 
                post_urls = %s, 
                likes = %s, 
                scraping_status = 'done' 
            WHERE id = %s
            """,
            (followers_list, following_list, captions, post_urls, likes, user_id)
        )
        conn.commit()
        cursor.close()
        print(f"[Info] - Successfully updated data for user {user_id}")
        return True
    except Exception as e:
        conn.rollback()
        print(f"[Error] - Failed to update user data: {e}")
        update_scraping_status(conn, user_id, 'failed')
        return False

def scrape(use_proxy=False, proxy_info=None, posts_count=3):
    # Create a temporary user data directory
    temp_user_data_dir = tempfile.mkdtemp()

    options = webdriver.ChromeOptions()
    options.add_argument(f"--user-data-dir={temp_user_data_dir}")
    # options.add_argument('--headless')  # Uncomment if you want to run headless

    # Configure proxy if enabled
    if use_proxy and proxy_info:
        if isinstance(proxy_info, dict):
            options.add_argument(f"--proxy-server={proxy_info['host']}:{proxy_info['port']}")
            print(f"[Info] - Using proxy: {proxy_info['host']}:{proxy_info['port']}")
        elif isinstance(proxy_info, str):
            options.add_argument(f"--proxy-server={proxy_info}")
            print(f"[Info] - Using proxy: {proxy_info}")

    bot = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()))

    try:
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

        # Initialize the scrapers
        scraper = InstagramScraper(bot)
        post_scraper = InstagramPostScraper(bot)
        
        # Use the InstagramLogin class for login
        instagram_login.login(bot, username, password)
        
        # Set to None to scrape all followers and following or use a specific count
        followers_count = None
        following_count = None

        for user_id, instagram_id in pending_users:
            try:
                # Update status to in_progress
                update_scraping_status(conn, user_id, 'in_progress')
                
                print(f"[Info] - Starting to scrape user {instagram_id}")
                # Scrape posts using the InstagramPostScraper class
                print(f"[Info] - Now scraping posts for {instagram_id}")
                posts, db_ready_posts = post_scraper.scrape_posts(instagram_id, num_posts=posts_count)
                time.sleep(randint(2, 8))
                # Scrape followers and following
                followers = scraper.scrape_followers_following(instagram_id, user_type='followers', count=followers_count)
                time.sleep(randint(2, 8))
                following = scraper.scrape_followers_following(instagram_id, user_type='following', count=following_count)
                
                
                # Update user data with all scraped information
                success = update_user_data(conn, user_id, followers, following, db_ready_posts)
                
                if not success:
                    print(f"[Warning] - Failed to update database for user {instagram_id}. Marked as failed.")
                    
                time.sleep(randint(5, 10))  # Wait between users to avoid being rate-limited
            except Exception as e:
                print(f"[Error] - Failed to scrape user {instagram_id}: {e}")
                update_scraping_status(conn, user_id, 'failed')

        if conn:
            conn.close()
            print("[Info] - Database connection closed")
    finally:
        bot.quit()
        shutil.rmtree(temp_user_data_dir)


app = FastAPI()

class ScrapeRequest(BaseModel):
    use_proxy: bool = False
    proxy_info: Optional[dict] = None

@app.post("/start-scraping")
def start_scraping(request: ScrapeRequest):
    try:
        print("[Info] - Received scraping request")
        scrape(use_proxy=request.use_proxy, proxy_info=request.proxy_info, posts_count=2)
        return {"message": "Scraping process started successfully"}
    except Exception as e:
        print(f"[Error] - Failed to start scraping: {e}")
        raise HTTPException(status_code=500, detail="Failed to start scraping process")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
