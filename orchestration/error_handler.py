# orchestration/error_handler.py
"""
Robust error handling with retries, circuit breakers, and graceful degradation.
"""

from typing import Callable, Any, Optional, Dict
from functools import wraps
import time
from datetime import datetime
from orchestration.state import ErrorRecord


class CircuitBreaker:
    """
    Circuit breaker pattern to prevent cascading failures.
    
    States:
    - CLOSED: Normal operation
    - OPEN: Too many failures, reject requests
    - HALF_OPEN: Testing if service recovered
    """
    
    def __init__(
        self,
        failure_threshold: int = 3,
        timeout: int = 60,
        name: str = "default"
    ):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.name = name
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection"""
        
        # Check if circuit is open
        if self.state == "OPEN":
            if self._should_attempt_reset():
                self.state = "HALF_OPEN"
            else:
                raise CircuitBreakerOpen(
                    f"Circuit breaker '{self.name}' is OPEN. "
                    f"Too many failures ({self.failure_count}). "
                    f"Will retry after {self.timeout}s."
                )
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        
        except Exception as e:
            self._on_failure()
            raise e
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset"""
        if self.last_failure_time is None:
            return True
        
        elapsed = time.time() - self.last_failure_time
        return elapsed >= self.timeout
    
    def _on_success(self):
        """Reset circuit breaker on success"""
        self.failure_count = 0
        self.state = "CLOSED"
    
    def _on_failure(self):
        """Track failure and potentially open circuit"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"


class CircuitBreakerOpen(Exception):
    """Raised when circuit breaker is open"""
    pass


# Global circuit breakers for different services
_circuit_breakers: Dict[str, CircuitBreaker] = {}


def get_circuit_breaker(name: str) -> CircuitBreaker:
    """Get or create a circuit breaker for a service"""
    if name not in _circuit_breakers:
        _circuit_breakers[name] = CircuitBreaker(
            failure_threshold=3,
            timeout=60,
            name=name
        )
    return _circuit_breakers[name]


def with_retry(
    max_retries: int = 3,
    backoff_factor: float = 2.0,
    exceptions: tuple = (Exception,),
    circuit_breaker_name: Optional[str] = None
):
    """
    Decorator for retry logic with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        backoff_factor: Multiplier for delay between retries (exponential)
        exceptions: Tuple of exceptions to catch and retry
        circuit_breaker_name: Optional circuit breaker to use
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            # Get circuit breaker if specified
            circuit_breaker = None
            if circuit_breaker_name:
                circuit_breaker = get_circuit_breaker(circuit_breaker_name)
            
            for attempt in range(max_retries + 1):
                try:
                    # Use circuit breaker if available
                    if circuit_breaker:
                        return circuit_breaker.call(func, *args, **kwargs)
                    else:
                        return func(*args, **kwargs)
                
                except CircuitBreakerOpen as e:
                    # Circuit breaker is open, don't retry
                    raise e
                
                except exceptions as e:
                    last_exception = e
                    
                    # Don't sleep on the last attempt
                    if attempt < max_retries:
                        delay = backoff_factor ** attempt
                        time.sleep(delay)
                        continue
                    else:
                        # Max retries exceeded
                        break
            
            # All retries failed
            raise MaxRetriesExceeded(
                f"Failed after {max_retries} retries. Last error: {str(last_exception)}"
            ) from last_exception
        
        return wrapper
    return decorator


class MaxRetriesExceeded(Exception):
    """Raised when max retries are exceeded"""
    pass


def create_error_record(
    agent: str,
    error: Exception,
    retry_count: int = 0
) -> ErrorRecord:
    """Create an error record for tracking"""
    
    # Determine if error is recoverable
    recoverable = not isinstance(error, (
        CircuitBreakerOpen,
        MaxRetriesExceeded,
        KeyboardInterrupt,
        SystemExit
    ))
    
    return ErrorRecord(
        agent=agent,
        error_type=type(error).__name__,
        message=str(error),
        timestamp=datetime.now().isoformat(),
        recoverable=recoverable,
        retry_count=retry_count
    )


def handle_agent_error(
    agent_name: str,
    error: Exception,
    state: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Handle agent errors gracefully and update state.
    
    Args:
        agent_name: Name of the agent that failed
        error: The exception that occurred
        state: Current state
        
    Returns:
        Updated state with error information
    """
    # Create error record
    error_record = create_error_record(
        agent=agent_name,
        error=error,
        retry_count=state.get("retry_count", 0)
    )
    
    # Add to error list
    if "errors" not in state:
        state["errors"] = []
    state["errors"].append(error_record)
    
    # Mark critical errors
    if not error_record["recoverable"]:
        state["has_critical_error"] = True
    
    # Add message for user
    if isinstance(error, CircuitBreakerOpen):
        state["messages"].append(
            f"⚠️ {agent_name} is temporarily unavailable. System is protecting itself from cascading failures."
        )
    elif isinstance(error, MaxRetriesExceeded):
        state["messages"].append(
            f"⚠️ {agent_name} failed after multiple retries. Continuing with available information."
        )
    else:
        state["messages"].append(
            f"⚠️ {agent_name} encountered an issue: {str(error)[:100]}"
        )
    
    return state


def safe_agent_execution(agent_func: Callable) -> Callable:
    """
    Wrapper for safe agent execution with error handling.
    
    Usage:
        @safe_agent_execution
        def my_agent(state):
            # agent logic
            return state
    """
    @wraps(agent_func)
    def wrapper(state: Dict[str, Any]) -> Dict[str, Any]:
        agent_name = agent_func.__name__
        
        try:
            return agent_func(state)
        
        except CircuitBreakerOpen as e:
            # Circuit breaker is open - skip this agent
            state = handle_agent_error(agent_name, e, state)
            state["messages"].append(
                f"Skipping {agent_name} due to circuit breaker. Proceeding with degraded functionality."
            )
            return state
        
        except MaxRetriesExceeded as e:
            # Max retries exceeded - try to continue
            state = handle_agent_error(agent_name, e, state)
            return state
        
        except Exception as e:
            # Unexpected error - log and try to continue
            state = handle_agent_error(agent_name, e, state)
            return state
    
    return wrapper


# ==============================
# Graceful degradation helpers
# ==============================

def can_proceed_with_degradation(state: Dict[str, Any]) -> bool:
    """
    Determine if we can proceed despite errors.
    
    Returns True if:
    - No critical errors
    - Essential data is available
    - At least one agent succeeded
    """
    if state.get("has_critical_error"):
        return False
    
    # Check if we have minimum required data
    has_work_order = bool(state.get("work_order"))
    has_intent = bool(state.get("intent"))
    
    # Check if at least one agent executed successfully
    execution_path = state.get("execution_path", [])
    has_progress = len(execution_path) > 0
    
    return has_work_order and has_intent and has_progress


def get_degraded_response(state: Dict[str, Any]) -> str:
    """Generate a response when operating in degraded mode"""
    
    errors = state.get("errors", [])
    work_order_id = state.get("work_order", {}).get("work_order_id", "Unknown")
    
    response_parts = [
        f"⚠️ **Partial Response for {work_order_id}**\n",
        "I encountered some issues but was able to gather the following information:\n"
    ]
    
    # Add what we know
    if state.get("required_parts"):
        response_parts.append(
            f"✓ Identified {len(state['required_parts'])} required parts"
        )
    
    if state.get("inventory_status"):
        response_parts.append(
            f"✓ Checked inventory for {len(state['inventory_status'])} items"
        )
    
    if state.get("reservation_status"):
        response_parts.append(
            "✓ Assessed reservation feasibility"
        )
    
    # Add what failed
    failed_agents = [e["agent"] for e in errors if not e["recoverable"]]
    if failed_agents:
        response_parts.append(
            f"\n⚠️ Unable to complete: {', '.join(set(failed_agents))}"
        )
    
    response_parts.append(
        "\n💡 **Recommendation:** Try again in a moment, or contact support if the issue persists."
    )
    
    return "\n".join(response_parts)
