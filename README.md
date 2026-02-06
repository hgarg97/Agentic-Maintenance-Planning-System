# Agentic Maintenance Planning System

An AI-powered multi-agent system for orchestrating maintenance operations in manufacturing environments. Built with LangGraph, LangChain, and Chainlit UI, this system coordinates multiple specialized AI agents to handle maintenance planning, inventory management, work order creation, and procurement.

---

## 🌟 Features

- **Multi-Agent Orchestration**: Coordinated team of AI agents working together using LangGraph
- **Real-time Chat Interface**: Interactive web UI powered by Chainlit
- **Human-in-the-Loop (HITL)**: Technician interactions with work orders, parts requests, and task completion
- **Database Integration**: PostgreSQL backend with comprehensive maintenance data model
- **Email Automation**: Automated vendor communication and report generation
- **Streaming Responses**: Real-time agent responses with per-agent avatars
- **Persistent State**: Conversation checkpointing with PostgreSQL

---

## 🤖 AI Agents

| Agent | Role | Responsibilities |
|-------|------|------------------|
| **James** | Maintenance Planner (Supervisor) | Routes tasks, coordinates agents, generates reports, handles user communication |
| **David** | Maintenance Supervisor | Creates work orders, assigns technicians, manages maintenance schedules |
| **Mira** | Inventory Manager | Queries inventory, checks stock levels, manages parts database |
| **Roberto** | Procurement Agent | Handles vendor communication, parts ordering, quote requests |
| **Technician** | Field Technician (HITL) | Interactive work order execution with human feedback |

---

## 📋 Prerequisites

Before installing, ensure you have the following:

- **Python 3.12** - [Download Python](https://www.python.org/downloads/)
- **PostgreSQL 16** - [Download PostgreSQL](https://www.postgresql.org/download/)
- **OpenAI API Key** - [Get API Key](https://platform.openai.com/api-keys)
- **Gmail Account** (optional, for email features) - [App Password Setup](https://support.google.com/accounts/answer/185833)

---

## 🚀 Installation & Setup

### 1. Clone the Repository

```bash
git clone https://github.com/hgarg97/Agentic-Maintenance-Planning-System.git
cd Agentic-Maintenance-Planning-System
```

### 2. Create Virtual Environment

```bash
python -p venv venv

# Activate on macOS/Linux
source venv/bin/activate

# Activate on Windows
venv\Scripts\activate

# If using Anaconda

conda create -p venv python=3.12

conda activate venv/
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Database Pre-Run Setup

#### 4.1 Create PostgreSQL Database

```bash
# Login to PostgreSQL
psql -U postgres

# Create database
CREATE DATABASE maintenance_db;

# Exit psql
\q
```

#### 4.2 Initialize Database Schema

```bash
# Run schema creation (creates tables, types, indexes)
psql -U postgres -d maintenance_db -f db/schema.sql
```

#### 4.3 Seed Database with Sample Data

```bash
# Load sample data (machines, parts, vendors, schedules)
psql -U postgres -d maintenance_db -f db/seed.sql
```

**Note**: The schema includes:
- 11 tables (industries, machines, parts_catalog, inventory, vendors, technicians, maintenance_tickets, work_orders, work_order_parts, purchase_requisitions, bom)
- ENUM types for statuses and priorities
- Foreign key relationships and indexes
- Sample data for textile manufacturing industry

### 5. Configure Environment Variables

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env with your credentials
nano .env  # or use your preferred editor
```

**Required Environment Variables**:

```bash
# OpenAI API Key (REQUIRED)
OPENAI_API_KEY=sk-your-api-key-here

# PostgreSQL Database (REQUIRED)
DB_HOST=localhost
DB_PORT=5432
DB_NAME=maintenance_db
DB_USER=postgres
DB_PASSWORD=your-db-password

# Gmail for Email Features (OPTIONAL)
GMAIL_USER=your.email@gmail.com
GMAIL_APP_PASSWORD=your-16-char-app-password

# Vendor Emails (OPTIONAL - for demo)
VENDOR_A_EMAIL=vendor.a@example.com
VENDOR_B_EMAIL=vendor.b@example.com

# User Email (OPTIONAL - for reports)
USER_EMAIL=user@example.com
```

---

## ▶️ Running the Application

### Start the Application

```bash
# Make sure virtual environment is activated
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Run Chainlit application
chainlit run app.py -w
```

The `-w` flag enables auto-reload on file changes (useful for development).

### Access the Interface

Open your browser and navigate to:
```
http://localhost:8000
```

You'll see the Chainlit chat interface with a welcome message from James (Maintenance Planner).

---

## 💬 Usage Examples

### Execute Daily Maintenance

```
User: Run today's daily maintenance schedule
```

The system will:
1. James routes to David
2. David queries today's scheduled maintenance
3. David creates work orders and assigns technicians
4. Technician agent presents HITL interface for each task
5. You interact with work orders (complete, request parts, reschedule, add notes)

### Check Inventory

```
User: What bearings do we have in stock?
```

The system will:
1. James routes to Mira
2. Mira queries the inventory database
3. Mira returns stock levels and details

### Request Parts

```
User: Order 5 hydraulic filters from vendor A
```

The system will:
1. James routes to Roberto
2. Roberto drafts vendor email
3. Roberto can send email (if configured) or provide draft

### Generate Report

```
User: Send me a maintenance status report
```

The system will:
1. James queries work orders and inventory
2. James generates formatted report
3. James emails report (if email configured) or displays it

---

## 📁 Project Structure

```
Agentic-Maintenance-Planning-System/
│
├── app.py                          # Main Chainlit entry point
│
├── agents/                         # AI Agent Definitions
│   ├── __init__.py
│   ├── james.py                    # Maintenance Planner (supervisor)
│   ├── david.py                    # Maintenance Supervisor
│   ├── mira.py                     # Inventory Manager
│   ├── roberto.py                  # Procurement Agent
│   └── technician.py               # Field Technician (HITL)
│
├── graph/                          # LangGraph Orchestration
│   ├── __init__.py
│   ├── state.py                    # Graph state definition (MaintenanceState)
│   ├── nodes.py                    # Node functions (agent wrappers)
│   ├── edges.py                    # Conditional routing logic
│   └── builder.py                  # Graph construction & compilation
│
├── tools/                          # Agent Tools (Database, Email, Formatting)
│   ├── __init__.py
│   ├── db_tools.py                 # Database query tools
│   ├── email_tools.py              # Email sending tools
│   └── formatting_tools.py         # Data formatting utilities
│
├── services/                       # Core Services
│   ├── __init__.py
│   ├── database.py                 # PostgreSQL connection pool
│   ├── llm_service.py              # OpenAI LLM client wrapper
│   └── email_service.py            # Gmail SMTP service
│
├── config/                         # Configuration
│   ├── __init__.py
│   ├── settings.py                 # Agent configs, UI settings, DB config
│   └── prompts.py                  # System prompts for each agent
│
├── ui/                             # Chainlit UI Components
│   ├── __init__.py
│   ├── avatars.py                  # Agent avatar registration
│   ├── cards.py                    # Work order card UI
│   └── streaming.py                # Streaming response manager
│
├── db/                             # Database Files
│   ├── schema.sql                  # PostgreSQL schema (DDL)
│   └── seed.sql                    # Sample data (DML)
│
├── tests/                          # Test Files
│   └── __init__.py
│
├── public/                         # Static Assets (avatars)
│   └── avatars/                    # Agent avatar images
│
├── .chainlit/                      # Chainlit Configuration
│   └── translations/               # UI translations
│
├── requirements.txt                # Python dependencies
├── .env.example                    # Environment template
├── .env                            # Your environment variables (not in git)
├── .gitignore                      # Git ignore rules
├── chainlit.md                     # Welcome message content
└── README.md                       # This file
```

---

## 📄 File Descriptions

### Core Application

| File | Purpose |
|------|---------|
| `app.py` | Main Chainlit application entry point. Handles chat lifecycle, message routing, streaming, HITL interrupts, and UI rendering. |

### Agents (`agents/`)

| File | Purpose |
|------|---------|
| `james.py` | **Maintenance Planner** - Supervisor agent that routes tasks, coordinates other agents, generates reports, and handles user communication. |
| `david.py` | **Maintenance Supervisor** - Creates work orders, assigns technicians, manages maintenance schedules and priorities. |
| `mira.py` | **Inventory Manager** - Queries inventory database, checks stock levels, provides parts information. |
| `roberto.py` | **Procurement Agent** - Handles vendor communication, drafts/sends emails, manages parts ordering. |
| `technician.py` | **Field Technician** - HITL agent that presents work orders to users and processes their actions (complete, request parts, reschedule). |

### Graph Orchestration (`graph/`)

| File | Purpose |
|------|---------|
| `state.py` | Defines `MaintenanceState` - the shared state passed between agents (messages, current agent, user intent, iteration count). |
| `nodes.py` | Node functions that wrap each agent's invocation in the graph. |
| `edges.py` | Conditional edge functions for routing between agents based on state. |
| `builder.py` | Constructs and compiles the LangGraph graph with PostgreSQL checkpointer. |

### Tools (`tools/`)

| File | Purpose |
|------|---------|
| `db_tools.py` | Database query tools (fetch machines, inventory, tickets, work orders, create work orders, update status). |
| `email_tools.py` | Email tools (send vendor emails, send reports). |
| `formatting_tools.py` | Utility tools for formatting data (work orders, inventory lists, markdown tables). |

### Services (`services/`)

| File | Purpose |
|------|---------|
| `database.py` | PostgreSQL connection pool manager using psycopg3. Provides async database connections. |
| `llm_service.py` | OpenAI LLM client wrapper. Initializes ChatOpenAI with GPT-4o-mini model. |
| `email_service.py` | Gmail SMTP service for sending emails via app password authentication. |

### Configuration (`config/`)

| File | Purpose |
|------|---------|
| `settings.py` | Central configuration: agent metadata, UI settings, database DSN, model names. |
| `prompts.py` | System prompts for each agent (James, David, Mira, Roberto, Technician). Defines personality and capabilities. |

### UI Components (`ui/`)

| File | Purpose |
|------|---------|
| `avatars.py` | Registers agent avatars for Chainlit UI. Maps agent names to avatar images. |
| `cards.py` | Work order card rendering and technician action buttons (complete, request parts, reschedule, add notes). |
| `streaming.py` | Manages streaming responses from agents. Handles message buffering and per-agent message display. |

### Database (`db/`)

| File | Purpose |
|------|---------|
| `schema.sql` | PostgreSQL DDL - creates 11 tables, ENUM types, indexes, and foreign keys. Defines the complete data model. |
| `seed.sql` | Sample data - loads textile manufacturing machines, parts catalog, vendors, technicians, and maintenance schedules. |

### Configuration Files

| File | Purpose |
|------|---------|
| `requirements.txt` | Python package dependencies (LangGraph, LangChain, Chainlit, psycopg, OpenAI, etc.). |
| `.env.example` | Template for environment variables (API keys, database credentials, email settings). |
| `.gitignore` | Excludes virtual environment, cache files, .env, database files from git. |
| `chainlit.md` | Welcome message displayed when chat session starts. Describes agents and capabilities. |

---

## 🔧 Configuration Details

### Agent Configuration (`config/settings.py`)

Each agent has:
- `name`: Display name
- `id`: Unique identifier
- `avatar`: Path to avatar image
- `color`: UI color theme
- `model`: LLM model to use (e.g., `gpt-4o-mini`)

### Database Schema

**Key Tables**:
- `industries`: Industry types (textile, automotive, etc.)
- `machines`: Equipment/assets requiring maintenance
- `parts_catalog`: Master parts list
- `inventory`: Current stock levels
- `vendors`: Supplier information
- `technicians`: Field technician roster
- `maintenance_tickets`: Scheduled maintenance tasks (CM/PM)
- `work_orders`: Generated work assignments
- `work_order_parts`: Parts required for work orders
- `purchase_requisitions`: Parts orders to vendors
- `bom`: Bill of materials (machine → parts mapping)

**ENUM Types**:
- `ticket_type`: CM (Corrective), PM (Preventive)
- `ticket_status`: open, assigned, in_progress, waiting_parts, completed, closed
- `work_order_status`: pending, assigned, in_progress, waiting_parts, completed, cancelled
- `requisition_status`: requested, quoted, ordered, delivered, cancelled
- `priority_level`: low, medium, high, critical

---

## 🛠️ Development

### Running in Development Mode

```bash
# Auto-reload on file changes
chainlit run app.py -w

# Debug mode with verbose logging
chainlit run app.py -w --debug
```

### Database Management

```bash
# Connect to database
psql -U postgres -d maintenance_db

# View tables
\dt

# Query example
SELECT * FROM machines;

# Reset database (WARNING: deletes all data)
psql -U postgres -d maintenance_db -f db/schema.sql
psql -U postgres -d maintenance_db -f db/seed.sql
```

### Testing Email Configuration

```python
# Test email sending
python -c "from services.email_service import EmailService; EmailService.send_email('test@example.com', 'Test', 'Test message')"
```

---

## 🐛 Troubleshooting

### Database Connection Errors

**Error**: `connection to server failed`

**Solution**:
1. Ensure PostgreSQL is running: `pg_ctl status`
2. Check credentials in `.env`
3. Verify database exists: `psql -U postgres -l`

### Import Errors

**Error**: `ModuleNotFoundError: No module named 'langgraph'`

**Solution**:
```bash
# Ensure virtual environment is activated
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

### Email Not Sending

**Solution**:
1. Use Gmail App Password (not regular password): [Setup Guide](https://support.google.com/accounts/answer/185833)
2. Enable 2FA on Gmail account first
3. Verify `GMAIL_USER` and `GMAIL_APP_PASSWORD` in `.env`

---

## 📚 Technology Stack

- **LangGraph**: Multi-agent orchestration and state management
- **LangChain**: LLM framework and tool integration
- **Chainlit**: Interactive chat UI framework
- **OpenAI GPT-4o-mini**: Large language model
- **PostgreSQL**: Relational database with checkpointing
- **psycopg3**: PostgreSQL driver with async support
- **Python 3.10+**: Core language

---