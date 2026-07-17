from app.aliexpress.client import AliExpressAffiliateClient
from app.core.database import get_async_session_maker
from app.services.product_discovery_persistence import ProductDiscoveryPersistenceService
from app.worker.async_utils import run_async
from app.worker.celery_app import celery_app


async def _refresh_hot_products() -> dict:
    session_maker = get_async_session_maker()
    client = AliExpressAffiliateClient()

    async with session_maker() as session:
        service = ProductDiscoveryPersistenceService(session, client)
        result = await service.refresh_hot_products()
        await session.commit()
    return result


async def _refresh_trending_products() -> dict:
    session_maker = get_async_session_maker()
    client = AliExpressAffiliateClient()

    async with session_maker() as session:
        service = ProductDiscoveryPersistenceService(session, client)
        result = await service.refresh_trending_products()
        await session.commit()
    return result


async def _refresh_categories() -> dict:
    session_maker = get_async_session_maker()
    client = AliExpressAffiliateClient()

    async with session_maker() as session:
        service = ProductDiscoveryPersistenceService(session, client)
        result = await service.refresh_categories()
        await session.commit()
    return result


@celery_app.task(name="app.worker.tasks.discovery.refresh_hot_products")
def refresh_hot_products() -> dict:
    return run_async(_refresh_hot_products())


@celery_app.task(name="app.worker.tasks.discovery.refresh_trending_products")
def refresh_trending_products() -> dict:
    return run_async(_refresh_trending_products())


@celery_app.task(name="app.worker.tasks.discovery.refresh_categories")
def refresh_categories() -> dict:
    return run_async(_refresh_categories())
