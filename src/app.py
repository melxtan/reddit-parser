import io
import json
import logging
import os
from datetime import datetime

import pandas as pd
import streamlit as st
from scrape_reddit import ScrapeReddit
from reddit_analysis import analyze_reddit_data, combine_analyses

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

if "post_data" not in st.session_state:
    st.session_state.post_data = None
if "aws_creds" not in st.session_state:
    st.session_state.aws_creds = None

password_input = st.text_input("Enter password to access the app:", type="password", key="password_input")

if password_input == "A7f@k9Lp#Q1z&W2x^mT3":
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

    def main() -> None:
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

        log_level_map = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL,
        }

        if st.button("Scrape", key="scrape_button"):
            if search_query:
                with st.spinner("Scraping data..."):
                    try:
                        scraper = ScrapeReddit(
                            use_api=use_api,
                            log_level=log_level_map[log_level],
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
                    except Exception as e:
                        st.error(f"An error occurred: {str(e)}")
                        st.error(f"Error type: {type(e).__name__}")
                        st.error(f"Error details: {e.args}")
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

            st.subheader("Reddit Post Analysis")

            if st.session_state.aws_creds:
                analyze_button = st.button("Analyze Posts", key="analyze_button")
                if analyze_button:
                    with st.spinner("Analyzing posts using Claude..."):
                        try:
                            os.environ["AWS_ACCESS_KEY_ID"] = st.session_state.aws_creds["access_key"]
                            os.environ["AWS_SECRET_ACCESS_KEY"] = st.session_state.aws_creds["secret_key"]

                            st.info("Starting analysis...")
                            analysis_results = analyze_reddit_data(
                                post_data=st.session_state.post_data,
                                region_name=st.session_state.aws_creds["region"],
                                max_workers=2,
                                rate_limit_per_second=0.5,
                                chunk_size=3
                            )

                            if analysis_results:
                                st.success("Analysis completed!")
                                combined_analysis = combine_analyses(analysis_results)

                                if combined_analysis:
                                    sections = combined_analysis.split("\n\n")
                                    for section in sections:
                                        if section.strip():
                                            if section.strip()[0].isdigit():
                                                with st.expander(section.split('\n')[0]):
                                                    st.write("\n".join(section.split('\n')[1:]))
                                            else:
                                                st.write(section)

                                download_data = {
                                    "combined_analysis": combined_analysis,
                                    "individual_chunks": analysis_results,
                                    "metadata": {
                                        "total_posts_analyzed": sum(r.get('posts_analyzed', 0) for r in analysis_results),
                                        "analysis_timestamp": datetime.now().isoformat(),
                                        "number_of_chunks": len(analysis_results)
                                    }
                                }

                                st.subheader("Download Analysis Results")

                                analysis_json = json.dumps(download_data, indent=2)
                                st.download_button(
                                    label="Download Full Analysis (JSON)",
                                    data=analysis_json,
                                    file_name=f"{filename}_analysis_full.json",
                                    mime="application/json",
                                    key="analysis_json"
                                )

                            else:
                                st.warning("No analysis results were returned")
                        except Exception as e:
                            st.error(f"Analysis failed: {str(e)}")
                            logging.exception("Analysis error:")
            else:
                st.warning("Please set your AWS credentials above to enable post analysis")

    if __name__ == "__main__":
        main()
else:
    st.error("Incorrect password. Access denied.")
