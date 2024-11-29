import json
import logging
import os
import re
import time
from collections import defaultdict
from typing import Any, Callable, Dict, List

import boto3
from botocore.config import Config
from prompt_utils import load_prompt

logger = logging.getLogger(__name__)

class RedditAnalyzer:
    _instance = None
    TASKS = [
        (1, "title_and_post_text_analysis"),
        (2, "language_feature_extraction"),
        (3, "sentiment_color_tracking"),
        (4, "trend_analysis"),
        (5, "correlation_analysis"),
    ]

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, region_name: str = "us-west-2", rate_limit_per_second: float = 0.2) -> None:
        if self._initialized:
            return

        config = Config(
            region_name=region_name,
            retries=dict(
                max_attempts=8,
                mode="adaptive"
            )
        )
        
        self.bedrock = boto3.client(
            service_name="bedrock-runtime",
            config=config
        )
        
        self.rate_limit_per_second = rate_limit_per_second
        self._request_timestamps = []
        self._max_requests_per_minute = 40  # AWS quota
        self._initialized = True

    def _extract_tag_content(self, content: str, tag: str) -> str:
        pattern = f"<{tag}>(.*?)</{tag}>"
        match = re.search(pattern, content, re.DOTALL)
        return match.group(1).strip() if match else ""

    def _extract_task_components(self, task_name: str) -> Dict[str, str]:
        try:
            # Load the prompt template for the specific task
            task_content = load_prompt(task_name)
            
            components = {
                "task": self._extract_tag_content(task_content, "task"),
                "requirements": self._extract_tag_content(task_content, "requirements"),
                "role": self._extract_tag_content(task_content, "role"),
                "context": self._extract_tag_content(task_content, "context"),
                "protocol": self._extract_tag_content(
                    task_content, "detailed_analysis_protocol"
                ),
                "output_format": self._extract_tag_content(task_content, "output_example"),
            }

            return components
            
        except Exception as e:
            logger.error(f"Error extracting task components: {str(e)}")
            raise

    def _rate_limit(self) -> None:
        current_time = time.time()
        # Remove timestamps older than 1 minute
        self._request_timestamps = [
            ts for ts in self._request_timestamps if current_time - ts < 60
        ]
        logger.debug(
            f"Current request count in last minute: {len(self._request_timestamps)}/{self._max_requests_per_minute}"
        )

        if len(self._request_timestamps) >= self._max_requests_per_minute:
            # Wait until we have capacity
            sleep_time = 60 - (current_time - self._request_timestamps[0])
            if sleep_time > 0:
                time.sleep(sleep_time)
            self._request_timestamps = self._request_timestamps[1:]

        self._request_timestamps.append(current_time)
        logger.debug(
            f"Added new timestamp. Updated count: {len(self._request_timestamps)}"
        )

    def _format_previous_results(self, analysis_results: defaultdict) -> str:
        formatted_results = "\nPrevious Analysis Results Summary:\n"

        task_sections = {
            "title_and_post_text_analysis": ["Purpose"],
            "language_feature_extraction": [
                "Descriptive adjective",
                "Product needs description phrases",
                "Professional terminology usage",
            ],
            "sentiment_color_tracking": [
                "Overall_sentiment",
                "Contextual sentiment interpretation",
            ],
            "trend_analysis": [
                "Post publication time distribution",
                "Comment peak periods",
                "Discussion activity variations",
                "Trend Prediction",
            ],
        }

        for task_name, sections in task_sections.items():
            if task_name in analysis_results:
                result = analysis_results[task_name]["analysis"]
                formatted_results += f"\n{task_name}:\n"

                for section in sections:
                    pattern = rf"{section}.*?(?=\n\n|$)"
                    matches = re.findall(pattern, result, re.DOTALL)
                    if matches:
                        section_content = (
                            str(matches[0])
                            if isinstance(matches[0], list)
                            else matches[0]
                        )
                        formatted_results += f"- {section_content.strip()}\n"

        return formatted_results

    def _clean_response_content(self, response_body: Any) -> str:
        try:
            if isinstance(response_body, dict):
                if "content" in response_body:
                    if isinstance(response_body["content"], list):
                        return (
                            response_body["content"][0]["text"]
                            if response_body["content"]
                            else ""
                        )
                    elif isinstance(response_body["content"], dict):
                        return response_body["content"].get("text", "")
                    else:
                        return str(response_body["content"])

                if "messages" in response_body and response_body["messages"]:
                    message = response_body["messages"][0]
                    if isinstance(message, dict):
                        if "content" in message:
                            if isinstance(message["content"], list):
                                return (
                                    message["content"][0]["text"]
                                    if message["content"]
                                    else ""
                                )
                            elif isinstance(message["content"], dict):
                                return message["content"].get("text", "")
                            else:
                                return str(message["content"])

            elif isinstance(response_body, list) and response_body:
                first_item = response_body[0]
                if isinstance(first_item, dict):
                    if "text" in first_item:
                        return first_item["text"]
                    elif "content" in first_item:
                        return first_item["content"]

            return str(response_body)

        except Exception as e:
            logger.error(f"Error cleaning response content: {str(e)}")
            return str(response_body)

    def _analyze_task(
        self,
        posts: List[Dict],
        task_name: str,
        task_number: int,
        analysis_results: defaultdict,
    ) -> Dict[str, Any]:
        max_retries = 3
        base_delay = 2

        try:
            components = self._extract_task_components(task_name)
        except ValueError as e:
            logger.error(f"Error extracting task components: {str(e)}")
            raise

        for attempt in range(max_retries):
            try:
                logger.debug(
                    f"Attempt {attempt + 1}/{max_retries} for task {task_name}"
                )
                self._rate_limit()

                if task_name == "correlation_analysis":
                    try:
                        previous_results = self._format_previous_results(
                            analysis_results
                        )
                        prompt = (
                            f"{components['role']}\n\n"
                            f"Task: {components['task']}\n"
                            f"Context: {components['context']}\n\n"
                            f"Analysis Protocol:\n{components['protocol']}\n\n"
                            f"You must format your response EXACTLY like this example:\n{components['output_format']}\n\n"
                            f"Do not deviate from this format or add any additional explanations.\n\n"
                            f"Previous analysis results to correlate:\n{previous_results}"
                        )
                    except Exception as e:
                        logger.error(f"Error formatting previous results: {str(e)}")
                        raise
                else:
                    prompt = (
                        f"{components['role']}\n\n"
                        f"Task: {components['task']}\n"
                        f"Context: {components['context']}\n\n"
                        f"Analysis Protocol:\n{components['protocol']}\n\n"
                        f"You must format your response EXACTLY like this example:\n{components['output_format']}\n\n"
                        f"Do not deviate from this format or add any additional explanations.\n\n"
                        f"Data to analyze:\n{json.dumps(posts, indent=2)}"
                    )

                logger.debug(f"Prompt length for {task_name}: {len(prompt)} characters")

                body = {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 4096,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "top_k": 250,
                    "top_p": 0.999,
                    "stop_sequences": [],
                }

                logger.debug(f"Sending request to Bedrock for task {task_name}")
                response = self.bedrock.invoke_model(
                    modelId="us.anthropic.claude-3-5-haiku-20241022-v1:0",
                    body=json.dumps(body),
                    accept="application/json",
                    contentType="application/json",
                )
                logger.debug(f"Received response from Bedrock for task {task_name}")

                response_body = json.loads(response["body"].read().decode())
                content = self._clean_response_content(response_body)

                result = {
                    "task_name": task_name,
                    "task_number": task_number,
                    "analysis": content,
                    "posts_analyzed": len(posts),
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
        callback: Callable[[str, Dict[str, Any]], None],
        num_top_posts: int = 10,
    ) -> None:
        sorted_posts = sorted(posts, key=lambda x: x["score"], reverse=True)
        top_posts = sorted_posts[:num_top_posts]

        logger.info(f"Starting analysis of {len(top_posts)} top posts")

        analysis_results = defaultdict(dict)

        for task_number, task_name in RedditAnalyzer.TASKS:
            try:
                result = self._analyze_task(
                    top_posts, task_name, task_number, analysis_results
                )
                logger.info(f"Successfully completed {task_name}")
                callback(task_name, result)
            except Exception as e:
                logger.error(f"Failed to analyze task {task_name}: {str(e)}")
                error_result = {
                    'task_name': task_name,
                    'task_number': task_number,
                    'error': str(e),
                    'posts_analyzed': 0
                }
                callback(task_name, error_result)

def analyze_reddit_data(
    post_data: List[Dict],
    callback: Callable[[str, Dict[str, Any]], None],
    region_name: str = "us-west-2",
    rate_limit_per_second: float = 0.2,
    num_top_posts: int = 10
) -> None:
    analyzer = RedditAnalyzer(
        region_name=region_name,
        rate_limit_per_second=rate_limit_per_second
    )
    
    analyzer.analyze_posts(post_data, callback, num_top_posts)
