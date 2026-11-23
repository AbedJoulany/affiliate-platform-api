from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import secrets
from collections.abc import Awaitable, Callable
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
    ForbiddenError,
    NotFoundError,
    ServiceUnavailableError,
    ValidationError,
)
from app.services.recommendations import RecommendationService
from app.services.workspace_settings import WorkspaceSettingsService

logger = logging.getLogger(__name__)

MAX_PRODUCTS = 2
REQUEST_DEADLINE_SECONDS = 180
# Keep the duplicate/uncertain-outcome guard alive beyond the maximum active
# request window.  This is bounded protection, not durable exactly-once billing.
GUARD_TTL_SECONDS = REQUEST_DEADLINE_SECONDS + 60
PUBLISHED_LOOKBACK = timedelta(days=7)

_COMPARE_AND_DELETE_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
end
return 0
"""

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
    idempotency_record: str
    fingerprint_key: str
    fingerprint_owner: str
    started_at: float


class _GenerationDeadlineExceeded(Exception):
    """Internal signal for the total protected execution deadline."""


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
        *,
        authorize_policy: bool = True,
    ) -> AutomationContentPreviewResponse:
        return await self._preview(
            user,
            workspace_id,
            payload,
            authorize_policy=authorize_policy,
        )

    async def preview_for_run(
        self,
        workspace_id: UUID,
        payload: AutomationContentPreviewRequest,
        run_id: UUID,
        *,
        on_selected: Callable[[list[Any]], Awaitable[None]],
        on_generation_started: Callable[[UUID], Awaitable[None]],
        on_generation_succeeded: Callable[[AutomationContentProductResult], Awaitable[None]],
    ) -> AutomationContentPreviewResponse:
        """Internal path for a validated durable run; no synthetic user is used."""
        return await self._preview(
            None,
            workspace_id,
            payload,
            authorize_policy=False,
            run_id=run_id,
            on_selected=on_selected,
            on_generation_started=on_generation_started,
            on_generation_succeeded=on_generation_succeeded,
        )

    async def _preview(
        self,
        user: User | None,
        workspace_id: UUID,
        payload: AutomationContentPreviewRequest,
        *,
        authorize_policy: bool,
        run_id: UUID | None = None,
        on_selected: Callable[[list[Any]], Awaitable[None]] | None = None,
        on_generation_started: Callable[[UUID], Awaitable[None]] | None = None,
        on_generation_succeeded: (
            Callable[[AutomationContentProductResult], Awaitable[None]] | None
        ) = None,
    ) -> AutomationContentPreviewResponse:
        policy_service = AutomationPolicyService(self.session)
        if authorize_policy:
            if user is None:
                raise ForbiddenError()
            await policy_service.get(user, workspace_id)
        elif user is None and run_id is None:
            raise ForbiddenError()
        policy = await self.policies.get_by_workspace_id(workspace_id)
        if policy is None:
            raise NotFoundError(
                "Automation policy not found; save an automation policy before generating"
            )
        if policy.revision != payload.expected_policy_revision:
            raise ConflictError("Automation policy changed; reload before generating")

        settings_service = WorkspaceSettingsService(self.session)
        settings = (
            await settings_service.get(user, str(workspace_id))
            if user is not None
            else await settings_service.get_for_internal_workspace(workspace_id)
        )
        preferences = self._resolve_preferences(policy, settings)
        self._validate_provider_configuration(preferences.provider)

        claim = await self._claim_duplicate_guard(
            user_id=str(user.id) if user is not None else f"automation-run:{run_id}",
            workspace_id=workspace_id,
            policy=policy,
            payload=payload,
            preferences=preferences,
        )
        provider_call_started = False
        try:
            discovery_service = AutomationDiscoveryService(self.session)
            discovery_operation = (
                discovery_service.preview(user, workspace_id)
                if user is not None
                else discovery_service.preview_for_orchestration(workspace_id)
            )
            discovery = await self._await_with_deadline(discovery_operation, claim)
            current_policy = await self._await_with_deadline(
                self.policies.get_by_workspace_id(workspace_id),
                claim,
            )
            if (
                current_policy is None
                or current_policy.revision != payload.expected_policy_revision
            ):
                raise ConflictError("Automation policy changed; reload before generating")

            selected = discovery.selected_products[: min(payload.max_products, MAX_PRODUCTS)]
            if on_selected is not None:
                await self._await_with_deadline(on_selected(selected), claim)
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

                product = await self._await_with_deadline(
                    self.products.get_by_id(selection.product_id),
                    claim,
                )
                eligibility = await self._await_with_deadline(
                    self._revalidate_product(product, workspace_id),
                    claim,
                )
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
                    remaining = self._remaining_seconds(claim)
                    if on_generation_started is not None:
                        await self._await_with_deadline(
                            on_generation_started(product.id),
                            claim,
                        )
                        remaining = self._remaining_seconds(claim)
                    # From this point onward the provider may have received a
                    # billable request even if the caller later times out or
                    # loses the connection.  Keep the bounded guard in that
                    # case rather than permitting an immediate duplicate.
                    provider_call_started = True
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

                generated_result = self._result(
                    product.id,
                    selection.rank,
                    selection.recommendation_score,
                    status="generated",
                    content=generated.content.strip(),
                    affiliate_url=product.affiliate_url,
                    requires_human_review=True,
                    warnings=["Product claims have not been independently verified"],
                )
                results.append(generated_result)
                if on_generation_succeeded is not None:
                    # Persist this product before beginning another potentially
                    # billable provider call, so a later worker crash preserves
                    # already completed work for Queue-only recovery.
                    await self._await_with_deadline(
                        on_generation_succeeded(generated_result),
                        claim,
                    )

            generated_count = sum(item.status == "generated" for item in results)
            response = AutomationContentPreviewResponse(
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
            if not provider_call_started:
                await self._release_guard(claim)
            return response
        except _GenerationDeadlineExceeded as exc:
            if not provider_call_started:
                await self._release_guard(claim)
            raise ServiceUnavailableError(
                "Content generation deadline exceeded before completion"
            ) from exc
        except asyncio.CancelledError:
            if not provider_call_started:
                await self._release_guard(claim)
            raise
        except Exception:
            if not provider_call_started:
                await self._release_guard(claim)
            raise

    @staticmethod
    def _remaining_seconds(claim: _GuardClaim) -> float:
        remaining = REQUEST_DEADLINE_SECONDS - (
            asyncio.get_running_loop().time() - claim.started_at
        )
        if remaining <= 0:
            raise _GenerationDeadlineExceeded
        return remaining

    async def _await_with_deadline(self, awaitable: Any, claim: _GuardClaim) -> Any:
        """Await one protected operation without exceeding the total budget."""
        try:
            remaining = self._remaining_seconds(claim)
        except _GenerationDeadlineExceeded:
            close = getattr(awaitable, "close", None)
            if close is not None:
                close()
            raise
        try:
            return await asyncio.wait_for(
                awaitable,
                timeout=remaining,
            )
        except TimeoutError as exc:
            raise _GenerationDeadlineExceeded from exc

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
        user_id: str,
        workspace_id: UUID,
        policy: AutomationPolicy,
        payload: AutomationContentPreviewRequest,
        preferences: EffectiveContentPreferences,
    ) -> _GuardClaim:
        # The fingerprint deliberately excludes the client idempotency key.
        # It represents the effective generation request, so equivalent
        # requests made with different keys still share the short-lived lock.
        canonical = json.dumps(
            {
                "version": 1,
                "workspace_id": str(workspace_id),
                "user_id": str(user_id),
                "policy_revision": policy.revision,
                "max_products": payload.max_products,
                "provider": preferences.provider.value,
                "language": preferences.language.value,
                "tone": preferences.tone.value,
                "content_type": preferences.content_type.value,
                "length": preferences.length.value,
                "acknowledge_ai_cost": payload.acknowledge_ai_cost,
            },
            separators=(",", ":"),
            sort_keys=True,
        )
        fingerprint = hashlib.sha256(canonical.encode()).hexdigest()
        key_hash = hashlib.sha256(
            f"{workspace_id}:{user_id}:{payload.idempotency_key}".encode()
        ).hexdigest()
        idempotency_key = f"automation:content:idempotency:{key_hash}"
        fingerprint_key = f"automation:content:fingerprint:{fingerprint}"
        fingerprint_owner = secrets.token_hex(16)
        idempotency_record = json.dumps(
            {"fingerprint": fingerprint, "owner": fingerprint_owner},
            separators=(",", ":"),
            sort_keys=True,
        )
        claimed_idempotency = False
        client: Any | None = None
        try:
            client = await get_automation_generation_redis()
            existing = await client.get(idempotency_key)
            if existing is not None:
                self._raise_idempotency_conflict(existing, fingerprint)
            if not await client.set(
                idempotency_key,
                idempotency_record,
                nx=True,
                ex=GUARD_TTL_SECONDS,
            ):
                existing = await client.get(idempotency_key)
                if existing is None:
                    raise ServiceUnavailableError(
                        "Content generation duplicate protection is unavailable"
                    )
                self._raise_idempotency_conflict(existing, fingerprint)
            claimed_idempotency = True
            if not await client.set(
                fingerprint_key,
                fingerprint_owner,
                nx=True,
                ex=GUARD_TTL_SECONDS,
            ):
                await self._compare_and_delete(
                    client,
                    idempotency_key,
                    idempotency_record,
                )
                raise ConflictError(
                    "Equivalent content generation request is already protected"
                )
            return _GuardClaim(
                client,
                idempotency_key,
                idempotency_record,
                fingerprint_key,
                fingerprint_owner,
                asyncio.get_running_loop().time(),
            )
        except ConflictError:
            raise
        except ServiceUnavailableError:
            raise
        except asyncio.CancelledError:
            if claimed_idempotency and client is not None:
                await self._compare_and_delete(
                    client,
                    idempotency_key,
                    idempotency_record,
                )
            raise
        except (RedisError, TimeoutError, OSError, ConnectionError) as exc:
            if claimed_idempotency and client is not None:
                try:
                    await self._compare_and_delete(
                        client,
                        idempotency_key,
                        idempotency_record,
                    )
                except Exception:
                    logger.warning("Failed to clean up content generation guard")
            raise ServiceUnavailableError(
                "Content generation duplicate protection is unavailable"
            ) from exc

    @staticmethod
    async def _compare_and_delete(client: Any, key: str, owner: str) -> bool:
        """Delete a Redis key only when it still belongs to this claim."""
        result = await client.eval(_COMPARE_AND_DELETE_SCRIPT, 1, key, owner)
        return bool(result)

    @staticmethod
    def _raise_idempotency_conflict(existing: str, fingerprint: str) -> None:
        try:
            record = json.loads(existing)
        except (TypeError, ValueError):
            record = None
        if not isinstance(record, dict) or record.get("fingerprint") != fingerprint:
            raise ConflictError("Idempotency key was used with different request parameters")
        raise ConflictError("Duplicate content generation request")

    async def _release_guard(self, claim: _GuardClaim) -> None:
        for key, owner in (
            (claim.idempotency_key, claim.idempotency_record),
            (claim.fingerprint_key, claim.fingerprint_owner),
        ):
            try:
                await self._compare_and_delete(claim.client, key, owner)
            except Exception:
                # Leaving a bounded guard in place is safer than risking
                # deletion of a newer request's ownership record.
                logger.warning("Failed to release content generation duplicate guard")
