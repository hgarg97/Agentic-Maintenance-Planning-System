# orchestration/agent_executor.py
"""
Agentic execution framework that enables true autonomous tool use.
Implements ReAct (Reasoning + Acting) pattern for agent decision-making.
"""

from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass
from langchain_openai import ChatOpenAI
from langchain_core.messages import (
    SystemMessage,
    HumanMessage,
    AIMessage,
    ToolMessage
)
from csv_helper import get_tool_registry
import json


@dataclass
class AgentResponse:
    """Structured response from an agent execution"""
    success: bool
    content: str
    tool_calls_made: List[Dict[str, Any]]
    reasoning_steps: List[str]
    final_state: Dict[str, Any]
    error: Optional[str] = None


class AgentExecutor:
    """
    Executes an agent with autonomous tool usage capability.
    
    The agent can:
    - Decide which tools to use based on its goal
    - Chain multiple tool calls together
    - Reason about results and adjust strategy
    - Handle errors and retry with different approaches
    """
    
    def __init__(
        self,
        agent_name: str,
        system_prompt: str,
        llm_model: str = "gpt-4o-mini",
        max_iterations: int = 5,
        temperature: float = 0.2
    ):
        self.agent_name = agent_name
        self.system_prompt = system_prompt
        self.max_iterations = max_iterations
        self.tool_registry = get_tool_registry()
        
        # Create LLM with tools bound
        from csv_helper import get_langchain_tools
        tools = get_langchain_tools()
        self.llm = ChatOpenAI(
            model=llm_model,
            temperature=temperature
        ).bind_tools(tools)
        
    def execute(
        self,
        task: str,
        context: Dict[str, Any],
        available_data: Optional[Dict[str, Any]] = None
    ) -> AgentResponse:
        """
        Execute the agent on a specific task with given context.
        
        Args:
            task: The specific task/goal for this agent
            context: Relevant context data (work order info, state, etc.)
            available_data: Optional pre-fetched data to avoid redundant tool calls
            
        Returns:
            AgentResponse with results and execution trace
        """
        messages = self._build_initial_messages(task, context, available_data)
        tool_calls_made = []
        reasoning_steps = []
        final_state = {}
        
        for iteration in range(self.max_iterations):
            try:
                # Agent thinks and potentially acts
                response = self.llm.invoke(messages)
                
                # Check if agent wants to use tools
                if response.tool_calls:
                    # Agent decided to use tools - execute them
                    tool_results = self._execute_tool_calls(response.tool_calls)
                    tool_calls_made.extend(tool_results)
                    
                    # Add AI response and tool results to conversation
                    messages.append(AIMessage(content=response.content or "", tool_calls=response.tool_calls))
                    
                    for tool_result in tool_results:
                        messages.append(ToolMessage(
                            content=json.dumps(tool_result["result"]),
                            tool_call_id=tool_result["call_id"]
                        ))
                        reasoning_steps.append(
                            f"Used {tool_result['tool_name']} with args {tool_result['args']}"
                        )
                    
                    # Continue loop - agent might need more tools
                    continue
                
                else:
                    # Agent is done - no more tools needed
                    reasoning_steps.append("Agent completed reasoning")
                    final_content = response.content or ""
                    
                    # Try to extract structured data if present
                    final_state = self._extract_structured_output(final_content)
                    
                    return AgentResponse(
                        success=True,
                        content=final_content,
                        tool_calls_made=tool_calls_made,
                        reasoning_steps=reasoning_steps,
                        final_state=final_state
                    )
                    
            except Exception as e:
                error_msg = f"Error in iteration {iteration}: {str(e)}"
                reasoning_steps.append(error_msg)
                
                # Try to recover
                if iteration < self.max_iterations - 1:
                    messages.append(HumanMessage(
                        content=f"That approach had an error: {str(e)}. Please try a different approach."
                    ))
                    continue
                else:
                    # Max retries exceeded
                    return AgentResponse(
                        success=False,
                        content="",
                        tool_calls_made=tool_calls_made,
                        reasoning_steps=reasoning_steps,
                        final_state={},
                        error=error_msg
                    )
        
        # Max iterations reached
        return AgentResponse(
            success=False,
            content="",
            tool_calls_made=tool_calls_made,
            reasoning_steps=reasoning_steps,
            final_state={},
            error=f"Max iterations ({self.max_iterations}) reached"
        )
    
    def _build_initial_messages(
        self,
        task: str,
        context: Dict[str, Any],
        available_data: Optional[Dict[str, Any]]
    ) -> List:
        """Build initial message chain for the agent"""
        messages = [SystemMessage(content=self.system_prompt)]
        
        # Build user message with task and context
        user_content_parts = [f"**Your Task:** {task}\n"]
        
        if context:
            user_content_parts.append("\n**Context:**")
            for key, value in context.items():
                if value is not None and value != "":
                    user_content_parts.append(f"- {key}: {value}")
        
        if available_data:
            user_content_parts.append("\n**Available Data (already fetched):**")
            for key, value in available_data.items():
                user_content_parts.append(f"- {key}: {json.dumps(value, default=str)[:200]}...")
        
        user_content_parts.append(
            "\n**Instructions:**"
            "\n1. Think about what information you need"
            "\n2. Use available tools to gather that information"
            "\n3. Reason through the problem step by step"
            "\n4. When you have enough information, provide your final answer"
            "\n\nYou can use tools multiple times if needed. Work systematically."
        )
        
        messages.append(HumanMessage(content="\n".join(user_content_parts)))
        return messages
    
    def _execute_tool_calls(self, tool_calls: List) -> List[Dict[str, Any]]:
        """Execute tool calls and return results"""
        results = []
        
        for tool_call in tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            call_id = tool_call["id"]
            
            try:
                # Get tool function from registry
                tool_fn = self.tool_registry.get(tool_name)
                
                if not tool_fn:
                    result = {"error": f"Tool {tool_name} not found in registry"}
                else:
                    # Execute the tool
                    result = tool_fn(**tool_args)
                
                results.append({
                    "call_id": call_id,
                    "tool_name": tool_name,
                    "args": tool_args,
                    "result": result,
                    "success": "error" not in result if isinstance(result, dict) else True
                })
                
            except Exception as e:
                results.append({
                    "call_id": call_id,
                    "tool_name": tool_name,
                    "args": tool_args,
                    "result": {"error": str(e)},
                    "success": False
                })
        
        return results
    
    def _extract_structured_output(self, content: str) -> Dict[str, Any]:
        """Try to extract structured JSON from agent output"""
        try:
            # Look for JSON in the content
            if "{" in content and "}" in content:
                # Extract JSON block
                start = content.find("{")
                end = content.rfind("}") + 1
                json_str = content[start:end]
                return json.loads(json_str)
        except:
            pass
        
        # Return content as-is if no JSON found
        return {"raw_output": content}


class AgentOrchestrator:
    """
    Manages multiple agents and coordinates their execution.
    Provides a higher-level interface for the graph nodes.
    """
    
    def __init__(self):
        self.agents: Dict[str, AgentExecutor] = {}
    
    def register_agent(
        self,
        agent_name: str,
        system_prompt: str,
        **kwargs
    ) -> None:
        """Register an agent with the orchestrator"""
        self.agents[agent_name] = AgentExecutor(
            agent_name=agent_name,
            system_prompt=system_prompt,
            **kwargs
        )
    
    def execute_agent(
        self,
        agent_name: str,
        task: str,
        context: Dict[str, Any],
        available_data: Optional[Dict[str, Any]] = None
    ) -> AgentResponse:
        """Execute a specific agent"""
        if agent_name not in self.agents:
            raise ValueError(f"Agent {agent_name} not registered")
        
        return self.agents[agent_name].execute(task, context, available_data)


# ==============================
# Convenience function for quick usage
# ==============================

def create_agentic_executor(
    agent_name: str,
    system_prompt: str,
    **kwargs
) -> AgentExecutor:
    """Factory function to create an agent executor"""
    return AgentExecutor(
        agent_name=agent_name,
        system_prompt=system_prompt,
        **kwargs
    )
