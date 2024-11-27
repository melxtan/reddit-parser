import io
import json
import logging
import os
from datetime import datetime
import pandas as pd
import streamlit as st
from scrape_reddit import ScrapeReddit
from reddit_analysis import analyze_reddit_data

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

if "post_data" not in st.session_state:
    st.session_state.post_data = None
if "analysis_results" not in st.session_state:
    st.session_state.analysis_results = {}
if "aws_creds" not in st.session_state:
    st.session_state.aws_creds = None
if "task_containers" not in st.session_state:
    st.session_state.task_containers = {}

password_input = st.text_input("Enter password to access the app:", type="password", key="password_input")

if password_input == "A7f@k9Lp#Q1z&W2x^mT3":
    st.title("Reddit Post Scraper")

    search_query = st.text_input("Enter a search query:", key="search_query")

    col1, col2 = st.columns(2)

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
            key="search_option"
        )

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
            key="time_filter"
        )

    max_posts = st.number_input(
        "Maximum number of posts to scrape (0 for no limit):", min_value=0, value=10, key="max_posts"
    )

    use_api = st.checkbox("Use Reddit API (faster, but may hit rate limits)", value=True, key="use_api")

    log_level = st.selectbox(
        "Select log level:",
        ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        index=1,
        key="log_level"
    )

    if st.button("Scrape", key="scrape_button"):
        if search_query:
            with st.spinner("Scraping data..."):
                try:
                    scraper = ScrapeReddit(
                        use_api=use_api,
                        log_level=logging.getLevelName(log_level),
                        client_id="uLbd7l7K0bLH2zsaTpIOTw",
                        client_secret="UOtiC3y7HAAiNyF-90fVQvDqgarVJg",
                        user_agent="melxtan",
                    )

                    st.info(f"Fetching posts. Max posts: {max_posts}")
                    post_urls = scraper.get_posts(
                        search_query,
                        time_filter=time_filter,
                        search_option=search_option,
                        limit=max_posts,
                    )

                    st.info(f"Fetching post info for {len(post_urls)} posts")
                    post_data = scraper.get_reddit_post_info(post_urls)

                    scraper.destroy()
                    st.session_state.post_data = post_data
                    st.session_state.analysis_results = {}  # Reset analysis results
                    st.session_state.task_containers = {}  # Reset task containers
                except Exception as e:
                    st.error(f"An error occurred: {str(e)}")
                    logging.exception("An error occurred during scraping:")
        else:
            st.warning("Please enter a search query.")

    if st.session_state.post_data:
        post_data = st.session_state.post_data
        df_data = [{**post, "comments": json.dumps(post["comments"])} for post in post_data]
        df = pd.DataFrame(df_data)

        st.subheader("Summary")
        st.write(f"Number of posts retrieved: {len(df)}")
        st.write(f"Total comments: {df['num_comments'].sum()}")
        st.write(f"Average score: {df['score'].mean():.2f}")

        st.subheader("Data Preview")
        st.dataframe(df)

        col1, col2 = st.columns(2)
        safe_query = search_query.replace(" ", "_").lower()[:30]
        filename = f"reddit_{safe_query}_{search_option}_{time_filter}"

        with col1:
            json_str = json.dumps(post_data, indent=2)
            st.download_button(
                label="Download JSON",
                data=json_str,
                file_name=f"{filename}.json",
                mime="application/json",
                key="post_data_json"
            )

        with col2:
            csv_buffer = io.StringIO()
            df.to_csv(csv_buffer, index=False)
            csv_str = csv_buffer.getvalue()
            st.download_button(
                label="Download CSV",
                data=csv_str,
                file_name=f"{filename}.csv",
                mime="text/csv",
                key="post_data_csv"
            )

        # AWS Credentials Section
        st.subheader("AWS Credentials")
        
        if not st.session_state.aws_creds:
            with st.form("aws_creds_form"):
                aws_access_key = st.text_input("AWS Access Key ID", type="password", key="aws_access_key")
                aws_secret_key = st.text_input("AWS Secret Access Key", type="password", key="aws_secret_key")
                aws_region = st.text_input("AWS Region", value="us-west-2", key="aws_region")
                
                if st.form_submit_button("Save AWS Credentials"):
                    if aws_access_key and aws_secret_key:
                        st.session_state.aws_creds = {
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
                st.session_state.aws_creds = None
                st.experimental_rerun()

        # Analysis Section
        if st.session_state.aws_creds:
            st.subheader("Reddit Post Analysis")
            
            if st.button("Analyze Reddit Posts"):
                try:
                    os.environ["AWS_ACCESS_KEY_ID"] = st.session_state.aws_creds["access_key"]
                    os.environ["AWS_SECRET_ACCESS_KEY"] = st.session_state.aws_creds["secret_key"]
                    
                    # Create placeholder containers for each task
                    st.session_state.task_containers = {
                        "title_and_post_text_analysis": st.empty(),
                        "language_feature_extraction": st.empty(),
                        "sentiment_color_tracking": st.empty(),
                        "trend_analysis": st.empty(),
                        "correlation_analysis": st.empty()
                    }
                    
                    # Reset analysis results
                    st.session_state.analysis_results = {}
                    
                    # Initialize status messages
                    for name, container in st.session_state.task_containers.items():
                        container.info(f"Waiting to start {name.replace('_', ' ').title()}...")
                    
                    def update_task_status(task_name: str, result: dict):
                        container = st.session_state.task_containers[task_name]
                        if 'error' in result:
                            container.error(f"Error in {task_name.replace('_', ' ').title()}: {result['error']}")
                        else:
                            container.success(f"{task_name.replace('_', ' ').title()} completed!")
                            st.session_state.analysis_results[task_name] = result
                            
                            # Create a new subheader and content for this task
                            st.subheader(task_name.replace('_', ' ').title())
                            st.write(result['analysis'])
                            st.write("---")
                    
                    # Start analysis with callback
                    analyze_reddit_data(
                        post_data=st.session_state.post_data,
                        callback=update_task_status,
                        region_name=st.session_state.aws_creds["region"],
                        rate_limit_per_second=0.5,
                        num_top_posts=20
                    )
                    
                except Exception as e:
                    st.error(f"Analysis failed: {str(e)}")
                    logging.exception("Analysis error:")
            
            # Display existing results if any
            if st.session_state.analysis_results:
                # Only show results if not currently analyzing
                if not st.session_state.task_containers:
                    for task_name, result in st.session_state.analysis_results.items():
                        if 'error' not in result:
                            st.subheader(task_name.replace('_', ' ').title())
                            st.write(result['analysis'])
                            st.write("---")
                
                # Show download button for complete results
                analysis_json = json.dumps(st.session_state.analysis_results, indent=2)
                st.download_button(
                    label="Download Complete Analysis (JSON)",
                    data=analysis_json,
                    file_name=f"{filename}_analysis.json",
                    mime="application/json",
                    key="analysis_json"
                )

else:
    st.error("Incorrect password. Access denied.")
