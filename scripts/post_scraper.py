import time
from random import randint
import os
import json
from datetime import datetime
import codecs
import psycopg2
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import NoSuchElementException, TimeoutException


def load_credentials_from_env():
    """Load Instagram credentials from environment variables"""
    load_dotenv()
    username = os.getenv("INSTAGRAM_USERNAME")
    password = os.getenv("INSTAGRAM_PASSWORD")
    
    if not username or not password:
        return None
    
    return username, password


def prompt_credentials():
    username = input("Enter your Instagram username: ")
    password = input("Enter your Instagram password: ")
    return username, password


def login(bot, username, password):
    bot.get('https://www.instagram.com/accounts/login/')
    time.sleep(randint(1, 5))

    # Check if cookies need to be accepted
    try:
        element = bot.find_element(By.XPATH, "/html/body/div[4]/div/div/div[3]/div[2]/button")
        element.click()
    except NoSuchElementException:
        print("[Info] - Instagram did not require to accept cookies this time.")

    print("[Info] - Logging in...")
    username_input = WebDriverWait(bot, 10).until(
        ec.element_to_be_clickable((By.CSS_SELECTOR, "input[name='username']")))
    password_input = WebDriverWait(bot, 10).until(
        ec.element_to_be_clickable((By.CSS_SELECTOR, "input[name='password']")))

    username_input.clear()
    username_input.send_keys(username)
    password_input.clear()
    password_input.send_keys(password)

    login_button = WebDriverWait(bot, 2).until(ec.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit']")))
    login_button.click()
    time.sleep(10)


def decode_unicode_string(raw_string):
    try:
        return codecs.decode(raw_string, 'unicode_escape').encode('utf-16', 'surrogatepass').decode('utf-16')
    except Exception:
        return raw_string  # fallback if decoding fails

def scrape_posts(bot, username, num_posts=3):
    """Scrape recent posts from a user's profile and extract metadata"""
    bot.get(f'https://www.instagram.com/{username}/')
    time.sleep(3.5)
    
    print(f"[Info] - Scraping {num_posts} recent posts for {username}...")
    
    posts = []
    post_links = []
    
    # First collect post links
    while len(post_links) < num_posts:
        # Find post elements
        time.sleep(2)
        post_elements = bot.find_elements(By.XPATH, "//a[contains(@href, '/p/')]")
        
        # Extract hrefs and add new ones
        for post in post_elements:
            href = post.get_attribute('href')
            if href and href not in post_links:
                post_links.append(href)
                
        if len(post_links) >= num_posts:
            break
            
        # Scroll down to load more posts
        bot.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(3)
        
        # Limit the number of scroll attempts
        if len(post_links) == 0:
            print("[Warning] - Could not find any posts")
            break
    
    # Limit to requested number of posts
    post_links = post_links[:num_posts]
    
    # Visit each post to extract metadata
    for index, link in enumerate(post_links):
        try:
            print(f"[Info] - Scraping post {index+1}/{len(post_links)}")
            post_data = extract_post_metadata(bot, link)
            posts.append(post_data)
            time.sleep(randint(1, 3))  # Avoid rate limiting
        except Exception as e:
            print(f"[Error] - Failed to scrape post {link}: {str(e)}")
    
    # Save posts data
    print(f"[Info] - Saving posts data for {username}...")
    with open(f'{username}_posts.json', 'w') as file:
        json.dump(posts, file, indent=4)
    
    return posts

def extract_post_metadata(bot, post_url):
    """Extract metadata from a single post"""
    bot.get(post_url)
    time.sleep(3)
    
    post_data = {
        "url": post_url,
        "timestamp": datetime.now().isoformat(),
        "scraped_at": datetime.now().isoformat()
    }
    
    try:
        # Try to get caption
        try:
            caption_element = WebDriverWait(bot, 5).until(
                ec.presence_of_element_located((By.CSS_SELECTOR, "h1._ap3a"))
            )
            raw_caption = caption_element.text if caption_element else ""
            post_data["caption"] = decode_unicode_string(raw_caption)
        except (TimeoutException, NoSuchElementException):
            post_data["caption"] = ""

            
        # Try to get image URL
        try:
            img_element = WebDriverWait(bot, 5).until(
                ec.presence_of_element_located((By.XPATH, "//img[@class='x5yr21d xu96u03 x10l6tqk x13vifvy x87ps6o xh8yej3']"))
            )
            post_data["image_url"] = img_element.get_attribute("src")
        except (TimeoutException, NoSuchElementException):
            post_data["image_url"] = ""
            
        # Try to get likes count
        try:
            likes_element = WebDriverWait(bot, 3).until(
                ec.presence_of_element_located((
                    By.XPATH,
                    "//span[contains(text(), 'others')]/span"
                ))
            )
            try:
                # Convert to integer and add 1
                likes_count = int(likes_element.text) + 1
                post_data["likes"] = str(likes_count)
            except ValueError:
                # If conversion fails, just use the text
                post_data["likes"] = likes_element.text
        except (TimeoutException, NoSuchElementException):
            post_data["likes"] = "Not available"

            
        # Try to get post date
        try:
            time_element = WebDriverWait(bot, 3).until(
                ec.presence_of_element_located((By.XPATH, "//time"))
            )
            post_data["posted_date"] = time_element.get_attribute("datetime")
        except (TimeoutException, NoSuchElementException):
            post_data["posted_date"] = ""

    except Exception as e:
        print(f"[Error] - Error parsing post metadata: {str(e)}")
        
    return post_data

def connect_to_db():
    """Create a connection to the PostgreSQL database using environment variables"""
    # Load environment variables from .env file
    load_dotenv()
    
    try:
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST", "localhost"),
            database=os.getenv("DB_NAME", "instagram"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", "postgres")
        )
        return conn
    except Exception as e:
        print(f"[Error] - Failed to connect to database: {str(e)}")
        return None

def save_to_database(username, posts_data):
    """Save scraped data to the PostgreSQL database"""
    conn = connect_to_db()
    if not conn:
        print("[Error] - Cannot save to database: No connection")
        return False
    
    try:
        cursor = conn.cursor()
        
        # First insert or update the user record
        cursor.execute(
            "INSERT INTO user_data (username) VALUES (%s) "
            "ON CONFLICT (username) DO UPDATE SET username = EXCLUDED.username "
            "RETURNING pk",
            (username,)
        )
        user_pk = cursor.fetchone()[0]
        
        # Extract data from posts
        post_urls = [post.get('image_url', '') for post in posts_data]
        captions = [post.get('caption', '') for post in posts_data]
        likes = [int(post.get('likes', '0')) if post.get('likes', '').isdigit() else 0 for post in posts_data]
        
        # Convert ISO dates to proper date objects
        posted_dates = []
        for post in posts_data:
            date_str = post.get('posted_date', '')
            try:
                if date_str:
                    date_obj = datetime.fromisoformat(date_str).date()
                    posted_dates.append(date_obj)
                else:
                    posted_dates.append(None)
            except Exception:
                posted_dates.append(None)
        
        # Check if user_detail record exists
        cursor.execute("SELECT pk FROM user_detail WHERE pk = %s", (user_pk,))
        user_detail_exists = cursor.fetchone() is not None
        
        if user_detail_exists:
            # Update existing record
            cursor.execute(
                "UPDATE user_detail SET post_urls = %s, captions = %s, likes = %s, posted_at = %s WHERE pk = %s",
                (post_urls, captions, likes, posted_dates, user_pk)
            )
        else:
            # Insert new record
            cursor.execute(
                "INSERT INTO user_detail (pk, post_urls, captions, likes, posted_at) VALUES (%s, %s, %s, %s, %s)",
                (user_pk, post_urls, captions, likes, posted_dates)
            )
        
        conn.commit()
        print(f"[Success] - Saved data for {username} to database")
        return True
        
    except Exception as e:
        conn.rollback()
        print(f"[Error] - Database operation failed: {str(e)}")
        return False
    finally:
        conn.close()

def scrape():
    credentials = load_credentials_from_env()

    if credentials is None:
        username, password = prompt_credentials()
    else:
        username, password = credentials

    usernames = input("Enter the Instagram usernames you want to scrape (separated by commas): ").split(",")
    
    # Ask for post count
    posts_count = int(input("How many recent posts do you want to scrape? "))
    
    # Ask if data should be saved to database
    save_to_db = input("Do you want to save the data to database? (y/n): ").lower() == 'y'

    options = webdriver.ChromeOptions()
    # options.add_argument('--headless')
    mobile_emulation = {
        "userAgent": "Mozilla/5.0 (Linux; Android 10; SM-G970F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.106 Mobile Safari/537.36"}
    options.add_experimental_option("mobileEmulation", mobile_emulation)

    bot = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()))
    login(bot, username, password)

    for user in usernames:
        user = user.strip()
        posts = scrape_posts(bot, user, posts_count)
        
        if save_to_db and posts:
            print(f"[Info] - Saving data for {user} to database...")
            save_to_database(user, posts)

    bot.quit()


if __name__ == '__main__':
    TIMEOUT = 15
    scrape()