from typing import List

from bs4 import BeautifulSoup
from markdownify import markdownify as md
from readability import Document
import re
from langchain_core.messages import SystemMessage, HumanMessage

from apix_agent.commons.type_def import AgentConfigSchema
from apix_agent.apix_agent_core.tools.web_search.models import UrlResultItem, ContentResultItem
from apix_agent.apix_agent_core.LLM.llm_adapter import LlmNodeAdapter
from apix_agent.commons.logger import logger


WEB_CLEAN_AGENT_PROMPT = """
    You are a content cleaning and formatting assistant. Your task is to process the raw search results provided by the search tool and transform them into clean, well-structured markdown format.

    Instructions:
    1. Remove all irrelevant information, duplicate content, and noise from the search results
    2. Extract the core valuable information
    3. Organize the cleaned content into proper markdown format
    4. Do not add any commentary, explanations, or conversational elements
    5. Output only the cleaned markdown content without any additional text

    Input: Raw search results will be provided below
    Output: Cleaned markdown content only, no other text
"""


class SearchResultCleaner:
    """
    Stateless result cleaner.
    """

    # --------------------------------------------------
    # Link-level cleaning
    # --------------------------------------------------
    def clean_links(
        self,
        results: List[UrlResultItem]
    ) -> List[UrlResultItem]:
        
        seen = set()
        cleaned: List[UrlResultItem] = []

        for item in results:
            if item.url in seen:
                continue
            seen.add(item.url)
            cleaned.append(item)

        return cleaned
    def _log_clean_result(self, mode: str, raw_length: int, content: str):

        cleaned_length = len(content or "")

        retention_ratio = (
            f"{(cleaned_length / raw_length):.2%}"
            if raw_length > 0
            else "N/A"
        )

        logger.info(
            "Clear search result: "
            f"mode={mode}, "
            f"raw={raw_length}, "
            f"cleaned={cleaned_length}, "
            f"retention={retention_ratio}"
        )

    # --------------------------------------------------
    # Content-level cleaning
    # --------------------------------------------------
    async def clean_content(
        self,
        item: ContentResultItem,
        config: AgentConfigSchema,
    ) -> ContentResultItem:

        mode = config.get("web_cleaner_mode", "rules") or "rules"
        raw_text = item.content or ""
        raw_length = len(raw_text)

        # LLM MODE
        if mode == "llm":

            llm_provider = config.get("models_provider", "")
            llm_model_name = config.get("model_name", "")
            model_api_key = config.get("api_key", "")

            if not llm_provider or not llm_model_name:
                return item

            no_reasoning_config = config.copy()
            no_reasoning_config["enable_think"] = False

            llm = LlmNodeAdapter.get_atapted_llm_node(
                provider=llm_provider,
                model=llm_model_name,
                api_key=model_api_key,
                config=no_reasoning_config,
            )

            prompt = [
                SystemMessage(content=WEB_CLEAN_AGENT_PROMPT),
                HumanMessage(content=raw_text),
            ]

            output = await LlmNodeAdapter.ainvoke(
                llm,
                input=prompt,
                reasoning=False,
                fall_back_config=config
            )

            item.content = (output.content or "").strip()

            self._log_clean_result("llm", raw_length, item.content)
            return item

        # RULE MODE (readability + markdownify)
        if mode == "rules":

            try:
                doc = Document(raw_text)
                main_html = doc.summary(html_partial=True)
            except Exception:
                main_html = raw_text

            soup = BeautifulSoup(main_html, "html.parser")

            for tag in soup(["script", "style", "noscript"]):
                tag.decompose()

            clean_html = str(soup)
            markdown_text = md(clean_html)

            lines = markdown_text.splitlines()
            cleaned_lines = []
            seen = set()

            for line in lines:
                line = line.strip()

                if not line:
                    continue
                if len(line) < 3:
                    continue
                if line in seen:
                    continue

                seen.add(line)
                cleaned_lines.append(line)

            final_text = "\n\n".join(cleaned_lines)
            final_text = re.sub(r"\n{3,}", "\n\n", final_text)

            item.content = final_text.strip()

            self._log_clean_result("rules", raw_length, item.content)
            return item

        # SIMPLE FALLBACK MODE (pure text filtering)
        lines = raw_text.splitlines()
        cleaned = []
        seen = set()

        noise_keywords = [
            "cookie",
            "subscribe",
            "sign up",
            "log in",
            "advertisement",
            "privacy policy",
            "terms of service",
        ]

        for line in lines:
            line = line.strip()

            if not line:
                continue
            if len(line) < 3:
                continue

            lower = line.lower()
            if any(k in lower for k in noise_keywords):
                continue

            if line in seen:
                continue

            seen.add(line)
            cleaned.append(line)

        final_text = "\n\n".join(cleaned)
        final_text = re.sub(r"\n{3,}", "\n\n", final_text)

        item.content = final_text.strip()

        self._log_clean_result("simple_rules", raw_length, item.content)
        return item