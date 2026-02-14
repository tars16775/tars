"""
╔══════════════════════════════════════════╗
║       TARS — LLM Client Abstraction      ║
╚══════════════════════════════════════════╝

Unified client for Anthropic (Claude) and
OpenAI-compatible APIs (Groq, Together, etc).

Normalizes responses so planner.py and
browser_agent.py don't care which provider
is behind the scenes.
"""

import json
import re
import uuid

# ─────────────────────────────────────────────
#  Normalized Response Objects
#  (Mimics Anthropic's format so existing code
#   works with zero changes)
# ─────────────────────────────────────────────

class ContentBlock:
    """A single content block (text or tool_use)."""
    def __init__(self, block_type, text=None, name=None, input_data=None, block_id=None):
        self.type = block_type
        self.text = text or ""
        self.name = name
        self.input = input_data or {}
        self.id = block_id


class Usage:
    """Token usage stats."""
    def __init__(self, input_tokens=0, output_tokens=0):
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class LLMResponse:
    """Normalized response — same shape as Anthropic's."""
    def __init__(self, content, stop_reason, usage):
        self.content = content          # List[ContentBlock]
        self.stop_reason = stop_reason  # "tool_use" | "end_turn"
        self.usage = usage              # Usage


# ─────────────────────────────────────────────
#  Tool Format Conversion
# ─────────────────────────────────────────────

def _anthropic_to_openai_tools(tools):
    """Convert Anthropic tool schemas to OpenAI function-calling format."""
    openai_tools = []
    for tool in tools:
        schema = tool.get("input_schema", {"type": "object", "properties": {}})
        # Ensure 'properties' key exists (OpenAI requires it)
        if "properties" not in schema:
            schema["properties"] = {}
        openai_tools.append({
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "parameters": schema,
            }
        })
    return openai_tools


def _openai_response_to_normalized(response):
    """Convert OpenAI chat completion response to our normalized format."""
    choice = response.choices[0]
    message = choice.message
    blocks = []

    # Text content
    if message.content:
        blocks.append(ContentBlock("text", text=message.content))

    # Tool calls
    has_tool_calls = False
    if message.tool_calls:
        has_tool_calls = True
        for tc in message.tool_calls:
            try:
                args = json.loads(tc.function.arguments) if tc.function.arguments else {}
            except json.JSONDecodeError:
                args = {}
            blocks.append(ContentBlock(
                "tool_use",
                name=tc.function.name,
                input_data=args,
                block_id=tc.id,
            ))

    stop_reason = "tool_use" if has_tool_calls else "end_turn"

    usage = Usage(
        input_tokens=getattr(response.usage, "prompt_tokens", 0),
        output_tokens=getattr(response.usage, "completion_tokens", 0),
    )

    return LLMResponse(content=blocks, stop_reason=stop_reason, usage=usage)


# ─────────────────────────────────────────────
#  Malformed Tool Call Recovery
#  (Groq/Llama sometimes generates XML-style
#   tool calls that fail validation. We parse
#   them here and recover.)
# ─────────────────────────────────────────────

def _parse_failed_tool_call(error):
    """
    Parse a Groq tool_use_failed error and extract the tool call.

    Groq's Llama models sometimes generate tool calls in XML format:
        <function=goto{"url": "https://example.com"}</function>
    or multi-param:
        <function=type{"selector": "#email", "text": "hello"}</function>

    We extract the function name and arguments, then build a proper
    LLMResponse as if the API had returned it correctly.

    Returns LLMResponse if parsed successfully, None otherwise.
    """
    error_str = str(error)

    # Try to get failed_generation directly from the error body (OpenAI SDK)
    failed_gen = None
    if hasattr(error, 'body') and isinstance(error.body, dict):
        failed_gen = error.body.get('failed_generation')
        if not failed_gen:
            # Sometimes nested under 'error'
            failed_gen = error.body.get('error', {}).get('failed_generation') if isinstance(error.body.get('error'), dict) else None

    # Fallback: regex extraction from error string
    if not failed_gen:
        fg_match = re.search(r"'failed_generation':\s*'(.+?)'\s*\}", error_str, re.DOTALL)
        if not fg_match:
            fg_match = re.search(r'"failed_generation":\s*"(.+?)"\s*\}', error_str, re.DOTALL)
        if fg_match:
            failed_gen = fg_match.group(1)
            failed_gen = failed_gen.replace('\\"', '"').replace("\\'", "'")

    # Pattern 2: Look for the XML pattern directly in the error string
    if not failed_gen:
        xml_match = re.search(r'<function=\w+.*?</function>', error_str)
        if xml_match:
            failed_gen = xml_match.group(0)

    # Pattern 3: "attempted to call tool 'tool_name={"args"}'" pattern  
    if not failed_gen:
        tool_match = re.search(r"attempted to call tool\s*'(\w+=\{.+)", error_str, re.DOTALL)
        if tool_match:
            raw = tool_match.group(1)
            # Clean up: remove trailing quote/bracket artifacts
            raw = raw.rstrip("'\"")
            failed_gen = raw

    if not failed_gen:
        return None

    # Now parse the XML-style function call(s)
    # Groq/Llama generates various formats:
    #   <function=goto{"url": "https://..."}</function>
    #   <function=goto>{"url": "https://..."}</function>  
    #   <function=look></function>
    #   <function=type{"selector": "#x", "text": "y"}</function>
    #   deploy_browser_agent={"task": "..."}  (no XML at all)

    # Unified pattern: function name, then optional JSON
    # Handle both <function=name>{"args"}</function> and <function=name{"args"}</function>
    calls = re.findall(
        r'<function=(\w+)>?\s*(.*?)\s*<?/function>',
        failed_gen,
        re.DOTALL,
    )

    # Fallback: no XML tags, just tool_name={"args"} or tool_name={...}
    if not calls:
        bare_match = re.match(r'(\w+)\s*=\s*(\{.+\})\s*$', failed_gen.strip(), re.DOTALL)
        if bare_match:
            calls = [(bare_match.group(1), bare_match.group(2))]

    # Fallback 2: look for tool_name({"args"}) pattern
    if not calls:
        paren_match = re.match(r'(\w+)\s*\(\s*(\{.+\})\s*\)\s*$', failed_gen.strip(), re.DOTALL)
        if paren_match:
            calls = [(paren_match.group(1), paren_match.group(2))]

    if not calls:
        return None

    blocks = []

    # Extract any text before the first <function tag
    text_before = re.split(r'<function=', failed_gen)[0].strip()
    if text_before:
        blocks.append(ContentBlock("text", text=text_before))

    for func_name, args_str in calls:
        # Parse the arguments JSON
        args = {}
        args_raw = args_str.strip()
        # Remove trailing > that sometimes gets captured
        if args_raw.endswith('>'):
            args_raw = args_raw[:-1].strip()
        if args_raw and args_raw.startswith('{'):
            try:
                args = json.loads(args_raw)
            except json.JSONDecodeError:
                # Try fixing common issues
                try:
                    # Remove trailing commas before }
                    cleaned = re.sub(r',\s*}', '}', args_raw)
                    # Fix escaped quotes
                    cleaned = cleaned.replace('\\"', '"')
                    args = json.loads(cleaned)
                except json.JSONDecodeError:
                    print(f"    ⚠️ [Parser] Could not parse args: {args_raw[:200]}")
                    pass

        call_id = f"call_{uuid.uuid4().hex[:24]}"
        blocks.append(ContentBlock(
            "tool_use",
            name=func_name,
            input_data=args,
            block_id=call_id,
        ))

    if not any(b.type == "tool_use" for b in blocks):
        return None

    print(f"    🔧 [LLM Client] Recovered {len(calls)} malformed tool call(s): {[c[0] for c in calls]}")

    return LLMResponse(
        content=blocks,
        stop_reason="tool_use",
        usage=Usage(input_tokens=0, output_tokens=0),
    )


# ─────────────────────────────────────────────
#  Conversation Format Conversion
# ─────────────────────────────────────────────

def _convert_history_for_openai(messages, system_prompt):
    """
    Convert Anthropic-style conversation history to OpenAI format.

    Anthropic style:
      - system is a separate param
      - assistant content = list of ContentBlock objects
      - tool results = [{"type": "tool_result", "tool_use_id": "...", "content": "..."}]

    OpenAI style:
      - system is a message with role "system"
      - assistant content = text + tool_calls
      - tool results = separate messages with role "tool"
    """
    openai_messages = [{"role": "system", "content": system_prompt}]

    for msg in messages:
        role = msg["role"]
        content = msg["content"]

        if role == "user":
            # Could be a string or a list of tool results
            if isinstance(content, str):
                openai_messages.append({"role": "user", "content": content})
            elif isinstance(content, list):
                # Tool results — convert to OpenAI tool messages
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "tool_result":
                        openai_messages.append({
                            "role": "tool",
                            "tool_call_id": item["tool_use_id"],
                            "content": str(item.get("content", "")),
                        })
            else:
                openai_messages.append({"role": "user", "content": str(content)})

        elif role == "assistant":
            # Could be a string, list of ContentBlock objects, or list of dicts
            if isinstance(content, str):
                openai_messages.append({"role": "assistant", "content": content})
            elif isinstance(content, list):
                # Extract text and tool calls from content blocks
                text_parts = []
                tool_calls = []
                for block in content:
                    # Handle ContentBlock objects
                    if hasattr(block, "type"):
                        if block.type == "text" and block.text:
                            text_parts.append(block.text)
                        elif block.type == "tool_use":
                            tool_calls.append({
                                "id": block.id,
                                "type": "function",
                                "function": {
                                    "name": block.name,
                                    "arguments": json.dumps(block.input if isinstance(block.input, dict) else {}),
                                }
                            })
                    # Handle raw dicts (shouldn't happen but be safe)
                    elif isinstance(block, dict):
                        if block.get("type") == "text":
                            text_parts.append(block.get("text", ""))
                        elif block.get("type") == "tool_use":
                            tool_calls.append({
                                "id": block.get("id", ""),
                                "type": "function",
                                "function": {
                                    "name": block.get("name", ""),
                                    "arguments": json.dumps(block.get("input", {})),
                                }
                            })

                assistant_msg = {"role": "assistant"}
                assistant_msg["content"] = "\n".join(text_parts) if text_parts else None
                if tool_calls:
                    assistant_msg["tool_calls"] = tool_calls
                openai_messages.append(assistant_msg)

    return openai_messages


# ─────────────────────────────────────────────
#  Streaming Wrapper
# ─────────────────────────────────────────────

class OpenAIStreamWrapper:
    """
    Wraps OpenAI streaming to match the interface planner.py expects.
    Collects the full response while yielding stream events.
    """
    def __init__(self, client, **kwargs):
        self._client = client
        self._kwargs = kwargs
        self._final_response = None

    def __enter__(self):
        self._stream = self._client.chat.completions.create(
            stream=True,
            **self._kwargs,
        )
        self._collected_text = ""
        self._collected_tool_calls = {}  # index -> {id, name, arguments}
        self._usage = Usage()
        self._events = []
        return self

    def __exit__(self, *args):
        pass

    def __iter__(self):
        for chunk in self._stream:
            if not chunk.choices:
                # Usage chunk at the end
                if hasattr(chunk, "usage") and chunk.usage:
                    self._usage = Usage(
                        input_tokens=getattr(chunk.usage, "prompt_tokens", 0),
                        output_tokens=getattr(chunk.usage, "completion_tokens", 0),
                    )
                continue

            delta = chunk.choices[0].delta

            # Text delta
            if delta.content:
                self._collected_text += delta.content
                # Yield an event-like object for streaming
                event = _StreamEvent(delta.content)
                yield event

            # Tool call deltas
            if delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index
                    if idx not in self._collected_tool_calls:
                        self._collected_tool_calls[idx] = {
                            "id": tc_delta.id or "",
                            "name": "",
                            "arguments": "",
                        }
                    if tc_delta.id:
                        self._collected_tool_calls[idx]["id"] = tc_delta.id
                    if tc_delta.function:
                        if tc_delta.function.name:
                            self._collected_tool_calls[idx]["name"] = tc_delta.function.name
                        if tc_delta.function.arguments:
                            self._collected_tool_calls[idx]["arguments"] += tc_delta.function.arguments

            # Check for usage in the chunk
            if hasattr(chunk, "usage") and chunk.usage:
                self._usage = Usage(
                    input_tokens=getattr(chunk.usage, "prompt_tokens", 0),
                    output_tokens=getattr(chunk.usage, "completion_tokens", 0),
                )

    def get_final_message(self):
        """Build the normalized response from collected stream data."""
        blocks = []

        if self._collected_text:
            blocks.append(ContentBlock("text", text=self._collected_text))

        has_tools = False
        for idx in sorted(self._collected_tool_calls.keys()):
            tc = self._collected_tool_calls[idx]
            has_tools = True
            try:
                args = json.loads(tc["arguments"]) if tc["arguments"] else {}
            except json.JSONDecodeError:
                args = {}
            blocks.append(ContentBlock(
                "tool_use",
                name=tc["name"],
                input_data=args,
                block_id=tc["id"],
            ))

        stop_reason = "tool_use" if has_tools else "end_turn"
        return LLMResponse(content=blocks, stop_reason=stop_reason, usage=self._usage)


class _StreamEvent:
    """Mimics Anthropic's content_block_delta event."""
    def __init__(self, text):
        self.type = "content_block_delta"
        self.delta = _Delta(text)

class _Delta:
    def __init__(self, text):
        self.text = text


# ─────────────────────────────────────────────
#  Main LLM Client
# ─────────────────────────────────────────────

class LLMClient:
    """
    Unified LLM client. Supports:
      - provider: "anthropic" → uses anthropic SDK
      - provider: "groq" / "together" / "openai" / "openrouter"
          → uses openai SDK with custom base_url

    Usage is identical to before — just swap the client.
    """

    PROVIDER_URLS = {
        "groq": "https://api.groq.com/openai/v1",
        "together": "https://api.together.xyz/v1",
        "openrouter": "https://openrouter.ai/api/v1",
        "openai": "https://api.openai.com/v1",
    }

    def __init__(self, provider, api_key, **kwargs):
        self.provider = provider
        self.api_key = api_key

        if provider == "anthropic":
            import anthropic
            self._client = anthropic.Anthropic(api_key=api_key)
            self._mode = "anthropic"
        else:
            from openai import OpenAI
            base_url = kwargs.get("base_url") or self.PROVIDER_URLS.get(provider)
            if not base_url:
                raise ValueError(f"Unknown provider '{provider}'. Use: anthropic, groq, together, openrouter, openai — or pass base_url=")
            self._client = OpenAI(api_key=api_key, base_url=base_url)
            self._mode = "openai"

    # ── Non-streaming call (used by agents) ──

    def create(self, model, max_tokens, system, tools, messages):
        """Create a completion (non-streaming). Returns normalized LLMResponse.
        
        Includes recovery logic for Groq/Llama tool_use_failed errors —
        the model sometimes generates malformed XML tool calls which the
        API rejects. We parse the failed generation and recover the tool call.
        """
        if self._mode == "anthropic":
            resp = self._client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system,
                tools=tools,
                messages=messages,
            )
            return self._wrap_anthropic_response(resp)
        else:
            import time as _time
            openai_tools = _anthropic_to_openai_tools(tools)
            openai_messages = _convert_history_for_openai(messages, system)

            max_retries = 3
            for attempt in range(1, max_retries + 1):
                try:
                    resp = self._client.chat.completions.create(
                        model=model,
                        max_tokens=max_tokens,
                        tools=openai_tools if openai_tools else None,
                        messages=openai_messages,
                    )
                    return _openai_response_to_normalized(resp)
                except Exception as e:
                    error_str = str(e)

                    # Groq/Llama tool_use_failed — try to recover the tool call
                    if "tool_use_failed" in error_str:
                        recovered = _parse_failed_tool_call(e)
                        if recovered:
                            return recovered
                        # If recovery failed, retry with a nudge
                        if attempt < max_retries:
                            _time.sleep(0.5 * attempt)
                            continue

                    # Rate limit — just retry
                    if "rate_limit" in error_str.lower() and attempt < max_retries:
                        _time.sleep(1.0 * attempt)
                        continue

                    raise

    # ── Streaming call (used by planner) ──

    def stream(self, model, max_tokens, system, tools, messages):
        """Stream a completion. Returns context manager with Anthropic-like interface."""
        if self._mode == "anthropic":
            return self._client.messages.stream(
                model=model,
                max_tokens=max_tokens,
                system=system,
                tools=tools,
                messages=messages,
            )
        else:
            openai_tools = _anthropic_to_openai_tools(tools)
            openai_messages = _convert_history_for_openai(messages, system)
            return OpenAIStreamWrapper(
                self._client,
                model=model,
                max_tokens=max_tokens,
                tools=openai_tools if openai_tools else None,
                messages=openai_messages,
            )

    # ── Helper ──

    def _wrap_anthropic_response(self, resp):
        """Wrap native Anthropic response into our normalized format (pass-through)."""
        # Anthropic responses already have .content, .stop_reason, .usage
        # that match our expected interface, so just return as-is
        return resp
