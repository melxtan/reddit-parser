import json
import logging
import time
from typing import List, Dict
import boto3
from botocore.config import Config
import tenacity
import streamlit as st

# Configure logging
logger = logging.getLogger(__name__)

class RedditAnalyzer:
    def __init__(self, region_name="us-west-2", rate_limit_per_second=2, rate_limit_sleep_time=10, max_retries=5, retry_backoff_factor=2):
        config = Config(
            region_name=region_name,
            retries=dict(
                max_attempts=max_retries,
                mode="standard"
            )
        )
        
        self.bedrock = boto3.client(
            service_name="bedrock-runtime",
            config=config
        )
        
        self.rate_limit_per_second = rate_limit_per_second
        self.rate_limit_sleep_time = rate_limit_sleep_time
        self.max_retries = max_retries
        self.retry_backoff_factor = retry_backoff_factor
        self._last_request_time = 0
        
        # Load template during initialization
        self.template = self._load_prompt_template()

    def _load_prompt_template(self):
        """Load the prompt template from current directory"""
        try:
            with open('prompts.txt', 'r', encoding='utf-8') as file:
                return file.read()
        except Exception as e:
            logger.error(f"Error loading template: {str(e)}")
            raise

    def _rate_limit(self):
        current_time = time.time()
        time_since_last_request = current_time - self._last_request_time
        if time_since_last_request < (1 / self.rate_limit_per_second):
            time.sleep(self.rate_limit_sleep_time)
        self._last_request_time = time.time()

    @tenacity.retry(
        stop=tenacity.stop_after_attempt(self.max_retries),
        wait=tenacity.wait_exponential(multiplier=self.retry_backoff_factor, min=4, max=60),
        retry=tenacity.retry_if_exception_type(Exception),
        before_sleep=lambda retry_state: logger.info(f"Retrying after {retry_state.next_action.sleep} seconds...")
    )
    def _analyze_task(self, posts: List[Dict], task_number: int) -> Dict:
        """Analyze a set of Reddit posts for a specific task"""
        self._rate_limit()
        
        try:
            # Get the subreddit from the first post in the list
            search_query = posts[0].get('subreddit', '') if posts else ''
            
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
            logger.info(f"Response structure: {json.dumps(response_body, indent=2)}")
            
            return {
                'task_number': task_number,
                'analysis': response_body['content'] if isinstance(response_body, dict) and 'content' in response_body else response_body['messages'][0]['content'],
                'posts_analyzed': len(posts)
            }
            
        except Exception as e:
            logger.error(f"Error in _analyze_task: {str(e)}")
            logger.error(f"Error type: {type(e).__name__}")
            raise

    def analyze_posts(self, posts: List[Dict], num_top_posts: int = 20) -> List[Dict]:
        """Analyze the top N Reddit posts based on score, highest to lowest"""
        # Sort the posts by score, highest to lowest
        posts = sorted(posts, key=lambda x: x['score'], reverse=True)
        top_posts = posts[:num_top_posts]

        results = []
        
        logger.info(f"Starting analysis of {len(top_posts)} top posts")
        
        for task_number in range(1, 6):
            if task_number == 1:
                st.info("Starting Title and Post Text Analysis...")
            elif task_number == 2:
                st.info("Starting Language Feature Extraction...")
            elif task_number == 3:
                st.info("Starting Sentiment Color Tracking...")
            elif task_number == 4:
                st.info("Starting Trend Analysis...")
            elif task_number == 5:
                st.info("Starting Correlation Analysis...")
            
            try:
                analysis = self._analyze_task(top_posts, task_number)
                results.append(analysis)
                logger.info(f"Successfully analyzed task {task_number} with {analysis.get('posts_analyzed', 0)} posts")
            except Exception as e:
                logger.error(f"Failed to analyze task {task_number}: {str(e)}")
                
        return results

def analyze_reddit_data(post_data: List[Dict], 
                       region_name: str = "us-west-2",
                       rate_limit_per_second: int = 2,
                       rate_limit_sleep_time: int = 10,
                       max_retries: int = 5,
                       retry_backoff_factor: int = 2,
                       num_top_posts: int = 20) -> List[Dict]:
    analyzer = RedditAnalyzer(
        region_name=region_name,
        rate_limit_per_second=rate_limit_per_second,
        rate_limit_sleep_time=rate_limit_sleep_time,
        max_retries=max_retries,
        retry_backoff_factor=retry_backoff_factor
    )
    
    return analyzer.analyze_posts(post_data, num_top_posts)
