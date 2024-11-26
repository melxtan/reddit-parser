import logging

import praw


class CustomReddit(praw.Reddit):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger(__name__)

    def search(self, query, **kwargs):
        self.logger.info(f"Performing custom search with query: {query}")
        params = {"q": query, "sort": kwargs.get("sort", "relevance"), "t": kwargs.get("time_filter", "all"), "limit": kwargs.get("limit", 100)}
        self.logger.debug(f"Search parameters before API call: {params}")

        response = self.get("/search", params=params)

        # Convert the response to a list and count the results
        results = list(response)
        self.logger.info(f"Received {len(results)} results")

        return response  # Return the original response for further processing

    def get(self, *args, **kwargs):
        self.logger.debug(f"Making GET request: args={args}, kwargs={kwargs}")
        response = super().get(*args, **kwargs)

        return response
