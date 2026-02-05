-- ============================================================
-- Agentic Maintenance Planning System - Seed Data
-- Demo-ready data for 2 industries, 6 machines, 12 parts,
-- 4 technicians, 2 vendors, 4 tickets, 2 work orders
-- ============================================================

-- ============================================================
-- Industries
-- ============================================================

INSERT INTO industries (name, code, description, is_active) VALUES
('Rubber Manufacturing', 'RUBBER', 'Rubber processing and manufacturing operations including mixing, extrusion, and calendering', TRUE),
('Oil & Gas', 'OIL_GAS', 'Oil and gas exploration, production, and refining operations', TRUE);

-- ============================================================
-- Machines
-- ============================================================

-- Rubber Manufacturing machines
INSERT INTO machines (industry_id, machine_code, name, location, manufacturer, model, install_date, status, criticality) VALUES
(1, 'MIX-001', 'Banbury Mixer #1',     'Building A - Bay 1', 'HF Mixing Group',  'GK400N',    '2020-03-15', 'operational', 'critical'),
(1, 'EXT-002', 'Rubber Extruder #2',   'Building A - Bay 3', 'Berstorff',        'GE90',      '2019-06-20', 'operational', 'high'),
(1, 'CAL-003', 'Calender Machine #3',  'Building B - Bay 1', 'Comerio Ercole',   'CER-600',   '2021-01-10', 'operational', 'medium');

-- Oil & Gas machines
INSERT INTO machines (industry_id, machine_code, name, location, manufacturer, model, install_date, status, criticality) VALUES
(2, 'PMP-001', 'Mud Pump #1',          'Platform B - Deck 2', 'National Oilwell', 'NOV 14-P',  '2018-09-01', 'operational', 'critical'),
(2, 'CMP-002', 'Gas Compressor #2',    'Platform B - Deck 3', 'Atlas Copco',      'ZH 10000',  '2019-11-15', 'operational', 'high'),
(2, 'GEN-003', 'Diesel Generator #3',  'Platform B - Utility', 'Caterpillar',     'CAT 3516B', '2020-07-22', 'maintenance', 'medium');

-- ============================================================
-- Parts Catalog
-- ============================================================

INSERT INTO parts_catalog (part_number, name, description, category, unit_of_measure, unit_cost, lead_time_days) VALUES
('BRG-6205-2RS',  'Deep Groove Ball Bearing 6205',     'SKF 6205-2RS sealed bearing, 25x52x15mm',        'Bearings',          'EA', 45.00,  3),
('SEAL-NBR-50',   'NBR O-Ring Seal 50mm',              'Nitrile rubber O-ring seal, 50mm ID, 5mm CS',     'Seals',             'EA', 8.50,   2),
('BLT-HEX-M12',  'Hex Bolt M12x50 Grade 8.8',         'High tensile hex bolt, M12x50, zinc plated',      'Fasteners',         'EA', 2.25,   1),
('MTR-15KW',     'AC Motor 15kW',                      '15kW 3-phase AC motor, 1450RPM, IE3 efficiency',  'Motors',            'EA', 2800.00, 14),
('FLT-HYD-10',   'Hydraulic Filter 10 Micron',         'Spin-on hydraulic filter, 10 micron, 250 PSI',    'Filters',           'EA', 65.00,  5),
('VBL-CONV-500',  'Conveyor Belt 500mm',               'Heavy-duty rubber conveyor belt, 500mm width',    'Belts',             'MTR', 120.00, 10),
('GRS-LITH-5',   'Lithium Grease 5kg',                 'Multi-purpose lithium grease, NLGI Grade 2',      'Lubricants',        'EA', 35.00,  2),
('PMP-IMP-200',  'Pump Impeller 200mm',                'Cast iron centrifugal pump impeller, 200mm dia',  'Pump Components',   'EA', 450.00, 12),
('VLV-GATE-4',   'Gate Valve 4 inch',                  '4 inch cast steel gate valve, 300# class',        'Valves',            'EA', 380.00, 8),
('SNS-TEMP-PT100','PT100 Temperature Sensor',           'PT100 RTD probe, -50 to 400C, 200mm insertion',  'Instrumentation',   'EA', 95.00,  4),
('CPN-CTRL-PLC', 'PLC Controller Module',              'Programmable logic controller, 16 I/O module',    'Controls',          'EA', 1200.00, 15),
('HSE-HYD-12',   'Hydraulic Hose 12mm',                '12mm ID steel-braided hydraulic hose, 400 BAR',   'Hoses',             'MTR', 28.00,  3);

-- ============================================================
-- BOM (Bill of Materials) - Which parts belong to which machines
-- ============================================================

-- Banbury Mixer #1 (MIX-001)
INSERT INTO bom (machine_id, part_id, quantity_required, is_critical) VALUES
(1, 1,  4, TRUE),   -- 4x Ball Bearings (critical)
(1, 2,  8, FALSE),  -- 8x O-Ring Seals
(1, 3,  12, FALSE), -- 12x Hex Bolts
(1, 7,  2, FALSE),  -- 2x Lithium Grease 5kg
(1, 4,  1, TRUE);   -- 1x AC Motor 15kW (critical)

-- Rubber Extruder #2 (EXT-002)
INSERT INTO bom (machine_id, part_id, quantity_required, is_critical) VALUES
(2, 1,  2, TRUE),   -- 2x Ball Bearings (critical)
(2, 2,  6, FALSE),  -- 6x O-Ring Seals
(2, 6,  1, TRUE),   -- 1x Conveyor Belt (critical)
(2, 5,  2, FALSE),  -- 2x Hydraulic Filters
(2, 12, 3, FALSE);  -- 3m Hydraulic Hose

-- Calender Machine #3 (CAL-003)
INSERT INTO bom (machine_id, part_id, quantity_required, is_critical) VALUES
(3, 1,  6, TRUE),   -- 6x Ball Bearings (critical)
(3, 7,  3, FALSE),  -- 3x Lithium Grease
(3, 10, 2, FALSE),  -- 2x Temperature Sensors
(3, 3,  20, FALSE); -- 20x Hex Bolts

-- Mud Pump #1 (PMP-001)
INSERT INTO bom (machine_id, part_id, quantity_required, is_critical) VALUES
(4, 8,  1, TRUE),   -- 1x Pump Impeller (critical)
(4, 2,  10, FALSE), -- 10x O-Ring Seals
(4, 9,  2, FALSE),  -- 2x Gate Valves
(4, 12, 5, FALSE),  -- 5m Hydraulic Hose
(4, 5,  3, FALSE);  -- 3x Hydraulic Filters

-- Gas Compressor #2 (CMP-002)
INSERT INTO bom (machine_id, part_id, quantity_required, is_critical) VALUES
(5, 1,  4, TRUE),   -- 4x Ball Bearings (critical)
(5, 5,  4, FALSE),  -- 4x Hydraulic Filters
(5, 10, 3, FALSE),  -- 3x Temperature Sensors
(5, 11, 1, TRUE),   -- 1x PLC Controller (critical)
(5, 7,  2, FALSE);  -- 2x Lithium Grease

-- Diesel Generator #3 (GEN-003)
INSERT INTO bom (machine_id, part_id, quantity_required, is_critical) VALUES
(6, 5,  2, TRUE),   -- 2x Hydraulic Filters (critical)
(6, 4,  1, TRUE),   -- 1x AC Motor (critical)
(6, 12, 4, FALSE),  -- 4m Hydraulic Hose
(6, 10, 2, FALSE);  -- 2x Temperature Sensors

-- ============================================================
-- Inventory - Mixed availability for demo scenarios
-- ============================================================

INSERT INTO inventory (part_id, quantity_on_hand, reorder_level, max_level, bin_location, last_counted) VALUES
(1,  15, 5,  40, 'A-1-01', '2026-01-28 09:00:00+00'),  -- Ball Bearings: well stocked
(2,  25, 10, 50, 'A-1-02', '2026-01-28 09:00:00+00'),  -- O-Ring Seals: well stocked
(3,  100, 20, 200, 'A-2-01', '2026-01-28 09:00:00+00'), -- Hex Bolts: well stocked
(4,  1,  1,  3,  'B-1-01', '2026-01-28 09:00:00+00'),  -- AC Motor: at reorder level
(5,  8,  5,  20, 'A-2-03', '2026-01-28 09:00:00+00'),  -- Hydraulic Filters: adequate
(6,  0,  2,  5,  'C-1-01', '2026-01-28 09:00:00+00'),  -- Conveyor Belt: OUT OF STOCK
(7,  6,  3,  15, 'A-3-01', '2026-01-28 09:00:00+00'),  -- Lithium Grease: adequate
(8,  0,  1,  3,  'B-2-01', '2026-01-28 09:00:00+00'),  -- Pump Impeller: OUT OF STOCK
(9,  3,  2,  8,  'B-2-02', '2026-01-28 09:00:00+00'),  -- Gate Valves: above reorder
(10, 4,  3,  10, 'A-3-03', '2026-01-28 09:00:00+00'),  -- Temp Sensors: above reorder
(11, 0,  1,  2,  'B-3-01', '2026-01-28 09:00:00+00'),  -- PLC Controller: OUT OF STOCK
(12, 12, 5,  25, 'C-2-01', '2026-01-28 09:00:00+00');   -- Hydraulic Hose: well stocked

-- ============================================================
-- Technicians
-- ============================================================

INSERT INTO technicians (employee_id, name, specialization, is_available, phone, email) VALUES
('TECH-001', 'Ahmed Khan',      'Mechanical',       TRUE,  '+1-555-0101', 'ahmed.k@maintenance.local'),
('TECH-002', 'Sarah Johnson',   'Electrical',        TRUE,  '+1-555-0102', 'sarah.j@maintenance.local'),
('TECH-003', 'Marcus Chen',     'Instrumentation',   TRUE,  '+1-555-0103', 'marcus.c@maintenance.local'),
('TECH-004', 'Eric Petrov',     'General Maintenance', FALSE, '+1-555-0104', 'eric.p@maintenance.local');

-- ============================================================
-- Vendors
-- ============================================================

INSERT INTO vendors (vendor_code, name, contact_name, email, phone, address, status, priority_rank, avg_lead_time_days) VALUES
('VEND-A', 'Alpha Industrial Supplies', 'John Miller',   'vendor.a@example.com', '+1-555-0201', '123 Industrial Ave, Houston, TX 77001',    'active', 1, 5),
('VEND-B', 'Beta Parts Corporation',    'Lisa Thompson', 'vendor.b@example.com', '+1-555-0202', '456 Manufacturing Blvd, Dallas, TX 75201', 'active', 2, 7);

-- ============================================================
-- Maintenance Tickets - Mix of CM and PM, various statuses
-- ============================================================

INSERT INTO maintenance_tickets (ticket_number, ticket_type, machine_id, title, description, priority, status, industry_name, reported_by, due_date, created_at) VALUES
('CM-2026-0001', 'CM', 1, 'Bearing Noise on Banbury Mixer',
 'Unusual grinding noise detected from the main drive bearings during operation. Vibration levels elevated. Immediate inspection and replacement recommended.',
 'critical', 'open', 'Rubber Manufacturing', 'Shift Supervisor', '2026-02-04', '2026-02-03 14:30:00+00'),

('PM-2026-0001', 'PM', 2, 'Scheduled Monthly PM - Rubber Extruder',
 'Monthly preventive maintenance: Check belt tension, lubrication points, hydraulic system inspection, filter replacement, and general condition assessment.',
 'medium', 'open', 'Rubber Manufacturing', 'System Auto', '2026-02-04', '2026-02-01 06:00:00+00'),

('CM-2026-0002', 'CM', 4, 'Mud Pump Impeller Wear',
 'Reduced pump output detected. Impeller shows signs of cavitation wear. Flow rate dropped by 15%. Replacement required.',
 'high', 'open', 'Oil & Gas', 'Operations Lead', '2026-02-05', '2026-02-03 10:00:00+00'),

('PM-2026-0002', 'PM', 3, 'Quarterly Inspection - Calender Machine',
 'Quarterly inspection: Bearing condition check, temperature sensor calibration, roller alignment verification, lubrication system check.',
 'low', 'open', 'Rubber Manufacturing', 'System Auto', '2026-02-07', '2026-02-01 06:00:00+00');

-- ============================================================
-- Pre-existing Work Orders (to show history)
-- ============================================================

-- No pre-existing work orders -- all will be created fresh during demo

-- ============================================================
-- Pre-existing Purchase Requisitions (to show history)
-- ============================================================

-- No pre-existing requisitions -- all will be created fresh during demo
