-- ============================================================
-- Agentic Maintenance Planning System - Database Schema
-- PostgreSQL DDL with ENUMs, 11 Tables, PKs, FKs, Indexes
-- ============================================================

-- Drop existing objects if re-running
DROP TABLE IF EXISTS purchase_requisitions CASCADE;
DROP TABLE IF EXISTS work_order_parts CASCADE;
DROP TABLE IF EXISTS work_orders CASCADE;
DROP TABLE IF EXISTS maintenance_tickets CASCADE;
DROP TABLE IF EXISTS inventory CASCADE;
DROP TABLE IF EXISTS bom CASCADE;
DROP TABLE IF EXISTS technicians CASCADE;
DROP TABLE IF EXISTS vendors CASCADE;
DROP TABLE IF EXISTS parts_catalog CASCADE;
DROP TABLE IF EXISTS machines CASCADE;
DROP TABLE IF EXISTS industries CASCADE;

DROP TYPE IF EXISTS ticket_type CASCADE;
DROP TYPE IF EXISTS ticket_status CASCADE;
DROP TYPE IF EXISTS work_order_status CASCADE;
DROP TYPE IF EXISTS requisition_status CASCADE;
DROP TYPE IF EXISTS priority_level CASCADE;

-- ============================================================
-- ENUM Types
-- ============================================================

CREATE TYPE ticket_type AS ENUM ('CM', 'PM');
CREATE TYPE ticket_status AS ENUM ('open', 'assigned', 'in_progress', 'waiting_parts', 'completed', 'closed');
CREATE TYPE work_order_status AS ENUM ('pending', 'assigned', 'in_progress', 'waiting_parts', 'completed', 'cancelled');
CREATE TYPE requisition_status AS ENUM ('requested', 'quoted', 'ordered', 'delivered', 'cancelled');
CREATE TYPE priority_level AS ENUM ('low', 'medium', 'high', 'critical');

-- ============================================================
-- Table 1: industries
-- Multi-industry support for scalability
-- ============================================================

CREATE TABLE industries (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(100) NOT NULL UNIQUE,
    code            VARCHAR(20)  NOT NULL UNIQUE,
    description     TEXT,
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- Table 2: machines
-- All machines across industries
-- ============================================================

CREATE TABLE machines (
    id              SERIAL PRIMARY KEY,
    industry_id     INTEGER NOT NULL REFERENCES industries(id) ON DELETE CASCADE,
    machine_code    VARCHAR(50)  NOT NULL UNIQUE,
    name            VARCHAR(200) NOT NULL,
    location        VARCHAR(200),
    manufacturer    VARCHAR(200),
    model           VARCHAR(100),
    install_date    DATE,
    status          VARCHAR(20) DEFAULT 'operational',  -- operational, down, maintenance
    criticality     priority_level DEFAULT 'medium',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_machines_industry ON machines(industry_id);
CREATE INDEX idx_machines_status ON machines(status);

-- ============================================================
-- Table 3: parts_catalog
-- Master catalog of all known parts
-- ============================================================

CREATE TABLE parts_catalog (
    id              SERIAL PRIMARY KEY,
    part_number     VARCHAR(50)  NOT NULL UNIQUE,
    name            VARCHAR(200) NOT NULL,
    description     TEXT,
    category        VARCHAR(100),
    unit_of_measure VARCHAR(20) DEFAULT 'EA',  -- EA, KG, LTR, MTR
    unit_cost       DECIMAL(12,2),
    lead_time_days  INTEGER DEFAULT 7,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_parts_category ON parts_catalog(category);

-- ============================================================
-- Table 4: bom (Bill of Materials)
-- Maps which parts belong to which machines
-- ============================================================

CREATE TABLE bom (
    id                  SERIAL PRIMARY KEY,
    machine_id          INTEGER NOT NULL REFERENCES machines(id) ON DELETE CASCADE,
    part_id             INTEGER NOT NULL REFERENCES parts_catalog(id) ON DELETE CASCADE,
    quantity_required   INTEGER DEFAULT 1,
    is_critical         BOOLEAN DEFAULT FALSE,
    UNIQUE(machine_id, part_id)
);

CREATE INDEX idx_bom_machine ON bom(machine_id);
CREATE INDEX idx_bom_part ON bom(part_id);

-- ============================================================
-- Table 5: inventory
-- Current stock levels per part
-- ============================================================

CREATE TABLE inventory (
    id                  SERIAL PRIMARY KEY,
    part_id             INTEGER NOT NULL REFERENCES parts_catalog(id) ON DELETE CASCADE UNIQUE,
    quantity_on_hand    INTEGER NOT NULL DEFAULT 0,
    reorder_level       INTEGER DEFAULT 5,
    max_level           INTEGER DEFAULT 50,
    bin_location        VARCHAR(50),
    last_counted        TIMESTAMPTZ,
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_inventory_part ON inventory(part_id);

-- ============================================================
-- Table 6: technicians
-- Available workforce
-- ============================================================

CREATE TABLE technicians (
    id              SERIAL PRIMARY KEY,
    employee_id     VARCHAR(20)  NOT NULL UNIQUE,
    name            VARCHAR(100) NOT NULL,
    specialization  VARCHAR(100),
    is_available    BOOLEAN DEFAULT TRUE,
    phone           VARCHAR(20),
    email           VARCHAR(100),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- Table 7: vendors
-- Supplier contacts
-- ============================================================

CREATE TABLE vendors (
    id                  SERIAL PRIMARY KEY,
    vendor_code         VARCHAR(20)  NOT NULL UNIQUE,
    name                VARCHAR(200) NOT NULL,
    contact_name        VARCHAR(100),
    email               VARCHAR(100) NOT NULL,
    phone               VARCHAR(20),
    address             TEXT,
    status              VARCHAR(20) DEFAULT 'active',  -- active, inactive
    priority_rank       INTEGER DEFAULT 1,  -- 1 = primary, 2 = fallback
    avg_lead_time_days  INTEGER DEFAULT 7,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- Table 8: maintenance_tickets
-- CM (Corrective) and PM (Preventive) maintenance tickets
-- ============================================================

CREATE TABLE maintenance_tickets (
    id                      SERIAL PRIMARY KEY,
    ticket_number           VARCHAR(30)  NOT NULL UNIQUE,
    ticket_type             ticket_type  NOT NULL,
    machine_id              INTEGER NOT NULL REFERENCES machines(id) ON DELETE CASCADE,
    title                   VARCHAR(300) NOT NULL,
    description             TEXT,
    priority                priority_level DEFAULT 'medium',
    status                  ticket_status DEFAULT 'open',
    industry_name           VARCHAR(100),
    reported_by             VARCHAR(100),
    assigned_to_technician_id INTEGER REFERENCES technicians(id),
    due_date                DATE,
    completed_at            TIMESTAMPTZ,
    notes                   TEXT,
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_tickets_status ON maintenance_tickets(status);
CREATE INDEX idx_tickets_type ON maintenance_tickets(ticket_type);
CREATE INDEX idx_tickets_machine ON maintenance_tickets(machine_id);
CREATE INDEX idx_tickets_due_date ON maintenance_tickets(due_date);

-- ============================================================
-- Table 9: work_orders
-- Assigned work for technicians (created by Agent David)
-- ============================================================

CREATE TABLE work_orders (
    id                  SERIAL PRIMARY KEY,
    work_order_number   VARCHAR(30) NOT NULL UNIQUE,
    ticket_id           INTEGER NOT NULL REFERENCES maintenance_tickets(id) ON DELETE CASCADE,
    technician_id       INTEGER REFERENCES technicians(id),
    description         TEXT,
    procedures          TEXT,
    status              work_order_status DEFAULT 'pending',
    estimated_hours     DECIMAL(5,2),
    actual_hours        DECIMAL(5,2),
    scheduled_date      DATE,
    started_at          TIMESTAMPTZ,
    completed_at        TIMESTAMPTZ,
    technician_notes    TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_wo_ticket ON work_orders(ticket_id);
CREATE INDEX idx_wo_technician ON work_orders(technician_id);
CREATE INDEX idx_wo_status ON work_orders(status);
CREATE INDEX idx_wo_scheduled ON work_orders(scheduled_date);

-- ============================================================
-- Table 10: work_order_parts
-- Parts needed per work order
-- ============================================================

CREATE TABLE work_order_parts (
    id                      SERIAL PRIMARY KEY,
    work_order_id           INTEGER NOT NULL REFERENCES work_orders(id) ON DELETE CASCADE,
    part_id                 INTEGER NOT NULL REFERENCES parts_catalog(id) ON DELETE CASCADE,
    quantity_required       INTEGER NOT NULL DEFAULT 1,
    quantity_issued         INTEGER DEFAULT 0,
    is_available            BOOLEAN DEFAULT FALSE,
    is_correct_for_machine  BOOLEAN DEFAULT TRUE,
    notes                   TEXT,
    created_at              TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_wop_work_order ON work_order_parts(work_order_id);
CREATE INDEX idx_wop_part ON work_order_parts(part_id);

-- ============================================================
-- Table 11: purchase_requisitions
-- Procurement tracking (created by Agent Roberto)
-- ============================================================

CREATE TABLE purchase_requisitions (
    id                  SERIAL PRIMARY KEY,
    requisition_number  VARCHAR(30)  NOT NULL UNIQUE,
    work_order_id       INTEGER REFERENCES work_orders(id),
    part_id             INTEGER NOT NULL REFERENCES parts_catalog(id) ON DELETE CASCADE,
    quantity            INTEGER NOT NULL,
    vendor_id           INTEGER REFERENCES vendors(id),
    status              requisition_status DEFAULT 'requested',
    quoted_price        DECIMAL(12,2),
    expected_delivery   DATE,
    actual_delivery     DATE,
    vendor_response     TEXT,
    fallback_vendor_id  INTEGER REFERENCES vendors(id),
    email_thread_id     VARCHAR(100),
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_pr_work_order ON purchase_requisitions(work_order_id);
CREATE INDEX idx_pr_vendor ON purchase_requisitions(vendor_id);
CREATE INDEX idx_pr_status ON purchase_requisitions(status);
CREATE INDEX idx_pr_part ON purchase_requisitions(part_id);
