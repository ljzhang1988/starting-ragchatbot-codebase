from openai import OpenAI
from typing import List, Optional, Dict, Any
import json

class AIGenerator:
    """Handles interactions with SiliconFlow (OpenAI-compatible) API for generating responses"""

    SYSTEM_PROMPT = """ You are an AI assistant specialized in course materials and educational content with access to a comprehensive search tool for course information.

Search Tool Usage:
- Use the search tool **only** for questions about specific course content or detailed educational materials
- **One search per query maximum**
- Synthesize search results into accurate, fact-based responses
- If search yields no results, state this clearly without offering alternatives

Outline Tool Usage:
- Use the `get_course_outline` tool when a user asks for a course outline, syllabus, table of contents, or lesson list
- When returning an outline, always include: course title, course link, and each lesson's number and title

Response Protocol:
- **General knowledge questions**: Answer using existing knowledge without searching
- **Course-specific questions**: Search first, then answer
- **Course outline / syllabus questions**: Use `get_course_outline`, then present the course title, course link, and the full numbered lesson list
- **No meta-commentary**:
 - Provide direct answers only — no reasoning process, search explanations, or question-type analysis
 - Do not mention "based on the search results"


All responses must be:
1. **Brief, Concise and focused** - Get to the point quickly
2. **Educational** - Maintain instructional value
3. **Clear** - Use accessible language
4. **Example-supported** - Include relevant examples when they aid understanding
Provide only the direct answer to what was asked.
"""

    def __init__(self, api_key: str, model: str, base_url: str = "https://api.siliconflow.cn/v1"):
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model

        self.base_params = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": 800
        }

    def generate_response(self, query: str,
                         conversation_history: Optional[str] = None,
                         tools: Optional[List] = None,
                         tool_manager=None) -> str:
        system_content = (
            f"{self.SYSTEM_PROMPT}\n\nPrevious conversation:\n{conversation_history}"
            if conversation_history
            else self.SYSTEM_PROMPT
        )

        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": query}
        ]

        api_params = {
            **self.base_params,
            "messages": messages,
        }

        # Convert Anthropic tool format to OpenAI tool format
        if tools:
            openai_tools = self._convert_tools(tools)
            api_params["tools"] = openai_tools
            api_params["tool_choice"] = "auto"

        response = self.client.chat.completions.create(**api_params)
        message = response.choices[0].message

        # Handle tool calls
        if message.tool_calls and tool_manager:
            return self._handle_tool_execution(message, messages, api_params, tool_manager)

        return message.content

    def _convert_tools(self, anthropic_tools: List[Dict]) -> List[Dict]:
        """Convert Anthropic tool format to OpenAI tool format"""
        openai_tools = []
        for tool in anthropic_tools:
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["input_schema"]
                }
            })
        return openai_tools

    def _handle_tool_execution(self, message, messages: List, base_params: Dict, tool_manager) -> str:
        # Add assistant message with tool calls
        messages.append({"role": "assistant", "content": message.content, "tool_calls": message.tool_calls})

        # Execute each tool call
        for tool_call in message.tool_calls:
            tool_name = tool_call.function.name
            tool_args = json.loads(tool_call.function.arguments)

            tool_result = tool_manager.execute_tool(tool_name, **tool_args)

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": tool_result
            })

        # Get final response without tools
        final_params = {
            **self.base_params,
            "messages": messages,
        }

        final_response = self.client.chat.completions.create(**final_params)
        return final_response.choices[0].message.content
