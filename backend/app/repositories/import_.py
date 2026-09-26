# backend/app/repositories/import_.py
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.category import Category
from app.models.import_ import ImportBatch, ImportError
from app.models.item import Item
from app.models.project import Project
from app.models.warehouse import Warehouse


class ImportRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_batch(self, batch: ImportBatch) -> ImportBatch:
        """Persists a new import batch header."""
        self.session.add(batch)
        return batch

    async def get_batch_by_id(self, batch_id: uuid.UUID) -> Optional[ImportBatch]:
        """Loads an import batch by primary key ID."""
        stmt = select(ImportBatch).where(ImportBatch.id == batch_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_errors(self, errors: List[ImportError]) -> List[ImportError]:
        """Persists a list of import row errors."""
        self.session.add_all(errors)
        return errors

    async def get_errors_by_batch_id(self, batch_id: uuid.UUID) -> List[ImportError]:
        """Retrieves all row errors for an import batch ordered by row number."""
        stmt = (
            select(ImportError)
            .where(ImportError.batch_id == batch_id)
            .order_by(ImportError.row_number)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update_batch(self, batch: ImportBatch) -> ImportBatch:
        """Updates an import batch."""
        self.session.add(batch)
        return batch

    async def bulk_create_items(self, items: List[Item]) -> List[Item]:
        """Bulk persists new items into the items catalog."""
        self.session.add_all(items)
        return items

    async def get_all_categories(self) -> Dict[str, Category]:
        """
        Retrieves active categories mapped by uppercase code and uppercase name
        to facilitate flexible spreadsheet matching.
        """
        stmt = select(Category).where(Category.is_active == True)
        result = await self.session.execute(stmt)
        categories = result.scalars().all()
        mapping: Dict[str, Category] = {}
        for cat in categories:
            if cat.code:
                mapping[cat.code.strip().upper()] = cat
            if cat.name:
                mapping[cat.name.strip().upper()] = cat
        return mapping

    async def get_existing_item_codes(self, codes: List[str]) -> Set[str]:
        """Finds existing item codes in the database to prevent duplicate key collisions."""
        if not codes:
            return set()
        stmt = select(Item.item_code).where(Item.item_code.in_(codes))
        result = await self.session.execute(stmt)
        return set(result.scalars().all())

    async def create_audit_log(
        self,
        actor_user_id: Optional[uuid.UUID],
        action: str,
        entity_type: str,
        entity_id: str,
        before_state: Optional[dict] = None,
        after_state: Optional[dict] = None,
        change_summary: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> AuditLog:
        """Records an audit event in audit_logs."""
        audit_log = AuditLog(
            id=uuid.uuid4(),
            actor_user_id=actor_user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            before_state=before_state,
            after_state=after_state,
            change_summary=change_summary,
            reason=reason,
            created_at=datetime.now(timezone.utc),
        )
        self.session.add(audit_log)
        return audit_log

    async def get_warehouse_by_code(self, code: str) -> Optional[Warehouse]:
        """Looks up a warehouse by code."""
        stmt = select(Warehouse).where(Warehouse.code == code)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_item_by_code(self, code: str) -> Optional[Item]:
        """Looks up an item by code."""
        stmt = select(Item).where(Item.item_code == code)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_project_by_code(self, code: str) -> Optional[Project]:
        """Looks up a project by code."""
        stmt = select(Project).where(Project.code == code)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_warehouses_by_codes(self, codes: List[str]) -> Dict[str, Warehouse]:
        """Retrieves warehouses mapped by uppercase code."""
        if not codes:
            return {}
        stmt = select(Warehouse).where(Warehouse.code.in_(codes))
        result = await self.session.execute(stmt)
        return {w.code.strip().upper(): w for w in result.scalars().all()}

    async def get_items_by_codes(self, codes: List[str]) -> Dict[str, Item]:
        """Retrieves items mapped by uppercase item_code."""
        if not codes:
            return {}
        stmt = select(Item).where(Item.item_code.in_(codes))
        result = await self.session.execute(stmt)
        return {i.item_code.strip().upper(): i for i in result.scalars().all()}

    async def get_projects_by_codes(self, codes: List[str]) -> Dict[str, Project]:
        """Retrieves projects mapped by uppercase code."""
        if not codes:
            return {}
        stmt = select(Project).where(Project.code.in_(codes))
        result = await self.session.execute(stmt)
        return {p.code.strip().upper(): p for p in result.scalars().all()}
