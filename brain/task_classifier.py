"""
╔══════════════════════════════════════════════════════════════╗
║      TARS — Task Classifier: Intent Understanding            ║
╠══════════════════════════════════════════════════════════════╣
║  Analyzes user tasks and determines:                         ║
║    - Which agent(s) to deploy                                ║
║    - Whether task needs decomposition                        ║
║    - Dependency ordering for multi-agent tasks               ║
║                                                              ║
║  Uses rule-based classification first (fast), falls back     ║
║  to LLM for ambiguous tasks.                                 ║
╚══════════════════════════════════════════════════════════════╝
"""

import re


# ─────────────────────────────────────────────
#  Rule-Based Classification (instant, no LLM)
# ─────────────────────────────────────────────

# Patterns for each agent category
PATTERNS = {
    "browser": [
        r"sign\s*up", r"log\s*in", r"create\s+account", r"fill\s+(out|in)\s+form",
        r"go\s+to\s+\S+\.\S+", r"open\s+\S+\.\S+",
        r"visit\s+\S+\.\S+", r"browse\s+to",
        r"click\s+on", r"navigate\s+to",
        r"on\s+the\s+website", r"on\s+the\s+page", r"web\s*page",
        r"gmail", r"facebook", r"twitter", r"instagram", r"linkedin",
        r"amazon", r"ebay", r"youtube", r"reddit", r"github\.com",
        r"google\.com", r"\.com\b", r"\.org\b", r"\.io\b", r"\.dev\b",
        r"order\s+(from|on)", r"book\s+(a|an|the)",
        r"check\s+my\s+(email|inbox)", r"submit\s+form",
        r"download\s+from", r"upload\s+to",
        r"search\s+(for|on|google|the\s+web)",
        r"(https?://|www\.)\S+",
    ],
    "coder": [
        r"(write|create|build|make)\s+(a\s+)?(script|program|app|application|website|api|server|bot|tool|function|class|module|package|library)",
        r"(fix|debug|solve|resolve)\s+(the\s+)?(bug|error|issue|problem|crash)",
        r"(refactor|optimize|improve|clean\s*up)\s+(the\s+)?code",
        r"(deploy|push|release|publish|ship)",
        r"(install|setup|configure|init)\s+(the\s+)?(project|package|dependency|environment)",
        r"(test|unit\s*test|integration\s*test)",
        r"git\s+(commit|push|pull|branch|merge|rebase|clone)",
        r"(add|create|implement)\s+(a\s+)?(feature|endpoint|route|component|page)",
        r"pip\s+install", r"npm\s+install", r"brew\s+install",
        r"(run|execute)\s+(the\s+)?(tests?|script|server|build)",
        r"\.(py|js|ts|html|css|json|yaml|yml|rb|go|rs|cpp|c|java|swift)\b",
        r"(python|javascript|typescript|node|react|vue|angular|django|flask|express|next)",
        r"dockerfile", r"docker", r"kubernetes", r"ci/cd", r"pipeline",
    ],
    "system": [
        r"open\s+(spotify|finder|terminal|safari|chrome|mail|calendar|notes|music|photos|messages|settings|preferences)",
        r"(play|pause|skip|volume)\s+(music|song|track|podcast)",
        r"(take|capture)\s+(a\s+)?screenshot",
        r"(change|set|adjust|modify)\s+(the\s+)?(brightness|volume|wallpaper|theme|display|resolution)",
        r"(lock|sleep|restart|shutdown|reboot)\s+(the\s+)?(mac|computer|screen)",
        r"(organize|clean|tidy)\s+(the\s+)?desktop",
        r"(connect|disconnect|pair)\s+(to\s+)?(bluetooth|wifi|airpods|headphones)",
        r"system\s+preferences", r"system\s+settings",
        r"keyboard\s+shortcut", r"automate",
        r"notification", r"dock", r"menubar", r"spotlight",
    ],
    "research": [
        r"(find|search|look\s+up|research|investigate|discover)\s+(the\s+)?(best|top|latest|cheapest|fastest|most|info|information|details|facts|data)",
        r"(what|who|when|where|why|how)\s+(is|are|was|were|do|does|did|can|could|would|should)",
        r"(compare|comparison|vs|versus|difference|between)",
        r"(review|reviews|rating|ratings)\s+(of|for)",
        r"(recommend|recommendation|suggest|suggestion)",
        r"(price|cost|pricing)\s+(of|for|comparison)",
        r"(weather|forecast|temperature)",
        r"(news|latest|update|updates)\s+(about|on|for)",
        r"(learn|explain|teach|tell)\s+(me\s+)?(about|how)",
        r"(summary|summarize|overview|breakdown)\s+(of|about)?",
        r"(pros?\s+and\s+cons?|advantages?\s+and\s+disadvantages?)",
    ],
    "file": [
        r"(find|locate|search\s+for)\s+(all\s+)?\S*(files?|documents?|photos?|images?|videos?|pdfs?|pngs?|jpe?gs?|csvs?|txts?)",
        r"(organize|sort|arrange|group|categorize)\s+(my\s+)?(files?|folder|downloads?|desktop|documents?)",
        r"(clean|clear|empty|purge)\s+(up\s+)?(the\s+)?(downloads?|desktop|trash|temp|cache)",
        r"(backup|archive|compress|zip|tar)\s+",
        r"(extract|unzip|untar|decompress)\s+",
        r"(move|copy|rename|duplicate)\s+(all\s+)?(files?|folder|directory)",
        r"(delete|remove|trash)\s+(all\s+)?(old|unused|duplicate|temp|temporary)",
        r"(how\s+much\s+space|disk\s+usage|storage)",
        r"(list|show|display)\s+(all\s+)?(files?|contents?)\s+(in|of)",
        r"\d+\s*(mb|gb|kb|tb)\b",
        r"(larger|bigger|smaller|over|under)\s+than\s+\d+",
    ],
    "chat": [
        r"^(hi|hello|hey|sup|yo|thanks|thank\s+you|good\s+(morning|afternoon|evening|night)|how\s+are\s+you|what'?s?\s+up)",
        r"^(ok|okay|cool|nice|great|awesome|perfect|got\s+it|understood)",
        r"^(yes|no|yeah|nah|sure|nope)$",
    ],
}


def classify_task(task):
    """
    Classify a task into agent categories.

    Returns:
        dict with:
            category: str — "browser", "coder", "system", "research", "file", "multi", "chat"
            agents: list — which agents to deploy
            confidence: float — 0.0-1.0 how confident the classification is
    """
    task_lower = task.lower().strip()
    scores = {cat: 0 for cat in PATTERNS}

    # Score each category by pattern matches
    for category, patterns in PATTERNS.items():
        for pattern in patterns:
            matches = re.findall(pattern, task_lower)
            if matches:
                scores[category] += len(matches)

    # Sort by score
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top_cat, top_score = ranked[0]
    second_cat, second_score = ranked[1]

    # No matches at all → probably chat or needs LLM classification
    if top_score == 0:
        return {
            "category": "chat",
            "agents": [],
            "confidence": 0.3,
            "needs_llm": True,
        }

    # Chat detected
    if top_cat == "chat":
        return {
            "category": "chat",
            "agents": [],
            "confidence": 0.8,
            "needs_llm": False,
        }

    # Single dominant category
    if top_score >= 2 and second_score <= 1:
        return {
            "category": top_cat,
            "agents": [top_cat],
            "confidence": min(0.9, 0.5 + top_score * 0.1),
            "needs_llm": False,
        }

    # Multiple categories have high scores → multi-agent
    if top_score >= 2 and second_score >= 2:
        agents = [cat for cat, score in ranked if score >= 2 and cat != "chat"]
        return {
            "category": "multi",
            "agents": agents,
            "confidence": 0.6,
            "needs_llm": True,  # LLM should decompose
        }

    # Low confidence single match
    return {
        "category": top_cat,
        "agents": [top_cat],
        "confidence": 0.4 + top_score * 0.1,
        "needs_llm": top_score < 2,  # Ask LLM to confirm if weak match
    }


# ─────────────────────────────────────────────
#  LLM-based classification (for ambiguous tasks)
# ─────────────────────────────────────────────

CLASSIFIER_PROMPT = """Classify this user task for an AI agent system. Choose which specialist agent(s) should handle it.

Available agents:
- browser — Web browsing, forms, web apps, online accounts, ordering, web research requiring clicking through sites
- coder — Writing code, building projects, debugging, git, deploying, terminal commands, installing packages
- system — macOS control: opening apps, keyboard shortcuts, screenshots, system settings, automation
- research — Deep research: finding information, comparing products, answering questions, fact-checking
- file — File management: organizing files, finding files, backup, compress, clean up directories

Task: {task}

Respond in this exact JSON format:
{{"category": "<single_best_category>", "agents": ["<agent1>", "<agent2_if_needed>"], "sub_tasks": [{{"agent": "<agent>", "task": "<specific_sub_task>"}}], "dependencies": {{"0": [], "1": [0]}}}}

Rules:
- "category" is the primary category
- "agents" lists ALL agents needed (can be 1 or more)
- "sub_tasks" breaks the work into specific tasks for each agent
- "dependencies" maps sub_task index to indices it depends on (empty list = independent)
- Keep sub_tasks SPECIFIC and ACTIONABLE
- If it's just a greeting or simple chat, use {{"category": "chat", "agents": [], "sub_tasks": [], "dependencies": {{}}}}

JSON:"""


def classify_with_llm(task, llm_client, model):
    """
    Use LLM to classify ambiguous tasks and decompose multi-agent ones.

    Returns dict with category, agents, sub_tasks, dependencies.
    """
    import json

    try:
        response = llm_client.create(
            model=model,
            max_tokens=1024,
            system="You are a task classifier. Output valid JSON only. No markdown, no explanation.",
            tools=[],
            messages=[{"role": "user", "content": CLASSIFIER_PROMPT.format(task=task)}],
        )

        # Extract text from response
        text = ""
        for block in response.content:
            if hasattr(block, "text") and block.text:
                text += block.text

        # Parse JSON
        text = text.strip()
        # Handle markdown code fences
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()

        result = json.loads(text)

        # Validate required fields
        result.setdefault("category", "chat")
        result.setdefault("agents", [])
        result.setdefault("sub_tasks", [])
        result.setdefault("dependencies", {})

        return result

    except Exception as e:
        # Fallback to rule-based
        basic = classify_task(task)
        return {
            "category": basic["category"],
            "agents": basic["agents"],
            "sub_tasks": [{"agent": basic["category"], "task": task}] if basic["agents"] else [],
            "dependencies": {},
            "error": f"LLM classification failed: {e}",
        }
