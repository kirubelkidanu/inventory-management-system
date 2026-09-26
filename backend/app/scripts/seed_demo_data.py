"""
Standalone Database Seeding Script for Master Data & Opening Balances.

Strictly follows:
- AGENTS.md (Dual-write invariant, no hardcoding WH001 in business logic, use TransactionService)
- docs/DATABASE.md
- docs/PROJECT_SPEC.md
- decisions.md (ADR-001 through ADR-007)

Usage:
    $env:PYTHONPATH = "backend"
    .\.venv\Scripts\python.exe backend/app/scripts/seed_demo_data.py
"""

import asyncio
from datetime import date, datetime, timezone
from decimal import Decimal
import json
import logging
import sys
import uuid

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.models import (
    Category,
    InventoryBalance,
    Item,
    Project,
    User,
    Warehouse,
)
from app.schemas.transaction import GRVCreate, TransactionLineCreate
from app.services.transaction import TransactionService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ims.seed")

# Deterministic User Profiles matching app/api/routes/auth.py DEMO_ACCOUNTS
DEMO_USERS = [
    {
        "id": uuid.UUID("11111111-1111-1111-1111-111111111111"),
        "email": "admin@ims.local",
        "full_name": "Alice Administrator",
        "role": "ADMIN",
    },
    {
        "id": uuid.UUID("22222222-2222-2222-2222-222222222222"),
        "email": "manager@ims.local",
        "full_name": "Bob Manager",
        "role": "INVENTORY_MANAGER",
    },
    {
        "id": uuid.UUID("33333333-3333-3333-3333-333333333333"),
        "email": "storekeeper@ims.local",
        "full_name": "Charlie Keeper",
        "role": "STORE_KEEPER",
    },
    {
        "id": uuid.UUID("44444444-4444-4444-4444-444444444444"),
        "email": "viewer@ims.local",
        "full_name": "Diana Auditor",
        "role": "VIEWER",
    },
]

# Standard Categories from docs/PROJECT_SPEC.md
SEED_CATEGORIES = [
    {"code": "01", "name": "CEMENT", "description": "Cement & Binding Materials"},
    {"code": "02", "name": "STEEL", "description": "Reinforcement & Structural Steel"},
    {"code": "07", "name": "PAINT AND CHEMICAL", "description": "Paints, Primers & Chemical Products"},
]

# Master Catalog Items
SEED_ITEMS = [
    {
        "item_code": "01-CM-00001",
        "description": "Portland Cement Grade 42.5N",
        "category_code": "01",
        "default_unit": "BAG",
    },
    {
        "item_code": "02-ST-00001",
        "description": "Reinforcement Bar 12mm High Yield",
        "category_code": "02",
        "default_unit": "PCS",
    },
    {
        "item_code": "02-ST-00002",
        "description": "Reinforcement Bar 16mm High Yield",
        "category_code": "02",
        "default_unit": "PCS",
    },
    {
        "item_code": "07-PC-00001",
        "description": "Anti-Rust Red Oxide Primer",
        "category_code": "07",
        "default_unit": "LTR",
    },
]


async def seed_users(session: AsyncSession) -> dict[str, User]:
    """
    Seeds demo users ensuring referential integrity with auth.users.
    """
    logger.info("--- Seeding Demo Users & Auth Link ---")
    user_map: dict[str, User] = {}

    for u_info in DEMO_USERS:
        # 1. Check if row exists in auth.users
        auth_check = await session.execute(
            text("SELECT id FROM auth.users WHERE email = :email"),
            {"email": u_info["email"]},
        )
        existing_auth_id = auth_check.scalar_one_or_none()

        auth_user_id = existing_auth_id or u_info["id"]

        if not existing_auth_id:
            logger.info("Inserting auth.users record for %s (id=%s)", u_info["email"], auth_user_id)
            await session.execute(
                text("""
                    INSERT INTO auth.users (
                        id,
                        email,
                        aud,
                        role,
                        created_at,
                        updated_at
                    ) VALUES (
                        :id,
                        :email,
                        'authenticated',
                        'authenticated',
                        NOW(),
                        NOW()
                    )
                """),
                {
                    "id": auth_user_id,
                    "email": u_info["email"],
                },
            )

        # 2. Check if row exists in public.users
        user_res = await session.execute(
            select(User).where(User.email == u_info["email"])
        )
        user_obj = user_res.scalar_one_or_none()

        if not user_obj:
            logger.info("Inserting public.users profile for %s (%s)", u_info["email"], u_info["role"])
            user_obj = User(
                id=u_info["id"],
                auth_user_id=auth_user_id,
                email=u_info["email"],
                full_name=u_info["full_name"],
                role=u_info["role"],
                is_active=True,
            )
            session.add(user_obj)
            await session.flush()
        else:
            logger.info("Existing public.users found for %s (%s)", u_info["email"], user_obj.role)

        user_map[u_info["role"]] = user_obj

    await session.commit()
    return user_map


async def seed_project(session: AsyncSession) -> Project:
    """
    Seeds Project PRJ-KZ-01: Kazanchis Commercial Complex.
    """
    logger.info("--- Seeding Project ---")
    stmt = select(Project).where(Project.code == "PRJ-KZ-01")
    res = await session.execute(stmt)
    project = res.scalar_one_or_none()

    if not project:
        logger.info("Creating Project PRJ-KZ-01: Kazanchis Commercial Complex")
        project = Project(
            id=uuid.uuid4(),
            code="PRJ-KZ-01",
            name="Kazanchis Commercial Complex",
            location="Kazanchis, Addis Ababa",
            is_active=True,
        )
        session.add(project)
        await session.commit()
        await session.refresh(project)
    else:
        logger.info("Project PRJ-KZ-01 already exists: id=%s", project.id)

    return project


async def seed_warehouses(session: AsyncSession, project: Project) -> tuple[Warehouse, Warehouse]:
    """
    Seeds Warehouses:
    - WH001: Central Logistics WH (linked to PRJ-KZ-01)
    - WH002: Site Store WH002 (Bole Site)
    """
    logger.info("--- Seeding Warehouses ---")

    # WH001
    wh1_res = await session.execute(select(Warehouse).where(Warehouse.code == "WH001"))
    wh001 = wh1_res.scalar_one_or_none()
    if not wh001:
        logger.info("Creating Warehouse WH001: Central Logistics WH")
        wh001 = Warehouse(
            id=uuid.uuid4(),
            code="WH001",
            name="Central Logistics WH",
            location="Kazanchis, Addis Ababa",
            default_project_id=project.id,
            is_active=True,
        )
        session.add(wh001)
    else:
        logger.info("Warehouse WH001 already exists: id=%s", wh001.id)

    # WH002
    wh2_res = await session.execute(select(Warehouse).where(Warehouse.code == "WH002"))
    wh002 = wh2_res.scalar_one_or_none()
    if not wh002:
        logger.info("Creating Warehouse WH002: Site Store WH002")
        wh002 = Warehouse(
            id=uuid.uuid4(),
            code="WH002",
            name="Site Store WH002",
            location="Bole Site",
            default_project_id=None,
            is_active=True,
        )
        session.add(wh002)
    else:
        logger.info("Warehouse WH002 already exists: id=%s", wh002.id)

    await session.commit()
    await session.refresh(wh001)
    await session.refresh(wh002)
    return wh001, wh002


async def seed_categories(session: AsyncSession) -> dict[str, Category]:
    """
    Seeds standard Categories 01, 02, 07.
    """
    logger.info("--- Seeding Item Categories ---")
    cat_map: dict[str, Category] = {}

    for c_info in SEED_CATEGORIES:
        res = await session.execute(select(Category).where(Category.code == c_info["code"]))
        cat = res.scalar_one_or_none()
        if not cat:
            logger.info("Creating Category %s: %s", c_info["code"], c_info["name"])
            cat = Category(
                id=uuid.uuid4(),
                code=c_info["code"],
                name=c_info["name"],
                description=c_info["description"],
                is_active=True,
            )
            session.add(cat)
            await session.flush()
        else:
            logger.info("Category %s already exists: id=%s", c_info["code"], cat.id)
        cat_map[c_info["code"]] = cat

    await session.commit()
    return cat_map


async def seed_items(session: AsyncSession, cat_map: dict[str, Category]) -> dict[str, Item]:
    """
    Seeds master catalog items.
    """
    logger.info("--- Seeding Master Catalog Items ---")
    item_map: dict[str, Item] = {}

    for item_def in SEED_ITEMS:
        res = await session.execute(select(Item).where(Item.item_code == item_def["item_code"]))
        item = res.scalar_one_or_none()
        category = cat_map[item_def["category_code"]]

        if not item:
            logger.info("Creating Item %s: %s", item_def["item_code"], item_def["description"])
            item = Item(
                id=uuid.uuid4(),
                item_code=item_def["item_code"],
                description=item_def["description"],
                category_id=category.id,
                default_unit=item_def["default_unit"],
                is_active=True,
            )
            session.add(item)
            await session.flush()
        else:
            logger.info("Item %s already exists: id=%s", item_def["item_code"], item.id)
        item_map[item_def["item_code"]] = item

    await session.commit()
    return item_map


async def seed_opening_balances(
    session: AsyncSession,
    admin_user: User,
    project: Project,
    wh001: Warehouse,
    items: dict[str, Item],
):
    """
    Seeds opening balances for WH001 via TransactionService GRV voucher.
    Strictly follows ADR-001 Dual-Write Invariant:
    - inventory_balances updated
    - stock_movements ledger appended
    """
    logger.info("--- Checking & Seeding Opening Stock Balances ---")

    # Check if WH001 has existing non-zero balances
    b_res = await session.execute(
        select(InventoryBalance).where(
            InventoryBalance.warehouse_id == wh001.id,
            InventoryBalance.quantity_on_hand > Decimal("0"),
        )
    )
    existing_balances = b_res.scalars().all()

    if existing_balances:
        logger.info(
            "WH001 already has %d active stock balance rows. Skipping opening GRV voucher.",
            len(existing_balances),
        )
        return

    logger.info("Posting Opening GRV Voucher via TransactionService for WH001...")

    grv_payload = GRVCreate(
        warehouse_id=wh001.id,
        project_id=project.id,
        transaction_date=date.today(),
        supplier_name="Initial Opening Stock Balance",
        invoice_no="INIT-OPENING-001",
        received_grv_no="GRV-OPENING-001",
        store_no="STORE-01",
        remarks="Opening inventory balances seed (ADR-001 dual-write invariant)",
        lines=[
            TransactionLineCreate(
                item_id=items["01-CM-00001"].id,
                quantity=Decimal("1200"),
                unit="BAG",
                remarks="Opening balance 1,200 BAG",
            ),
            TransactionLineCreate(
                item_id=items["02-ST-00001"].id,
                quantity=Decimal("500"),
                unit="PCS",
                remarks="Opening balance 500 PCS",
            ),
            TransactionLineCreate(
                item_id=items["02-ST-00002"].id,
                quantity=Decimal("350"),
                unit="PCS",
                remarks="Opening balance 350 PCS",
            ),
        ],
    )

    tx_service = TransactionService(session)
    tx = await tx_service.create_and_post_grv(user_id=admin_user.id, payload=grv_payload)
    logger.info("Opening GRV Voucher successfully posted! Tx Number: %s", tx.transaction_number)


async def print_verification_summary(session: AsyncSession):
    """
    Prints a detailed verification audit of seeded data in the database.
    """
    logger.info("==================================================")
    logger.info("        DATABASE SEEDING VERIFICATION AUDIT       ")
    logger.info("==================================================")

    # 1. Users
    u_res = await session.execute(select(User).order_by(User.role))
    users = u_res.scalars().all()
    logger.info("Users (%d total):", len(users))
    for u in users:
        logger.info("  - %s <%s> Role: %s (id: %s)", u.full_name, u.email, u.role, u.id)

    # 2. Projects
    p_res = await session.execute(select(Project).order_by(Project.code))
    projects = p_res.scalars().all()
    logger.info("Projects (%d total):", len(projects))
    for p in projects:
        logger.info("  - [%s] %s | Location: %s", p.code, p.name, p.location)

    # 3. Warehouses
    w_res = await session.execute(select(Warehouse).order_by(Warehouse.code))
    warehouses = w_res.scalars().all()
    logger.info("Warehouses (%d total):", len(warehouses))
    for w in warehouses:
        logger.info("  - [%s] %s | Location: %s", w.code, w.name, w.location)

    # 4. Categories
    c_res = await session.execute(select(Category).order_by(Category.code))
    cats = c_res.scalars().all()
    logger.info("Categories (%d total):", len(cats))
    for c in cats:
        logger.info("  - [%s] %s", c.code, c.name)

    # 5. Items
    i_res = await session.execute(select(Item).order_by(Item.item_code))
    items = i_res.scalars().all()
    logger.info("Catalog Items (%d total):", len(items))
    for item in items:
        logger.info("  - [%s] %s (Unit: %s)", item.item_code, item.description, item.default_unit)

    # 6. Current Inventory Balances
    b_res = await session.execute(
        select(InventoryBalance, Warehouse, Item)
        .join(Warehouse, InventoryBalance.warehouse_id == Warehouse.id)
        .join(Item, InventoryBalance.item_id == Item.id)
        .order_by(Warehouse.code, Item.item_code)
    )
    balances = b_res.all()
    logger.info("Inventory Balances (%d records):", len(balances))
    for bal, wh, itm in balances:
        logger.info(
            "  - %s @ %s: On-Hand=%s, Reserved=%s, Available=%s %s",
            itm.item_code,
            wh.code,
            bal.quantity_on_hand,
            bal.quantity_reserved,
            bal.quantity_on_hand - bal.quantity_reserved,
            itm.default_unit,
        )

    # 7. Stock Movements Count
    m_count_res = await session.execute(text("SELECT count(*) FROM stock_movements;"))
    m_count = m_count_res.scalar()
    logger.info("Stock Movements Ledger: %d entries", m_count)

    # 8. Reconciliation Discrepancy Check (vw_reconciliation_discrepancies)
    disc_res = await session.execute(text("SELECT count(*) FROM vw_reconciliation_discrepancies;"))
    disc_count = disc_res.scalar()
    if disc_count == 0:
        logger.info("Reconciliation View Discrepancies: 0 (Dual-Write 100%% IN BALANCE)")
    else:
        logger.error("ALERT: %d Discrepancies detected in vw_reconciliation_discrepancies!", disc_count)

    logger.info("==================================================")


async def main():
    settings = get_settings()
    logger.info("Connecting to target database...")
    logger.info("Target Host: %s", settings.DATABASE_URL.split("@")[-1])

    async with AsyncSessionLocal() as session:
        # Step 1: Seed Users
        users = await seed_users(session)
        admin_user = users["ADMIN"]

        # Step 2: Seed Project
        project = await seed_project(session)

        # Step 3: Seed Warehouses
        wh001, wh002 = await seed_warehouses(session, project)

        # Step 4: Seed Categories
        cats = await seed_categories(session)

        # Step 5: Seed Items
        items = await seed_items(session, cats)

        # Step 6: Seed Opening Balances
        await seed_opening_balances(
            session=session,
            admin_user=admin_user,
            project=project,
            wh001=wh001,
            items=items,
        )

        # Step 7: Print Verification Summary
        await print_verification_summary(session)


if __name__ == "__main__":
    asyncio.run(main())
