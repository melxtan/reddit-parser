#!/usr/bin/env python
# coding: utf-8

import logging
import os
import random
import re
import time

import praw
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.safari.options import Options as SafariOptions
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class ScrapeReddit:
    def __init__(
        self,
        client_id=None,
        client_secret=None,
        user_agent=None,
        use_api=False,
        log_level=logging.INFO,
    ):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(log_level)

        self.use_api = use_api

        # Use provided values or fall back to environment variables
        self.client_id = client_id or os.getenv("REDDIT_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("REDDIT_CLIENT_SECRET")
        self.user_agent = user_agent or os.getenv("REDDIT_USER_AGENT")

        if not all([self.client_id, self.client_secret, self.user_agent]):
            raise ValueError(
                (
                    "Missing Reddit API credentials. "
                    "Please provide them as parameters "
                    "or set them as environment variables."
                )
            )

        self.reddit = praw.Reddit(
            client_id=self.client_id,
            client_secret=self.client_secret,
            user_agent=self.user_agent,
        )
        self.urls = set()
        if not use_api:
            self.driver = self.init_webdriver()

    def init_webdriver(self):
        drivers = [
            (webdriver.Safari, SafariOptions()),
            (webdriver.Chrome, ChromeOptions()),
            (webdriver.Firefox, FirefoxOptions()),
        ]

        for Driver, options in drivers:
            try:
                if Driver == webdriver.Safari:
                    driver = Driver()
                else:
                    options.add_argument("--headless")
                    driver = Driver(options=options)

                driver.set_window_size(1024, 768)
                return driver
            except WebDriverException:
                continue

        raise Exception("No supported WebDriver found. Please install Chrome, Firefox, or Safari.")

    def lazy_scroll(self, max_scrolls=10):
        for _ in range(max_scrolls):
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
        return self.driver.page_source

    def get_posts(self, search_query):
        if self.use_api:
            self._get_posts_api(search_query)
        else:
            self._get_posts_webdriver(search_query)

    def _get_posts_api(self, search_query):
        for submission in self.reddit.subreddit("all").search(search_query, limit=None):
            self.urls.add(f"https://www.reddit.com{submission.permalink}")
        self.logger.info(f"Collected {len(self.urls)} URLs")

    def _get_posts_webdriver(self, search_query):
        search_url = f"https://www.reddit.com/search/?q={search_query.replace(' ', '+')}"
        self.driver.get(search_url)

        try:
            WebDriverWait(self.driver, 30).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-testid='post-container']"))
            )
        except TimeoutException:
            self.logger.warning("Timeout waiting for posts to load. Proceeding anyway.")

        html = self.lazy_scroll()
        soup = BeautifulSoup(html, "html.parser")

        post_links = soup.find_all("a", href=re.compile(r"^/r/.*?/comments/"))
        base_url = "https://www.reddit.com"

        for link in post_links:
            full_url = base_url + link["href"]
            if full_url not in self.urls:
                self.urls.add(full_url)

        self.logger.info(f"Collected {len(self.urls)} URLs")

    def get_reddit_post_info(self, limit=None):
        if not self.urls:
            self.logger.warning("No posts found. Please run get_posts() first.")
            return None

        post_data = []

        for count, url in enumerate(self.urls):
            if limit and count >= limit:
                break

            self.logger.info(f"Processing post {count + 1}: {url}")

            try:
                time.sleep(random.uniform(1, 3))
                submission = self.reddit.submission(url=url)
                post_info = {
                    "id": submission.id,
                    "title": submission.title,
                    "post_text": submission.selftext,
                    "num_comments": submission.num_comments,
                    "score": submission.score,
                    "author": str(submission.author),
                    "subreddit": submission.subreddit.display_name,
                    "created_utc": submission.created_utc,
                    "comments": [],
                }

                submission.comments.replace_more(limit=0)  # Remove MoreComments objects
                for comment in submission.comments.list():
                    comment_info = {
                        "body": comment.body,
                        "author": str(comment.author),
                        "created_utc": comment.created_utc,
                        "score": comment.score,
                    }
                    post_info["comments"].append(comment_info)

                post_data.append(post_info)

            except Exception as e:
                self.logger.error(f"Failed to fetch post info for {url}: {str(e)}")

        return post_data

    def destroy(self):
        if not self.use_api and self.driver:
            self.driver.quit()
