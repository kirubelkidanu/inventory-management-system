-- Migration 005: Seed expanded categories (15: STATIONERY, 16: HOUSEHOLD, 17: CLEAN, 18: COMPUTER & IT)

INSERT INTO categories (id, code, name, description, is_active)
VALUES
    (gen_random_uuid(), '15', 'STATIONERY', 'Office Supplies, Paper & Stationery', true),
    (gen_random_uuid(), '16', 'HOUSEHOLD', 'Household Goods, Appliances & Supplies', true),
    (gen_random_uuid(), '17', 'CLEAN', 'Cleaning Materials, Detergents & Janitorial Supplies', true),
    (gen_random_uuid(), '18', 'COMPUTER & IT', 'Computers, IT Hardware & Networking Equipment', true)
ON CONFLICT (code) DO UPDATE
SET name = EXCLUDED.name,
    description = EXCLUDED.description,
    is_active = true,
    updated_at = NOW();
