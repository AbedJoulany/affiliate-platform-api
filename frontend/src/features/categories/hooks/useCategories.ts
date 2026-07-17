"use client";

import { useQuery } from "@tanstack/react-query";
import { getCategories, getPlatformReadiness } from "../api/categories.api";

export function useCategories() {
  return useQuery({ queryKey: ["categories"], queryFn: getCategories, retry: false });
}

export function usePlatformReadiness() {
  return useQuery({ queryKey: ["readiness"], queryFn: getPlatformReadiness, retry: false });
}
