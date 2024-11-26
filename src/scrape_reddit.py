#!/usr/bin/env python
# coding: utf-8

import json
import logging
import random
import re
import time
from datetime import datetime
from typing import List

from bs4 import BeautifulSoup
from custom_reddit import CustomReddit
from praw.models import Comment
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.safari.options import Options as SafariOptions
from selenium.webdriver.support import expected_conditions as EC  # noqa: N812
from selenium.webdriver.support.ui import WebDriverWait


class ScrapeReddit:
    def __init__(
        self,
        client_id,
        client_secret,
        user_agent,
        use_api=False,
        log_level=logging.INFO,
    ):
        # Set up logger for this class
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(log_level)

        # Set up logging for praw and prawcore
        handler = logging.StreamHandler()
        handler.setLevel(log_level)
        for logger_name in ("praw", "prawcore"):
            logger = logging.getLogger(logger_name)
            logger.setLevel(log_level)
            logger.addHandler(handler)

        self.use_api = use_api

        # Use provided values or fall back to environment variables
        self.client_id = client_id
        self.client_secret = client_secret
        self.user_agent = user_agent

        if not all([self.client_id, self.client_secret, self.user_agent]):
            raise ValueError("Missing Reddit API credentials. Please provide them as parameters or set them as environment variables.")

        self.reddit = CustomReddit(
            client_id=self.client_id,
            client_secret=self.client_secret,
            user_agent=self.user_agent,
        )
        if not use_api:
            self.driver = self.init_webdriver()

    def init_webdriver(self):
        drivers = [
            (webdriver.Safari, SafariOptions()),
            (webdriver.Chrome, ChromeOptions()),
            (webdriver.Firefox, FirefoxOptions()),
        ]

        for driver, options in drivers:
            try:
                if driver == webdriver.Safari:
                    driver = driver()
                else:
                    options.add_argument("--headless")
                    driver = driver(options=options)

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

    def get_posts(self, search_query, time_filter="all", search_option="relevance", limit=None) -> List[str]:
        if self.use_api:
            return self._get_posts_api(search_query, time_filter, search_option, limit)
        else:
            return self._get_posts_webdriver(search_query, time_filter, search_option, limit)

    def _get_posts_api(self, search_query, time_filter, search_option, limit) -> List[str]:
        self.logger.info(f"Searching for '{search_query}' with time filter: {time_filter} and search option: {search_option}")
        urls = []
        sort_mapping = {"relevance": "relevance", "hot": "hot", "top": "top", "new": "new", "comments": "comments"}
        sort = sort_mapping.get(search_option, "relevance")

        for submission in self.reddit.search(query=search_query, sort=sort, time_filter=time_filter, limit=limit):
            urls.append(f"https://www.reddit.com{submission.permalink}")

        self.logger.info(f"Collected {len(urls)} URLs")
        self.logger.debug(f"URLs: {urls}")
        return urls

    def _get_posts_webdriver(self, search_query, time_filter, search_option, limit) -> List[str]:
        self.logger.info(f"Searching for '{search_query}' with time filter: {time_filter} and search option: {search_option}")

        # Map search_option to Reddit's URL parameter
        sort_mapping = {"relevance": "relevance", "hot": "hot", "top": "top", "new": "new", "comments": "comments"}
        sort = sort_mapping.get(search_option, "relevance")

        time_param = f"&t={time_filter}" if time_filter != "all" else ""
        search_url = f"https://www.reddit.com/search/?q={search_query.replace(' ', '+')}&sort={sort}{time_param}"
        self.driver.get(search_url)

        try:
            WebDriverWait(self.driver, 30).until(EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-testid='post-container']")))
        except TimeoutException:
            self.logger.warning("Timeout waiting for posts to load. Proceeding anyway.")

        html = self.lazy_scroll()
        soup = BeautifulSoup(html, "html.parser")

        post_links = soup.find_all("a", href=re.compile(r"^/r/.*?/comments/"))
        base_url = "https://www.reddit.com"

        urls = []
        seen = set()
        for link in post_links:
            full_url = base_url + link["href"]
            if full_url not in seen:
                urls.append(full_url)
                seen.add(full_url)

        self.logger.info(f"Collected {len(urls)} unique URLs")
        return urls[:limit] if limit else urls

    def get_reddit_post_info(self, urls):
        post_data = []
        self.logger.info(f"Starting to process posts. Total URLs: {len(urls)}")

        for count, url in enumerate(urls):
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
                    "created_at": datetime.utcfromtimestamp(submission.created_utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
                    "comments": [],
                }

                submission.comments.replace_more(limit=0)  # Remove MoreComments objects
                comments: List[Comment] = submission.comments.list()  # type: ignore
                for comment in comments:
                    comment_info = {
                        "body": comment.body,
                        "author": str(comment.author),
                        "created_utc": comment.created_utc,
                        "created_at": datetime.utcfromtimestamp(comment.created_utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
                        "score": comment.score,
                    }
                    post_info["comments"].append(comment_info)

                # Convert comments to JSON string
                post_info["comments"] = json.dumps(post_info["comments"])

                post_data.append(post_info)
                self.logger.info(f"Successfully processed post {count + 1}")

            except Exception as e:
                self.logger.error(f"Failed to fetch post info for {url}: {str(e)}")

        self.logger.info(f"Finished processing posts. Total posts processed: {len(post_data)}")
        return post_data

    def destroy(self):
        if not self.use_api and self.driver:
            self.driver.quit()
