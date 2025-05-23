import os
import time
from random import randint
import asyncio
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from dotenv import load_dotenv, set_key

class InstagramLogin:
    def __init__(self):
        self.env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    
    def save_credentials(self, username, password):
        set_key(self.env_path, 'INSTAGRAM_USERNAME', username)
        set_key(self.env_path, 'INSTAGRAM_PASSWORD', password)
        print("[Info] - Credentials saved to .env file")

    def load_credentials(self):
        # Load variables from .env file
        load_dotenv()
        
        username = os.environ.get('INSTAGRAM_USERNAME')
        password = os.environ.get('INSTAGRAM_PASSWORD')
        
        if username and password:
            return username, password
        
        return None

    def prompt_credentials(self):
        username = input("Enter your Instagram username: ")
        password = input("Enter your Instagram password: ")
        self.save_credentials(username, password)
        return username, password

    def wait_for_element(self, bot, by, selector, timeout=10):
        try:
            element = WebDriverWait(bot, timeout).until(
                EC.presence_of_element_located((by, selector))
            )
            return element
        except TimeoutException:
            raise TimeoutError(f"Element {selector} not found after {timeout} seconds")

    def login(self, bot, username, password):
        bot.get('https://www.instagram.com/accounts/login/')
        time.sleep(randint(1, 5))

        # Check if cookies need to be accepted
        try:
            element = bot.find_element(By.XPATH, "/html/body/div[4]/div/div/div[3]/div[2]/button")
            element.click()
        except Exception:
            print("[Info] - Instagram did not require to accept cookies this time.")

        print("[Info] - Logging in...")
        
        username_input = self.wait_for_element(bot, By.CSS_SELECTOR, "input[name='username']")
        password_input = self.wait_for_element(bot, By.CSS_SELECTOR, "input[name='password']")

        username_input.clear()
        username_input.send_keys(username)
        password_input.clear()
        password_input.send_keys(password)

        login_button = self.wait_for_element(bot, By.CSS_SELECTOR, "button[type='submit']")
        login_button.click()
        time.sleep(10)
