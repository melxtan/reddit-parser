import io
import json
import logging
import os
from datetime import datetime
import pandas as pd
import streamlit as st
from scrape_reddit import ScrapeReddit
from reddit_analysis import analyze_reddit_data

# ... (keep all the existing imports and initial setup)

# Inside the analysis section where analyze_reddit_data is called, update it to:
if st.session_state.aws_creds:
    st.subheader("Reddit Post Analysis")
    
    if st.button("Analyze Reddit Posts"):
        try:
            os.environ["AWS_ACCESS_KEY_ID"] = st.session_state.aws_creds["access_key"]
            os.environ["AWS_SECRET_ACCESS_KEY"] = st.session_state.aws_creds["secret_key"]
            
            # Initialize containers for each task's section
            for task_name in task_order:
                st.subheader(task_name.replace('_', ' ').title())
                status_container = st.empty()
                result_container = st.empty()
                st.write("---")
                st.session_state.task_containers[task_name] = {
                    'status': status_container,
                    'result': result_container
                }
            
            # Container for download button
            download_container = st.empty()
            st.session_state.task_containers['download'] = download_container
            
            # Reset analysis results
            st.session_state.analysis_results = {}
            
            # Initialize status messages
            for task_name in task_order:
                st.session_state.task_containers[task_name]['status'].info(
                    f"Running {task_name.replace('_', ' ').title()}..."
                )
            
            def update_task_status(task_name: str, result: dict):
                containers = st.session_state.task_containers[task_name]
                if 'error' in result:
                    containers['status'].error(
                        f"Error in {task_name.replace('_', ' ').title()}: {result['error']}"
                    )
                else:
                    containers['status'].success(
                        f"{task_name.replace('_', ' ').title()} completed!"
                    )
                    containers['result'].write(result['analysis'])
                    st.session_state.analysis_results[task_name] = result
                    
                    # If this was the last task, show the download button
                    if len(st.session_state.analysis_results) == len(task_order):
                        analysis_json = json.dumps(st.session_state.analysis_results, indent=2)
                        st.session_state.task_containers['download'].download_button(
                            label="Download Complete Analysis (JSON)",
                            data=analysis_json,
                            file_name=f"{filename}_analysis.json",
                            mime="application/json",
                            key="analysis_json_new"
                        )
            
            # Start analysis with callback and search query
            analyze_reddit_data(
                post_data=st.session_state.post_data,
                callback=update_task_status,
                region_name=st.session_state.aws_creds["region"],
                rate_limit_per_second=0.5,
                num_top_posts=20,
                search_query=st.session_state.search_query  # Add the search query
            )
            
        except Exception as e:
            st.error(f"Analysis failed: {str(e)}")
            logging.exception("Analysis error:")
