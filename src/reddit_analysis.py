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
    def __init__(self, region_name="us-west-2", rate_limit_per_second=2, rate_limit_sleep_time=10):
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
        self.rate_limit_sleep_time = rate_limit_sleep_time
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
        stop=tenacity.stop_after_attempt(5),
        wait=tenacity.wait_exponential(multiplier=1, min=4, max=60),
        retry=tenacity.retry_if_exception_type(Exception),
        before_sleep=lambda retry_state: logger.info(f"Retrying after {retry_state.next_action.sleep} seconds...")
    )
    
    def _title_and_post_text_analysis(self, posts: List[Dict]) -> Dict:
        """Analyze the title and post text"""
        self._rate_limit()
        st.info("Running Title and Post Text Analysis...")
        
        try:
            # Get the subreddit from the first post in the list
            search_query = posts[0].get('subreddit', '') if posts else ''
            
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 4096,
                "messages": [
                    {
                        "role": "user",
                        "content": f"Please analyze this Reddit data according to the following protocol:\n\n{json.dumps(posts, indent=2)}\n\nProtocol:\n{self.template.split('<title_and_post_text_analysis>')[1].split('</title_and_post_text_analysis>')[0]}"
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
                'task_number': 1,
                'analysis': response_body['content'] if isinstance(response_body, dict) and 'content' in response_body else response_body['messages'][0]['content'],
                'posts_analyzed': len(posts)
            }
            
        except Exception as e:
            logger.error(f"Error in _title_and_post_text_analysis: {str(e)}")
            logger.error(f"Error type: {type(e).__name__}")
            raise

    def _language_feature_extraction(self, posts: List[Dict]) -> Dict:
        """Analyze language features"""
        self._rate_limit()
        st.info("Running Language Feature Extraction...")
        
        try:
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 4096,
                "messages": [
                    {
                        "role": "user",
                        "content": f"Please analyze this Reddit data according to the following protocol:\n\n{json.dumps(posts, indent=2)}\n\nProtocol:\n{self.template.split('<language_feature_extraction>')[1].split('</language_feature_extraction>')[0]}"
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
                'task_number': 2,
                'analysis': response_body['content'] if isinstance(response_body, dict) and 'content' in response_body else response_body['messages'][0]['content'],
                'posts_analyzed': len(posts)
            }
            
        except Exception as e:
            logger.error(f"Error in _language_feature_extraction: {str(e)}")
            logger.error(f"Error type: {type(e).__name__}")
            raise

    def _sentiment_color_tracking(self, posts: List[Dict]) -> Dict:
        """Analyze sentiment"""
        self._rate_limit()
        st.info("Running Sentiment Color Tracking...")
        
        try:
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 4096,
                "messages": [
                    {
                        "role": "user",
                        "content": f"Please analyze this Reddit data according to the following protocol:\n\n{json.dumps(posts, indent=2)}\n\nProtocol:\n{self.template.split('<sentiment_color_tracking>')[1].split('</sentiment_color_tracking>')[0]}"
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
                'task_number': 3,
                'analysis': response_body['content'] if isinstance(response_body, dict) and 'content' in response_body else response_body['messages'][0]['content'],
                'posts_analyzed': len(posts)
            }
            
        except Exception as e:
            logger.error(f"Error in _sentiment_color_tracking: {str(e)}")
            logger.error(f"Error type: {type(e).__name__}")
            raise

    def _trend_analysis(self, posts: List[Dict]) -> Dict:
        """Analyze trends"""
        self._rate_limit()
        st.info("Running Trend Analysis...")
        
        try:
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 4096,
                "messages": [
                    {
                        "role": "user",
                        "content": f"Please analyze this Reddit data according to the following protocol:\n\n{json.dumps(posts, indent=2)}\n\nProtocol:\n{self.template.split('<trend_analysis>')[1].split('</trend_analysis>')[0]}"
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
                'task_number': 4,
                'analysis': response_body['content'] if isinstance(response_body, dict) and 'content' in response_body else response_body['messages'][0]['content'],
                'posts_analyzed': len(posts)
            }
            
        except Exception as e:
            logger.error(f"Error in _trend_analysis: {str(e)}")
            logger.error(f"Error type: {type(e).__name__}")
            raise

    def _correlation_analysis(self, posts: List[Dict]) -> Dict:
        """Analyze correlations"""
        self._rate_limit()
        st.info("Running Correlation Analysis...")
        
        try:
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 4096,
                "messages": [
                    {
                        "role": "user",
                        "content": f"Please analyze this Reddit data according to the following protocol:\n\n{json.dumps(posts, indent=2)}\n\nProtocol:\n{self.template.split('<correlation_analysis>')[1].split('</correlation_analysis>')[0]}"
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
                'task_number': 5,
                'analysis': response_body['content'] if isinstance(response_body, dict) and 'content' in response_body else response_body['messages'][0]['content'],
                'posts_analyzed': len(posts)
            }
            
        except Exception as e:
            logger.error(f"Error in _correlation_analysis: {str(e)}")
            logger.error(f"Error type: {type(e).__name__}")
            raise

    def analyze_posts(self, posts: List[Dict], num_top_posts: int = 20) -> List[Dict]:
        """Analyze the top N Reddit posts based on score, highest to lowest"""
        # Sort the posts by score, highest to lowest
        posts = sorted(posts, key=lambda x: x['score'], reverse=True)
        top_posts = posts[:num_top_posts]

        results = []
        
        logger.info(f"Starting analysis of {len(top_posts)} top posts")
        
        title_and_post_text_analysis = self._title_and_post_text_analysis(top_posts)
        results.append(title_and_post_text_analysis)
        
        language_feature_extraction = self._language_feature_extraction(top_posts)
        results.append(language_feature_extraction)
        
        sentiment_color_tracking = self._sentiment_color_tracking(top_posts)
        results.append(sentiment_color_tracking)
        
        trend_analysis = self._trend_analysis(top_posts)
        results.append(trend_analysis)
        
        correlation_analysis = self._correlation_analysis(top_posts)
        results.append(correlation_analysis)
        
        return results

def analyze_reddit_data(post_data: List[Dict], 
                       region_name: str = "us-west-2",
                       rate_limit_per_second: int = 2,
                       rate_limit_sleep_time: int = 10,
                       num_top_posts: int = 20) -> List[Dict]:
    analyzer = RedditAnalyzer(
        region_name=region_name,
        rate_limit_per_second=rate_limit_per_second,
        rate_limit_sleep_time=rate_limit_sleep_time
    )
    
    return analyzer.analyze_posts(post_data, num_top_posts)
