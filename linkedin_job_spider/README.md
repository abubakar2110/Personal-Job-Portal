# LinkedIn Job Spider

A Scrapy spider that collects job listings from LinkedIn.

## Setup

1. Install dependencies:
```
pip install -r requirements.txt
```

2. Create a `.env` file in the project root with your LinkedIn credentials:
```
LINKEDIN_USER=your_email@example.com
LINKEDIN_PASS=your_password
```

## Running the Spider

From the `linkedin_job_spider` directory, run:
```
scrapy crawl linkedin_jobs
```

## Output

Collected job data will be saved to:
- JSON file: `linkedin_job_data/linkedin_jobs_[timestamp].json`
- TXT file: `linkedin_job_data/linkedin_jobs_[timestamp].txt`

## Troubleshooting

If you're not getting job results:

1. Check screenshots in the working directory for debugging info
2. LinkedIn may be blocking the scraper - try changing your credentials
3. Try running without headless mode by commenting out the headless option
4. Increase the wait time by changing the human_delay function 