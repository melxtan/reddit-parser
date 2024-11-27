import json
import logging
import time
from typing import List, Dict, Callable, Tuple
import boto3
from botocore.config import Config
import re
from collections import defaultdict

# Configure logging
logger = logging.getLogger(__name__)

class RedditAnalyzer:
    def __init__(self, region_name="us-west-2", rate_limit_per_second=0.2):
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
        self._last_request_time = 0
        self.template = self._load_prompt_template()
        
        # Store results from previous tasks
        self.analysis_results = defaultdict(dict)
        
        self.tasks = [
            (1, "title_and_post_text_analysis"),
            (2, "language_feature_extraction"),
            (3, "sentiment_color_tracking"),
            (4, "trend_analysis"),
            (5, "correlation_analysis")
        ]

    def _load_prompt_template(self):
        try:
            with open('prompts.txt', 'r', encoding='utf-8') as file:
                return file.read()
        except Exception as e:
            logger.error(f"Error loading template: {str(e)}")
            raise

    def _extract_tag_content(self, content: str, tag: str) -> str:
        """Extract content between specified XML tags"""
        pattern = f"<{tag}>(.*?)</{tag}>"
        match = re.search(pattern, content, re.DOTALL)
        return match.group(1).strip() if match else ""

    def _extract_task_components(self, task_name: str) -> Dict[str, str]:
        """Extract all components of a task section"""
        task_pattern = f"<{task_name}>(.*?)</{task_name}>"
        task_match = re.search(task_pattern, self.template, re.DOTALL)
        
        if not task_match:
            raise ValueError(f"Could not find task section for {task_name}")
            
        task_content = task_match.group(1).strip()
        
        components = {
            'task': self._extract_tag_content(task_content, 'task'),
            'requirements': self._extract_tag_content(task_content, 'requirements'),
            'role': self._extract_tag_content(task_content, 'role'),
            'context': self._extract_tag_content(task_content, 'context'),
            'protocol': self._extract_tag_content(task_content, 'detailed_analysis_protocol'),
            'output_format': self._extract_tag_content(task_content, 'output_example')
        }
        
        return components

    def _rate_limit(self):
        current_time = time.time()
        time_since_last_request = current_time - self._last_request_time
        if time_since_last_request < (1 / self.rate_limit_per_second):
            sleep_time = (1 / self.rate_limit_per_second) - time_since_last_request
            time.sleep(sleep_time)
        self._last_request_time = time.time()

    def _analyze_task(self, posts: List[Dict], task_name: str, task_number: int) -> Dict:
        max_retries = 8
        base_delay = 10
        
        try:
            components = self._extract_task_components(task_name)
        except ValueError as e:
            logger.error(f"Error extracting task components: {str(e)}")
            raise
        
        for attempt in range(max_retries):
            try:
                self._rate_limit()
                
                # For correlation analysis, include results from previous tasks
                previous_results = ""
                if task_name == "correlation_analysis":
                    previous_results = "\nPrevious analysis results:\n"
                    for prev_task in ["title_and_post_text_analysis", "language_feature_extraction", 
                                    "sentiment_color_tracking", "trend_analysis"]:
                        if prev_task in self.analysis_results:
                            previous_results += f"\n{prev_task} results:\n"
                            previous_results += self.analysis_results[prev_task]['analysis']
                            previous_results += "\n"
                
                prompt = (
                    f"{components['role']}\n\n"
                    f"Task: {components['task']}\n"
                    f"Context: {components['context']}\n\n"
                    f"Requirements: {components['requirements']}\n\n"
                    f"Analysis Protocol:\n{components['protocol']}\n\n"
                    f"You must format your response EXACTLY like this example:\n{components['output_format']}\n\n"
                    f"Do not deviate from this format or add any additional explanations.\n\n"
                    f"Data to analyze:\n{json.dumps(posts, indent=2)}"
                    f"{previous_results}"  # Include previous results for correlation analysis
                )
                
                body = {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 4096,
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "temperature": 0.3,
                    "top_k": 250,
                    "top_p": 0.999,
                    "stop_sequences": []
                }
                
                response = self.bedrock.invoke_model(
                    modelId="anthropic.claude-3-haiku-20240307-v1:0",
                    body=json.dumps(body),
                    accept="application/json",
                    contentType="application/json"
                )
                
                response_body = json.loads(response['body'].read().decode())
                
                result = {
                    'task_name': task_name,
                    'task_number': task_number,
                    'analysis': response_body['content'] if isinstance(response_body, dict) and 'content' in response_body else response_body['messages'][0]['content'],
                    'posts_analyzed': len(posts)
                }
                
                # Store the result for potential use in correlation analysis
                self.analysis_results[task_name] = result
                
                return result
                
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"Final retry failed for task {task_name}: {str(e)}")
                    raise
                
                delay = base_delay * (2 ** attempt)
                logger.warning(f"Attempt {attempt + 1} failed for task {task_name}, retrying in {delay} seconds...")
                time.sleep(delay)
            
    def analyze_posts(self, posts: List[Dict], callback: Callable[[str, Dict], None], num_top_posts: int = 20):
        """Analyze Reddit posts sequentially and call the callback with results as they complete"""
        sorted_posts = sorted(posts, key=lambda x: x['score'], reverse=True)
        top_posts = sorted_posts[:num_top_posts]
        
        logger.info(f"Starting analysis of {len(top_posts)} top posts")
        
        # Clear previous results at the start of a new analysis
        self.analysis_results.clear()
        
        for task_number, task_name in self.tasks:
            try:
                result = self._analyze_task(top_posts, task_name, task_number)
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

def analyze_reddit_data(post_data: List[Dict], 
                       callback: Callable[[str, Dict], None],
                       region_name: str = "us-west-2",
                       rate_limit_per_second: float = 0.2,
                       num_top_posts: int = 10):
    analyzer = RedditAnalyzer(
        region_name=region_name,
        rate_limit_per_second=rate_limit_per_second
    )
    
    analyzer.analyze_posts(post_data, callback, num_top_posts)
