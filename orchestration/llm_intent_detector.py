"""
LLM-powered intent detection for maintenance queries.
Uses a small, fast LLM to understand user intent accurately.
"""

from langchain_openai import ChatOpenAI
from typing import Dict, Literal
import json
import re


# Intent types
IntentType = Literal[
    "maintenance_planning",
    "material_readiness", 
    "blockage_reason",
    "material_reservation",
    "procurement_status"
]


class IntentDetector:
    """
    LLM-powered intent detector that understands maintenance queries.
    Uses a lightweight LLM for fast, accurate intent classification.
    """
    
    def __init__(self, model: str = "gpt-4o-mini", temperature: float = 0.0):
        """
        Initialize the intent detector.
        
        Args:
            model: LLM model to use (default: gpt-4o-mini for speed)
            temperature: Temperature for LLM (0.0 for deterministic)
        """
        self.llm = ChatOpenAI(model=model, temperature=temperature)
        
        self.intent_definitions = {
            "maintenance_planning": "User wants to plan, schedule, or organize maintenance work",
            "material_readiness": "User wants to check if materials/parts are available",
            "blockage_reason": "User wants to understand why work is blocked or cannot proceed",
            "material_reservation": "User wants to reserve or allocate materials for work",
            "procurement_status": "User wants to check purchase orders or procurement status"
        }
    
    def detect_intent(self, user_query: str, work_order_id: str = None) -> Dict[str, str]:
        """
        Detect the user's intent using LLM reasoning.
        
        Args:
            user_query: The user's natural language query
            work_order_id: Optional work order ID mentioned in query
            
        Returns:
            Dictionary with 'intent', 'confidence', and 'reasoning'
        """
        
        prompt = self._build_intent_prompt(user_query, work_order_id)
        
        try:
            response = self.llm.invoke(prompt)
            result = self._parse_intent_response(response.content)
            return result
        
        except Exception as e:
            # Fallback to keyword-based detection
            print(f"Intent detection error: {e}, falling back to keywords")
            return self._fallback_detection(user_query)
    
    def _build_intent_prompt(self, user_query: str, work_order_id: str = None) -> str:
        """Build the prompt for intent classification"""
        
        intent_descriptions = "\n".join([
            f"- **{intent}**: {desc}"
            for intent, desc in self.intent_definitions.items()
        ])
        
        wo_context = f"\nWork Order ID: {work_order_id}" if work_order_id else ""
        
        prompt = f"""You are an intent classifier for an industrial maintenance system.

Classify the user's intent into ONE of these categories:

{intent_descriptions}

User Query: "{user_query}"{wo_context}

Analyze the query and respond with ONLY a JSON object (no markdown, no code blocks):

{{
  "intent": "<intent_name>",
  "confidence": "high|medium|low",
  "reasoning": "<brief explanation of why you chose this intent>"
}}

Examples:

Query: "Plan WO-101"
{{"intent": "maintenance_planning", "confidence": "high", "reasoning": "User explicitly asks to plan maintenance"}}

Query: "Why is WO-102 blocked?"
{{"intent": "blockage_reason", "confidence": "high", "reasoning": "User asks why work is blocked"}}

Query: "Do we have parts for WO-103?"
{{"intent": "material_readiness", "confidence": "high", "reasoning": "User asks about parts availability"}}

Query: "Check materials for WO-104"
{{"intent": "material_readiness", "confidence": "high", "reasoning": "User wants to check material status"}}

Query: "Reserve materials for WO-105"
{{"intent": "material_reservation", "confidence": "high", "reasoning": "User wants to reserve materials"}}

Query: "What's the status of PR-123?"
{{"intent": "procurement_status", "confidence": "high", "reasoning": "User asks about purchase requisition status"}}

Now classify this query:
"""
        
        return prompt
    
    def _parse_intent_response(self, response_text: str) -> Dict[str, str]:
        """Parse the LLM's JSON response"""
        
        # Clean up response - remove markdown code blocks if present
        cleaned = response_text.strip()
        if cleaned.startswith("```"):
            # Remove markdown code blocks
            lines = cleaned.split("\n")
            cleaned = "\n".join([
                line for line in lines 
                if not line.strip().startswith("```")
            ])
        
        # Remove any "json" language identifier
        cleaned = cleaned.replace("```json", "").replace("```", "").strip()
        
        try:
            result = json.loads(cleaned)
            
            # Validate intent
            if result["intent"] not in self.intent_definitions:
                result["intent"] = "maintenance_planning"
                result["confidence"] = "low"
                result["reasoning"] = "Invalid intent, defaulting to planning"
            
            return result
        
        except json.JSONDecodeError as e:
            print(f"Failed to parse intent response: {cleaned}")
            return {
                "intent": "maintenance_planning",
                "confidence": "low",
                "reasoning": f"Parse error: {str(e)}"
            }
    
    def _fallback_detection(self, user_query: str) -> Dict[str, str]:
        """
        Fallback keyword-based detection if LLM fails.
        This is a safety net.
        """
        query_lower = user_query.lower()
        
        # Priority order - most specific first
        if ("why" in query_lower and "block" in query_lower) or "blocked" in query_lower:
            return {
                "intent": "blockage_reason",
                "confidence": "medium",
                "reasoning": "Keyword match: 'blocked' or 'why block'"
            }
        
        elif "material" in query_lower or "inventory" in query_lower or "parts" in query_lower or "check" in query_lower:
            return {
                "intent": "material_readiness",
                "confidence": "medium",
                "reasoning": "Keyword match: materials/inventory/parts/check"
            }
        
        elif "reserve" in query_lower or "reservation" in query_lower or "allocate" in query_lower:
            return {
                "intent": "material_reservation",
                "confidence": "medium",
                "reasoning": "Keyword match: reserve/reservation/allocate"
            }
        
        elif "purchase" in query_lower or "procurement" in query_lower or "pr" in query_lower or "requisition" in query_lower:
            return {
                "intent": "procurement_status",
                "confidence": "medium",
                "reasoning": "Keyword match: purchase/procurement/PR"
            }
        
        elif "plan" in query_lower or "schedule" in query_lower:
            return {
                "intent": "maintenance_planning",
                "confidence": "medium",
                "reasoning": "Keyword match: plan/schedule"
            }
        
        else:
            return {
                "intent": "maintenance_planning",
                "confidence": "low",
                "reasoning": "No clear match, defaulting to planning"
            }


# ===================================
# Convenience function for quick use
# ===================================

_detector = None

def detect_intent(user_query: str, work_order_id: str = None) -> Dict[str, str]:
    """
    Detect intent using LLM. Creates a singleton detector instance.
    
    Args:
        user_query: User's natural language query
        work_order_id: Optional work order ID
        
    Returns:
        Dict with 'intent', 'confidence', and 'reasoning'
    
    Example:
        >>> result = detect_intent("Why is WO-101 blocked?", "WO-101")
        >>> print(result)
        {
            "intent": "blockage_reason",
            "confidence": "high",
            "reasoning": "User asks why work order is blocked"
        }
    """
    global _detector
    
    if _detector is None:
        _detector = IntentDetector()
    
    return _detector.detect_intent(user_query, work_order_id)
