# Reddit Post Scraper

## Overview

This project is a Streamlit-based web application that allows users to scrape Reddit posts based on search queries. It uses Selenium for web scraping and PRAW (Python Reddit API Wrapper) for accessing Reddit's API.

## Features

- Search for Reddit posts using keywords
- Scrape post details including title, author, score, and comments
- Download scraped data as a CSV file
- User-friendly interface powered by Streamlit
- User authentication backed by Supabase

## Installation

1. Clone this repository:

```
git clone https://github.com/my-moon-watcher/reddit-parser.git
cd reddit-scraper
```

2. Install Poetry if you haven't already:

```
curl -sSL https://install.python-poetry.org | python3 -
```

3. Install the project and its dependencies:

```
pip install .
```

This will install the project and all its dependencies as specified in the pyproject.toml file.

4. Set up your Reddit API credentials:

- Create a Reddit account if you don't have one
- Go to https://www.reddit.com/prefs/apps and create a new app
- Select "script" as the app type
- Note down the client ID and client secret

5. Set up Supabase:

- Go to https://supabase.io/ and create a new project
- Note down the Supabase URL and API key

Alternatively, you can set up Supabase locally:

- Install Docker if you haven't already: https://docs.docker.com/get-docker/
- Clone the Supabase repository: `git clone https://github.com/supabase/supabase`
- Navigate to the docker directory: `cd supabase/docker`
- Start the Supabase local setup: `docker-compose up`
- Note down the Supabase URL and API key from the local setup

6. Create a `.streamlit/secrets.toml` file in the project root and add your Reddit API and Supabase credentials:

```
APP_PASSWORD=your_password
REDDIT_CLIENT_ID=your_client_id
REDDIT_CLIENT_SECRET=your_client_secret
REDDIT_USER_AGENT=your_user_agent
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
```

## Usage

1. Run the Streamlit app:

```
streamlit run src/reddit_scraper/app.py
```

2. Open your web browser and go to http://localhost:8501
3. Enter the password to access this app
4. Enter a search query in the text input field
5. Optionally, set the maximum number of posts to scrape
6. Click the "Scrape" button to start the scraping process
7. Once the scraping is complete, you can download the results as a CSV file

## Project Structure

```
reddit-parser/
│
├── ScrapeReddit.py
├── src/
│   ├── reddit_scraper/
│   │   ├── app.py
│   │   └── ScrapeReddit.py
├── pyproject.toml
└── README.md
```

- `src/reddit_scraper/app.py`: Contains the Streamlit web application code
- `src/reddit_scraper/ScrapeReddit.py`: Implements the ScrapeReddit class for web scraping
- `pyproject.toml`: Project configuration and dependencies

## Dependencies

All project dependencies are listed in the pyproject.toml file. The main dependencies include:

- streamlit
- pandas
- praw
- selenium
- beautifulsoup4
- python-dotenv
- supabase

To install development dependencies, you can use:

```
pip install .[dev]
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License.

## Disclaimer

Be sure to comply with Reddit's API terms of service and robots.txt file. Respect rate limits and be mindful of the load you put on Reddit's servers.
