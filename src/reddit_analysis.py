import json
import logging
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Union
import boto3
from botocore.config import Config
import tenacity

# Configure logging
logger = logging.getLogger(__name__)

class RedditAnalyzer:
    def __init__(self, region_name="us-west-2", max_workers=5, rate_limit_per_second=2):
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
        
        self.max_workers = max_workers
        self.rate_limit_per_second = rate_limit_per_second
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
            time.sleep((1 / self.rate_limit_per_second) - time_since_last_request + 1)
        self._last_request_time = time.time()

    @tenacity.retry(
        stop=tenacity.stop_after_attempt(5),
        wait=tenacity.wait_exponential(multiplier=1, min=4, max=60),
        retry=tenacity.retry_if_exception_type(Exception),
        before_sleep=lambda retry_state: logger.info(f"Retrying after {retry_state.next_action.sleep} seconds...")
    )
    
    def _analyze_chunk(self, posts: List[Dict]) -> Dict:
        """Analyze a chunk of Reddit posts"""
        self._rate_limit()
        
        try:
            # Get the subreddit from the first post in the chunk
            search_query = posts[0].get('subreddit', '') if posts else ''
            
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 4096,
                "messages": [
                    {
                        "role": "user",
                        "content": f"Please analyze this Reddit data according to the following protocol:\n\n{json.dumps(posts, indent=2)}\n\nProtocol:\n{self.template}"
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
                'chunk_id': f"chunk_{time.time()}",
                'analysis': response_body['content'] if isinstance(response_body, dict) and 'content' in response_body else response_body['messages'][0]['content'],
                'posts_analyzed': len(posts)
            }
            
        except Exception as e:
            logger.error(f"Error in _analyze_chunk: {str(e)}")
            logger.error(f"Error type: {type(e).__name__}")
            raise
            
    def analyze_posts(self, posts: List[Dict], chunk_size: int = 5) -> List[Dict]:
        """Split posts into chunks and analyze each chunk"""
        # Split posts into chunks
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
                    logger.info(f"Successfully analyzed chunk with {analysis.get('posts_analyzed', 0)} posts")
                except Exception as e:
                    logger.error(f"Failed to analyze chunk: {str(e)}")
                    
        return results

def analyze_reddit_data(post_data: List[Dict], 
                       region_name: str = "us-west-2",
                       max_workers: int = 5,
                       rate_limit_per_second: int = 2,
                       chunk_size: int = 5) -> List[Dict]:
    analyzer = RedditAnalyzer(
        region_name=region_name,
        max_workers=max_workers,
        rate_limit_per_second=rate_limit_per_second
    )
    
    return analyzer.analyze_posts(post_data, chunk_size)

def combine_analyses(results: List[Dict]) -> Dict[str, Union[str, List[Dict], Dict]]:
    """Combine multiple chunk analyses into one coherent analysis."""
    combined_text = ""
    individual_chunks = []

    for result in results:
        if not result or not result.get("analysis"):
            logging.warning("Empty result or missing analysis encountered, skipping.")
            continue

        analysis = result.get("analysis", {})
        analysis_text = ""

        if isinstance(analysis, str):
            analysis_text = analysis
        elif isinstance(analysis, dict):
            content = analysis.get("content")
            if isinstance(content, list):
                analysis_text = "\n".join(
                    item.get("text", "")
                    for item in content
                    if isinstance(item, dict) and item.get("type") == "text"
                )
            elif isinstance(content, str):
                analysis_text = content
            elif "text" in analysis:
                analysis_text = analysis["text"]
            else:
                logging.warning(f"Unexpected analysis structure: {analysis}")
        else:
            logging.warning(f"Unknown analysis type: {type(analysis)}")

        if analysis_text.strip():
            individual_chunks.append(result)
            combined_text += analysis_text.strip() + "\n\n"

    return {
        "combined_analysis": combined_text.strip() if combined_text.strip() else None,
        "individual_chunks": individual_chunks,
        "metadata": {
            "total_posts_analyzed": sum(r.get("posts_analyzed", 0) for r in individual_chunks),
            "analysis_timestamp": datetime.now().isoformat(),
            "number_of_chunks": len(individual_chunks)
        }
    }
