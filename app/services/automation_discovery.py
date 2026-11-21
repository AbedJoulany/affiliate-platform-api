from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.enums import UserRole
from app.models.automation_policy import AutomationPolicy
from app.repositories.automation_policy import AutomationPolicyRepository
from app.repositories.product import ProductRepository
from app.repositories.queue import ProductPublishingHistory, QueueRepository
from app.repositories.workspace import (
    WorkspaceMembershipRepository,
    WorkspaceRepository,
)
from app.schemas.automation_discovery import (
    AutomationDiscoveryExcludedCounts,
    AutomationDiscoveryPreviewResponse,
    AutomationDiscoverySelectedProduct,
)
from app.schemas.recommendations import RecommendationQuery
from app.services.automation_policy import AutomationPolicyService
from app.services.exceptions import ForbiddenError, NotFoundError
from app.services.recommendations import RecommendationService


class AutomationDiscoveryService:
    """Read-only catalog selection for a manual automation preview.

    This service deliberately does not create runs, queue items, or publishing
    attempts. It evaluates the saved policy against a bounded snapshot of the
    global Product catalog while applying workspace-specific publishing history
    exclusions.
    """

    CANDIDATE_CAP = 1000
    PROBE_LIMIT = CANDIDATE_CAP + 1
    PUBLISHED_LOOKBACK = timedelta(days=7)

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.policies = AutomationPolicyRepository(session)
        self.products = ProductRepository(session)
        self.queues = QueueRepository(session)
        self.memberships = WorkspaceMembershipRepository(session)
        self.workspaces = WorkspaceRepository(session)

    async def preview(
        self,
        user: User,
        workspace_id: UUID,
    ) -> AutomationDiscoveryPreviewResponse:
        await self._authorize(user, workspace_id)
        policy = await self.policies.get_by_workspace_id(workspace_id)
        if policy is None:
            raise NotFoundError(
                "Automation policy not found; save an automation policy before previewing"
            )

        # Reuse the policy service's destination-readiness semantics without
        # invoking any provider API or changing the policy.
        policy_read = await AutomationPolicyService(self.session).get(user, workspace_id)
        query = self._recommendation_query(policy)
        selection_timestamp = datetime.now(UTC)
        candidates_with_probe = await self.products.list_active_recommendation_candidates(
            min_price=query.min_price,
            max_price=query.max_price,
            min_rating=query.min_rating,
            min_orders=query.min_orders,
            min_discount=query.min_discount,
            min_commission=query.min_commission,
            max_commission=query.max_commission,
            limit=self.PROBE_LIMIT,
        )
        truncated = len(candidates_with_probe) > self.CANDIDATE_CAP
        candidates = candidates_with_probe[: self.CANDIDATE_CAP]
        history = await self.queues.product_publishing_history(
            workspace_id,
            [product.id for product in candidates],
            now=selection_timestamp,
            recent_window_start=selection_timestamp - self.PUBLISHED_LOOKBACK,
        )

        eligible, excluded = self._exclude_candidates(candidates, history)
        recommendation_service = RecommendationService(self.session)
        ranked = recommendation_service.rank_candidates(eligible, query)
        excluded.keyword_mismatch = len(eligible) - len(ranked)
        selected = ranked[: query.top_n]

        warnings = list(policy_read.warnings)
        if not policy.enabled:
            warnings.append("Policy is disabled; this response is a preview only")
        elif not policy_read.configuration_ready:
            warnings.append(
                "Policy is not configuration-ready; this response is a preview only"
            )
        if truncated:
            warnings.append(
                "Candidate cap reached; ranking covers the inspected catalog slice only"
            )

        return AutomationDiscoveryPreviewResponse(
            workspace_id=workspace_id,
            policy_id=policy.id,
            policy_revision=policy.revision,
            policy_enabled=policy.enabled,
            configuration_ready=policy_read.configuration_ready,
            selection_timestamp=selection_timestamp,
            truncated=truncated,
            candidates_inspected=len(candidates),
            eligible_count=len(ranked),
            selected_count=len(selected),
            selected_products=[
                AutomationDiscoverySelectedProduct(
                    product_id=item.product.id,
                    rank=index,
                    recommendation_score=item.score.total,
                )
                for index, item in enumerate(selected, start=1)
            ],
            excluded_counts=excluded,
            warnings=warnings,
        )

    async def _authorize(self, user: User, workspace_id: UUID) -> None:
        if await self.workspaces.get_by_id(workspace_id) is None:
            raise ForbiddenError()
        if user.role == UserRole.ADMIN:
            return
        if await self.memberships.get_membership(workspace_id, user.id) is None:
            raise ForbiddenError()

    @staticmethod
    def _recommendation_query(policy: AutomationPolicy) -> RecommendationQuery:
        return RecommendationQuery(
            keywords=policy.keywords,
            min_price=policy.min_price,
            max_price=policy.max_price,
            min_rating=policy.min_rating,
            min_orders=policy.min_orders,
            min_discount=policy.min_discount,
            min_commission=policy.min_commission,
            max_commission=policy.max_commission,
            top_n=policy.products_per_run,
        )

    @staticmethod
    def _exclude_candidates(
        candidates: list,
        history: ProductPublishingHistory,
    ) -> tuple[list, AutomationDiscoveryExcludedCounts]:
        counts = AutomationDiscoveryExcludedCounts()
        eligible = []
        for product in candidates:
            # Safety exclusions have precedence so each inspected product is
            # counted once and an ambiguous outcome is never hidden by another
            # reason.
            if product.id in history.unresolved_ambiguous:
                counts.unresolved_ambiguous += 1
            elif product.id in history.queued_or_scheduled:
                counts.queued_or_scheduled += 1
            elif product.id in history.recently_published:
                counts.recently_published += 1
            elif not RecommendationService.has_valid_affiliate_url(product.affiliate_url):
                counts.missing_affiliate_url += 1
            else:
                eligible.append(product)
        return eligible, counts
