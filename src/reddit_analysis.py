import json
import logging
import time
import re
from typing import List, Dict, Callable, Tuple
import boto3
from botocore.config import Config
from pybars import Compiler
from collections import defaultdict
import functools

# Configure logging
logger = logging.getLogger(__name__)

class RedditAnalyzer:
    def __init__(self, region_name="us-west-2", rate_limit_per_second=0.2, search_query=""):
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
        self.compiler = Compiler()

        def json_helper(this, value):
            return json.dumps(value, indent=2)

        def concat_helper(this, *args):
            return ''.join([str(arg) for arg in args])
        
        # Add helpers for templates
        self.helpers = {
            'json': json.dumps,
            'concat': lambda *args: ''.join([str(arg) for arg in args])
        }
        
        # Initialize partials dict
        self.partials = {}
        self.templates = self._load_templates()
        self.analysis_results = defaultdict(dict)
        self.search_query = search_query
        
        self.tasks = [
            (1, "title_and_post_text_analysis"),
            (2, "language_feature_extraction"),
            (3, "sentiment_color_tracking"),
            (4, "trend_analysis"),
            (5, "correlation_analysis")
        ]

    @functools.lru_cache(maxsize=None)
    def _load_templates(self):
        """Load and compile all Handlebars templates with caching"""
        templates = {}
        try:
            # First load the base template as a partial
            with open('templates/base.hbs', 'r', encoding='utf-8') as file:
                base_source = file.read()
                self.partials['base'] = self.compiler.compile(base_source)
            
            # Load individual task templates
            task_files = [
                'title_and_post_text_analysis',
                'language_feature_extraction',
                'sentiment_color_tracking',
                'trend_analysis',
                'correlation_analysis'
            ]
            
            for task in task_files:
                with open(f'templates/{task}.hbs', 'r', encoding='utf-8') as file:
                    source = file.read()
                    templates[task] = self.compiler.compile(source)
            
            return templates
            
        except Exception as e:
            logger.error(f"Error loading templates: {str(e)}")
            raise

    def _get_task_prompt(self, task_name: str, context: Dict) -> str:
        """Generate prompt using Handlebars template"""
        try:
            template = self.templates[task_name]
            return template(context, helpers=self.helpers, partials=self.partials)
        except Exception as e:
            logger.error(f"Error generating prompt for {task_name}: {str(e)}")
            raise

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
                    pattern = fr"{section}.*?(?=\n\n|$)"
                    matches = re.findall(pattern, result, re.DOTALL)
                    if matches:
                        section_content = str(matches[0]) if isinstance(matches[0], list) else matches[0]
                        formatted_results += f"- {section_content.strip()}\n"
        
        return formatted_results

    def _analyze_task(self, posts: List[Dict], task_name: str, task_number: int) -> Dict:
        max_retries = 8
        base_delay = 10
        
        for attempt in range(max_retries):
            try:
                self._rate_limit()
                
                # Create context for templates
                context = {
                    'search_query': self.search_query,
                    'posts': posts,
                    'previous_results': self._format_previous_results() if task_name == "correlation_analysis" else None
                }
                
                # Generate prompt using template
                prompt = self._get_task_prompt(task_name, context)
                
                # Use boto3 client with Claude 3
                body = {
                    "anthropic_version": "bedrock-2024-02-01",
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
                    modelId="anthropic.claude-3-sonnet-20240229-v1:0",
                    body=json.dumps(body),
                    accept="application/json",
                    contentType="application/json"
                )
                
                response_body = json.loads(response['body'].read().decode())
                content = response_body['content'][0]['text'] if 'content' in response_body else response_body
                
                result = {
                    'task_name': task_name,
                    'task_number': task_number,
                    'analysis': content,
                    'posts_analyzed': len(posts)
                }
                
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
                       num_top_posts: int = 10,
                       search_query: str = ""):
    analyzer = RedditAnalyzer(
        region_name=region_name,
        rate_limit_per_second=rate_limit_per_second,
        search_query=search_query
    )
    
    analyzer.analyze_posts(post_data, callback, num_top_posts)
