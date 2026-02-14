"""
╔══════════════════════════════════════════════════════════════╗
║      TARS — Research Agent: The Deep Researcher              ║
╠══════════════════════════════════════════════════════════════╣
║  Expert at multi-source research, fact-finding, analysis.    ║
║  Searches the web, reads pages, extracts info, takes notes,  ║
║  and synthesizes findings into comprehensive answers.        ║
║                                                              ║
║  Uses browser engine under the hood for web access.          ║
║  Own LLM loop. Inherits from BaseAgent.                      ║
╚══════════════════════════════════════════════════════════════╝
"""

from agents.base_agent import BaseAgent
from agents.agent_tools import (
    TOOL_WEB_SEARCH, TOOL_BROWSE, TOOL_EXTRACT,
    TOOL_NOTE, TOOL_NOTES, TOOL_DONE, TOOL_STUCK,
)
from hands.browser import (
    act_google, act_goto, act_read_page, act_read_url, _activate_chrome,
)


# ─────────────────────────────────────────────
#  System Prompt
# ─────────────────────────────────────────────

RESEARCH_SYSTEM_PROMPT = """You are TARS Research Agent — the world's best research analyst. You find, verify, and synthesize information from multiple sources with academic rigor and journalistic thoroughness.

## Your Capabilities
- Search Google for any topic
- Read full web pages (articles, docs, product pages, etc.)
- Extract specific information from pages
- Take structured notes as you research
- Review all collected notes
- Synthesize findings into comprehensive answers

## Your Research Process
1. **Define** — Understand exactly what information is needed
2. **Search** — Start with a broad web_search to find relevant sources
3. **Read** — Use `browse` to read the most promising results
4. **Extract** — Use `extract` to pull specific data points from pages
5. **Note** — Save every important finding with `note` (key-value pairs)
6. **Verify** — Cross-reference claims across multiple sources (minimum 2-3 sources)
7. **Synthesize** — Review all `notes` and compile final answer

## Research Standards
- **Accuracy** — Never make claims without sourcing them. If sources disagree, note the disagreement.
- **Completeness** — Answer all aspects of the question. If something can't be found, say so explicitly.
- **Recency** — Prefer recent sources. Note dates when they matter.
- **Objectivity** — Present multiple viewpoints on controversial topics.
- **Specificity** — Include specific numbers, names, dates, URLs — not vague generalizations.

## Rules
1. ALWAYS search multiple sources. Never rely on a single source.
2. Use `note` to save findings AS you research — don't try to remember everything.
3. Review your `notes` before writing the final synthesis.
4. If a web page is too long, use `extract` with a specific question instead of `browse`.
5. Include source URLs in your final summary so findings can be verified.
6. Distinguish between facts, opinions, and unverified claims.
7. If the question has a definitive answer (e.g., "what's the capital of France"), be concise.
8. If the question requires analysis (e.g., "best laptop under $1000"), be thorough with pros/cons.
9. Call `done` with your complete research summary. Call `stuck` if sources are insufficient.
10. Be efficient — don't over-research simple questions.

## CRITICAL ANTI-HALLUCINATION RULES
- You MUST actually search and read sources using your tools before making claims.
- NEVER claim you created accounts, sent emails, or performed actions — you are a RESEARCH agent.
- If a task requires DOING something (signup, login, clicking buttons), call `stuck` immediately.
- Every claim in your summary must be backed by a tool call (web_search, browse, extract).
- If you didn't find it through your tools, don't claim it exists.
"""


class ResearchAgent(BaseAgent):
    """Autonomous research agent — deep multi-source research and synthesis."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._notes = {}  # Working memory for research findings

    @property
    def agent_name(self):
        return "Research Agent"

    @property
    def agent_emoji(self):
        return "🔍"

    @property
    def system_prompt(self):
        return RESEARCH_SYSTEM_PROMPT

    @property
    def tools(self):
        return [
            TOOL_WEB_SEARCH, TOOL_BROWSE, TOOL_EXTRACT,
            TOOL_NOTE, TOOL_NOTES, TOOL_DONE, TOOL_STUCK,
        ]

    def _on_start(self, task):
        """Clear notes and activate Chrome for new research task."""
        self._notes = {}
        _activate_chrome()

    def _dispatch(self, name, inp):
        """Route research tool calls."""
        try:
            if name == "web_search":
                return self._web_search(inp["query"])

            elif name == "browse":
                return self._browse(inp["url"])

            elif name == "extract":
                return self._extract(inp["url"], inp["question"])

            elif name == "note":
                return self._note(inp["key"], inp["value"])

            elif name == "notes":
                return self._get_notes()

            return f"Unknown research tool: {name}"
        except Exception as e:
            return f"ERROR: {e}"

    def _web_search(self, query):
        """Quick Google search and return results."""
        text = act_google(query)
        if isinstance(text, dict):
            return text.get("content", str(text))
        return str(text) if text else "No search results found."

    def _browse(self, url):
        """Navigate to URL and read full page content."""
        act_goto(url)
        import time
        time.sleep(2)
        content = act_read_page()
        if isinstance(content, dict):
            text = content.get("content", str(content))
        else:
            text = str(content)
        # Truncate very long pages
        if len(text) > 15000:
            text = text[:12000] + "\n\n... [page truncated — use 'extract' for specific info] ..."
        url_info = act_read_url()
        url_str = url_info.get("content", url) if isinstance(url_info, dict) else str(url_info)
        return f"URL: {url_str}\n\n{text}"

    def _extract(self, url, question):
        """Navigate to URL and extract specific info."""
        act_goto(url)
        import time
        time.sleep(2)
        content = act_read_page()
        if isinstance(content, dict):
            text = content.get("content", str(content))
        else:
            text = str(content)
        # Return the page content — the LLM will extract the answer
        if len(text) > 15000:
            text = text[:12000] + "\n\n... [truncated] ..."
        return f"Page content for question '{question}':\n\n{text}"

    def _note(self, key, value):
        """Save a research finding."""
        self._notes[key] = value
        return f"📝 Noted: {key} = {value[:200]}{'...' if len(value) > 200 else ''} ({len(self._notes)} notes total)"

    def _get_notes(self):
        """Review all collected notes."""
        if not self._notes:
            return "No notes yet. Use 'note' to save findings as you research."
        lines = [f"## Research Notes ({len(self._notes)} findings)\n"]
        for i, (key, value) in enumerate(self._notes.items(), 1):
            lines.append(f"{i}. **{key}**: {value}")
        return "\n".join(lines)
