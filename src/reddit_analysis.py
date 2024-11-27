import json
import logging
import time
import re
from typing import List, Dict, Callable, Tuple
from anthropic import AnthropicBedrock
from pybars import Compiler
from collections import defaultdict

# Configure logging
logger = logging.getLogger(__name__)

class RedditAnalyzer:
    def __init__(self, region_name="us-west-2", rate_limit_per_second=0.2, search_query="", aws_access_key=None, aws_secret_key=None):
        client_kwargs = {"aws_region": region_name}
        if aws_access_key and aws_secret_key:
            client_kwargs.update({
                "aws_access_key": aws_access_key,
                "aws_secret_key": aws_secret_key
            })
            
        self.client = AnthropicBedrock(**client_kwargs)
        
        self.rate_limit_per_second = rate_limit_per_second
        self._last_request_time = 0
        self.compiler = Compiler()
        
        # Add helpers for templates
        self.helpers = {
            'json': json.dumps,
            'concat': lambda *args: ''.join([str(arg) for arg in args])
        }
        
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

    def _load_templates(self):
        """Load and compile all Handlebars templates"""
        templates = {}
        try:
            # Compile base template with helpers
            with open('templates/base.hbs', 'r', encoding='utf-8') as file:
                source = file.read()
                templates['base'] = self.compiler.compile(source)
            
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
                    # Compile each template with helpers
                    templates[task] = self.compiler.compile(source)
            
            return templates
            
        except Exception as e:
            logger.error(f"Error loading templates: {str(e)}")
            raise

    def _get_task_prompt(self, task_name: str, context: Dict) -> str:
        """Generate prompt using Handlebars template"""
        try:
            template = self.templates[task_name]
            # Pass helpers when executing the template
            return template(context, helpers=self.helpers)
        except Exception as e:
            logger.error(f"Error generating prompt for {task_name}: {str(e)}")
            raise

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
                
                # Use AnthropicBedrock client with correct syntax
                message = self.client.messages.create(
                    model="anthropic.claude-3-5-sonnet-20241022-v1:0",
                    max_tokens=4096,
                    messages=[{
                        "role": "user",
                        "content": prompt
                    }]
                )
                
                # Extract content from the message
                content = message.content[0].text
                
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
                       search_query: str = "",
                       aws_access_key: str = None,
                       aws_secret_key: str = None):
    analyzer = RedditAnalyzer(
        region_name=region_name,
        rate_limit_per_second=rate_limit_per_second,
        search_query=search_query,
        aws_access_key=aws_access_key,
        aws_secret_key=aws_secret_key
    )
    
    analyzer.analyze_posts(post_data, callback, num_top_posts)
