"""
LangChain chain assembly and model initialisation.

Exported:
    initialize_model(model_name, use_gpt, gpt_api_key)
        Builds analysis_chain and sentiment_chain for the session.

    run_analysis(stock_code, text) -> {"summary": str, "sentiment_score": float}
        Runs the full chain on a new article.

    score_summary(summary) -> float
        Runs only the sentiment leg on a pre-existing summary.
"""

import re
import logging
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI

from prompts import SUMMARY_PROMPT, SENTIMENT_PROMPT

logger = logging.getLogger(__name__)

_analysis_chain = None   # {stock_code, text}  ->  {…, summary, sentiment_score}
_sentiment_chain = None  # {summary}            ->  float


def _clean_summary(text: str) -> str:
    text = text.strip()
    text = text.split("Final answer:")[-1].strip()
    text = text.split("\n")[-1].strip()
    return text.replace("Summary:", "").strip()


def _parse_score(text: str) -> float:
    match = re.search(r'[01](?:\.\d+)?|\.\d+', text.strip())
    if match:
        return round(max(0.0, min(1.0, float(match.group()))), 4)
    logger.warning("Could not parse sentiment score from %r — defaulting to 0.5", text)
    return 0.5


def is_no_info(summary: str) -> bool:
    return "no direct information about" in summary.lower()


def initialize_model(model_name: str, use_gpt: bool = False, gpt_api_key: str = None):
    global _analysis_chain, _sentiment_chain

    llm = (
        ChatOpenAI(model="gpt-4.1", api_key=gpt_api_key, temperature=0)
        if use_gpt
        else ChatOllama(model=model_name, temperature=0,
                        base_url="http://host.docker.internal:11434")
    )

    summary_chain = (
        SUMMARY_PROMPT
        | llm
        | StrOutputParser()
        | RunnableLambda(_clean_summary)
    )

    _sentiment_chain = (
        SENTIMENT_PROMPT
        | llm
        | StrOutputParser()
        | RunnableLambda(_parse_score)
    )

    # Full chain: adds "summary" then "sentiment_score" to the input dict
    _analysis_chain = (
        RunnablePassthrough.assign(summary=summary_chain)
        | RunnablePassthrough.assign(sentiment_score=_sentiment_chain)
    )

    logger.info("Chains initialised — model: %s", "GPT" if use_gpt else model_name)


def run_analysis(stock_code: str, text: str) -> dict:
    """Returns {"summary": str, "sentiment_score": float, ...}"""
    return _analysis_chain.invoke({"stock_code": stock_code, "text": text})


def score_summary(summary: str) -> float:
    """Score a pre-existing summary without regenerating it."""
    return _sentiment_chain.invoke({"summary": summary})
