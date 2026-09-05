# Huizenzoeker Agent 🕵️‍♂️🏡

An autonomous, cloud-native real estate monitoring agent that leverages Large Language Models (LLMs) to scrape, evaluate, and notify users of new property listings matching highly specific architectural and financial criteria.

## Overview

This project automates the time-consuming process of monitoring real estate markets. For my own search for a property in Apeldoorn, I built this application to solve a real-world logistical problem using modern web scraping, AI evaluation, and continuous integration pipelines. 

The agent runs fully autonomously via GitHub Actions, analyzes newly listed properties in the Apeldoorn area, and delivers high-priority matches directly to a mobile device via Telegram.

## Key Features

- **Cloud-Native Automation:** Scheduled execution using GitHub Actions cron jobs, completely removing the need for a local server.
- **Intelligent Evaluation:** Integrates `pydantic-ai` with Google's Gemini models (using a cascade model approach for API efficiency) to analyze property descriptions against a strict, custom criteria profile.
- **Robust State Management:** Maintains a JSON-based memory file (`gezien_huizen.json`) to track historical data and prevent duplicate notifications.
- **Instant Notifications:** Direct integration with the Telegram Bot API for real-time, formatted alerts.

## Tech Stack

| Component | Technology |
| :--- | :--- |
| **Language** | Python |
| **Web Scraping** | Playwright (Headless browsing) |
| **AI / LLM Integration** | Pydantic-AI, Google Gemini API |
| **CI/CD & Automation** | GitHub Actions |
| **Notifications** | Telegram Bot API |
| **Version Control** | Git, GitHub |

## Architecture & Workflow

1. **Trigger:** A GitHub Actions workflow (`scraper.yml`) initiates the Python script twice daily (09:00 & 17:00 CET).
2. **Scrape:** Playwright navigates target real estate broker websites, bypassing basic blocks, and extracts newly listed properties.
3. **Filter & Evaluate:** The script cross-references the local JSON memory to skip previously evaluated listings. Unknown listings are fed to the Gemini LLM with a strict prompt defining the structural requirements and budget constraints.
4. **Notify:** If the LLM scores the property an 8/10 or higher, a summarized analysis, including pros, cons, and a direct URL, is dispatched via Telegram.
5. **Persist State:** The system commits the updated JSON file back to the repository. The workflow uses conditional logic to only push when changes are detected, utilizing self-healing Git commands to prevent merge conflicts.

## Setup & Local Development

1. Clone the repository:
   ```bash
   git clone [https://github.com/wjstienstra/huizenzoeker_agent.git](https://github.com/wjstienstra/huizenzoeker_agent.git)
2. pip install -r requirements.txt
   playwright install
3. Setup .env variables and/or github secrets:
   GEMINI_API_KEY=your_google_api_key
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token
   TELEGRAM_CHAT_ID=your_telegram_chat_id
4. run python main.py

## Future Roadmap
- Multi-Tenant Architecture: Abstracting the search criteria into a central configuration file (search_profiles.json) to simultaneously support multiple users with disparate search profiles (e.g., varying budgets and       locations like) on a single deployment.
- Advanced Data Parsing: Expanding Playwright capabilities to parse image alt-tags for deeper LLM context.
