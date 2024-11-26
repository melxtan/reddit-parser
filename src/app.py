#!/usr/bin/env python
# coding: utf-8

import io
import json
import logging
import os

import pandas as pd
import streamlit as st
from scrape_reddit import ScrapeReddit
from reddit_analysis import analyze_reddit_data

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# Initialize session state
if "post_data" not in st.session_state:
    st.session_state.post_data = None
if "aws_credentials" not in st.session_state:
    st.session_state.aws_credentials = None

# Password input
password_input = st.text_input("Enter password to access the app:", type="password")

# Check if the password is correct
if password_input == "A7f@k9Lp#Q1z&W2x^mT3":

    st.subheader("AWS Credentials")
    
    # Only show credentials form if not already set
    if not st.session_state.aws_creds:
        with st.form("aws_creds_form"):
            aws_access_key = st.text_input("AWS Access Key ID", type="password")
            aws_secret_key = st.text_input("AWS Secret Access Key", type="password")
            aws_region = st.text_input("AWS Region", value="us-west-2")
            
            if st.form_submit_button("Save AWS Credentials"):
                if aws_access_key and aws_secret_key:
                    st.session_state.aws_credentials = {
                        "access_key": aws_access_key,
                        "secret_key": aws_secret_key,
                        "region": aws_region
                    }
                    st.success("AWS credentials saved!")
                else:
                    st.error("Please enter both AWS Access Key ID and Secret Access Key")
                    
    else:
        st.success("AWS credentials are set")
        if st.button("Clear AWS Credentials", key="clear_creds"):
            st.session_state.aws_credentials = None
            st.experimental_rerun()

    def main():
        st.title("Reddit Post Scraper")

        # Input for search query keyword
        search_query = st.text_input("Enter a search query:")

        # Create two columns for the filters
        col1, col2 = st.columns(2)

        # Search option selection in the first column
        with col1:
            search_option = st.selectbox(
                "Select search option:",
                ["relevance", "hot", "top", "new", "comments"],
                format_func=lambda x: {
                    "relevance": "Relevance",
                    "hot": "Hot",
                    "top": "Top",
                    "new": "New",
                    "comments": "Comment count",
                }[x],
            )

        # Time filter selection in the second column
        with col2:
            time_filter = st.selectbox(
                "Select time filter:",
                ["all", "year", "month", "week", "day", "hour"],
                format_func=lambda x: {
                    "all": "All time",
                    "year": "Past year",
                    "month": "Past month",
                    "week": "Past week",
                    "day": "Today",
                    "hour": "Past hour",
                }[x],
            )
    
        # Option to limit the number of posts
        max_posts = st.number_input(
            "Maximum number of posts to scrape (0 for no limit):", min_value=0, value=10
        )
    
        # Option to choose between API and WebDriver
        use_api = st.checkbox(
            "Use Reddit API (faster, but may hit rate limits)", value=True
        )
    
        # Log level selection
        log_level = st.selectbox(
            "Select log level:",
            ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
            index=1,
        )
    
        # Map log level string to logging module's level
        log_level_map = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL,
        }
    
        if st.button("Scrape"):
            if search_query:
                with st.spinner("Scraping data..."):
                    try:
                        # Instantiate the scraper with selected log level
                        scraper = ScrapeReddit(
                            use_api=use_api,
                            log_level=log_level_map[log_level],
                            client_id="uLbd7l7K0bLH2zsaTpIOTw",
                            client_secret="UOtiC3y7HAAiNyF-90fVQvDqgarVJg",
                            user_agent="melxtan",
                        )
    
                        # Get the posts with time filter and search option
                        st.info(f"Fetching posts. Max posts: {max_posts}")
                        post_urls = scraper.get_posts(
                            search_query,
                            time_filter=time_filter,
                            search_option=search_option,
                            limit=max_posts,
                        )
    
                        # Fetch detailed post information
                        st.info(f"Fetching post info for {len(post_urls)} posts")
                        post_data = scraper.get_reddit_post_info(post_urls)
    
                        # Clean up
                        scraper.destroy()
    
                        # Store the post_data in session state
                        st.session_state.post_data = post_data
                    except Exception as e:
                        st.error(f"An error occurred: {str(e)}")
                        st.error(f"Error type: {type(e).__name__}")
                        st.error(f"Error details: {e.args}")
                        logging.exception("An error occurred during scraping:")
            else:
                st.warning("Please enter a search query.")
    
        # Display results if data exists in session state
        if st.session_state.post_data:
            post_data = st.session_state.post_data
    
            # Convert comments to JSON strings for DataFrame display
            df_data = [
                {**post, "comments": json.dumps(post["comments"])} for post in post_data
            ]
            df = pd.DataFrame(df_data)
    
            # Display summary
            st.subheader("Summary")
            st.write(f"Number of posts retrieved: {len(df)}")
            st.write(f"Total comments: {df['num_comments'].sum()}")
            st.write(f"Average score: {df['score'].mean():.2f}")
    
            # Display preview
            st.subheader("Data Preview")
            st.dataframe(df)
    
            # Create two columns for download buttons
            col1, col2 = st.columns(2)
    
            # Create a filename with query, search option, and time filter
            safe_query = search_query.replace(" ", "_").lower()[:30]
            filename = f"reddit_{safe_query}_{search_option}_{time_filter}"
    
            # JSON download button
            with col1:
                json_str = json.dumps(post_data, indent=2)
                st.download_button(
                    label="Download JSON",
                    data=json_str,
                    file_name=f"{filename}.json",
                    mime="application/json",
                )
    
            # CSV download button
            with col2:
                csv_buffer = io.StringIO()
                df.to_csv(csv_buffer, index=False)
                csv_str = csv_buffer.getvalue()
                st.download_button(
                    label="Download CSV",
                    data=csv_str,
                    file_name=f"{filename}.csv",
                    mime="text/csv",
                )
    
            # Analysis section
            st.subheader("Reddit Post Analysis")
            
            if st.session_state.aws_credentials:
                analyze_button = st.button("Analyze Posts", key="analyze_button")
                if analyze_button:
                    with st.spinner("Analyzing posts using Claude..."):
                        try:
                            # Set AWS credentials from session state
                            os.environ["AWS_ACCESS_KEY_ID"] = st.session_state.aws_credentials["access_key"]
                            os.environ["AWS_SECRET_ACCESS_KEY"] = st.session_state.aws_credentials["secret_key"]
                            
                            analysis_results = analyze_reddit_data(
                                post_data=st.session_state.post_data,
                                region_name=st.session_state.aws_credentials["region"],
                                max_workers=3,
                                rate_limit_per_second=2,
                                chunk_size=5
                            )
                            
                            for i, result in enumerate(analysis_results, 1):
                                with st.expander(f"Analysis Result {i}"):
                                    st.write(f"Analysis for chunk {result.get('chunk_id', i)}:")
                                    st.write(result.get('analysis', 'No analysis available'))
                            
                            # Add download button for analysis results
                            analysis_json = json.dumps(analysis_results, indent=2)
                            st.download_button(
                                label="Download Analysis Results",
                                data=analysis_json,
                                file_name=f"{filename}_analysis.json",
                                mime="application/json",
                                key="download_analysis"
                            )
                            
                        except Exception as e:
                            st.error(f"Analysis failed: {str(e)}")
                            st.error(f"Error type: {type(e).__name__}")
                            st.error(f"Error details: {e.args}")
            else:
                st.warning("Please set your AWS credentials above to enable post analysis")

    if __name__ == "__main__":
        main()
else:
    st.error("Incorrect password. Access denied.")
