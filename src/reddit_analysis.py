import json
import logging
import time
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict
import boto3
from botocore.config import Config
import tenacity
from pybars import Compiler

# Configure logging
logger = logging.getLogger(__name__)

class RedditAnalyzer:
    def __init__(self, region_name="us-east-1", max_workers=5, rate_limit_per_second=2):
        # Configure boto3 client with retry configuration
        config = Config(
            region_name=region_name,
            retries=dict(
                max_attempts=10,
                mode="adaptive"
            )
        )
        
        self.bedrock = boto3.client(
            service_name="bedrock-runtime",
            config=config
        )
        
        self.max_workers = max_workers
        self.rate_limit_per_second = rate_limit_per_second
        self._last_request_time = 0
        
        # Load template during initialization
        self.template = self._load_prompt_template()

    def _load_prompt_template(self):
        """Load and compile the Handlebars template"""
        try:
            # Try multiple possible locations for the template
            possible_paths = [
                'prompt.hbs',  # Current directory
                os.path.join(os.path.dirname(__file__), 'prompt.hbs'),  # Same directory as script
                os.path.join(os.path.dirname(__file__), '..', 'prompt.hbs'),  # Parent directory
                os.path.join('src', 'prompt.hbs'),  # src directory
            ]
            
            template_content = None
            template_path = None
            
            for path in possible_paths:
                try:
                    if os.path.exists(path):
                        with open(path, 'r', encoding='utf-8') as file:
                            template_content = file.read()
                            template_path = path
                            logger.info(f"Found template at: {path}")
                            break
                except Exception as e:
                    logger.debug(f"Couldn't load template from {path}: {str(e)}")
            
            if template_content is None:
                raise FileNotFoundError(
                    f"Could not find prompt.hbs in any of these locations: {', '.join(possible_paths)}"
                )
            
            compiler = Compiler()
            return compiler.compile(template_content)
            
        except Exception as e:
            logger.error(f"Error loading template: {str(e)}")
            raise

    def _rate_limit(self):
        """Implement rate limiting"""
        current_time = time.time()
        time_since_last_request = current_time - self._last_request_time
        if time_since_last_request < (1 / self.rate_limit_per_second):
            time.sleep((1 / self.rate_limit_per_second) - time_since_last_request)
        self._last_request_time = time.time()

    @tenacity.retry(
        stop=tenacity.stop_after_attempt(5),
        wait=tenacity.wait_exponential(multiplier=1, min=4, max=60),
        retry=tenacity.retry_if_exception_type(Exception),
        before_sleep=lambda retry_state: logger.info(f"Retrying after {retry_state.next_action.sleep} seconds...")
    )
    def _analyze_chunk(self, chunk: Dict) -> Dict:
        """Analyze a single chunk of Reddit data using Claude"""
        self._rate_limit()
        
        try:
            # Prepare context for template
            context = {
                'search_query': chunk.get('subreddit', ''),  # or another relevant field
                'data': json.dumps(chunk, indent=2)
            }
            
            # Render the template
            prompt_content = self.template(context)
            
            # Prepare the prompt
            prompt = {
                "prompt": "\n\nHuman: Please analyze this Reddit data according to the following protocol:\n\n" + 
                         prompt_content + "\n\nAssistant: ",
                "max_tokens": 4096,
                "temperature": 0.7,
                "top_p": 0.9,
            }
            
            # Call Bedrock
            response = self.bedrock.invoke_model(
                modelId="anthropic.claude-3-haiku-20240307",
                body=json.dumps(prompt)
            )
            
            # Parse response
            response_body = json.loads(response.get('body').read())
            return {
                'chunk_id': chunk.get('id'),
                'analysis': response_body.get('completion')
            }
            
        except Exception as e:
            logger.error(f"Error in _analyze_chunk: {str(e)}")
            raise

    def analyze_posts(self, posts: List[Dict], chunk_size: int = 5) -> List[Dict]:
        """Analyze Reddit posts in chunks using Claude through Amazon Bedrock"""
        chunks = [posts[i:i + chunk_size] for i in range(0, len(posts), chunk_size)]
        results = []
        
        logger.info(f"Starting analysis of {len(posts)} posts in {len(chunks)} chunks")
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_chunk = {
                executor.submit(self._analyze_chunk, chunk): chunk 
                for chunk in chunks
            }
            
            for future in as_completed(future_to_chunk):
                chunk = future_to_chunk[future]
                try:
                    analysis = future.result()
                    results.append(analysis)
                    logger.info(f"Successfully analyzed chunk {analysis.get('chunk_id')}")
                except Exception as e:
                    logger.error(f"Failed to analyze chunk: {str(e)}")
                    
        return results

def analyze_reddit_data(post_data: List[Dict], 
                       region_name: str = "us-east-1",
                       max_workers: int = 5,
                       rate_limit_per_second: int = 2,
                       chunk_size: int = 5) -> List[Dict]:
    """Main function to analyze Reddit data"""
    analyzer = RedditAnalyzer(
        region_name=region_name,
        max_workers=max_workers,
        rate_limit_per_second=rate_limit_per_second
    )
    
    return analyzer.analyze_posts(post_data, chunk_size)
