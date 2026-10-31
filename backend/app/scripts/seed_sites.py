"""
Official Client Sites & Warehouse Bin Locations Seeding Script.

Configures the client's official 13 project sites and warehouse bin locations,
archives placeholder records (WH001, WH002, PRJ-KZ-01) while preserving 100%
referential integrity and ledger balance.

Usage:
    $env:PYTHONPATH = "backend"
    .\.venv\Scripts\python.exe backend/app/scripts/seed_sites.py
"""

import asyncio
import logging
import uuid
from typing import Any, Dict, List

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.models.project import Project
from app.models.warehouse import Warehouse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ims.seed_sites")

OFFICIAL_SITES: List[Dict[str, Any]] = [
    {
        "project_code": "PRJ-KZ",
        "project_name": "Kazanchis Project",
        "project_location": "Kazanchis, Addis Ababa",
        "warehouse_code": "KZ-WH-001",
        "warehouse_name": "Kazanchis Store / Bin 001",
        "warehouse_location": "Kazanchis Site",
    },
    {
        "project_code": "PRJ-KL",
        "project_name": "Kality Project",
        "project_location": "Kality, Addis Ababa",
        "warehouse_code": "KL-WH-001",
        "warehouse_name": "Kality Store / Bin 001",
        "warehouse_location": "Kality Site",
    },
    {
        "project_code": "PRJ-KL-GAR",
        "project_name": "Kaliti Garage",
        "project_location": "Kality Garage, Addis Ababa",
        "warehouse_code": "KL-WH-002",
        "warehouse_name": "Kaliti Garage Store / Bin 002",
        "warehouse_location": "Kaliti Garage Site",
    },
    {
        "project_code": "PRJ-GR",
        "project_name": "Goro ICT Park Project",
        "project_location": "Goro ICT Park, Addis Ababa",
        "warehouse_code": "GR-WH-001",
        "warehouse_name": "Goro ICT Park Store / Bin 001",
        "warehouse_location": "Goro ICT Park Site",
    },
    {
        "project_code": "PRJ-LM",
        "project_name": "Lamberet Project",
        "project_location": "Lamberet, Addis Ababa",
        "warehouse_code": "LM-WH-001",
        "warehouse_name": "Lamberet Store / Bin 001",
        "warehouse_location": "Lamberet Site",
    },
    {
        "project_code": "PRJ-ET",
        "project_name": "Entoto Project",
        "project_location": "Entoto, Addis Ababa",
        "warehouse_code": "ET-WH-001",
        "warehouse_name": "Entoto Store / Bin 001",
        "warehouse_location": "Entoto Site",
    },
    {
        "project_code": "PRJ-JM",
        "project_name": "Jimma Project",
        "project_location": "Jimma, Oromia",
        "warehouse_code": "JM-WH-001",
        "warehouse_name": "Jimma Store / Bin 001",
        "warehouse_location": "Jimma Site",
    },
    {
        "project_code": "PRJ-BS",
        "project_name": "Beshasha Project",
        "project_location": "Beshasha, Oromia",
        "warehouse_code": "BS-WH-001",
        "warehouse_name": "Beshasha Store / Bin 001",
        "warehouse_location": "Beshasha Site",
    },
    {
        "project_code": "PRJ-NK",
        "project_name": "Nekemt Project",
        "project_location": "Nekemt, Oromia",
        "warehouse_code": "NK-WH-001",
        "warehouse_name": "Nekemt Store / Bin 001",
        "warehouse_location": "Nekemt Site",
    },
    {
        "project_code": "PRJ-CK",
        "project_name": "Chaka Project",
        "project_location": "Chaka, Addis Ababa",
        "warehouse_code": "CK-WH-001",
        "warehouse_name": "Chaka Store / Bin 001",
        "warehouse_location": "Chaka Site",
    },
    {
        "project_code": "PRJ-JM3",
        "project_name": "Jemo 3 Project",
        "project_location": "Jemo 3, Addis Ababa",
        "warehouse_code": "JM3-WH-001",
        "warehouse_name": "Jemo 3 Store / Bin 001",
        "warehouse_location": "Jemo 3 Site",
    },
    {
        "project_code": "PRJ-HO",
        "project_name": "Head Office",
        "project_location": "Head Office, Addis Ababa",
        "warehouse_code": "HO-WH-001",
        "warehouse_name": "Head Office Store / Bin 001",
        "warehouse_location": "Head Office Central Store",
    },
    {
        "project_code": "PRJ-AB",
        "project_name": "Ambo Project",
        "project_location": "Ambo, Oromia",
        "warehouse_code": "AB-WH-0001",
        "warehouse_name": "Ambo Store / Bin 0001",
        "warehouse_location": "Ambo Site",
    },
]


async def archive_placeholder_records(session: AsyncSession) -> None:
    """
    Safely archives placeholder records (WH001, WH002, PRJ-KZ-01) without
    deleting historical transactions or violating ledger invariants.
    """
    logger.info("--- Archiving Placeholder Warehouses & Projects ---")

    # 1. Archive WH001
    wh001_res = await session.execute(select(Warehouse).where(Warehouse.code == "WH001"))
    wh001 = wh001_res.scalar_one_or_none()
    if wh001:
        wh001.name = "[Archived] Central Logistics WH"
        wh001.is_active = False
        logger.info("Archived placeholder warehouse WH001 (id=%s)", wh001.id)

    # 2. Archive WH002
    wh002_res = await session.execute(select(Warehouse).where(Warehouse.code == "WH002"))
    wh002 = wh002_res.scalar_one_or_none()
    if wh002:
        wh002.name = "[Archived] Site Store WH002"
        wh002.is_active = False
        logger.info("Archived placeholder warehouse WH002 (id=%s)", wh002.id)

    # 3. Archive PRJ-KZ-01
    prj01_res = await session.execute(select(Project).where(Project.code == "PRJ-KZ-01"))
    prj01 = prj01_res.scalar_one_or_none()
    if prj01:
        prj01.name = "[Archived] Kazanchis Commercial Complex"
        prj01.is_active = False
        logger.info("Archived placeholder project PRJ-KZ-01 (id=%s)", prj01.id)

    await session.commit()


async def seed_official_sites(session: AsyncSession) -> None:
    """
    Idempotently creates or updates the 13 official client projects and warehouses.
    """
    logger.info("--- Seeding 13 Official Client Sites & Warehouse Bin Locations ---")

    for site in OFFICIAL_SITES:
        # 1. Project
        p_res = await session.execute(select(Project).where(Project.code == site["project_code"]))
        project = p_res.scalar_one_or_none()

        if not project:
            logger.info("Creating Project [%s] %s", site["project_code"], site["project_name"])
            project = Project(
                id=uuid.uuid4(),
                code=site["project_code"],
                name=site["project_name"],
                location=site["project_location"],
                is_active=True,
            )
            session.add(project)
            await session.flush()
        else:
            project.name = site["project_name"]
            project.location = site["project_location"]
            project.is_active = True
            logger.info("Updated existing Project [%s] %s", site["project_code"], project.name)

        # 2. Warehouse Bin Location
        w_res = await session.execute(select(Warehouse).where(Warehouse.code == site["warehouse_code"]))
        warehouse = w_res.scalar_one_or_none()

        if not warehouse:
            logger.info("Creating Warehouse [%s] %s (Project: %s)", site["warehouse_code"], site["warehouse_name"], site["project_code"])
            warehouse = Warehouse(
                id=uuid.uuid4(),
                code=site["warehouse_code"],
                name=site["warehouse_name"],
                location=site["warehouse_location"],
                default_project_id=project.id,
                is_active=True,
            )
            session.add(warehouse)
            await session.flush()
        else:
            warehouse.name = site["warehouse_name"]
            warehouse.location = site["warehouse_location"]
            warehouse.default_project_id = project.id
            warehouse.is_active = True
            logger.info("Updated existing Warehouse [%s] %s", site["warehouse_code"], warehouse.name)

    await session.commit()


async def print_verification_audit(session: AsyncSession) -> None:
    """
    Audits active projects, active warehouses, and verifies reconciliation invariants.
    """
    logger.info("==================================================")
    logger.info("       OFFICIAL SITES SEEDING VERIFICATION        ")
    logger.info("==================================================")

    # 1. Projects
    p_res = await session.execute(select(Project).order_by(Project.is_active.desc(), Project.code.asc()))
    projects = p_res.scalars().all()
    active_projects = [p for p in projects if p.is_active]
    logger.info("Projects (%d total, %d active):", len(projects), len(active_projects))
    for p in projects:
        status_label = "ACTIVE" if p.is_active else "INACTIVE/ARCHIVED"
        logger.info("  - [%s] %s | Location: %s (%s)", p.code, p.name, p.location, status_label)

    # 2. Warehouses
    w_res = await session.execute(select(Warehouse).order_by(Warehouse.is_active.desc(), Warehouse.code.asc()))
    warehouses = w_res.scalars().all()
    active_warehouses = [w for w in warehouses if w.is_active]
    logger.info("Warehouses (%d total, %d active):", len(warehouses), len(active_warehouses))
    for w in warehouses:
        status_label = "ACTIVE" if w.is_active else "INACTIVE/ARCHIVED"
        logger.info("  - [%s] %s | Location: %s (%s)", w.code, w.name, w.location, status_label)

    # 3. Reconciliation Discrepancy Invariant Check
    disc_res = await session.execute(text("SELECT count(*) FROM vw_reconciliation_discrepancies;"))
    disc_count = disc_res.scalar()
    if disc_count == 0:
        logger.info("Reconciliation View Discrepancies: 0 (Ledger Dual-Write 100%% IN BALANCE)")
    else:
        logger.error("ALERT: %d Discrepancies detected in vw_reconciliation_discrepancies!", disc_count)

    logger.info("==================================================")


async def main():
    settings = get_settings()
    logger.info("Connecting to target database host: %s", settings.DATABASE_URL.split("@")[-1])

    async with AsyncSessionLocal() as session:
        await archive_placeholder_records(session)
        await seed_official_sites(session)
        await print_verification_audit(session)


if __name__ == "__main__":
    asyncio.run(main())
