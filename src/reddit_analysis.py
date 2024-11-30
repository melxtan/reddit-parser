import json
import logging
import time
from collections import defaultdict
from typing import Any, Callable, Dict, List

import boto3
from botocore.config import Config
from prompt_utils import load_prompt

from llm_caller import LLMCaller, LLMConfig

logger = logging.getLogger(__name__)


def prepare_posts_for_llm(posts: List[Dict], min_comment_score: int = 1) -> str:
    # First un-stringify the comments that were JSON stringified
    for post in posts:
        if isinstance(post["comments"], str):
            post["comments"] = json.loads(post["comments"])

        if "created_at" in post:
            post["created_at"] = post["created_at"].split()[
                0
            ]  # Get date part before first space. from "2024-10-31 17:23:59 UTC", to "2024-10-31"

        # Filter out low-score comments and clean up timestamps
        post["comments"] = [
            {
                **comment,
                "created_at": comment["created_at"].split()[0]
                if "created_at" in comment
                else None,
            }
            for comment in post["comments"]
            if comment["score"] >= min_comment_score
        ]

    return json.dumps(posts, ensure_ascii=False, indent=2)


class RedditAnalyzer:
    _instance = None
    TASKS = [
        "post_types_analysis",
        "keyword_pattern_analysis",
        "sentiment_analysis",
        "trend_analysis",
        "proposed_SEO_content_strategies",
    ]

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(
        self, region_name: str = "us-west-2", rate_limit_per_second: float = 0.2
    ) -> None:
        if self._initialized:
            return

        config = Config(
            region_name=region_name,
            retries=dict(max_attempts=8, mode="adaptive"),
        )

        bedrock = boto3.client(
            service_name="bedrock-runtime",
            config=config,
        )

        llm_config = LLMConfig(
            model_id="us.anthropic.claude-3-5-haiku-20241022-v1:0",
        )

        self.llm_caller = LLMCaller(bedrock, llm_config)
        self.rate_limit_per_second = rate_limit_per_second
        self._request_timestamps = []
        self._max_requests_per_minute = 40
        self._initialized = True

    def _rate_limit(self) -> None:
        current_time = time.time()
        self._request_timestamps = [
            ts for ts in self._request_timestamps if current_time - ts < 60
        ]
        logger.debug(
            f"Current request count in last minute: {len(self._request_timestamps)}/{self._max_requests_per_minute}"
        )

        if len(self._request_timestamps) >= self._max_requests_per_minute:
            sleep_time = 60 - (current_time - self._request_timestamps[0])
            if sleep_time > 0:
                time.sleep(sleep_time)
            self._request_timestamps = self._request_timestamps[1:]

        self._request_timestamps.append(current_time)
        logger.debug(
            f"Added new timestamp. Updated count: {len(self._request_timestamps)}"
        )

    def _format_previous_results(self, analysis_results: defaultdict) -> dict[str, str]:
        formatted_results = {}
        for key, result in analysis_results.items():
            analysis_text = result.get("analysis", "")

            # Check if the content is already properly wrapped in correct XML tags
            if not (
                analysis_text.startswith(f"<{key}>")
                and analysis_text.endswith(f"</{key}>")
            ):
                # Wrap the content in appropriate XML tags
                formatted_results[key] = f"<{key}>{analysis_text}</{key}>"
            else:
                formatted_results[key] = analysis_text

        return formatted_results

    def _analyze_task(
        self,
        scraped_info: str,
        posts_analyzed: int,
        task_name: str,
        task_number: int,
        analysis_results: defaultdict,
        search_query: str,
    ) -> Dict[str, Any]:
        max_retries = 3
        base_delay = 2

        variables = {
            "search_query": search_query,
            "scraped_info": scraped_info,
        }
        for attempt in range(max_retries):
            try:
                logger.debug(f"Attempt {attempt + 1}/{max_retries} for task {task_name}")
                self._rate_limit()

                if task_name == "proposed_SEO_content_strategies":
                    variables.update(self._format_previous_results(analysis_results))

                prompt = load_prompt(task_name, variables)
                system_message = load_prompt(f"{task_name}_system")

                logger.debug(f"Prompt length for {task_name}: {len(prompt)} characters")

                response = self.llm_caller.call_with_prefill(
                    system_message=system_message,
                    user_message=prompt,
                    assistant_prefill=f"<{task_name}>",
                    trace_name=f"{task_name}-attempt-{attempt+1}",
                )

                result = {
                    "task_name": task_name,
                    "task_number": task_number,
                    "analysis": response.content,
                    "posts_analyzed": posts_analyzed,
                }
                logger.info(
                    f"Successfully completed task {task_name} on attempt {attempt + 1}"
                )

                analysis_results[task_name] = result
                return result

            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"Final retry failed for task {task_name}: {str(e)}")
                    raise

                delay = base_delay * (2**attempt)
                logger.warning(
                    f"Attempt {attempt + 1} failed for task {task_name}, retrying in {delay} seconds..."
                )
                time.sleep(delay)
                continue

    def analyze_posts(
        self,
        posts: List[Dict],
        search_query: str,
        callback: Callable[[str, Dict[str, Any]], None],
        num_top_posts: int = 10,
        min_comment_score: int = 1,
    ) -> None:
        sorted_posts = sorted(posts, key=lambda x: x["score"], reverse=True)
        top_posts = sorted_posts[:num_top_posts]

        logger.info(f"Starting analysis of {len(top_posts)} top posts")

        scraped_info = prepare_posts_for_llm(
            top_posts, min_comment_score=min_comment_score
        )
        logger.info(f"Scraped info length: {len(scraped_info)}")
        analysis_results = defaultdict(dict)

        for task_number, task_name in enumerate(RedditAnalyzer.TASKS):
            try:
                result = self._analyze_task(
                    scraped_info,
                    len(top_posts),
                    task_name,
                    task_number + 1,
                    analysis_results,
                    search_query,
                )
                logger.info(f"Successfully completed {task_name}")
                callback(task_name, result)
            except Exception as e:
                logger.error(f"Failed to analyze task {task_name}: {str(e)}")
                error_result = {
                    "task_name": task_name,
                    "task_number": task_number,
                    "error": str(e),
                    "posts_analyzed": 0,
                }
                callback(task_name, error_result)


def analyze_reddit_data(
    post_data: List[Dict],
    search_query: str,
    callback: Callable[[str, Dict[str, Any]], None],
    region_name: str = "us-west-2",
    rate_limit_per_second: float = 0.2,
    num_top_posts: int = 10,
    min_comment_score: int = 1,
) -> None:
    analyzer = RedditAnalyzer(
        region_name=region_name,
        rate_limit_per_second=rate_limit_per_second,
    )
    analyzer.analyze_posts(
        post_data, search_query, callback, num_top_posts, min_comment_score
    )
