#!/usr/bin/env python
# coding: utf-8

# In[2]:


import streamlit as st
import pandas as pd
import praw
import os
from dotenv import load_dotenv
from ScrapeReddit import ScrapeReddit

# Load environment variables
load_dotenv()

# Set the password (you should use a more secure method in production)
PASSWORD = "Z9#mK2xP$qL7vF8nR3yT"

# Password input
password_input = st.text_input("Enter password to access the app:", type="password")

# Check if the password is correct
if password_input == PASSWORD:
    # Initialize Reddit client
    reddit_client = praw.Reddit(
        client_id=os.getenv('REDDIT_CLIENT_ID'),
        client_secret=os.getenv('REDDIT_CLIENT_SECRET'),
        user_agent=os.getenv('REDDIT_USER_AGENT')
    )

    def main():
        st.title("Reddit Post Scraper")

        # Input for search query keyword
        search_query = st.text_input("Enter a search query:")

        # Option to limit the number of posts
        max_posts = st.number_input("Maximum number of posts to scrape (0 for no limit):", min_value=0, value=10)

        if st.button("Scrape"):
            if search_query:
                with st.spinner("Scraping data..."):
                    try:
                        # Instantiate the scraper
                        scraper = ScrapeReddit(reddit_client)

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




