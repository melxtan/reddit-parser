import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Callable
import json
import logging
import time
import boto3
from botocore.config import Config

logger = logging.getLogger(__name__)

@dataclass
class PromptComponent:
    task: str
    requirements: str
    role: str
    context: str
    protocol: str
    output_format: str

@dataclass
class TaskDefinition:
    name: str
    number: int
    component: PromptComponent

class PromptHandler:
    def __init__(self, prompts_dir: str):
        """
        Initialize PromptHandler with a directory containing XML prompt files.
        
        Args:
            prompts_dir: Directory containing the XML prompt files
        """
        self.prompts_dir = prompts_dir
        self.tasks = self._load_tasks()

    def _load_prompt_file(self, task_name: str) -> PromptComponent:
        """Load and parse a single XML prompt file."""
        file_path = os.path.join(self.prompts_dir, f"{task_name}.xml")
        
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            
            component = PromptComponent(
                task=root.find('task').text.strip(),
                requirements=root.find('requirements').text.strip(),
                role=root.find('role').text.strip(),
                context=root.find('context').text.strip(),
                protocol=root.find('detailed_analysis_protocol').text.strip(),
                output_format=root.find('output_example').text.strip()
            )
            return component
            
        except Exception as e:
            logger.error(f"Error loading prompt file {file_path}: {str(e)}")
            raise

    def _load_tasks(self) -> List[TaskDefinition]:
        """Load all task definitions from XML files."""
        tasks = []
        for task_number, task_name in RedditAnalyzer.TASKS:
            try:
                component = self._load_prompt_file(task_name)
                tasks.append(TaskDefinition(
                    name=task_name,
                    number=task_number,
                    component=component
                ))
            except Exception as e:
                logger.error(f"Failed to load task {task_name}: {str(e)}")
                raise
        
        return tasks

    def format_prompt(self, task_def: TaskDefinition, posts: List[Dict], previous_results: Optional[str] = None) -> str:
        """Format the prompt for a specific task."""
        component = task_def.component
        
        # Get the search query from the first post (assuming all posts have the same search query)
        search_query = posts[0].get('search_query', '') if posts else ''
        
        # Replace {{search_query}} in task text
        task = component.task.replace('{{search_query}}', search_query)
        
        if task_def.name == "correlation_analysis":
            prompt = (
                f"{component.role}\n\n"
                f"Task: {task}\n"
                f"Context: {component.context}\n\n"
                f"Analysis Protocol:\n{component.protocol}\n\n"
                f"You must format your response EXACTLY like this example:\n{component.output_format}\n\n"
                f"Do not deviate from this format or add any additional explanations.\n\n"
                f"Previous analysis results to correlate:\n{previous_results}"
            )
        else:
            prompt = (
                f"{component.role}\n\n"
                f"Task: {task}\n"
                f"Context: {component.context}\n\n"
                f"Requirements:\n{component.requirements}\n\n"
                f"Definitions and Examples:\n{component.protocol}\n\n"
                f"You must format your response EXACTLY like this example:\n{component.output_format}\n\n"
                f"Do not deviate from this format or add any additional explanations.\n\n"
                f"Data to analyze:\n{json.dumps(posts, indent=2)}"
            )
        
        return prompt

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
        
        # Initialize prompt handler with prompts directory
        current_dir = os.path.dirname(os.path.abspath(__file__))
        prompts_dir = os.path.join(current_dir, "prompts")
        self.prompt_handler = PromptHandler(prompts_dir)
        
        self._initialized = True

    def _format_previous_results(self, analysis_results: Dict) -> str:
        formatted_results = "\nPrevious Analysis Results Summary:\n"
        
        for task_def in self.prompt_handler.tasks[:-1]:  # Exclude correlation analysis
            if task_def.name in analysis_results:
                result = analysis_results[task_def.name]["analysis"]
                formatted_results += f"\n{task_def.name}:\n{result}\n"
        
        return formatted_results

    def _rate_limit(self) -> None:
        current_time = time.time()
        self._request_timestamps = [
            ts for ts in self._request_timestamps if current_time - ts < 60
        ]
        
        if len(self._request_timestamps) >= self._max_requests_per_minute:
            sleep_time = 60 - (current_time - self._request_timestamps[0])
            if sleep_time > 0:
                time.sleep(sleep_time)
            self._request_timestamps = self._request_timestamps[1:]

        self._request_timestamps.append(current_time)

    def _clean_response_content(self, response_body: Any) -> str:
        try:
            if isinstance(response_body, dict):
                if "content" in response_body:
                    if isinstance(response_body["content"], list):
                        return response_body["content"][0]["text"] if response_body["content"] else ""
                    elif isinstance(response_body["content"], dict):
                        return response_body["content"].get("text", "")
                    else:
                        return str(response_body["content"])

            return str(response_body)

        except Exception as e:
            logger.error(f"Error cleaning response content: {str(e)}")
            return str(response_body)

    def _analyze_task(self, posts: List[Dict], task_def: TaskDefinition, analysis_results: Dict) -> Dict:
        max_retries = 3
        base_delay = 2

        for attempt in range(max_retries):
            try:
                logger.debug(f"Attempt {attempt + 1}/{max_retries} for task {task_def.name}")
                self._rate_limit()

                previous_results = self._format_previous_results(analysis_results) if task_def.name == "correlation_analysis" else None
                prompt = self.prompt_handler.format_prompt(task_def, posts, previous_results)

                body = {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 4096,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "top_k": 250,
                    "top_p": 0.999,
                    "stop_sequences": [],
                }

                response = self.bedrock.invoke_model(
                    modelId="us.anthropic.claude-3-5-haiku-20241022-v1:0",
                    body=json.dumps(body),
                    accept="application/json",
                    contentType="application/json",
                )

                response_body = json.loads(response["body"].read().decode())
                content = self._clean_response_content(response_body)

                return {
                    "task_name": task_def.name,
                    "task_number": task_def.number,
                    "analysis": content,
                    "posts_analyzed": len(posts)
                }

            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"Final retry failed for task {task_def.name}: {str(e)}")
                    raise

                delay = base_delay * (2**attempt)
                logger.warning(f"Attempt {attempt + 1} failed for task {task_def.name}, retrying in {delay} seconds...")
                time.sleep(delay)

    def analyze_posts(self, posts: List[Dict], callback: Callable[[str, Dict], None], num_top_posts: int = 10) -> None:
        sorted_posts = sorted(posts, key=lambda x: x["score"], reverse=True)
        top_posts = sorted_posts[:num_top_posts]
        
        logger.info(f"Starting analysis of {len(top_posts)} top posts")
        analysis_results = {}

        for task_def in self.prompt_handler.tasks:
            try:
                result = self._analyze_task(top_posts, task_def, analysis_results)
                logger.info(f"Successfully completed {task_def.name}")
                analysis_results[task_def.name] = result
                callback(task_def.name, result)
            except Exception as e:
                logger.error(f"Failed to analyze task {task_def.name}: {str(e)}")
                error_result = {
                    'task_name': task_def.name,
                    'task_number': task_def.number,
                    'error': str(e),
                    'posts_analyzed': 0
                }
                callback(task_def.name, error_result)

def analyze_reddit_data(
    post_data: List[Dict],
    callback: Callable[[str, Dict[str, Any]], None],
    region_name: str = "us-west-2",
    rate_limit_per_second: float = 0.2,
    num_top_posts: int = 10,
    search_query: str = ""  # Add search_query parameter
) -> None:
    # Add search_query to each post
    for post in post_data:
        post['search_query'] = search_query
        
    analyzer = RedditAnalyzer(
        region_name=region_name,
        rate_limit_per_second=rate_limit_per_second
    )
    
    analyzer.analyze_posts(post_data, callback, num_top_posts)
