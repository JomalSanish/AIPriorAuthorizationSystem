import os
from unittest.mock import patch, MagicMock
from langchain_core.prompts import ChatPromptTemplate
from utils.llm_utils import run_chain_with_fallback
from pydantic import BaseModel

class DummySchema(BaseModel):
    name: str

def test_run_chain_with_fallback_success_gemini():
    # Mock ChatOpenAI
    with patch("utils.llm_utils.ChatOpenAI") as mock_chat_openai:
        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value = mock_llm
        # Since LangChain calls the mock directly, we set the return value of __call__
        mock_llm.return_value = DummySchema(name="Gemini Success")
        mock_chat_openai.return_value = mock_llm

        prompt = ChatPromptTemplate.from_template("test {input}")
        
        with patch.dict(os.environ, {"OPENAI_API_KEY": "fake_openai_key", "GEMINI_API_KEY": "fake_gemini_key"}):
            res = run_chain_with_fallback(prompt, {"input": "hello"}, structured_schema=DummySchema)
            assert res.name == "Gemini Success"
            
            # Assert Gemini was instantiated
            mock_chat_openai.assert_any_call(
                model="gemini-1.5-flash",
                temperature=0,
                openai_api_key="fake_gemini_key",
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
            )

def test_run_chain_with_fallback_trigger_openai():
    # Mock ChatOpenAI to fail on Gemini first call and succeed on OpenAI second call
    with patch("utils.llm_utils.ChatOpenAI") as mock_chat_openai:
        mock_gemini_llm = MagicMock()
        mock_gemini_llm.with_structured_output.side_effect = Exception("Gemini rate limit error")
        
        mock_openai_llm = MagicMock()
        mock_openai_llm.with_structured_output.return_value = mock_openai_llm
        # Set the return value of __call__ for OpenAI mock
        mock_openai_llm.return_value = DummySchema(name="OpenAI Fallback Success")
        
        mock_chat_openai.side_effect = [mock_gemini_llm, mock_openai_llm]

        prompt = ChatPromptTemplate.from_template("test {input}")
        
        with patch.dict(os.environ, {"OPENAI_API_KEY": "fake_openai_key", "GEMINI_API_KEY": "fake_gemini_key"}):
            res = run_chain_with_fallback(prompt, {"input": "hello"}, structured_schema=DummySchema)
            assert res.name == "OpenAI Fallback Success"
            
            # Verify it instantiated OpenAI
            mock_chat_openai.assert_any_call(
                model="gpt-4o-mini",
                temperature=0,
                openai_api_key="fake_openai_key"
            )
