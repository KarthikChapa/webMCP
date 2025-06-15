# WebMCP (Web Model Context Protocol)

WebMCP is an AI-powered system that allows you to control a web browser using natural language commands. It leverages Large Language Models (LLMs) to understand your goals and Playwright to automate browser actions.

## Features

*   **Natural Language Control:** Interact with the web using plain English.
*   **Multi-LLM Support:** Primarily uses models via OpenRouter (e.g., Gemini Flash 2.0), with a flexible client for other models.
*   **Comprehensive Browser Automation:** Supports navigation, clicks, typing, data extraction, screenshots, and more.
*   **Intelligent Task Management:** Includes features for loop prevention and automatic task completion.
*   **Real-Time CLI Feedback:** Observe the AI's actions and retrieved information in real-time.
*   **Python-based:** Built with Python, Playwright, and FastAPI (for potential server extension).

## Project Structure

```
WebMCP_GitHub_Release/
├── src/
│   ├── browser/
│   │   ├── __init__.py
│   │   └── automation.py   # Playwright browser automation logic
│   ├── llm/
│   │   ├── __init__.py
│   │   └── client.py       # LLM client (OpenRouter)
│   ├── __init__.py
│   ├── cli_mcp.py          # Main CLI application
│   └── config.py           # Configuration loader
├── .env.example            # Example environment file
├── requirements.txt        # Python dependencies
└── README.md               # This file
```

## Setup

1.  **Clone the repository:**
    ```bash
    git clone <your-repo-url>
    cd WebMCP_GitHub_Release
    ```

2.  **Create a virtual environment (recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Install Playwright browsers:**
    ```bash
    playwright install
    ```
    (This might require `python -m playwright install` on some systems)

5.  **Set up environment variables:**
    *   Copy `.env.example` to `.env`:
        ```bash
        cp .env.example .env
        ```
    *   Edit the `.env` file and add your `OPENROUTER_API_KEY`:
        ```env
        OPENROUTER_API_KEY="YOUR_OPENROUTER_API_KEY_HERE"
        ```
        Get your API key from [OpenRouter.ai](https://openrouter.ai/).

## Usage

Run the CLI application:

```bash
python src/cli_mcp.py
```

You will be prompted to enter your goal. For example:

*   `get the current stock price for AAPL`
*   `what is the weather in London?`
*   `search for images of cats and take a screenshot`
*   `navigate to wikipedia.org and search for "artificial intelligence"`

Type `exit` to quit the CLI.
Type `test_login` for a pre-defined test script (currently configured for a hypothetical Instagram login).

## How it Works

1.  The user provides a goal in natural language via the CLI.
2.  `cli_mcp.py` sends this goal to an LLM (via `llm/client.py`) along with a system prompt that defines available browser actions and JSON output format.
3.  The LLM returns a sequence of browser actions in JSON format.
4.  `cli_mcp.py` interprets these actions and uses `browser/automation.py` (which wraps Playwright) to execute them.
5.  Information from the browser (page content, URLs, errors) is fed back into the context for the LLM in subsequent turns.
6.  The loop continues until the LLM determines the goal is achieved, an error occurs that cannot be resolved, or the maximum number of iterations is reached.
7.  A final summary and answer (if applicable) are presented to the user.

## Key Components

*   **`cli_mcp.py`**: The main command-line interface. It manages the interaction loop, communicates with the LLM, and orchestrates browser actions.
*   **`browser/automation.py`**: Handles all direct interactions with the web browser using Playwright. It provides a simplified API for actions like navigating, clicking, typing, etc.
*   **`llm/client.py`**: Manages communication with Large Language Models, primarily through OpenRouter. It handles API requests, model selection, and basic rate limiting.
*   **`config.py`**: Loads configuration settings from environment variables (e.g., API keys, log levels).
*   **System Prompts (in `cli_mcp.py`)**: These are crucial instructions given to the LLM to guide its behavior, define the available actions, and enforce the JSON output format.

## Customization

*   **LLM Models:** Modify `llm/client.py` to use different models or LLM providers. The current setup prioritizes free models on OpenRouter.
*   **Browser Actions:** Extend `browser/automation.py` and update the `SYSTEM_PROMPT_MCP` in `cli_mcp.py` to add new browser capabilities.
*   **Prompts:** Experiment with the system prompts in `cli_mcp.py` to fine-tune the AI's behavior and decision-making.

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues.
