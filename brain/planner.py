"""
╔══════════════════════════════════════════╗
║       TARS — Brain: LLM Planner          ║
╚══════════════════════════════════════════╝

The brain of TARS. Sends messages to the LLM,
handles tool calls, manages the thinking loop,
and streams all events to the dashboard.

Supports: Groq, Together, Anthropic, OpenRouter,
or any OpenAI-compatible endpoint.
"""

import time
from datetime import datetime
from brain.llm_client import LLMClient, _parse_failed_tool_call
from brain.prompts import TARS_SYSTEM_PROMPT, RECOVERY_PROMPT
from brain.tools import TARS_TOOLS
from utils.event_bus import event_bus


class TARSBrain:
    def __init__(self, config, tool_executor, memory_manager):
        self.config = config
        llm_cfg = config["llm"]
        self.client = LLMClient(
            provider=llm_cfg["provider"],
            api_key=llm_cfg["api_key"],
            base_url=llm_cfg.get("base_url"),
        )
        self.heavy_model = llm_cfg["heavy_model"]
        self.fast_model = llm_cfg["fast_model"]
        self.tool_executor = tool_executor
        self.memory = memory_manager
        self.conversation_history = []
        self.max_retries = config["safety"]["max_retries"]

    def _get_system_prompt(self):
        """Build the system prompt with current context."""
        import os
        memory_context = self.memory.get_context_summary()
        return TARS_SYSTEM_PROMPT.format(
            humor_level=self.config["agent"]["humor_level"],
            cwd=os.getcwd(),
            current_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            active_project=self.memory.get_active_project(),
            memory_context=memory_context,
        )

    def _choose_model(self, message):
        """Choose heavy or fast model based on task complexity."""
        complex_keywords = [
            "plan", "architect", "design", "debug", "fix", "analyze",
            "refactor", "why", "explain", "complex", "build", "create project",
            "set up", "configure", "optimize", "review"
        ]
        msg_lower = message.lower()
        if any(kw in msg_lower for kw in complex_keywords):
            return self.heavy_model
        return self.fast_model

    def think(self, user_message, use_heavy=None):
        """
        Send a message to Claude and process the response.
        Handles tool calls in a loop until Claude gives a final text response.
        Streams events to the dashboard in real-time.
        """
        # Choose model
        if use_heavy is not None:
            model = self.heavy_model if use_heavy else self.fast_model
        else:
            model = self._choose_model(user_message)

        event_bus.emit("thinking_start", {"model": model})

        # Add user message to history
        self.conversation_history.append({
            "role": "user",
            "content": user_message
        })

        # Keep conversation manageable — last 40 messages
        if len(self.conversation_history) > 40:
            self.conversation_history = self.conversation_history[-40:]

        retry_count = 0

        while True:
            call_start = time.time()

            try:
                # Use streaming for real-time dashboard updates
                with self.client.stream(
                    model=model,
                    max_tokens=4096,
                    system=self._get_system_prompt(),
                    tools=TARS_TOOLS,
                    messages=self.conversation_history,
                ) as stream:
                    for event in stream:
                        if event.type == "content_block_delta":
                            if hasattr(event.delta, "text"):
                                chunk = event.delta.text
                                event_bus.emit("thinking", {
                                    "text": chunk,
                                    "model": model,
                                })

                    # Get the final message
                    response = stream.get_final_message()

                call_duration = time.time() - call_start

                # Emit API stats
                usage = response.usage
                event_bus.emit("api_call", {
                    "model": model,
                    "tokens_in": usage.input_tokens,
                    "tokens_out": usage.output_tokens,
                    "duration": call_duration,
                })

            except Exception as e:
                # Try to recover from Groq tool_use_failed
                error_str = str(e)
                if "tool_use_failed" in error_str:
                    recovered = _parse_failed_tool_call(e)
                    if recovered:
                        response = recovered
                        call_duration = time.time() - call_start
                        event_bus.emit("api_call", {
                            "model": model, "tokens_in": 0,
                            "tokens_out": 0, "duration": call_duration,
                        })
                        print(f"  🔧 Brain: Recovered malformed tool call from Groq")
                    else:
                        # Recovery failed — try non-streaming fallback
                        try:
                            response = self.client.create(
                                model=model,
                                max_tokens=4096,
                                system=self._get_system_prompt(),
                                tools=TARS_TOOLS,
                                messages=self.conversation_history,
                            )
                            call_duration = time.time() - call_start
                            event_bus.emit("api_call", {
                                "model": model,
                                "tokens_in": response.usage.input_tokens,
                                "tokens_out": response.usage.output_tokens,
                                "duration": call_duration,
                            })
                            print(f"  🔧 Brain: Non-streaming fallback succeeded")
                        except Exception as e2:
                            event_bus.emit("error", {"message": f"LLM API error: {e2}"})
                            return f"❌ LLM API error: {e2}"
                else:
                    event_bus.emit("error", {"message": f"LLM API error: {e}"})
                    return f"❌ LLM API error: {e}"

            # Process response
            assistant_content = response.content
            self.conversation_history.append({
                "role": "assistant",
                "content": assistant_content
            })

            # Check if Claude wants to use tools
            if response.stop_reason == "tool_use":
                tool_results = []
                for block in assistant_content:
                    if block.type == "tool_use":
                        tool_name = block.name
                        tool_input = block.input
                        tool_id = block.id

                        # Emit tool call event
                        event_bus.emit("tool_called", {
                            "tool_name": tool_name,
                            "tool_input": tool_input,
                        })

                        # Execute the tool
                        print(f"  🔧 Executing: {tool_name}({tool_input})")
                        exec_start = time.time()
                        result = self.tool_executor.execute(tool_name, tool_input)
                        exec_duration = time.time() - exec_start

                        # Emit tool result event
                        event_bus.emit("tool_result", {
                            "tool_name": tool_name,
                            "content": result.get("content", str(result))[:500],
                            "success": result.get("success", not result.get("error")),
                            "duration": exec_duration,
                        })

                        # Emit iMessage events for the dashboard
                        if tool_name == "send_imessage":
                            event_bus.emit("imessage_sent", {
                                "message": tool_input.get("message", "")
                            })
                        elif tool_name == "wait_for_reply" and result.get("success"):
                            event_bus.emit("imessage_received", {
                                "message": result.get("content", "")
                            })

                        # Check for failure and retry logic
                        if result.get("error"):
                            retry_count += 1
                            if retry_count >= self.max_retries:
                                result["content"] = (
                                    result.get("content", "") +
                                    f"\n\n⚠️ This has failed {retry_count} times. "
                                    "Consider asking Abdullah for help via send_imessage."
                                )

                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_id,
                            "content": result.get("content", str(result)),
                        })

                # Add tool results back to conversation
                self.conversation_history.append({
                    "role": "user",
                    "content": tool_results
                })

                # New thinking block for next iteration
                event_bus.emit("thinking_start", {"model": model})

                # Continue the loop — Claude will process tool results
                continue

            else:
                # Claude gave a final text response — extract it
                final_text = ""
                for block in assistant_content:
                    if hasattr(block, "text"):
                        final_text += block.text

                event_bus.emit("task_completed", {"response": final_text[:300]})
                return final_text

    def reset_conversation(self):
        """Clear conversation history for a fresh start."""
        self.conversation_history = []
        event_bus.emit("status_change", {"status": "online", "label": "READY"})
