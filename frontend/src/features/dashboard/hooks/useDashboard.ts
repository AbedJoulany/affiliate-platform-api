"use client";

import { useQuery } from "@tanstack/react-query";
import { getDashboardOverview } from "../api/dashboard.api";

export function useDashboard() {
  return useQuery({ queryKey: ["dashboard"], queryFn: getDashboardOverview, retry: false });
}
