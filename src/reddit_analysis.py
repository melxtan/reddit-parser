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
        pattern = f"<{tag}>(.*?)</{tag}>"
        match = re.search(pattern, content, re.DOTALL)
        return match.group(1).strip() if match else ""

    def _extract_task_components(self, task_name: str) -> Dict[str, str]:
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

    def _format_previous_results(self) -> str:
        """Format previous results in a concise way for correlation analysis"""
        formatted_results = "\nPrevious Analysis Results Summary:\n"
        
        # Map of tasks to their relevant sections
        task_sections = {
            "title_and_post_text_analysis": ["Purpose"],
            "language_feature_extraction": ["Descriptive adjective", "Product needs description phrases", "Professional terminology usage"],
            "sentiment_color_tracking": ["Overall_sentiment", "Contextual sentiment interpretation"],
            "trend_analysis": ["Post publication time distribution", "Comment peak periods", "Discussion activity variations", "Trend Prediction"]
        }
        
        for task_name, sections in task_sections.items():
            if task_name in self.analysis_results:
                result = self.analysis_results[task_name]['analysis']
                formatted_results += f"\n{task_name}:\n"
                
                # Extract relevant sections using regex
                for section in sections:
                    pattern = f"{section}.*?(?=\n\n|\Z)"
                    matches = re.findall(pattern, result, re.DOTALL)
                    if matches:
                        # Convert matches[0] to string if it's a list
                        section_content = str(matches[0]) if isinstance(matches[0], list) else matches[0]
                        formatted_results += f"- {section_content.strip()}\n"
        
        return formatted_results

    def _clean_response_content(self, response_body) -> str:
        """Clean and extract text content from API response"""
        try:
            # Handle dictionary response
            if isinstance(response_body, dict):
                if 'content' in response_body:
                    if isinstance(response_body['content'], list):
                        return response_body['content'][0]['text'] if response_body['content'] else ''
                    elif isinstance(response_body['content'], dict):
                        return response_body['content'].get('text', '')
                    else:
                        return str(response_body['content'])
                
                # Handle messages format
                if 'messages' in response_body and response_body['messages']:
                    message = response_body['messages'][0]
                    if isinstance(message, dict):
                        if 'content' in message:
                            if isinstance(message['content'], list):
                                return message['content'][0]['text'] if message['content'] else ''
                            elif isinstance(message['content'], dict):
                                return message['content'].get('text', '')
                            else:
                                return str(message['content'])
            
            # Handle list response
            elif isinstance(response_body, list) and response_body:
                first_item = response_body[0]
                if isinstance(first_item, dict):
                    if 'text' in first_item:
                        return first_item['text']
                    elif 'content' in first_item:
                        return first_item['content']
            
            # If we can't parse it in a specific way, convert to string
            return str(response_body)
            
        except Exception as e:
            logger.error(f"Error cleaning response content: {str(e)}")
            return str(response_body)

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
                
                # Create different prompts for correlation vs other tasks
                if task_name == "correlation_analysis":
                    try:
                        previous_results = self._format_previous_results()
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
                
                # Log prompt length for debugging
                logger.debug(f"Prompt length for {task_name}: {len(prompt)} characters")
                
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
                    modelId="anthropic.claude-3-5-haiku-20241022-v1:0",
                    body=json.dumps(body),
                    accept="application/json",
                    contentType="application/json"
                )
                
                response_body = json.loads(response['body'].read().decode())
                
                # Clean the response content
                content = self._clean_response_content(response_body)
                
                result = {
                    'task_name': task_name,
                    'task_number': task_number,
                    'analysis': content,
                    'posts_analyzed': len(posts)
                }
                
                # Store the result
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
