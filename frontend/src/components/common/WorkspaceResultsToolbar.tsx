"use client";

import type { ReactNode } from "react";
import { RefreshCw, Search } from "lucide-react";
import { Button, Input, Select } from "@/components/ui/primitives";

export type WorkspaceToolbarOption<T extends string | number> = {
  value: T;
  label: string;
};

export function WorkspaceResultsToolbar<
  TSort extends string,
  TDensity extends string = "comfortable" | "compact",
>({
  search,
  onSearchChange,
  searchPlaceholder = "بحث…",
  searchLabel = "البحث",
  countLabel,
  filters,
  sort,
  density,
  columns,
  pageSize,
  refreshing,
  onRefresh,
  actions,
}: {
  search: string;
  onSearchChange: (value: string) => void;
  searchPlaceholder?: string;
  searchLabel?: string;
  countLabel: ReactNode;
  filters?: ReactNode;
  sort?: {
    value: TSort;
    label: string;
    options: ReadonlyArray<WorkspaceToolbarOption<TSort>>;
    onChange: (value: TSort) => void;
  };
  density?: {
    value: TDensity;
    label: string;
    options: ReadonlyArray<WorkspaceToolbarOption<TDensity>>;
    onChange: (value: TDensity) => void;
  };
  columns?: ReactNode;
  pageSize?: {
    value: number;
    options: readonly number[];
    onChange: (value: number) => void;
  };
  refreshing: boolean;
  onRefresh: () => void;
  actions?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-lg border border-border bg-surface p-3">
      <label className="relative min-w-[16rem] flex-1">
        <span className="sr-only">{searchLabel}</span>
        <Search
          className="pointer-events-none absolute start-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
          aria-hidden
        />
        <Input
          className="ps-9"
          value={search}
          onChange={(event) => onSearchChange(event.target.value)}
          placeholder={searchPlaceholder}
        />
      </label>

      <span className="text-sm font-medium tabular-nums">{countLabel}</span>
      {filters}

      {sort ? (
        <Select
          className="w-auto"
          aria-label={sort.label}
          value={sort.value}
          onChange={(event) => sort.onChange(event.target.value as TSort)}
        >
          {sort.options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </Select>
      ) : null}

      {density ? (
        <Select
          className="w-auto"
          aria-label={density.label}
          value={density.value}
          onChange={(event) => density.onChange(event.target.value as TDensity)}
        >
          {density.options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </Select>
      ) : null}

      {columns}

      {pageSize ? (
        <Select
          className="w-auto"
          aria-label="حجم الصفحة"
          value={String(pageSize.value)}
          onChange={(event) => pageSize.onChange(Number(event.target.value))}
        >
          {pageSize.options.map((size) => (
            <option key={size} value={size}>
              {size} / صفحة
            </option>
          ))}
        </Select>
      ) : null}

      <Button
        type="button"
        variant="outline"
        className="px-3"
        loading={refreshing}
        onClick={onRefresh}
        aria-label="تحديث النتائج"
      >
        <RefreshCw className="size-4" />
      </Button>
      {actions}
    </div>
  );
}
