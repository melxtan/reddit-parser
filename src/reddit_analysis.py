import json
import logging
import time
from typing import List, Dict
import boto3
from botocore.config import Config

# Configure logging
logger = logging.getLogger(__name__)

class RedditAnalyzer:
    def __init__(self, region_name="us-west-2", rate_limit_per_second=0.5):
        config = Config(
            region_name=region_name,
            retries=dict(
                max_attempts=5,
                mode="adaptive"
            )
        )
        
        self.bedrock = boto3.client(
            service_name="bedrock-runtime",
            config=config
        )
        
        self.rate_limit_per_second = rate_limit_per_second
        self._last_request_time = 0
        
        # Load template during initialization
        self.template = self._load_prompt_template()
        
        # Define tasks
        self.tasks = [
            (1, "title_and_post_text_analysis"),
            (2, "language_feature_extraction"),
            (3, "sentiment_color_tracking"),
            (4, "trend_analysis"),
            (5, "correlation_analysis")
        ]

    def _load_prompt_template(self):
        """Load the prompt template from current directory"""
        try:
            with open('prompts.txt', 'r', encoding='utf-8') as file:
                return file.read()
        except Exception as e:
            logger.error(f"Error loading template: {str(e)}")
            raise

    def _rate_limit(self):
        """Implement rate limiting with wait"""
        current_time = time.time()
        time_since_last_request = current_time - self._last_request_time
        if time_since_last_request < (1 / self.rate_limit_per_second):
            sleep_time = (1 / self.rate_limit_per_second) - time_since_last_request
            time.sleep(sleep_time)
        self._last_request_time = time.time()

    def _analyze_task(self, posts: List[Dict], task_name: str, task_number: int) -> Dict:
        """Analyze a set of Reddit posts for a specific task with exponential backoff"""
        max_retries = 5
        base_delay = 4
        
        for attempt in range(max_retries):
            try:
                self._rate_limit()
                
                body = {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 4096,
                    "messages": [
                        {
                            "role": "user",
                            "content": f"Please analyze this Reddit data according to the following protocol:\n\n{json.dumps(posts, indent=2)}\n\nProtocol:\nTask {task_number}: {self.template.split('\n')[task_number-1]}"
                        }
                    ],
                    "temperature": 0.7,
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
                
                return {
                    'task_name': task_name,
                    'task_number': task_number,
                    'analysis': response_body['content'] if isinstance(response_body, dict) and 'content' in response_body else response_body['messages'][0]['content'],
                    'posts_analyzed': len(posts)
                }
                
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"Final retry failed for task {task_name}: {str(e)}")
                    raise
                
                delay = base_delay * (2 ** attempt)
                logger.warning(f"Attempt {attempt + 1} failed for task {task_name}, retrying in {delay} seconds...")
                time.sleep(delay)
            
    def analyze_posts(self, posts: List[Dict], num_top_posts: int = 20) -> Dict[str, Dict]:
        """Analyze Reddit posts sequentially with individual task results"""
        # Sort posts by score
        sorted_posts = sorted(posts, key=lambda x: x['score'], reverse=True)
        top_posts = sorted_posts[:num_top_posts]
        
        results = {}
        logger.info(f"Starting analysis of {len(top_posts)} top posts")
        
        for task_number, task_name in self.tasks:
            try:
                result = self._analyze_task(top_posts, task_name, task_number)
                results[task_name] = result
                logger.info(f"Successfully completed {task_name}")
            except Exception as e:
                logger.error(f"Failed to analyze task {task_name}: {str(e)}")
                results[task_name] = {
                    'task_name': task_name,
                    'task_number': task_number,
                    'error': str(e),
                    'posts_analyzed': 0
                }
                
        return results

def analyze_reddit_data(post_data: List[Dict], 
                       region_name: str = "us-west-2",
                       rate_limit_per_second: float = 0.5,
                       num_top_posts: int = 20) -> Dict[str, Dict]:
    analyzer = RedditAnalyzer(
        region_name=region_name,
        rate_limit_per_second=rate_limit_per_second
    )
    
    return analyzer.analyze_posts(post_data, num_top_posts)
