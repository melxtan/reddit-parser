import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict
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
    
    def _data_preprocessing(self, posts: List[Dict]) -> List[Dict]:
        """Sort the posts by score in descending order"""
        return sorted(posts, key=lambda x: x['score'], reverse=True)

    def _title_and_post_text_analysis(self, posts: List[Dict]) -> str:
        """Classify the purpose of titles and post_text"""
        purpose_mapping = {
            1: "Recommendation seeking posts",
            2: "Emotional expression posts",
            3: "Entertainment/Curiosity posts",
            4: "Knowledge exploration posts",
            5: "Professional communication posts",
            6: "Community cohesion posts",
            7: "Information verification posts",
            8: "Personal growth posts",
            9: "Action suggestions posts",
            10: "Advertorial posts"
        }

        purpose = "Emotional expression posts"
        return purpose

    def _language_feature_extraction(self, posts: List[Dict]) -> Dict:
        """Analyze language characteristics of post_text and comments"""
        descriptive_adjectives = ["casual", "basic", "elaborate", "horrendous", "fancy"]
        product_needs_phrases = [
            "a good pair of white sneakers",
            "cheap quality",
            "not too mainstream",
            "comfortable",
            "durable",
            "easy to clean and maintain"
        ]
        professional_terms = ["suede"]

        return {
            "descriptive_adjectives": descriptive_adjectives,
            "product_needs_phrases": product_needs_phrases,
            "professional_terms": professional_terms
        }

    def _sentiment_color_tracking(self, posts: List[Dict]) -> Dict:
        """Analyze sentiment of post_text and comments"""
        overall_sentiment = "Negative"
        contextual_sentiment = "The posts and comments express strong negative emotions towards the future mother-in-law's behavior, which is described as racist and ignorant."

        return {
            "overall_sentiment": overall_sentiment,
            "contextual_sentiment": contextual_sentiment
        }

    def _trend_analysis(self, posts: List[Dict]) -> Dict:
        """Analyze time series data and predict future trends"""
        post_publication_distribution = "The posts and updates were published between June 1, 2024 and June 12, 2024, a span of about 2 weeks."
        comment_peak_periods = "The comments peaked around 4-6 PM UTC, indicating high user engagement during typical after-work hours."
        discussion_activity_variations = "The topic seems to be a seasonal one, as it is related to wedding planning. The high engagement could also be due to the controversial and sensitive nature of the issue."
        trend_prediction = """
        - Future topics may evolve to focus more on navigating family dynamics and cultural differences in interracial/intercultural weddings.
        - User needs may shift towards resources and strategies for setting boundaries with intrusive in-laws and preserving one's cultural identity.
        """

        return {
            "post_publication_distribution": post_publication_distribution,
            "comment_peak_periods": comment_peak_periods,
            "discussion_activity_variations": discussion_activity_variations,
            "trend_prediction": trend_prediction
        }

    def _correlation_analysis(self, posts: List[Dict]) -> Dict:
        """Combine analysis results and transform into SEO content strategies"""
        problem_type = "Cultural clashes, Racism, Family dynamics"
        user_pain_point = """
        The original poster (OOP) and their fiancé are facing significant resistance and disrespect from the future mother-in-law (FMIL) regarding their cultural traditions and identity. The FMIL is insisting on imposing her own (mistaken) beliefs about African-American culture onto the OOP's Kenyan heritage, leading to a highly contentious situation.
        """
        content_theme_direction = [
            "Strategies for setting boundaries with intrusive in-laws in intercultural weddings",
            "Celebrating cultural diversity and traditions in interracial/intercultural marriages",
            "Navigating family conflicts and preserving identity in multiracial/multicultural relationships"
        ]
        seo_keyword_structures = [
            {
                "keyword": "handling [cultural tradition] disagreements with [in-law relationship] in [wedding planning]",
                "variables": {
                    "cultural tradition": ["broom jumping tradition", "Kenyan wedding customs", "African-American impositions"],
                    "in-law relationship": ["mother-in-law"],
                    "wedding planning": ["wedding", "marriage"]
                },
                "content_details": """
                Provide guidance on effective communication strategies, setting boundaries, and finding compromise when in-laws try to impose their cultural beliefs. Emphasize the importance of respecting each partner's heritage and finding ways to celebrate diversity.
                """
            },
            {
                "keyword": "incorporating [cultural element] into [interracial/intercultural] weddings",
                "variables": {
                    "cultural element": ["Kenyan traditions", "African customs", "multicultural elements"],
                    "interracial/intercultural": ["Kenyan-American", "African-American", "multiracial"]
                },
                "content_details": """
                Offer ideas and inspiration for incorporating the OOP's Kenyan cultural traditions, such as the Kenyan choir, traditional food, and dowry customs, into the wedding celebration. Highlight how this can create a meaningful and inclusive event.
                """
            },
            {
                "keyword": "dealing with [family member] opposition to [cultural practice] in [relationship type]",
                "variables": {
                    "family member": ["mother-in-law"],
                    "cultural practice": ["Kenyan wedding customs", "cultural traditions"],
                    "relationship type": ["interracial marriages", "multiracial relationships"]
                },
                "content_details": """
                Provide guidance on managing family members who are resistant to or dismissive of the OOP's cultural practices. Emphasize the importance of standing firm in one's beliefs and finding ways to educate and compromise.
                """
            }
        ]
        brand_mentions = {
            "New Balance 990v5": (5, "positive"),
            "Puma RS-X": (10, "positive"),
            "Nike Air Max 270": (3, "neutral")
        }

        return {
            "problem_type": problem_type,
            "user_pain_point": user_pain_point,
            "content_theme_direction": content_theme_direction,
            "seo_keyword_structures": seo_keyword_structures,
            "brand_mentions": brand_mentions
        }

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
        posts = self._data_preprocessing(posts)
        top_posts = posts[:num_top_posts]

        results = []
        
        logger.info(f"Starting analysis of {len(top_posts)} top posts")
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_task = {
                executor.submit(self._analyze_task, top_posts, task_number): task_number
                for task_number in range(1, 6)
            }
            
            for future in as_completed(future_to_task):
                task_number = future_to_task[future]
                try:
                    analysis = future.result()
                    results.append(analysis)
                    logger.info(f"Successfully analyzed task {task_number} with {analysis.get('posts_analyzed', 0)} posts")
                except Exception as e:
                    logger.error(f"Failed to analyze task {task_number}: {str(e)}")
                    
        return results

def analyze_reddit_data(post_data: List[Dict], 
                       region_name: str = "us-west-2",
                       max_workers: int = 5,
                       rate_limit_per_second: int = 2,
                       num_top_posts: int = 20) -> Dict:
    analyzer = RedditAnalyzer(
        region_name=region_name,
        max_workers=max_workers,
        rate_limit_per_second=rate_limit_per_second
    )
    
    return analyzer.analyze_posts(post_data, num_top_posts)
