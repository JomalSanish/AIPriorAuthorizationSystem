from __future__ import annotations

import os
import logging
from typing import Any, TypeVar, Type
from pydantic import BaseModel
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

logger = logging.getLogger("llm_utils")

T = TypeVar("T", bound=BaseModel)

def run_chain_with_fallback(
    prompt: ChatPromptTemplate,
    inputs: dict[str, Any],
    structured_schema: Type[T] | None = None,
    temperature: float = 0
) -> Any:
    """Execute LLM chain using Gemini, with automatic fallback to OpenAI if Gemini fails."""
    openai_key = os.getenv("OPENAI_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY")
    
    # 1. Try Gemini first
    if gemini_key:
        try:
            logger.info("Attempting LLM execution with Gemini (gemini-1.5-flash)...")
            # Google Generative AI OpenAI-compatible base URL
            llm = ChatOpenAI(
                model="gemini-1.5-flash",
                temperature=temperature,
                openai_api_key=gemini_key,
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
            )
            if structured_schema:
                chain = prompt | llm.with_structured_output(structured_schema)
            else:
                chain = prompt | llm
            return chain.invoke(inputs)
        except Exception as e:
            logger.warning(f"Gemini invocation failed: {e}. Checking fallback options...")
            if not openai_key:
                raise e

    # 2. Try OpenAI fallback
    if openai_key:
        logger.info("Executing LLM execution fallback with OpenAI (gpt-4o-mini)...")
        llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=temperature,
            openai_api_key=openai_key
        )
        if structured_schema:
            chain = prompt | llm.with_structured_output(structured_schema)
        else:
            chain = prompt | llm
        return chain.invoke(inputs)

    raise ValueError("Neither OPENAI_API_KEY nor GEMINI_API_KEY is configured or valid.")
