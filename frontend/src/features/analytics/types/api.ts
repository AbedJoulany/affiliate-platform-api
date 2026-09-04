export interface AnalyticsDayPoint {
  date: string;
  clicks: number;
  conversions: number;
}

export interface AnalyticsOverview {
  from: string;
  to: string;
  total_clicks: number;
  total_conversions: number;
  conversion_rate: number;
  total_revenue: string | number;
  by_day: AnalyticsDayPoint[];
}

export interface AnalyticsCampaignFunnel {
  campaign_id: string;
  campaign_name: string;
  from: string;
  to: string;
  total_clicks: number;
  total_conversions: number;
  attributed_conversions: number;
  conversion_rate: number;
  total_revenue: string | number;
  by_day: AnalyticsDayPoint[];
}

export interface AnalyticsRange {
  from: string;
  to: string;
}

export interface CampaignOption {
  id: string;
  name: string;
  status: string;
}
