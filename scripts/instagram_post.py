import time
from random import randint
import codecs
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as ec
from selenium.common.exceptions import NoSuchElementException, TimeoutException

class InstagramPostScraper:
    def __init__(self, driver):
        self.bot = driver

    def decode_unicode_string(self, raw_string):
        try:
            return codecs.decode(raw_string, 'unicode_escape').encode('utf-16', 'surrogatepass').decode('utf-16')
        except Exception:
            return raw_string

    def scrape_posts(self, username, num_posts=3):
        """Scrape recent posts from a user's profile and extract metadata"""
        self.bot.get(f'https://www.instagram.com/{username}/')
        time.sleep(3.5)
        
        print(f"[Info] - Scraping {num_posts} recent posts for {username}...")
        
        posts = []
        post_links = []
        
        while len(post_links) < num_posts:
            time.sleep(2)
            post_elements = self.bot.find_elements(By.XPATH, "//a[contains(@href, '/p/')]")
            
            for post in post_elements:
                href = post.get_attribute('href')
                if href and href not in post_links:
                    post_links.append(href)
                    
            if len(post_links) >= num_posts:
                break
                
            self.bot.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(3)
            
            if len(post_links) == 0:
                print("[Warning] - Could not find any posts")
                break
        
        post_links = post_links[:num_posts]
        
        # Initialize lists for database insertion
        captions = []
        post_urls = []
        likes_list = []
        
        for index, link in enumerate(post_links):
            try:
                print(f"[Info] - Scraping post {index+1}/{len(post_links)}")
                post_data = self.extract_post_metadata(link)
                posts.append(post_data)
                
                # Add data to the respective lists
                captions.append(post_data["caption"])
                post_urls.append(post_data["image_url"])
                likes_list.append(post_data["likes"])
                
                time.sleep(randint(1, 3))
            except Exception as e:
                print(f"[Error] - Failed to scrape post {link}: {str(e)}")
        
        # Return both the detailed posts and the database-ready format
        db_ready_data = {
            "captions": captions,
            "post_urls": post_urls,
            "likes": likes_list
        }
        
        return posts, db_ready_data

    def extract_post_metadata(self, post_url):
        """Extract only caption, image_url, and likes from a single post"""
        self.bot.get(post_url)
        time.sleep(3)
        
        post_data = {"url": post_url}

        # Caption
        try:
            caption_element = WebDriverWait(self.bot, 5).until(
                ec.presence_of_element_located((By.CSS_SELECTOR, "h1._ap3a"))
            )
            raw_caption = caption_element.text if caption_element else ""
            post_data["caption"] = self.decode_unicode_string(raw_caption)
        except (TimeoutException, NoSuchElementException):
            post_data["caption"] = ""

        # Image URL
        try:
            img_element = WebDriverWait(self.bot, 5).until(
                ec.presence_of_element_located((By.XPATH, "//img[@class='x5yr21d xu96u03 x10l6tqk x13vifvy x87ps6o xh8yej3']"))
            )
            post_data["image_url"] = img_element.get_attribute("src")
        except (TimeoutException, NoSuchElementException):
            post_data["image_url"] = ""

        # Likes
        try:
            likes_element = WebDriverWait(self.bot, 3).until(
                ec.presence_of_element_located((
                    By.XPATH,
                    "//span[contains(text(), 'others')]/span"
                ))
            )
            try:
                likes_count = int(likes_element.text) + 1
                post_data["likes"] = likes_count  # Store as integer, not string
            except ValueError:
                # Try to convert to int if possible
                try:
                    post_data["likes"] = int(likes_element.text)
                except ValueError:
                    post_data["likes"] = 0
        except (TimeoutException, NoSuchElementException):
            post_data["likes"] = 0  # Default to 0 if not available
            
        return post_data
