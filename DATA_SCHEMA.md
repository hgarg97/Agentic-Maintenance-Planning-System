# 📘 RUBBER RECYCLING MAINTENANCE - DATA SCHEMA

*(Authoritative data contract for Rubber Recycling Agentic Maintenance System)*

---

## 🔄 KEY DIFFERENCES FROM SHELL SYSTEM

### What Changed:
- ❌ **Removed:** `bom.csv` (equipment-based parts) → Replaced with WO-specific parts
- ❌ **Removed:** `material_reservations.csv` → Replaced with `part_issues.csv`
- ❌ **Removed:** `purchase_requisitions.csv` → Not needed (focus on usage, not procurement)
- ✅ **Added:** `maintenance_requests.csv` (MR workflow)
- ✅ **Added:** `spare_parts.csv` (catalog with min/reorder levels)
- ✅ **Added:** `part_issues.csv` (actual part consumption tracking)
- ✅ **Added:** `technician_assignments.csv` (who does what)
- ✅ **Added:** `work_order_tasks.csv` (task checklist per WO)
- ⚠️ **Modified:** `work_orders.csv` (added frequency, assigned_to, status, etc.)

### Philosophy Shift:
```
SHELL SYSTEM:           RUBBER SYSTEM:
Planning-focused   →    Execution-focused
Can we execute?    →    Execute and track
Material planning  →    Spare parts usage
Procurement        →    Inventory management
```

---

## 1️⃣ maintenance_requests.csv [NEW]

**Purpose**
Operators raise maintenance requests when they detect issues or anomalies.
This is the ENTRY POINT of the maintenance workflow.

**Schema**

```csv
mr_id,equipment,raised_by,priority,issue_description,status,created_date,wo_created
```

**Columns**

| Column            | Type   | Required | Description                                        |
| ----------------- | ------ | -------- | -------------------------------------------------- |
| mr_id             | string | ✅        | Unique MR identifier (e.g. `MR-001`)               |
| equipment         | string | ✅        | Equipment name (e.g. "Primary Shredder")           |
| raised_by         | string | ✅        | Operator name/ID (e.g. "OP-John")                  |
| priority          | string | ✅        | `High` / `Medium` / `Low`                          |
| issue_description | string | ✅        | What the operator observed                         |
| status            | string | ✅        | `Open` / `WO Created` / `Closed`                   |
| created_date      | date   | ✅        | When MR was raised (YYYY-MM-DD HH:MM)              |
| wo_created        | string | ❌        | Reference to WO if created (e.g. "WO-PS-999")      |

**Example Data**

```csv
MR-001,Primary Shredder,OP-John,High,Unusual noise from shredder bearing area,WO Created,2025-01-15 09:30,WO-PS-999
MR-002,Air Compressor,OP-Sarah,Medium,Pressure gauge reading unstable,Open,2025-01-15 14:20,
MR-003,Primary Shredder,OP-Mike,Low,Minor hydraulic oil leak visible,Open,2025-01-16 08:00,
```

**Usage Pattern**
```
Operator → Raises MR → MS reviews → Creates WO → MR status = "WO Created"
```

---

## 2️⃣ work_orders.csv [MODIFIED]

**Purpose**
Central work order tracking with lifecycle information.

**Schema**

```csv
work_order_id,mr_id,equipment,wo_type,frequency,job_description,raised_by,assigned_to,status,priority,created_date,scheduled_date,completed_date,duration_hours
```

**Columns**

| Column          | Type   | Required | Description                                             |
| --------------- | ------ | -------- | ------------------------------------------------------- |
| work_order_id   | string | ✅        | Unique WO ID (e.g. `WO-PS-015`)                         |
| mr_id           | string | ❌        | Link to MR if reactive (empty for preventive)           |
| equipment       | string | ✅        | Equipment name                                          |
| wo_type         | string | ✅        | `Preventive` / `Corrective` / `Breakdown` / `Inspection` |
| frequency       | string | ❌        | For preventive: `Daily` / `Weekly` / `Monthly` / `Annual` |
| job_description | string | ✅        | Scope of work                                           |
| raised_by       | string | ✅        | Who created WO (usually MS)                             |
| assigned_to     | string | ❌        | Technician role assigned (e.g. "HT-Mike")               |
| status          | string | ✅        | `Open` / `Assigned` / `In Progress` / `Completed` / `Closed` |
| priority        | string | ✅        | `Critical` / `High` / `Medium` / `Low`                  |
| created_date    | date   | ✅        | When WO was created                                     |
| scheduled_date  | date   | ❌        | When work is planned                                    |
| completed_date  | date   | ❌        | When work finished                                      |
| duration_hours  | number | ❌        | Actual hours spent                                      |

**Example Data**

```csv
work_order_id,mr_id,equipment,wo_type,frequency,job_description,raised_by,assigned_to,status,priority,created_date,scheduled_date,completed_date,duration_hours
WO-PS-001,,Primary Shredder,Preventive,Daily,Daily inspection and operational check,MS-Sarah,OP-John,Completed,Medium,2025-01-15,2025-01-15,2025-01-15,0.5
WO-PS-007,,Primary Shredder,Preventive,Weekly,Knife bolt torque check and inspection,MS-Sarah,MMT-James,Completed,Medium,2025-01-10,2025-01-12,2025-01-12,1.0
WO-PS-015,,Primary Shredder,Preventive,Monthly,Hydraulic filter replacement,MS-Sarah,HT-Mike,Completed,Medium,2025-01-01,2025-01-15,2025-01-15,1.2
WO-PS-030,,Primary Shredder,Preventive,Annual,Complete knife replacement and shaft alignment,MS-Sarah,MMT-James,Open,High,2025-01-10,2025-02-01,,
WO-PS-999,MR-001,Primary Shredder,Corrective,,Investigate and repair bearing noise,MS-Sarah,MMT-James,In Progress,High,2025-01-15,2025-01-15,,
WO-AC-001,,Air Compressor,Preventive,Daily,Daily compressor check and condensate drain,MS-Sarah,OP-Sarah,Completed,Low,2025-01-15,2025-01-15,2025-01-15,0.3
WO-AC-006,,Air Compressor,Preventive,Monthly,Oil filter replacement,MS-Sarah,MMT-David,Open,Medium,2025-01-10,2025-01-20,,
WO-AC-012,,Air Compressor,Preventive,Quarterly,Oil and separator change (2000hrs),MS-Sarah,MMT-David,Open,Medium,2025-01-05,2025-02-15,,
```

**Join Rules**

```
work_orders.mr_id → maintenance_requests.mr_id (optional)
work_orders.equipment → spare_parts.equipment (for BOM lookup)
```

---

## 3️⃣ spare_parts.csv [NEW - Replaces bom.csv]

**Purpose**
Master catalog of spare parts with inventory thresholds.
This is WO-SPECIFIC, not just equipment-based.

**Schema**

```csv
part_code,part_name,equipment,category,wo_type,required_qty_per_job,min_stock,reorder_level,unit_cost,supplier
```

**Columns**

| Column               | Type   | Required | Description                                      |
| -------------------- | ------ | -------- | ------------------------------------------------ |
| part_code            | string | ✅        | Unique part ID (e.g. `PS-KN-001`)                |
| part_name            | string | ✅        | Part description                                 |
| equipment            | string | ✅        | Which equipment this part belongs to             |
| category             | string | ✅        | `Cutting` / `Hydraulic` / `Lubrication` / `Seal` |
| wo_type              | string | ❌        | Which WO types need this (e.g. "WO-PS-015")      |
| required_qty_per_job | number | ✅        | Standard quantity per maintenance job            |
| min_stock            | number | ✅        | Minimum stock level                              |
| reorder_level        | number | ✅        | When to reorder                                  |
| unit_cost            | number | ❌        | Cost per unit (optional)                         |
| supplier             | string | ❌        | Supplier name (optional)                         |

**Example Data**

```csv
part_code,part_name,equipment,category,wo_type,required_qty_per_job,min_stock,reorder_level,unit_cost,supplier
PS-KN-001,Shredder Knife Set (Full),Primary Shredder,Cutting,WO-PS-030,1,1,2,5500.00,ABC Cutters Inc
PS-KB-002,Knife Bolt Set,Primary Shredder,Cutting,WO-PS-030,1,2,4,180.00,FastenRight Ltd
PS-SP-003,Knife Spacer Set,Primary Shredder,Cutting,WO-PS-030,1,2,3,95.00,FastenRight Ltd
PS-HF-004,Hydraulic Oil Filter,Primary Shredder,Hydraulic,WO-PS-015,1,6,8,42.50,FilterPro
PS-HO-005,Hydraulic Oil (20L),Primary Shredder,Hydraulic,WO-PS-030,1,2,3,215.00,OilSupply Co
PS-SS-006,Shaft Seal Set,Primary Shredder,Seal,WO-PS-030,2,4,6,125.00,SealTech
PS-BRG-007,Bearing Set 6310,Primary Shredder,Mechanical,WO-PS-999,1,2,3,320.00,BearingWorld
AC-OF-101,Compressor Oil Filter,Air Compressor,Lubrication,WO-AC-006,1,4,6,28.00,FilterPro
AC-OIL-102,Compressor Oil (5L),Air Compressor,Lubrication,WO-AC-012,2,2,3,85.00,OilSupply Co
AC-AOS-103,Air-Oil Separator,Air Compressor,Separation,WO-AC-012,1,1,2,165.00,CompAir Parts
AC-IF-104,Intake Air Filter,Air Compressor,Filtration,WO-AC-012,1,3,5,35.00,FilterPro
```

**Join Rules**

```
spare_parts.part_code → inventory.part_id
spare_parts.equipment → work_orders.equipment
spare_parts.wo_type → work_orders.work_order_id (WO matching)
```

---

## 4️⃣ inventory.csv [MODIFIED]

**Purpose**
Real-time inventory levels for spare parts.

**Schema**

```csv
part_id,part_name,current_stock,min_stock,reorder_level,store_location,last_updated
```

**Columns**

| Column         | Type   | Required | Description                              |
| -------------- | ------ | -------- | ---------------------------------------- |
| part_id        | string | ✅        | Same as `spare_parts.part_code`          |
| part_name      | string | ✅        | Display name                             |
| current_stock  | number | ✅        | Current available quantity               |
| min_stock      | number | ✅        | Minimum stock threshold                  |
| reorder_level  | number | ✅        | Reorder point                            |
| store_location | string | ❌        | Physical location                        |
| last_updated   | date   | ✅        | Last inventory update timestamp          |

**Example Data**

```csv
part_id,part_name,current_stock,min_stock,reorder_level,store_location,last_updated
PS-KN-001,Shredder Knife Set (Full),3,1,2,Maintenance Store - Shelf A3,2025-01-15
PS-KB-002,Knife Bolt Set,5,2,4,Maintenance Store - Bin B12,2025-01-15
PS-SP-003,Knife Spacer Set,4,2,3,Maintenance Store - Bin B12,2025-01-15
PS-HF-004,Hydraulic Oil Filter,7,6,8,Maintenance Store - Shelf C2,2025-01-15
PS-HO-005,Hydraulic Oil (20L),3,2,3,Chemical Store - Tank 5,2025-01-14
PS-SS-006,Shaft Seal Set,8,4,6,Maintenance Store - Shelf D1,2025-01-15
PS-BRG-007,Bearing Set 6310,2,2,3,Maintenance Store - Shelf E2,2025-01-16
AC-OF-101,Compressor Oil Filter,5,4,6,Maintenance Store - Shelf C2,2025-01-15
AC-OIL-102,Compressor Oil (5L),4,2,3,Chemical Store - Tank 2,2025-01-15
AC-AOS-103,Air-Oil Separator,1,1,2,Maintenance Store - Shelf F1,2025-01-15
AC-IF-104,Intake Air Filter,6,3,5,Maintenance Store - Shelf C3,2025-01-15
```

**Join Rule**

```
inventory.part_id = spare_parts.part_code
```

**Business Logic**

```python
if current_stock <= min_stock:
    alert = "CRITICAL - Reorder immediately"
elif current_stock <= reorder_level:
    alert = "WARNING - Reorder soon"
else:
    alert = "OK"
```

---

## 5️⃣ part_issues.csv [NEW - Replaces material_reservations.csv]

**Purpose**
Tracks actual spare parts issued to technicians for work orders.
This is CONSUMPTION tracking, not reservation.

**Schema**

```csv
issue_id,work_order_id,part_code,quantity_issued,issued_by,issued_to,issue_date,return_qty,notes
```

**Columns**

| Column          | Type   | Required | Description                                    |
| --------------- | ------ | -------- | ---------------------------------------------- |
| issue_id        | string | ✅        | Unique issue ID (e.g. `ISS-001`)               |
| work_order_id   | string | ✅        | WO this part is for                            |
| part_code       | string | ✅        | Part being issued                              |
| quantity_issued | number | ✅        | How many issued                                |
| issued_by       | string | ✅        | Storekeeper who issued (e.g. "SK-Ali")         |
| issued_to       | string | ✅        | Technician receiving (e.g. "HT-Mike")          |
| issue_date      | date   | ✅        | When issued                                    |
| return_qty      | number | ❌        | If any returned (unused parts)                 |
| notes           | string | ❌        | Additional comments                            |

**Example Data**

```csv
issue_id,work_order_id,part_code,quantity_issued,issued_by,issued_to,issue_date,return_qty,notes
ISS-001,WO-PS-015,PS-HF-004,1,SK-Ali,HT-Mike,2025-01-15 10:00,0,Monthly filter change
ISS-002,WO-PS-007,PS-KB-002,1,SK-Ali,MMT-James,2025-01-12 09:30,0,Torque check - bolts replaced
ISS-003,WO-PS-999,PS-BRG-007,1,SK-Ali,MMT-James,2025-01-15 11:00,0,Bearing replacement for noise issue
ISS-004,WO-AC-006,AC-OF-101,1,SK-Ali,MMT-David,2025-01-10 14:00,0,Routine oil filter change
```

**Join Rules**

```
part_issues.work_order_id → work_orders.work_order_id
part_issues.part_code → spare_parts.part_code
```

**Inventory Update Logic**

```python
When part is issued:
    inventory.current_stock -= part_issues.quantity_issued

If part is returned:
    inventory.current_stock += part_issues.return_qty
```

---

## 6️⃣ technician_assignments.csv [NEW]

**Purpose**
Tracks which technicians are assigned to which work orders.

**Schema**

```csv
assignment_id,work_order_id,technician_role,technician_name,assigned_date,status,completion_notes
```

**Columns**

| Column            | Type   | Required | Description                                      |
| ----------------- | ------ | -------- | ------------------------------------------------ |
| assignment_id     | string | ✅        | Unique assignment ID (e.g. `ASG-001`)            |
| work_order_id     | string | ✅        | Work order reference                             |
| technician_role   | string | ✅        | `OP` / `MMT` / `EMT` / `HT`                      |
| technician_name   | string | ✅        | Name/ID (e.g. "HT-Mike")                         |
| assigned_date     | date   | ✅        | When assigned                                    |
| status            | string | ✅        | `Assigned` / `In Progress` / `Completed`         |
| completion_notes  | string | ❌        | Notes after completion                           |

**Example Data**

```csv
assignment_id,work_order_id,technician_role,technician_name,assigned_date,status,completion_notes
ASG-001,WO-PS-015,HT,HT-Mike,2025-01-15,Completed,Filter changed. System pressure normal.
ASG-002,WO-PS-030,MMT,MMT-James,2025-01-10,Assigned,Scheduled for Feb 1st shutdown
ASG-003,WO-PS-999,MMT,MMT-James,2025-01-15,In Progress,Bearing noise confirmed. Replacing bearing set.
ASG-004,WO-AC-006,MMT,MMT-David,2025-01-10,Assigned,
ASG-005,WO-PS-007,MMT,MMT-James,2025-01-12,Completed,Torque values recorded. All within spec.
```

**Join Rule**

```
technician_assignments.work_order_id → work_orders.work_order_id
```

---

## 7️⃣ work_order_tasks.csv [NEW - Optional]

**Purpose**
Task checklist for each work order (useful for complex WOs).

**Schema**

```csv
task_id,work_order_id,task_sequence,task_description,requires_loto,completed,verified_by
```

**Columns**

| Column           | Type    | Required | Description                              |
| ---------------- | ------- | -------- | ---------------------------------------- |
| task_id          | string  | ✅        | Unique task ID (e.g. `TASK-001`)         |
| work_order_id    | string  | ✅        | Parent work order                        |
| task_sequence    | number  | ✅        | Order of execution (1, 2, 3...)          |
| task_description | string  | ✅        | What needs to be done                    |
| requires_loto    | boolean | ✅        | Does this task need Lockout/Tagout?      |
| completed        | boolean | ✅        | Task done?                               |
| verified_by      | string  | ❌        | Who verified completion (e.g. "SO-Khan") |

**Example Data**

```csv
task_id,work_order_id,task_sequence,task_description,requires_loto,completed,verified_by
TASK-001,WO-PS-015,1,Lockout hydraulic system and tag,Yes,True,SO-Khan
TASK-002,WO-PS-015,2,Drain hydraulic oil from filter housing,No,True,
TASK-003,WO-PS-015,3,Remove old hydraulic filter,No,True,
TASK-004,WO-PS-015,4,Clean filter housing,No,True,
TASK-005,WO-PS-015,5,Install new hydraulic filter PS-HF-004,No,True,
TASK-006,WO-PS-015,6,Refill hydraulic oil and check level,No,True,
TASK-007,WO-PS-015,7,Remove lockout and test system,Yes,True,SO-Khan
```

**Join Rule**

```
work_order_tasks.work_order_id → work_orders.work_order_id
```

---

## 8️⃣ maintenance_schedule.csv [KEPT - Minor modification]

**Purpose**
Schedule preventive maintenance work orders.

**Schema**

```csv
schedule_id,work_order_id,equipment,scheduled_date,frequency,last_completed,next_due
```

**Columns**

| Column         | Type   | Required | Description                           |
| -------------- | ------ | -------- | ------------------------------------- |
| schedule_id    | string | ✅        | Unique schedule ID                    |
| work_order_id  | string | ✅        | Template WO ID (e.g. "WO-PS-015")     |
| equipment      | string | ✅        | Equipment name                        |
| scheduled_date | date   | ✅        | When to execute                       |
| frequency      | string | ✅        | `Daily` / `Weekly` / `Monthly` / etc. |
| last_completed | date   | ❌        | Last execution date                   |
| next_due       | date   | ✅        | Next scheduled execution              |

**Example Data**

```csv
schedule_id,work_order_id,equipment,scheduled_date,frequency,last_completed,next_due
SCH-001,WO-PS-001,Primary Shredder,2025-01-16,Daily,2025-01-15,2025-01-16
SCH-002,WO-PS-007,Primary Shredder,2025-01-19,Weekly,2025-01-12,2025-01-19
SCH-003,WO-PS-015,Primary Shredder,2025-02-15,Monthly,2025-01-15,2025-02-15
SCH-004,WO-AC-001,Air Compressor,2025-01-16,Daily,2025-01-15,2025-01-16
SCH-005,WO-AC-006,Air Compressor,2025-01-20,Monthly,2024-12-20,2025-01-20
```

---

## 🔑 CRITICAL DESIGN RULES

### 1️⃣ Equipment Naming (Same as Shell)
- Equipment is **NAME-BASED**, not ID-based
- Joins use exact string match
- Examples: "Primary Shredder", "Air Compressor"

### 2️⃣ Part Identity
```
spare_parts.part_code == inventory.part_id == part_issues.part_code
```

### 3️⃣ Work Order Lifecycle
```
MR (Optional) → WO Created → Tech Assigned → Parts Issued → 
Work Done → WO Completed → WO Closed
```

### 4️⃣ Status Flow

**MR Status:**
```
Open → WO Created → Closed
```

**WO Status:**
```
Open → Assigned → In Progress → Completed → Closed
```

**Assignment Status:**
```
Assigned → In Progress → Completed
```

### 5️⃣ CSV Helper Contract (Same Philosophy)
- Functions accept `work_order_id` (string) OR `work_order` (dict)
- Internally normalize to ID
- All joins happen inside helper functions
- Agents never manipulate CSV directly

---

## 📊 DATA RELATIONSHIPS DIAGRAM

```
maintenance_requests (MR)
    ↓ (optional - only for reactive)
work_orders (WO) ←──────────┐
    ↓                        │
    ├─→ spare_parts ────→ inventory (stock levels)
    │        ↓
    ├─→ part_issues (consumption)
    │
    ├─→ technician_assignments (who does it)
    │
    └─→ work_order_tasks (checklist)

maintenance_schedule
    ↓
work_orders (preventive only)
```

---

## 🎯 KEY DIFFERENCES SUMMARY

| Aspect               | Shell System           | Rubber System          |
| -------------------- | ---------------------- | ---------------------- |
| **Focus**            | Can we execute?        | Execute & track        |
| **Entry Point**      | Direct WO              | MR → WO                |
| **Parts Lookup**     | BOM (equipment-based)  | Spare parts (WO-based) |
| **Material Action**  | Reserve                | Issue (consume)        |
| **Procurement**      | Create PR              | Track usage only       |
| **Assignment**       | Implicit               | Explicit (assignments) |
| **Task Tracking**    | No                     | Yes (optional)         |
| **Inventory Update** | On reservation         | On issue               |
| **Lifecycle**        | Plan → Reserve → Buy   | Create → Assign → Do   |

---

## ✅ IMPLEMENTATION PRIORITY

### Phase 1: Core (Essential)
1. ✅ `work_orders.csv`
2. ✅ `spare_parts.csv`
3. ✅ `inventory.csv`
4. ✅ `part_issues.csv`

### Phase 2: Workflow (Important)
5. ✅ `maintenance_requests.csv`
6. ✅ `technician_assignments.csv`

### Phase 3: Advanced (Optional for POC)
7. ⭐ `work_order_tasks.csv`
8. ⭐ `maintenance_schedule.csv`

---

**This schema is production-ready and follows industry CMMS best practices.**
