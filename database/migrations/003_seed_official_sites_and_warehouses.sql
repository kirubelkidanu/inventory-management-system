-- ------------------------------------------------------------------------------
-- Migration 003: Official Client Sites & Warehouse Bin Locations
-- Deprecate placeholder WH001 / WH002 / PRJ-KZ-01
-- Populate 13 official project sites and warehouse bin locations
-- ------------------------------------------------------------------------------

-- 1. Archive placeholder records (preserve referential integrity for historical ledger)
UPDATE warehouses
SET name = '[Archived] Central Logistics WH', is_active = FALSE
WHERE code = 'WH001';

UPDATE warehouses
SET name = '[Archived] Site Store WH002', is_active = FALSE
WHERE code = 'WH002';

UPDATE projects
SET name = '[Archived] Kazanchis Commercial Complex', is_active = FALSE
WHERE code = 'PRJ-KZ-01';

-- 2. Insert or update 13 official projects
INSERT INTO projects (code, name, location, is_active) VALUES
('PRJ-KZ', 'Kazanchis Project', 'Kazanchis, Addis Ababa', TRUE),
('PRJ-KL', 'Kality Project', 'Kality, Addis Ababa', TRUE),
('PRJ-KL-GAR', 'Kaliti Garage', 'Kality Garage, Addis Ababa', TRUE),
('PRJ-GR', 'Goro ICT Park Project', 'Goro ICT Park, Addis Ababa', TRUE),
('PRJ-LM', 'Lamberet Project', 'Lamberet, Addis Ababa', TRUE),
('PRJ-ET', 'Entoto Project', 'Entoto, Addis Ababa', TRUE),
('PRJ-JM', 'Jimma Project', 'Jimma, Oromia', TRUE),
('PRJ-BS', 'Beshasha Project', 'Beshasha, Oromia', TRUE),
('PRJ-NK', 'Nekemt Project', 'Nekemt, Oromia', TRUE),
('PRJ-CK', 'Chaka Project', 'Chaka, Addis Ababa', TRUE),
('PRJ-JM3', 'Jemo 3 Project', 'Jemo 3, Addis Ababa', TRUE),
('PRJ-HO', 'Head Office', 'Head Office, Addis Ababa', TRUE),
('PRJ-AB', 'Ambo Project', 'Ambo, Oromia', TRUE)
ON CONFLICT (code) DO UPDATE SET
name = EXCLUDED.name,
location = EXCLUDED.location,
is_active = TRUE;

-- 3. Insert or update 13 official warehouse bin locations linked to projects
INSERT INTO warehouses (code, name, location, default_project_id, is_active) VALUES
('KZ-WH-001', 'Kazanchis Store / Bin 001', 'Kazanchis Site', (SELECT id FROM projects WHERE code = 'PRJ-KZ'), TRUE),
('KL-WH-001', 'Kality Store / Bin 001', 'Kality Site', (SELECT id FROM projects WHERE code = 'PRJ-KL'), TRUE),
('KL-WH-002', 'Kaliti Garage Store / Bin 002', 'Kaliti Garage Site', (SELECT id FROM projects WHERE code = 'PRJ-KL-GAR'), TRUE),
('GR-WH-001', 'Goro ICT Park Store / Bin 001', 'Goro ICT Park Site', (SELECT id FROM projects WHERE code = 'PRJ-GR'), TRUE),
('LM-WH-001', 'Lamberet Store / Bin 001', 'Lamberet Site', (SELECT id FROM projects WHERE code = 'PRJ-LM'), TRUE),
('ET-WH-001', 'Entoto Store / Bin 001', 'Entoto Site', (SELECT id FROM projects WHERE code = 'PRJ-ET'), TRUE),
('JM-WH-001', 'Jimma Store / Bin 001', 'Jimma Site', (SELECT id FROM projects WHERE code = 'PRJ-JM'), TRUE),
('BS-WH-001', 'Beshasha Store / Bin 001', 'Beshasha Site', (SELECT id FROM projects WHERE code = 'PRJ-BS'), TRUE),
('NK-WH-001', 'Nekemt Store / Bin 001', 'Nekemt Site', (SELECT id FROM projects WHERE code = 'PRJ-NK'), TRUE),
('CK-WH-001', 'Chaka Store / Bin 001', 'Chaka Site', (SELECT id FROM projects WHERE code = 'PRJ-CK'), TRUE),
('JM3-WH-001', 'Jemo 3 Store / Bin 001', 'Jemo 3 Site', (SELECT id FROM projects WHERE code = 'PRJ-JM3'), TRUE),
('HO-WH-001', 'Head Office Store / Bin 001', 'Head Office Central Store', (SELECT id FROM projects WHERE code = 'PRJ-HO'), TRUE),
('AB-WH-0001', 'Ambo Store / Bin 0001', 'Ambo Site', (SELECT id FROM projects WHERE code = 'PRJ-AB'), TRUE)
ON CONFLICT (code) DO UPDATE SET
name = EXCLUDED.name,
location = EXCLUDED.location,
default_project_id = EXCLUDED.default_project_id,
is_active = TRUE;
