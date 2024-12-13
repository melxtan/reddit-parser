
#!/usr/bin/env python
# coding: utf-8

import logging
import random
import re
import time
from datetime import datetime
from typing import List, Optional, Tuple, Type

from bs4 import BeautifulSoup
from custom_reddit import CustomReddit
from praw.models import Comment, Submission
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.safari.options import Options as SafariOptions
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class ScrapeReddit:
    """A class to scrape Reddit content using either the API or web scraping."""

    SORT_MAPPING = {
        "relevance": "relevance",
        "hot": "hot",
        "top": "top",
        "new": "new",
        "comments": "comments",
    }

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        user_agent: str,
        use_api: bool = False,
        log_level: int = logging.INFO,
    ) -> None:
        """Initialize the Reddit scraper.

        Args:
            client_id: Reddit API client ID
            client_secret: Reddit API client secret
            user_agent: User agent string for Reddit API
            use_api: Whether to use Reddit's API instead of web scraping
            log_level: Logging level to use
        
        Raises:
            ValueError: If Reddit API credentials are missing
        """
        self._setup_logging(log_level)
        self.use_api = use_api

        if not all([client_id, client_secret, user_agent]):
            raise ValueError(
                "Missing Reddit API credentials. Please provide them as parameters "
                "or set them as environment variables."
            )

        self.reddit = CustomReddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent,
        )
        self.driver: Optional[WebDriver] = None if use_api else self._init_webdriver()

    def _setup_logging(self, log_level: int) -> None:
        """Set up logging for the scraper and PRAW."""
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(log_level)

        handler = logging.StreamHandler()
        handler.setLevel(log_level)
        for logger_name in ("praw", "prawcore"):
            logger = logging.getLogger(logger_name)
            logger.setLevel(log_level)
            logger.addHandler(handler)

    def _init_webdriver(self) -> WebDriver:
        """Initialize a webdriver instance with appropriate options.

        Returns:
            WebDriver: Initialized webdriver instance

        Raises:
            Exception: If no supported WebDriver is found
        """
        drivers: List[Tuple[Type[WebDriver], object]] = [
            (webdriver.Safari, SafariOptions()),
            (webdriver.Chrome, ChromeOptions()),
            (webdriver.Firefox, FirefoxOptions()),
        ]

        for driver_class, options in drivers:
            try:
                if driver_class == webdriver.Safari:
                    driver = driver_class()
                else:
                    options.add_argument("--headless")  # type: ignore
                    driver = driver_class(options=options)  # type: ignore

                driver.set_window_size(1024, 768)
                return driver
            except WebDriverException:
                continue

        raise Exception(
            "No supported WebDriver found. Please install Chrome, Firefox, or Safari."
        )

    def _lazy_scroll(self, max_scrolls: int = 10) -> str:
        """Scroll the page gradually to load more content.

        Args:
            max_scrolls: Maximum number of scroll operations

        Returns:
            str: Page source after scrolling
        """
        for _ in range(max_scrolls):
            self.driver.execute_script(  # type: ignore
                "window.scrollTo(0, document.body.scrollHeight);"
            )
            time.sleep(2)
        return self.driver.page_source  # type: ignore

    def get_posts(
        self,
        search_query: str,
        time_filter: str = "all",
        search_option: str = "relevance",
        limit: Optional[int] = None,
    ) -> List[str]:
        """Get Reddit posts based on search criteria.

        Args:
            search_query: Search term to look for
            time_filter: Time period to filter results
            search_option: Sort method for results
            limit: Maximum number of posts to return

        Returns:
            List of Reddit post URLs
        """
        if self.use_api:
            return self._get_posts_api(search_query, time_filter, search_option, limit)
        return self._get_posts_webdriver(search_query, time_filter, search_option, limit)

    def _get_posts_api(
        self,
        search_query: str,
        time_filter: str,
        search_option: str,
        limit: Optional[int],
    ) -> List[str]:
        """Get posts using Reddit's API.

        Args:
            search_query: Search term to look for
            time_filter: Time period to filter results
            search_option: Sort method for results
            limit: Maximum number of posts to return

        Returns:
            List of Reddit post URLs
        """
        self.logger.info(
            "Searching for '%s' with time filter: %s and search option: %s",
            search_query,
            time_filter,
            search_option,
        )

        sort = self.SORT_MAPPING.get(search_option, "relevance")
        urls = [
            f"https://www.reddit.com{submission.permalink}"
            for submission in self.reddit.search(
                query=search_query,
                sort=sort,
                time_filter=time_filter,
                limit=limit,
            )
        ]

        self.logger.info("Collected %d URLs", len(urls))
        return urls

    def _get_posts_webdriver(
        self,
        search_query: str,
        time_filter: str,
        search_option: str,
        limit: Optional[int],
    ) -> List[str]:
        """Get posts using web scraping.

        Args:
            search_query: Search term to look for
            time_filter: Time period to filter results
            search_option: Sort method for results
            limit: Maximum number of posts to return

        Returns:
            List of Reddit post URLs
        """
        self.logger.info(
            "Searching for '%s' with time filter: %s and search option: %s",
            search_query,
            time_filter,
            search_option,
        )

        sort = self.SORT_MAPPING.get(search_option, "relevance")
        time_param = f"&t={time_filter}" if time_filter != "all" else ""
        search_url = (
            f"https://www.reddit.com/search/?q={search_query.replace(' ', '+')}"
            f"&sort={sort}{time_param}"
        )

        if not self.driver:
            raise RuntimeError("WebDriver not initialized")

        self.driver.get(search_url)
        try:
            WebDriverWait(self.driver, 30).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "div[data-testid='post-container']")
                )
            )
        except TimeoutException:
            self.logger.warning("Timeout waiting for posts to load. Proceeding anyway.")

        soup = BeautifulSoup(self._lazy_scroll(), "html.parser")
        post_links = soup.find_all("a", href=re.compile(r"^/r/.*?/comments/"))

        urls = [
            f"https://www.reddit.com{link['href']}"
            for link in post_links
            if f"https://www.reddit.com{link['href']}" not in set()
        ]

        self.logger.info("Collected %d unique URLs", len(urls))
        return urls[:limit] if limit else urls

    @staticmethod
    def _clean_text(text: str) -> str:
        """Remove invisible characters and their HTML entity equivalents from text.

        Args:
            text: Text to clean

        Returns:
            Cleaned text
        """
        html_pattern = r"&#x200B;|&#x200C;|&#x200D;|&#xFEFF;"
        text = re.sub(html_pattern, "", text)

        invisible_chars_pattern = r"[\u200B-\u200D\uFEFF]"
        return re.sub(invisible_chars_pattern, "", text)

    def get_reddit_post_info(self, urls: List[str]) -> List[dict]:
        """Get detailed information about Reddit posts.

        Args:
            urls: List of Reddit post URLs to process

        Returns:
            List of dictionaries containing post information
        """
        post_data = []
        self.logger.info("Starting to process posts. Total URLs: %d", len(urls))

        for count, url in enumerate(urls, 1):
            self.logger.info("Processing post %d: %s", count, url)
            try:
                time.sleep(random.uniform(1, 3))
                submission: Submission = self.reddit.submission(url=url)
                post_info = self._extract_post_info(submission)
                post_data.append(post_info)
                self.logger.info("Successfully processed post %d", count)

            except Exception as e:
                self.logger.error("Failed to fetch post info for %s: %s", url, str(e))

        self.logger.info("Finished processing posts. Total posts processed: %d", len(post_data))
        return post_data

    def _extract_post_info(self, submission: Submission) -> dict:
        """Extract information from a Reddit submission.

        Args:
            submission: Reddit submission object

        Returns:
            Dictionary containing post information
        """
        post_info = {
            "id": submission.id,
            "title": self._clean_text(submission.title),
            "body": self._clean_text(submission.selftext),
            "num_comments": submission.num_comments,
            "score": submission.score,
            "author": str(submission.author),
            "subreddit": submission.subreddit.display_name,
            "created_at": datetime.utcfromtimestamp(
                submission.created_utc
            ).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "comments": [],
        }

        submission.comments.replace_more(limit=0)
        comments: List[Comment] = submission.comments.list()
        post_info["comments"] = [
            {
                "body": self._clean_text(comment.body),
                "author": str(comment.author),
                "created_at": datetime.utcfromtimestamp(
                    comment.created_utc
                ).strftime("%Y-%m-%d %H:%M:%S UTC"),
                "score": comment.score,
            }
            for comment in comments
        ]

        return post_info

    def destroy(self) -> None:
        """Clean up resources."""
        if not self.use_api and self.driver:
            self.driver.quit()

    def get_subreddit_posts(
        self,
        subreddit_name: str,
        search_option: str = "hot",
        time_filter: str = "all",
        limit: Optional[int] = None,
    ) -> List[str]:
        """Get posts from a specific subreddit.

        Args:
            subreddit_name: Name of the subreddit
            search_option: Sort method for results
            time_filter: Time period to filter results
            limit: Maximum number of posts to return

        Returns:
            List of Reddit post URLs
        """
        if self.use_api:
            return self._get_subreddit_posts_api(
                subreddit_name, search_option, time_filter, limit
            )
        return self._get_subreddit_posts_webdriver(
            subreddit_name, search_option, time_filter, limit
        )

    def _get_subreddit_posts_api(
        self,
        subreddit_name: str,
        search_option: str,
        time_filter: str,
        limit: Optional[int],
    ) -> List[str]:
        """Get subreddit posts using Reddit's API.

        Args:
            subreddit_name: Name of the subreddit
            search_option: Sort method for results
            time_filter: Time period to filter results
            limit: Maximum number of posts to return

        Returns:
            List of Reddit post URLs
        """
        self.logger.info(
            "Fetching posts from r/%s with sort: %s and time filter: %s",
            subreddit_name,
            search_option,
            time_filter,
        )

        subreddit = self.reddit.subreddit(subreddit_name)
        posts = {
            "hot": lambda: subreddit.hot(limit=limit),
            "new": lambda: subreddit.new(limit=limit),
            "top": lambda: subreddit.top(time_filter=time_filter, limit=limit),
        }.get(search_option, lambda: subreddit.hot(limit=limit))()

        urls = [f"https://www.reddit.com{submission.permalink}" for submission in posts]
        self.logger.info("Collected %d URLs from r/%s", len(urls), subreddit_name)
        return urls
    
    def _get_subreddit_posts_webdriver(
        self,
        subreddit_name: str,
        search_option: str,
        time_filter: str,
        limit: Optional[int],
    ) -> List[str]:
        """Get subreddit posts using web scraping.

        Args:
            subreddit_name: Name of the subreddit
            search_option: Sort method for results
            time_filter: Time period to filter results
            limit: Maximum number of posts to return

        Returns:
            List of Reddit post URLs

        Raises:
            RuntimeError: If WebDriver is not initialized
        """
        self.logger.info(
            "Fetching posts from r/%s with sort: %s and time filter: %s",
            subreddit_name,
            search_option,
            time_filter,
        )

        if not self.driver:
            raise RuntimeError("WebDriver not initialized")

        sort_url = f"/{search_option}" if search_option != "hot" else ""
        time_param = (
            f"?t={time_filter}"
            if time_filter != "all" and search_option == "top"
            else ""
        )
        subreddit_url = f"https://www.reddit.com/r/{subreddit_name}{sort_url}{time_param}"

        self.driver.get(subreddit_url)
        try:
            WebDriverWait(self.driver, 30).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "div[data-testid='post-container']")
                )
            )
        except TimeoutException:
            self.logger.warning("Timeout waiting for posts to load. Proceeding anyway.")

        soup = BeautifulSoup(self._lazy_scroll(), "html.parser")
        post_links = soup.find_all("a", href=re.compile(r"^/r/.*?/comments/"))
        base_url = "https://www.reddit.com"

        urls = []
        seen = set()
        for link in post_links:
            full_url = base_url + link["href"]
            if full_url not in seen:
                urls.append(full_url)
                seen.add(full_url)

        self.logger.info("Collected %d unique URLs from r/%s", len(urls), subreddit_name)
        return urls[:limit] if limit else urls
