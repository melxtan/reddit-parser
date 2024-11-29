import io
import json
import logging
import os
import re

import pandas as pd
import streamlit as st
from reddit_analysis import analyze_reddit_data
from scrape_reddit import ScrapeReddit
from prompt_utils import load_prompt


def initialize_app() -> None:
    logging.basicConfig(
        level=st.secrets.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    if "post_data" not in st.session_state:
        st.session_state.post_data = None
    if "analysis_results" not in st.session_state:
        st.session_state.analysis_results = {}
    if "aws_creds" not in st.session_state:
        st.session_state.aws_creds = None
    if "task_containers" not in st.session_state:
        st.session_state.task_containers = {}
    if "debug_info" not in st.session_state:
        st.session_state.debug_info = {}


def handle_aws_credentials():
    if not st.session_state.aws_creds:
        with st.sidebar.form("aws_creds_form"):
            aws_access_key = st.text_input(
                "AWS Access Key ID", type="password", key="aws_access_key"
            )
            aws_secret_key = st.text_input(
                "AWS Secret Access Key", type="password", key="aws_secret_key"
            )
            aws_region = st.text_input("AWS Region", value="us-west-2", key="aws_region")

            if st.form_submit_button("Save AWS Credentials"):
                if aws_access_key and aws_secret_key:
                    st.session_state.aws_creds = {
                        "access_key": aws_access_key,
                        "secret_key": aws_secret_key,
                        "region": aws_region,
                    }
                    st.sidebar.success("AWS credentials saved!")
                else:
                    st.sidebar.error("Please enter both AWS Access Key ID and Secret Access Key")
    else:
        st.sidebar.success("AWS credentials are set")
        if st.sidebar.button("Clear AWS Credentials", key="clear_creds"):
            st.session_state.aws_creds = None
            st.rerun()


def render_search_interface():
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
            key="search_option",
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
            key="time_filter",
        )

    max_posts = st.number_input(
        "Maximum number of posts to scrape (0 for no limit):",
        min_value=0,
        value=10,
        key="max_posts",
    )

    use_api = st.checkbox(
        "Use Reddit API (faster, but may hit rate limits)", value=True, key="use_api"
    )

    log_level = st.selectbox(
        "Select log level:",
        ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        index=1,
        key="log_level",
    )

    return search_query, search_option, time_filter, max_posts, use_api, log_level


def scrape_reddit_data(
    search_query, search_option, time_filter, max_posts, use_api, log_level
):
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
        return post_data

    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
        logging.exception("An error occurred during scraping:")
        return None


def display_data_summary(post_data, search_query, search_option, time_filter):
    df_data = [{**post, "comments": json.dumps(post["comments"])} for post in post_data]
    df = pd.DataFrame(df_data)

    st.subheader("Summary")
    st.write(f"Number of posts retrieved: {len(df)}")
    st.write(f"Total comments: {df['num_comments'].sum()}")
    st.write(f"Average score: {df['score'].mean():.2f}")

    st.subheader("Data Preview")
    st.dataframe(df)

    return df


def create_download_buttons(df, post_data, search_query, search_option, time_filter):
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
            key="post_data_json",
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
            key="post_data_csv",
        )

    return filename

def create_task_containers(task_order):
    st.session_state.task_containers = {}
    for task_name in task_order:
        try:
            prompt_content = load_prompt(task_name)
            title = re.search(r"<title>(.*?)</title>", prompt_content)
            task_title = title.group(1) if title else task_name.replace("_", " ").title()
        except Exception as e:
            logger.warning(f"Could not load prompt title for {task_name}: {e}")
            task_title = task_name.replace("_", " ").title()

        st.subheader(task_title)
        status_container = st.empty()
        status_container.info(f"Running {task_title}...")
        result_container = st.empty()
        st.divider()
        
        st.session_state.task_containers[task_name] = {
            "status": status_container,
            "result": result_container,
        }


def update_task_status(task_name: str, result: dict, task_order: list, filename: str):
    containers = st.session_state.task_containers[task_name]
    task_display_name = task_name.replace("_", " ").title()

    if "error" in result:
        containers["status"].error(
            f"Error in {task_display_name}: {result['error']}"
        )
    else:
        containers["status"].success(f"{task_display_name} completed")
        containers["result"].write(result["analysis"])
        st.session_state.analysis_results[task_name] = result

        if len(st.session_state.analysis_results) == len(task_order):
            st.success("Analysis completed successfully")
            col1, col2 = st.columns([3, 1])
            with col1:
                st.download_button(
                    label="Download Complete Analysis (JSON)",
                    data=json.dumps(st.session_state.analysis_results, indent=2),
                    file_name=f"{filename}_analysis.json",
                    mime="application/json",
                    key="analysis_json_final",
                )
            with col2:
                if st.button("Run New Analysis"):
                    st.session_state.analysis_results = {}
                    st.session_state.task_containers = {}
                    st.session_state.post_data = None
                    st.rerun()


def display_analysis_results(task_order, filename):
    for task_name in task_order:
        if task_name in st.session_state.analysis_results:
            result = st.session_state.analysis_results[task_name]
            if "error" not in result:
                st.subheader(task_name.replace("_", " ").title())
                st.write(result["analysis"])
                st.divider()

    col1, col2 = st.columns([3, 1])
    with col1:
        st.download_button(
            label="Download Complete Analysis (JSON)",
            data=json.dumps(st.session_state.analysis_results, indent=2),
            file_name=f"{filename}_analysis.json",
            mime="application/json",
            key="analysis_json_final",
        )
    with col2:
        if st.button("Run New Analysis"):
            # Only reset non-widget session state
            st.session_state.analysis_results = {}
            st.session_state.task_containers = {}
            st.session_state.post_data = None
            st.rerun()

def display_analysis_results(task_order, filename):
    for task_name in task_order:
        if task_name in st.session_state.analysis_results:
            result = st.session_state.analysis_results[task_name]
            if "error" not in result:
                st.subheader(task_name.replace("_", " ").title())
                st.write(result["analysis"])
                st.divider()

    col1, col2 = st.columns([3, 1])
    with col1:
        st.download_button(
            label="Download Complete Analysis (JSON)",
            data=json.dumps(st.session_state.analysis_results, indent=2),
            file_name=f"{filename}_analysis.json",
            mime="application/json",
            key="analysis_json_final",
        )
    with col2:
        if st.button("Run New Analysis"):
            # Reset all relevant session state variables
            st.session_state.analysis_results = {}
            st.session_state.task_containers = {}
            st.session_state.post_data = None
            st.rerun()


def run_analysis(post_data, task_order, filename):
    try:
        os.environ["AWS_ACCESS_KEY_ID"] = st.session_state.aws_creds["access_key"]
        os.environ["AWS_SECRET_ACCESS_KEY"] = st.session_state.aws_creds["secret_key"]

        num_top_posts = 10
        st.info(
            f"Due to rate limit, we are currently only analyzing up to top {num_top_posts} posts with highest scores."
        )

        create_task_containers(task_order)
        st.session_state.analysis_results = {}

        def callback(task_name: str, result: dict) -> None:
            update_task_status(task_name, result, task_order, filename)

        analyze_reddit_data(
            post_data=post_data,
            callback=callback,
            region_name=st.session_state.aws_creds["region"],
            rate_limit_per_second=0.5,
            num_top_posts=num_top_posts,
        )

    except Exception as e:
        st.error(f"Analysis failed: {str(e)}")
        logging.exception("Analysis error:")


def main():
    task_order = [
        "title_and_post_text_analysis",
        "language_feature_extraction",
        "sentiment_color_tracking",
        "trend_analysis",
        "correlation_analysis",
    ]

    initialize_app()

    # Move password input to sidebar
    with st.sidebar:
        st.title("Authentication")
        password_input = st.text_input(
            "Enter password to access the app:", type="password", key="password_input"
        )
        
        if password_input == "A7f@k9Lp#Q1z&W2x^mT3":
            st.success("Authentication successful!")
            
            # Move AWS credentials section to sidebar
            st.title("AWS Credentials")
            handle_aws_credentials()

    # Main content area
    if password_input == "A7f@k9Lp#Q1z&W2x^mT3":
        st.title("Reddit Post Scraper")

        search_query, search_option, time_filter, max_posts, use_api, log_level = (
            render_search_interface()
        )

        if st.button("Scrape", key="scrape_button"):
            if search_query:
                with st.spinner("Scraping data..."):
                    post_data = scrape_reddit_data(
                        search_query,
                        search_option,
                        time_filter,
                        max_posts,
                        use_api,
                        log_level,
                    )
                    if post_data:
                        st.session_state.post_data = post_data
                        st.session_state.analysis_results = {}
                        st.session_state.task_containers = {}
                        st.session_state.debug_info = {}
            else:
                st.warning("Please enter a search query.")

        if st.session_state.post_data:
            df = display_data_summary(
                st.session_state.post_data, search_query, search_option, time_filter
            )
            filename = create_download_buttons(
                df, st.session_state.post_data, search_query, search_option, time_filter
            )

            if st.session_state.aws_creds:
                st.subheader("Reddit Post Analysis")

                if st.button("Analyze Reddit Posts"):
                    run_analysis(st.session_state.post_data, task_order, filename)
                elif st.session_state.analysis_results:
                    display_analysis_results(task_order, filename)

    else:
        st.sidebar.error("Incorrect password. Access denied.")


if __name__ == "__main__":
    main()
