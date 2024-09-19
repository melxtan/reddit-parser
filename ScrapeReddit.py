#!/usr/bin/env python
# coding: utf-8

# In[26]:


from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.safari.options import Options as SafariOptions
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
import time
import re
import praw
import random
from praw.models import MoreComments
from praw.exceptions import InvalidURL

class ScrapeReddit:
    def __init__(self, reddit_client):
        self.driver = self.init_webdriver()
        self.urls = set()
        self.reddit = reddit_client  # Reddit client for PRAW API
    
    def init_webdriver(self):
        drivers = [
            (webdriver.Safari, SafariOptions()),
            (webdriver.Chrome, ChromeOptions()),
            (webdriver.Firefox, FirefoxOptions())
        ]
        
        for Driver, options in drivers:
            try:
                if Driver == webdriver.Safari:
                    # Safari doesn't support headless mode, so we'll just use it as is
                    driver = Driver()
                else:
                    options.add_argument('--headless')
                    driver = Driver(options=options)
                
                driver.set_window_size(1024, 768)  # Set window size
                return driver
            except WebDriverException:
                continue
        
        raise Exception("No supported WebDriver found. Please install Chrome, Firefox, or Safari.")

    def lazy_scroll(self, max_scrolls=10):
        for _ in range(max_scrolls):
            self.driver.execute_script('window.scrollTo(0, document.body.scrollHeight);')
            time.sleep(2)
        return self.driver.page_source

    def get_posts(self, search_query):
        search_url = f"https://www.reddit.com/search/?q={search_query.replace(' ', '+')}"
        self.driver.get(search_url)

        try:
            WebDriverWait(self.driver, 30).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-testid='post-container']"))
            )
        except TimeoutException:
            print(f"Timeout waiting for posts to load. Proceeding anyway.")

        html = self.lazy_scroll()
        soup = BeautifulSoup(html, 'html.parser')

        # Extract all post links
        post_links = soup.find_all('a', href=re.compile(r'^/r/.*?/comments/'))
        base_url = "https://www.reddit.com"
        
        for link in post_links:
            full_url = base_url + link['href']
            if full_url not in self.urls:
                self.urls.add(full_url)
        
        print(f"Collected {len(self.urls)} URLs")

    def get_reddit_post_info(self, limit=None):
        if not self.urls:
            print("No posts found. Please run get_posts() first.")
            return None
        
        post_data = []
        
        for count, url in enumerate(self.urls):
            if limit and count >= limit:
                break

            print(f"Processing post {count + 1}: {url}")
            
            try:
                time.sleep(random.uniform(1, 3)) 
                submission = self.reddit.submission(url=url)
                post_info = {
                    'id': submission.id,
                    'title': submission.title,
                    'post_text': submission.selftext,
                    'num_comments': submission.num_comments,
                    'score': submission.score,
                    'author': str(submission.author),
                    'subreddit': submission.subreddit.display_name,
                    'created_utc': submission.created_utc,
                    'comments': []
                }
                
                submission.comments.replace_more(limit=0)  # Remove MoreComments objects
                for comment in submission.comments.list():
                    comment_info = {
                        'body': comment.body,
                        'author': str(comment.author),
                        'created_utc': comment.created_utc,
                        'score': comment.score
                    }
                    post_info['comments'].append(comment_info)
                
                post_data.append(post_info)
            
            except Exception as e:
                print(f"Failed to fetch post info for {url}: {str(e)}")

        return post_data

    def destroy(self):
        if self.driver:
            self.driver.quit()

