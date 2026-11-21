from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from redis import asyncio as redis
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.content_validation import validate_generated_content
from app.ai.factory import get_ai_provider
from app.auth.models import User
from app.core.config import get_settings
from app.core.enums import (
    AIProviderType,
    ContentLanguage,
    ContentLength,
    ContentType,
    ProductStatus,
    ToneProfile,
)
from app.models.automation_policy import AutomationPolicy
from app.models.product import Product
from app.repositories.automation_policy import AutomationPolicyRepository
from app.repositories.product import ProductRepository
from app.repositories.queue import ProductPublishingHistory, QueueRepository
from app.schemas.automation_content import (
    AutomationContentPreviewRequest,
    AutomationContentPreviewResponse,
    AutomationContentProductResult,
)
from app.services.ai_content import AIContentService
from app.services.automation_discovery import AutomationDiscoveryService
from app.services.automation_policy import AutomationPolicyService
from app.services.exceptions import (
    AIProviderError,
    ConflictError,
    NotFoundError,
    ServiceUnavailableError,
    ValidationError,
)
from app.services.recommendations import RecommendationService
from app.services.workspace_settings import WorkspaceSettingsService

logger = logging.getLogger(__name__)

MAX_PRODUCTS = 2
GUARD_TTL_SECONDS = 180
REQUEST_DEADLINE_SECONDS = 180
PUBLISHED_LOOKBACK = timedelta(days=7)

_generation_redis: Any | None = None


async def get_automation_generation_redis() -> Any:
    global _generation_redis
    if _generation_redis is None:
        settings = get_settings()
        _generation_redis = redis.from_url(
            settings.broker_url,
            socket_connect_timeout=1.0,
            socket_timeout=1.0,
            decode_responses=True,
        )
    return _generation_redis


@dataclass(frozen=True, slots=True)
class EffectiveContentPreferences:
    provider: AIProviderType
    language: ContentLanguage
    tone: ToneProfile
    content_type: ContentType
    length: ContentLength


@dataclass(frozen=True, slots=True)
class _GuardClaim:
    client: Any
    idempotency_key: str
    fingerprint_key: str
    fingerprint: str
    started_at: float


class AutomationContentGenerationService:
    """Explicit, stateless, non-publishing automation content preview."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.policies = AutomationPolicyRepository(session)
        self.products = ProductRepository(session)
        self.queues = QueueRepository(session)
        self.ai = AIContentService(session)

    async def preview(
        self,
        user: User,
        workspace_id: UUID,
        payload: AutomationContentPreviewRequest,
    ) -> AutomationContentPreviewResponse:
        policy_service = AutomationPolicyService(self.session)
        await policy_service.get(user, workspace_id)
        policy = await self.policies.get_by_workspace_id(workspace_id)
        if policy is None:
            raise NotFoundError(
                "Automation policy not found; save an automation policy before generating"
            )
        if policy.revision != payload.expected_policy_revision:
            raise ConflictError("Automation policy changed; reload before generating")

        settings = await WorkspaceSettingsService(self.session).get(user, str(workspace_id))
        preferences = self._resolve_preferences(policy, settings)
        self._validate_provider_configuration(preferences.provider)

        claim = await self._claim_duplicate_guard(
            user_id=user.id,
            workspace_id=workspace_id,
            policy=policy,
            payload=payload,
            preferences=preferences,
        )
        try:
            discovery = await AutomationDiscoveryService(self.session).preview(user, workspace_id)
            current_policy = await self.policies.get_by_workspace_id(workspace_id)
            if (
                current_policy is None
                or current_policy.revision != payload.expected_policy_revision
            ):
                raise ConflictError("Automation policy changed; reload before generating")

            selected = discovery.selected_products[: min(payload.max_products, MAX_PRODUCTS)]
            results: list[AutomationContentProductResult] = []
            warnings = [
                "This preview may incur AI provider charges.",
                "Generated product claims require human review and are not independently verified.",
            ]
            warnings.extend(discovery.warnings)
            provider_failure = False

            for selection in selected:
                if provider_failure:
                    results.append(
                        self._result(
                            selection.product_id,
                            selection.rank,
                            selection.recommendation_score,
                            status="skipped_after_global_failure",
                            error_category="provider_unavailable",
                        )
                    )
                    continue

                product = await self.products.get_by_id(selection.product_id)
                eligibility = await self._revalidate_product(product, workspace_id)
                if eligibility is not None:
                    results.append(
                        self._result(
                            selection.product_id,
                            selection.rank,
                            selection.recommendation_score,
                            status=eligibility[0],
                            error_category=eligibility[1],
                        )
                    )
                    continue

                try:
                    remaining = REQUEST_DEADLINE_SECONDS - (
                        asyncio.get_running_loop().time() - claim.started_at
                    )
                    if remaining <= 0:
                        raise TimeoutError
                    generated = await asyncio.wait_for(
                        self.ai.generate_for_product(
                            product,
                            provider=preferences.provider,
                            content_type=preferences.content_type,
                            tone=preferences.tone,
                            language=preferences.language,
                            length=preferences.length,
                        ),
                        timeout=remaining,
                    )
                except TimeoutError:
                    results.append(
                        self._result(
                            product.id,
                            selection.rank,
                            selection.recommendation_score,
                            status="failed_timeout",
                            error_category="provider_timeout",
                        )
                    )
                    provider_failure = True
                    continue
                except AIProviderError as exc:
                    category = getattr(exc, "category", "provider_error")
                    results.append(
                        self._result(
                            product.id,
                            selection.rank,
                            selection.recommendation_score,
                            status="failed_provider",
                            error_category=category,
                        )
                    )
                    provider_failure = category in {
                        "provider_authentication_error",
                        "provider_rate_limited",
                        "provider_unavailable",
                    }
                    continue
                except ValidationError:
                    results.append(
                        self._result(
                            product.id,
                            selection.rank,
                            selection.recommendation_score,
                            status="failed_configuration",
                            error_category="provider_configuration_error",
                        )
                    )
                    provider_failure = True
                    continue
                except Exception:
                    logger.exception(
                        "Automation content generation failed product_id=%s provider=%s",
                        product.id,
                        preferences.provider.value,
                    )
                    results.append(
                        self._result(
                            product.id,
                            selection.rank,
                            selection.recommendation_score,
                            status="failed_provider",
                            error_category="unexpected_generation_error",
                        )
                    )
                    continue

                failures = validate_generated_content(generated.content, preferences.content_type)
                if failures:
                    results.append(
                        self._result(
                            product.id,
                            selection.rank,
                            selection.recommendation_score,
                            status="failed_validation",
                            error_category="content_validation_failed",
                            warnings=failures,
                        )
                    )
                    continue

                results.append(
                    self._result(
                        product.id,
                        selection.rank,
                        selection.recommendation_score,
                        status="generated",
                        content=generated.content.strip(),
                        affiliate_url=product.affiliate_url,
                        requires_human_review=True,
                        warnings=["Product claims have not been independently verified"],
                    )
                )

            generated_count = sum(item.status == "generated" for item in results)
            return AutomationContentPreviewResponse(
                workspace_id=workspace_id,
                policy_id=policy.id,
                policy_revision=payload.expected_policy_revision,
                generated_at=datetime.now(UTC),
                requested_max_products=payload.max_products,
                selected_count=len(selected),
                generated_count=generated_count,
                failed_count=len(results) - generated_count,
                provider=preferences.provider,
                results=results,
                warnings=warnings,
            )
        except asyncio.CancelledError:
            await self._release_guard(claim)
            raise
        except Exception:
            await self._release_guard(claim)
            raise

    async def _revalidate_product(
        self,
        product: Product | None,
        workspace_id: UUID,
    ) -> tuple[str, str] | None:
        if product is None:
            return "failed_not_found", "product_not_found"
        if product.status != ProductStatus.ACTIVE:
            return "skipped_ineligible", "product_inactive"
        if not RecommendationService.has_valid_affiliate_url(product.affiliate_url):
            return "skipped_ineligible", "missing_affiliate_url"
        now = datetime.now(UTC)
        history: ProductPublishingHistory = await self.queues.product_publishing_history(
            workspace_id,
            [product.id],
            now=now,
            recent_window_start=now - PUBLISHED_LOOKBACK,
        )
        if (
            product.id in history.queued_or_scheduled
            or product.id in history.recently_published
            or product.id in history.unresolved_ambiguous
        ):
            return "skipped_ineligible", "history_exclusion"
        return None

    @staticmethod
    def _resolve_preferences(
        policy: AutomationPolicy,
        settings: Any,
    ) -> EffectiveContentPreferences:
        try:
            return EffectiveContentPreferences(
                provider=AIProviderType(
                    policy.ai_provider or settings.default_ai_provider.value
                ),
                language=ContentLanguage(
                    policy.content_language or settings.default_content_language.value
                ),
                tone=ToneProfile(policy.tone or settings.default_tone.value),
                content_type=ContentType(
                    policy.content_type or settings.default_content_type.value
                ),
                length=ContentLength(
                    policy.content_length or settings.default_content_length.value
                ),
            )
        except ValueError as exc:
            raise ValidationError("Automation content preferences are invalid") from exc

    @staticmethod
    def _validate_provider_configuration(provider: AIProviderType) -> None:
        try:
            instance = get_ai_provider(provider)
        except ValidationError as exc:
            raise ValidationError("Selected AI provider is not configured") from exc
        if not instance.is_configured:
            raise ValidationError("Selected AI provider is not configured")

    @staticmethod
    def _result(
        product_id: UUID,
        rank: int,
        score: Any,
        **values: Any,
    ) -> AutomationContentProductResult:
        return AutomationContentProductResult(
            product_id=product_id,
            selection_rank=rank,
            recommendation_score=float(score) if score is not None else None,
            **values,
        )

    async def _claim_duplicate_guard(
        self,
        *,
        user_id: UUID,
        workspace_id: UUID,
        policy: AutomationPolicy,
        payload: AutomationContentPreviewRequest,
        preferences: EffectiveContentPreferences,
    ) -> _GuardClaim:
        canonical = json.dumps(
            {
                "workspace_id": str(workspace_id),
                "user_id": str(user_id),
                "policy_revision": policy.revision,
                "max_products": payload.max_products,
                "provider": preferences.provider.value,
                "idempotency_key": payload.idempotency_key,
            },
            sort_keys=True,
        )
        fingerprint = hashlib.sha256(canonical.encode()).hexdigest()
        key_hash = hashlib.sha256(
            f"{workspace_id}:{user_id}:{payload.idempotency_key}".encode()
        ).hexdigest()
        idempotency_key = f"automation:content:idempotency:{key_hash}"
        fingerprint_key = f"automation:content:fingerprint:{fingerprint}"
        claimed_idempotency = False
        try:
            client = await get_automation_generation_redis()
            existing = await client.get(idempotency_key)
            if existing is not None and existing != fingerprint:
                raise ConflictError("Idempotency key was used with different request parameters")
            if existing is not None:
                raise ConflictError("Duplicate content generation request")
            if not await client.set(
                idempotency_key,
                fingerprint,
                nx=True,
                ex=GUARD_TTL_SECONDS,
            ):
                raise ConflictError("Duplicate content generation request")
            claimed_idempotency = True
            if not await client.set(
                fingerprint_key,
                fingerprint,
                nx=True,
                ex=GUARD_TTL_SECONDS,
            ):
                await client.delete(idempotency_key)
                raise ConflictError("Duplicate content generation request")
            return _GuardClaim(
                client,
                idempotency_key,
                fingerprint_key,
                fingerprint,
                asyncio.get_running_loop().time(),
            )
        except ConflictError:
            raise
        except (RedisError, TimeoutError, OSError, ConnectionError) as exc:
            if claimed_idempotency:
                try:
                    await client.delete(idempotency_key)
                except Exception:
                    logger.warning("Failed to clean up content generation guard")
            raise ServiceUnavailableError(
                "Content generation duplicate protection is unavailable"
            ) from exc

    async def _release_guard(self, claim: _GuardClaim) -> None:
        try:
            if await claim.client.get(claim.idempotency_key) == claim.fingerprint:
                await claim.client.delete(claim.idempotency_key)
            if await claim.client.get(claim.fingerprint_key) == claim.fingerprint:
                await claim.client.delete(claim.fingerprint_key)
        except Exception:
            logger.warning("Failed to release content generation duplicate guard")
