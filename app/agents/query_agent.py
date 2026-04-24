"""
Query parsing agent using LangChain LCEL.

Converts a natural language query into a structured ParsedGitHubQuery
using a typed PydanticOutputParser — no free-form text leaks out.
"""
from __future__ import annotations

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableSerializable
from langchain_google_genai import ChatGoogleGenerativeAI

from app.core.config import get_settings
from app.core.exceptions import LLMError, QueryParsingError
from app.core.logging import get_logger
from app.schemas.search import ParsedGitHubQuery
from app.utils.fallback_parser import fallback_parse_query

logger = get_logger(__name__)

_SYSTEM_PROMPT = """\
You are a GitHub repository search query optimizer.
Given a natural language description of what a developer is looking for,
extract structured fields to build an optimal GitHub search query.

Rules:
- `query`: short keyword phrase, no GitHub qualifiers, no filler words
- `language`: programming language if clearly mentioned or implied, else null
- `min_stars`: infer from intent: "popular"→1000, "beginner"→100, "best"→500, otherwise 0
- `pushed_after`: only set when user asks for "recent", "new", "latest" repos (use YYYY-01-01 of current year); else null
- `fork`: true when forks should be included, false when they should be excluded, else null
- `archived`: true when archived repos should be included, false when they should be excluded, else null
- `topic`: set to a single topic slug when the query explicitly requests a repository topic, else null
- `license`: set to a license identifier when the query explicitly requests a license, else null

{format_instructions}
"""

_HUMAN_PROMPT = "Natural language query: {user_query}"


def build_query_agent() -> RunnableSerializable:
    settings = get_settings()

    parser = PydanticOutputParser(pydantic_object=ParsedGitHubQuery)

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", _SYSTEM_PROMPT),
            ("human", _HUMAN_PROMPT),
        ]
    ).partial(format_instructions=parser.get_format_instructions())

    llm = ChatGoogleGenerativeAI(
        model=settings.llm_model,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
        api_key=settings.gemini_api_key,
    )

    # LCEL pipeline: prompt | llm | structured parser
    chain: RunnableSerializable = prompt | llm | parser
    return chain


async def parse_query(user_query: str) -> ParsedGitHubQuery:
    """
    Attempt LLM-based parsing; fall back to rule-based extraction on failure.
    """
    settings = get_settings()

    if not settings.gemini_api_key:
        logger.warning("parse_query.no_api_key", fallback="rule-based")
        return fallback_parse_query(user_query)

    try:
        chain = build_query_agent()
        result: ParsedGitHubQuery = await chain.ainvoke({"user_query": user_query})
        logger.info("parse_query.llm_success", parsed=result.model_dump())
        return result
    except Exception as exc:
        logger.warning("parse_query.llm_failed", error=str(exc), fallback="rule-based")
        try:
            return fallback_parse_query(user_query)
        except Exception as fb_exc:
            raise QueryParsingError(
                "Both LLM and fallback parsing failed",
                {"llm_error": str(exc), "fallback_error": str(fb_exc)},
            ) from fb_exc
