# intelligent_query_parser.py - INTELLIGENT LLM-POWERED QUERY HANDLER
"""
Intelligent query handler that uses an LLM agent to:
1. Understand natural language queries flexibly
2. Reason about which CSV functions to call and in what order
3. Chain multiple function calls to build comprehensive answers
4. Synthesize results from multiple tables

Example queries this can handle:
- "What parts does WO-AC-025 require?"
- "Show me all details about part PS-HF-004 including its inventory and any pending orders"
- "Which work orders need the same parts as WO-PS-015?"
- "What's the status of parts for work order WO-AC-006?"
"""

import re
import json
from typing import Tuple, Dict, Any
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from csv_helper import get_langchain_tools, get_tool_registry

# ==============================
# Query Agent System Prompt
# ==============================

QUERY_AGENT_PROMPT = """You are an intelligent data query assistant for a maintenance management system.

**Your Role:**
Answer user questions about work orders, spare parts, inventory, roles, and schedules by:
1. Understanding what the user is asking
2. Deciding which data functions to call (you can call multiple)
3. Synthesizing the results into a clear, comprehensive answer

**Available Data Functions:**
- get_work_order_by_id: Get details of a specific work order
- get_all_work_orders: List all work orders
- get_required_parts_for_work_order: Get parts needed for a work order
- check_inventory_for_parts: Check inventory availability (REQUIRES required_parts LIST)
- get_role_for_work_order: Get assigned role for a work order
- get_all_roles: List all maintenance roles
- get_scheduled_work_orders: Get scheduled work orders

**CRITICAL TOOL USAGE RULES:**

User: "What parts does WO-AC-025 require?"
Your thinking:
1. First, get the work order details to understand what it is
2. Then get required parts for that work order
3. Check inventory status for those parts
4. Synthesize all this into a comprehensive answer with tables

User: "Show me everything about part PS-HF-004"
Your thinking:
1. Get spare parts details for PS-HF-004
2. Check current inventory status for this part
3. Look for work orders that use this part (search in required_parts)
4. Present a complete picture with all related information

Note

1. **check_inventory_for_parts MUST receive a required_parts argument (a LIST of parts)**
   
   CORRECT Examples:
   ✅ check_inventory_for_parts(required_parts=[{"part_code": "AC-OF-101", "required_quantity": 1}])
   ✅ check_inventory_for_parts(required_parts=<result_from_get_required_parts>)
   
   WRONG Examples:
   ❌ check_inventory_for_parts()  # Missing argument
   ❌ check_inventory_for_parts({})  # Empty dict instead of list
   ❌ check_inventory_for_parts(required_parts={})  # Empty dict

2. **Always chain tools in the correct order:**
   
   Step 1: get_required_parts_for_work_order("WO-AC-025")
   Result: [{"part_code": "AC-OF-101", ...}, ...]
   
   Step 2: check_inventory_for_parts(required_parts=<result from step 1>)
   
   The result from step 1 MUST be passed to step 2!

3. **If you get an error about missing 'required_parts' argument:**
   - Look at the previous tool call result
   - That result IS the required_parts list
   - Pass it to check_inventory_for_parts

**Concrete Example of Correct Tool Chaining:**

User asks: "What parts does WO-AC-018 require?"

Tool Call #1:
```json
{
  "name": "get_required_parts_for_work_order",
  "args": {"work_order_or_id": "WO-AC-018"}
}
```
Returns: [{"part_code": "AC-MOT-015", "part_name": "Motor Coupling", "required_quantity": 3}, ...]

Tool Call #2 (CORRECT):
```json
{
  "name": "check_inventory_for_parts",
  "args": {
    "required_parts": [
      {"part_code": "AC-MOT-015", "part_name": "Motor Coupling", "required_quantity": 3}
    ]
  }
}
```

**Response Format:**
- Use markdown with headers (##, ###)
- Use tables for structured data
- Use emojis for visual appeal (📋 🔧 📦 ⚠️ ✅)
- Be concise but comprehensive
- Always provide actionable information

**Critical:**
- If the user asks to "execute" a work order, return "EXECUTE_WORKFLOW" in your response
- Otherwise, answer the data query completely using available tools
- ALWAYS call tools - don't make up answers from memory
- NEVER call check_inventory_for_parts without the required_parts LIST argument
"""


# ==============================
# Intelligent Query Agent
# ==============================

class IntelligentQueryAgent:
    """LLM-powered agent that can reason about queries and chain tool calls"""
    
    def __init__(self, model: str = "gpt-4o-mini", max_iterations: int = 10):
        self.tools = get_langchain_tools()
        self.tool_registry = get_tool_registry()
        self.llm = ChatOpenAI(model=model, temperature=0.2).bind_tools(self.tools)
        self.max_iterations = max_iterations
    
    def process_query(self, user_query: str) -> Tuple[bool, str]:
        """
        Process a user query using LLM reasoning and tool calling.
        
        Returns:
            Tuple of (handled, response)
            - handled: True if query was handled, False if should execute workflow
            - response: Answer to the query or empty string if workflow execution needed
        """
        
        # Quick check: If user explicitly says "execute", route to workflow
        if "execute" in user_query.lower() and re.search(r'\b(WO-[A-Z]+-\d+)\b', user_query, re.IGNORECASE):
            return False, ""  # Let workflow handler take over
        
        messages = [
            SystemMessage(content=QUERY_AGENT_PROMPT),
            HumanMessage(content=user_query)
        ]
        
        tool_calls_made = []
        
        for iteration in range(self.max_iterations):
            try:
                # Get LLM response
                response = self.llm.invoke(messages)
                
                # Check if LLM wants to use tools
                if response.tool_calls:
                    # Execute tool calls
                    messages.append(AIMessage(content=response.content or "", tool_calls=response.tool_calls))
                    
                    for tool_call in response.tool_calls:
                        tool_name = tool_call["name"]
                        tool_args = tool_call["args"]
                        tool_id = tool_call["id"]
                        
                        try:
                            # Execute the tool
                            tool_fn = self.tool_registry[tool_name]
                            result = tool_fn(**tool_args)
                            
                            tool_calls_made.append({
                                "tool": tool_name,
                                "args": tool_args,
                                "result": result,
                                "success": True
                            })
                            
                            # Add tool result to conversation
                            messages.append(ToolMessage(
                                content=json.dumps(result, default=str),
                                tool_call_id=tool_id
                            ))
                            
                        except Exception as e:
                            error_result = {"error": str(e)}
                            tool_calls_made.append({
                                "tool": tool_name,
                                "args": tool_args,
                                "result": error_result,
                                "success": False
                            })
                            
                            messages.append(ToolMessage(
                                content=json.dumps(error_result),
                                tool_call_id=tool_id
                            ))
                    
                    # Continue loop - LLM might need more tools
                    continue
                
                else:
                    # LLM is done - has final answer
                    final_answer = response.content or ""
                    
                    # Check if LLM is requesting workflow execution
                    if "EXECUTE_WORKFLOW" in final_answer:
                        return False, ""
                    
                    # Format the answer nicely
                    formatted_answer = self._format_answer(final_answer, tool_calls_made)
                    return True, formatted_answer
            
            except Exception as e:
                # Error in LLM call
                return True, f"❌ **Error processing query:** {str(e)}\n\nPlease try rephrasing your question."
        
        # Max iterations reached
        return True, "⚠️ **Query too complex** - reached maximum analysis steps. Please try breaking your question into smaller parts."
    
    def _format_answer(self, llm_answer: str, tool_calls: list) -> str:
        """Format the final answer with metadata"""
        
        # Clean up the answer
        answer = llm_answer.strip()
        
        # Add query metadata (optional - can be removed if too verbose)
        if tool_calls and len(tool_calls) > 0:
            metadata = f"\n\n---\n\n<details>\n<summary>🔍 <i>Query Details ({len(tool_calls)} data operations)</i></summary>\n\n"
            for idx, call in enumerate(tool_calls, 1):
                tool_name = call['tool'].replace('_', ' ').title()
                success = "✅" if call['success'] else "❌"
                metadata += f"{idx}. {success} {tool_name}\n"
            metadata += "\n</details>"
            
            answer += metadata
        
        return answer


# ==============================
# Main Query Handler (entry point)
# ==============================

# Global agent instance
_query_agent = None

def get_query_agent() -> IntelligentQueryAgent:
    """Get or create the global query agent"""
    global _query_agent
    if _query_agent is None:
        _query_agent = IntelligentQueryAgent()
    return _query_agent


async def handle_data_query(user_input: str) -> Tuple[bool, str]:
    """
    Main entry point for handling data queries.
    
    Args:
        user_input: User's question
        
    Returns:
        Tuple of (handled, response_message)
        - handled: True if query was handled, False if should proceed to workflow execution
        - response_message: Response to send to user
    """
    
    try:
        agent = get_query_agent()
        return agent.process_query(user_input)
    
    except Exception as e:
        # Fallback error handling
        return True, f"❌ **Error:** {str(e)}\n\nPlease try again or rephrase your question."