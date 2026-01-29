from typing import TypedDict, List, Dict, Optional, Literal, Any


# ==============================
# Core domain objects
# ==============================

class WorkOrder(TypedDict):
    work_order_id: str
    equipment: str
    job_type: str
    description: str


class MaintenanceTask(TypedDict):
    description: str


class RequiredPart(TypedDict):
    part_id: str
    required_quantity: float


class InventoryRecord(TypedDict):
    part_id: str
    available_quantity: float
    location: Optional[str]


class ReservationRecord(TypedDict):
    work_order_id: str
    part_id: str
    reserved_quantity: float
    status: Literal["Reserved", "Not Available"]
    reservation_id: Optional[str]


class PurchaseRequest(TypedDict):
    work_order_id: str
    part_id: str
    purchase_quantity: float
    reason: str


# ==============================
# Agent-specific contexts (Role-Based Maintenance)
# ==============================

class OperatorContext(TypedDict, total=False):
    """Context specific to operator agent"""
    issue_identified: bool
    issue_description: str
    severity: str
    operational_impact: str


class SupervisorContext(TypedDict, total=False):
    """Context specific to supervisor agent"""
    wo_created: bool
    assigned_to: str  # MMT, EMT, HT
    technician_name: str  # Mike, Eric, Henry
    requires_lockout: bool
    safety_critical: bool
    assignment_reasoning: str


class TechnicianContext(TypedDict, total=False):
    """Context specific to technician agent"""
    technician_role: str  # MMT, EMT, HT
    technician_name: str  # Mike, Eric, Henry
    tasks_planned: List[str]
    parts_requested: List[str]
    estimated_time: str
    work_completed: bool
    tasks_done: List[str]
    parts_used: List[str]


class InventoryContext(TypedDict, total=False):
    """Context specific to inventory agent (storekeeper)"""
    spares_checked: int
    spares_available: int
    spares_issued: int
    issue_records: List[Dict[str, Any]]
    shortages: List[str]
    reorder_alerts: List[str]


class SafetyContext(TypedDict, total=False):
    """Context specific to safety officer agent (REPLACED BY HUMAN APPROVAL)"""
    verification_complete: bool
    loto_compliant: bool
    ppe_correct: bool
    safety_devices_tested: bool
    guards_in_place: bool
    equipment_safe: bool
    approval_status: str  # APPROVED or REJECTED
    wo_can_close: bool
    safety_notes: str


class HumanApprovalContext(TypedDict, total=False):
    """Context for human approval step"""
    recommendation: str  # James's recommendation (APPROVE/HOLD)
    recommendation_reason: str  # Why James recommends this
    awaiting_approval: bool  # Is system waiting for human?
    human_decision: str  # User's choice (APPROVED/ON_HOLD)
    human_notes: str  # Optional notes from human
    decision_timestamp: str


# Legacy contexts (kept for backward compatibility)
class RoutingContext(TypedDict, total=False):
    """Context specific to routing agent"""
    intent: str
    confidence: str
    routing_reason: str


class PlanningContext(TypedDict, total=False):
    """Context specific to planning agent"""
    plan_overview: str
    key_dependencies: List[str]
    risk_factors: List[str]
    tasks_identified: int


class ReservationContext(TypedDict, total=False):
    """Context specific to reservation agent"""
    reservation_attempted: bool
    parts_reserved: int
    blocking_parts: List[str]


class PurchaseContext(TypedDict, total=False):
    """Context specific to purchase agent"""
    requisitions_created: int
    pr_ids: List[str]
    total_purchase_quantity: float


# ==============================
# Error tracking
# ==============================

class ErrorRecord(TypedDict):
    agent: str
    error_type: str
    message: str
    timestamp: str
    recoverable: bool
    retry_count: int


# ==============================
# Main orchestration state
# ==============================

class MaintenanceState(TypedDict):
    # ---- Core input/output ----
    user_query: str
    work_order: WorkOrder
    final_answer: Optional[str]
    
    # ---- Intent & routing ----
    intent: Optional[str]
    next_agent: Optional[str]
    
    # ---- Role-Based Maintenance Fields (NEW) ----
    # Operator phase
    issue_identified: bool
    issue_description: str
    severity: str
    
    # Supervisor phase
    assigned_technician: str  # MMT, EMT, or HT
    technician_name: str  # Mike, Eric, or Henry
    requires_lockout: bool
    safety_critical: bool
    
    # Technician phase
    work_started: bool
    
    # Safety phase
    work_completed: bool
    verification_passed: bool
    wo_closed: bool
    
    # ---- Shared data (accessed by multiple agents) ----
    required_parts: List[RequiredPart]
    inventory_status: Dict[str, InventoryRecord]
    reservation_status: Dict[str, ReservationRecord]
    purchase_requests: List[PurchaseRequest]
    
    # ---- Decision flags ----
    can_execute: bool
    purchase_required: bool
    skip_planning: bool  # Legacy - allows dynamic routing
    skip_inventory: bool
    skip_reservation: bool
    skip_purchase: bool
    
    # ---- Agent-specific contexts ----
    operator_context: Optional[OperatorContext]
    supervisor_context: Optional[SupervisorContext]
    technician_context: Optional[TechnicianContext]
    inventory_context: Optional[InventoryContext]
    safety_context: Optional[SafetyContext]
    human_approval_context: Optional[HumanApprovalContext]
    
    # Legacy contexts (backward compatibility)
    routing_context: Optional[RoutingContext]
    planning_context: Optional[PlanningContext]
    reservation_context: Optional[ReservationContext]
    purchase_context: Optional[PurchaseContext]
    
    # Plan field (for compatibility)
    plan: Optional[str]
    
    # ---- Execution tracking ----
    current_step: str
    execution_path: List[str]  # Track which agents actually executed
    tool_calls: List[Dict[str, Any]]
    
    # ---- Error handling ----
    errors: List[ErrorRecord]
    has_critical_error: bool
    retry_count: int
    
    # ---- Observability ----
    messages: List[str]
    total_tool_calls: int
    total_llm_calls: int