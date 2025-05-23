from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from instagram_login import InstagramLogin
from instagram_post import InstagramPostScraper

if __name__ == "__main__":
    # Initialize WebDriver
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
    target_username = input("Enter the username to scrape posts from: ")
    num_posts = int(input("Enter the number of posts to scrape: "))
    # Login to Instagram
    login_manager = InstagramLogin()
    credentials = login_manager.load_credentials()
    if not credentials:
        credentials = login_manager.prompt_credentials()
    
    username, password = credentials
    login_manager.login(driver, username, password)
    
    # Scrape posts
    scraper = InstagramPostScraper(driver)

    
    posts, db_ready_data = scraper.scrape_posts(target_username, num_posts)
    
    # Print the scraped data
    # print(posts)
    print(db_ready_data)
    
    # Close the browser
    driver.quit()
