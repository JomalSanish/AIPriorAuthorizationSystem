# Quickstart: Unified Prior Auth Flow & Mock Policy Ground Truth

This guide helps configure and run the unified single-pane Prior Authorization assistant.

## Prerequisites

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Configure your OpenAI API key in a `.env` file in the project root:
   ```env
   OPENAI_API_KEY=sk-...
   ```

## Ground Truth Setup

Ensure `data/mock_policies.json` exists containing prior authorization guidelines.

## Running the Dashboard

Launch the application:
```bash
streamlit run app.py
```

## Running Tests

Run the integration tests:
```bash
pytest tests/
```
