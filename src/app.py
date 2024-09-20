#!/usr/bin/env python
# coding: utf-8

import logging
import os

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from ScrapeReddit import ScrapeReddit

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

# Password input
password_input = st.text_input("Enter password to access the app:", type="password")

# Check if the password is correct
if password_input == os.getenv("APP_PASSWORD"):

    def main():
        st.title("Reddit Post Scraper")

        # Input for search query keyword
        search_query = st.text_input("Enter a search query:")

        # Option to limit the number of posts
        max_posts = st.number_input("Maximum number of posts to scrape (0 for no limit):", min_value=0, value=10)

        # Option to choose between API and WebDriver
        use_api = st.checkbox("Use Reddit API (faster, but may hit rate limits)")

        # Log level selection
        log_level = st.selectbox(
            "Select log level:",
            ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
            index=1,
        )

        if st.button("Scrape"):
            if search_query:
                with st.spinner("Scraping data..."):
                    try:
                        # Instantiate the scraper with selected log level
                        scraper = ScrapeReddit(use_api=use_api, log_level=getattr(logging, log_level))

                        # Get the posts
                        scraper.get_posts(search_query)

                        # Fetch detailed post information
                        post_data = scraper.get_reddit_post_info(limit=max_posts if max_posts > 0 else None)

                        # Clean up
                        scraper.destroy()

                        if post_data:
                            # Convert to DataFrame
                            df = pd.DataFrame(post_data)

                            # Generate CSV
                            csv = df.to_csv(index=False)

                            # Provide download link
                            st.download_button(
                                label="Download CSV",
                                data=csv,
                                file_name=f"reddit_search_{search_query.replace(' ', '_')}.csv",
                                mime="text/csv",
                            )

                            # Display preview
                            st.subheader("Data Preview")
                            st.dataframe(df.head())

                            # Display summary
                            st.subheader("Summary")
                            st.write(f"Total posts scraped: {len(df)}")
                            st.write(f"Total comments: {df['num_comments'].sum()}")
                            st.write(f"Average score: {df['score'].mean():.2f}")
                        else:
                            st.error("No data found. Please try a different search query.")
                    except Exception as e:
                        st.error(f"An error occurred: {str(e)}")
            else:
                st.warning("Please enter a search query.")

    if __name__ == "__main__":
        main()
else:
    st.error("Incorrect password. Access denied.")


# In[ ]:
