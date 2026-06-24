from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.aliexpress.client import AliExpressAffiliateClient
from app.core.database import get_db
from app.services.aliexpress_import import AliExpressImportService


def get_aliexpress_client() -> AliExpressAffiliateClient:
    return AliExpressAffiliateClient()


def get_aliexpress_import_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    client: Annotated[AliExpressAffiliateClient, Depends(get_aliexpress_client)],
) -> AliExpressImportService:
    return AliExpressImportService(db, client)


AliExpressClientDep = Annotated[AliExpressAffiliateClient, Depends(get_aliexpress_client)]
AliExpressImportServiceDep = Annotated[AliExpressImportService, Depends(get_aliexpress_import_service)]
