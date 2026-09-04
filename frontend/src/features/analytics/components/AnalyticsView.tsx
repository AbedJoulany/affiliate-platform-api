"use client";

import { useMemo, useState } from "react";
import {
  EmptyState,
  ErrorState,
  LoadingState,
  NoActiveWorkspaceState,
} from "@/components/common/states";
import { PageContainer, PageHeader } from "@/components/layout/page";
import { Input, Select } from "@/components/ui/primitives";
import { getApiErrorMessage } from "@/services/api-client";
import { useActiveWorkspaceId } from "@/lib/workspace";
import { AnalyticsOverviewCards } from "./AnalyticsOverviewCards";
import { CampaignFunnelChart } from "./CampaignFunnelChart";
import { ClickConversionChart } from "./ClickConversionChart";
import {
  useActiveCampaigns,
  useAnalyticsOverview,
  useCampaignFunnel,
} from "../hooks/useAnalytics";
import { defaultAnalyticsRange, rangeToQuery } from "../lib/range";

export function AnalyticsView() {
  const workspaceId = useActiveWorkspaceId();
  const initial = useMemo(() => defaultAnalyticsRange(), []);
  const [fromDate, setFromDate] = useState(initial.fromDate);
  const [toDate, setToDate] = useState(initial.toDate);
  const [campaignId, setCampaignId] = useState("");
  const range = useMemo(() => rangeToQuery(fromDate, toDate), [fromDate, toDate]);
  const overview = useAnalyticsOverview(range);
  const campaigns = useActiveCampaigns();
  const funnel = useCampaignFunnel(campaignId || null, range);

  if (!workspaceId) {
    return (
      <PageContainer>
        <PageHeader title="التحليلات" description="نقرات وتحويلات مساحة العمل النشطة." />
        <NoActiveWorkspaceState />
      </PageContainer>
    );
  }

  return (
    <PageContainer>
      <PageHeader
        title="التحليلات"
        description="مؤشرات النقرات والتحويلات للحملات داخل مساحة العمل الحالية."
        actions={
          <div className="flex flex-wrap items-end gap-2">
            <label className="text-sm">
              من
              <Input
                className="mt-1 w-40"
                dir="ltr"
                type="date"
                value={fromDate}
                onChange={(event) => setFromDate(event.target.value)}
              />
            </label>
            <label className="text-sm">
              إلى
              <Input
                className="mt-1 w-40"
                dir="ltr"
                type="date"
                value={toDate}
                onChange={(event) => setToDate(event.target.value)}
              />
            </label>
          </div>
        }
      />

      {overview.isPending ? (
        <LoadingState rows={6} />
      ) : overview.isError ? (
        <ErrorState
          message={getApiErrorMessage(overview.error, "تعذر تحميل التحليلات.")}
          onRetry={() => void overview.refetch()}
        />
      ) : overview.data.total_clicks === 0 && overview.data.total_conversions === 0 ? (
        <EmptyState
          title="لا توجد بيانات في هذا النطاق"
          description="لم تُسجَّل نقرات أو تحويلات للحملات في مساحة العمل خلال الفترة المحددة."
        />
      ) : (
        <div className="space-y-6">
          <AnalyticsOverviewCards overview={overview.data} />
          <ClickConversionChart series={overview.data.by_day} />
        </div>
      )}

      <section className="mt-8 space-y-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <h2 className="font-semibold">قمع الحملة</h2>
          <label className="text-sm sm:w-72">
            الحملة النشطة
            <Select
              className="mt-1"
              value={campaignId}
              onChange={(event) => setCampaignId(event.target.value)}
              aria-label="اختيار حملة"
            >
              <option value="">اختر حملة</option>
              {(campaigns.data ?? []).map((campaign) => (
                <option key={campaign.id} value={campaign.id}>
                  {campaign.name}
                </option>
              ))}
            </Select>
          </label>
        </div>
        {!campaignId ? (
          <EmptyState
            title="لم تُحدَّد حملة"
            description="اختر حملة نشطة لعرض قمع النقرات إلى التحويلات."
          />
        ) : funnel.isPending ? (
          <LoadingState rows={4} />
        ) : funnel.isError ? (
          <ErrorState
            message={getApiErrorMessage(funnel.error, "تعذر تحميل قمع الحملة.")}
            onRetry={() => void funnel.refetch()}
          />
        ) : (
          <CampaignFunnelChart funnel={funnel.data} />
        )}
      </section>
    </PageContainer>
  );
}
