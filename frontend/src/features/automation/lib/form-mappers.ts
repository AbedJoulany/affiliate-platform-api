import type {
  AutomationContent,
  AutomationContentPatch,
  AutomationDiscovery,
  AutomationDiscoveryPatch,
  AutomationPolicy,
  AutomationPolicyPatch,
  AutomationSchedule,
} from "../types/api";
import type { AutomationFormValues } from "./schemas";

function text(value: string | number | null | undefined): string {
  return value === null || value === undefined ? "" : String(value);
}

export function toAutomationFormValues(policy: AutomationPolicy): AutomationFormValues {
  return {
    enabled: policy.enabled,
    destination_provider: policy.destination?.provider ?? "",
    destination_id:
      policy.destination?.provider === "telegram"
        ? policy.destination.channel_id ?? ""
        : policy.destination?.page_id ?? "",
    keywords: policy.discovery.keywords ?? "",
    min_price: text(policy.discovery.min_price),
    max_price: text(policy.discovery.max_price),
    min_rating: text(policy.discovery.min_rating),
    min_orders: text(policy.discovery.min_orders),
    min_discount: text(policy.discovery.min_discount),
    min_commission: text(policy.discovery.min_commission),
    max_commission: text(policy.discovery.max_commission),
    products_per_run: policy.discovery.products_per_run,
    frequency: policy.schedule.frequency,
    preferred_time_local: policy.schedule.preferred_time_local,
    posts_per_day: policy.schedule.posts_per_day,
    ai_provider: policy.content.ai_provider ?? "",
    language: policy.content.language ?? "",
    tone: policy.content.tone ?? "",
    content_type: policy.content.content_type ?? "",
    length: policy.content.length ?? "",
  };
}

function optionalText(value: string): string | null {
  const trimmed = value.trim();
  return trimmed === "" ? null : trimmed;
}

function changed<T>(current: T, initial: T): boolean {
  return current !== initial;
}

function initialFormValue(policy: AutomationPolicy): AutomationFormValues {
  return toAutomationFormValues(policy);
}

function buildDiscoveryPatch(
  values: AutomationFormValues,
  initial: AutomationDiscovery,
): AutomationDiscoveryPatch {
  const initialValues = {
    keywords: initial.keywords ?? "",
    min_price: text(initial.min_price),
    max_price: text(initial.max_price),
    min_rating: text(initial.min_rating),
    min_orders: text(initial.min_orders),
    min_discount: text(initial.min_discount),
    min_commission: text(initial.min_commission),
    max_commission: text(initial.max_commission),
    products_per_run: initial.products_per_run,
  };
  const patch: AutomationDiscoveryPatch = {};
  if (changed(values.keywords, initialValues.keywords)) patch.keywords = optionalText(values.keywords);
  for (const [key, value] of [
    ["min_price", values.min_price],
    ["max_price", values.max_price],
    ["min_rating", values.min_rating],
    ["min_discount", values.min_discount],
    ["min_commission", values.min_commission],
    ["max_commission", values.max_commission],
  ] as const) {
    if (changed(value, initialValues[key])) patch[key] = optionalText(value);
  }
  if (changed(values.min_orders, initialValues.min_orders)) {
    patch.min_orders = values.min_orders === "" ? null : Number(values.min_orders);
  }
  if (changed(values.products_per_run, initialValues.products_per_run)) {
    patch.products_per_run = values.products_per_run;
  }
  return patch;
}

function buildSchedulePatch(
  values: AutomationFormValues,
  initial: AutomationSchedule,
) {
  const patch: { frequency?: "daily"; preferred_time_local?: string; posts_per_day?: number } = {};
  if (values.frequency !== initial.frequency) patch.frequency = values.frequency;
  if (values.preferred_time_local !== initial.preferred_time_local) {
    patch.preferred_time_local = values.preferred_time_local;
  }
  if (values.posts_per_day !== initial.posts_per_day) patch.posts_per_day = values.posts_per_day;
  return patch;
}

function buildContentPatch(
  values: AutomationFormValues,
  initial: AutomationContent,
): AutomationContentPatch {
  const patch: AutomationContentPatch = {};
  const initialValues = {
    ai_provider: initial.ai_provider ?? "",
    language: initial.language ?? "",
    tone: initial.tone ?? "",
    content_type: initial.content_type ?? "",
    length: initial.length ?? "",
  };
  for (const key of ["ai_provider", "language", "tone", "content_type", "length"] as const) {
    if (values[key] !== initialValues[key]) {
      patch[key === "language" ? "language" : key] = optionalText(values[key]) as never;
    }
  }
  return patch;
}

export function buildAutomationPatch(
  values: AutomationFormValues,
  initial: AutomationPolicy,
): AutomationPolicyPatch {
  const patch: AutomationPolicyPatch = { expected_revision: initial.revision };
  const initialValues = initialFormValue(initial);
  if (values.enabled !== initialValues.enabled) patch.enabled = values.enabled;

  if (
    values.destination_provider !== initialValues.destination_provider ||
    values.destination_id !== initialValues.destination_id
  ) {
    if (!values.destination_provider || !values.destination_id) {
      patch.destination = null;
    } else if (values.destination_provider === "telegram") {
      patch.destination = { provider: "telegram", channel_id: values.destination_id };
    } else {
      patch.destination = { provider: "facebook", page_id: values.destination_id };
    }
  }

  const discovery = buildDiscoveryPatch(values, initial.discovery);
  if (Object.keys(discovery).length > 0) patch.discovery = discovery;
  const schedule = buildSchedulePatch(values, initial.schedule);
  if (Object.keys(schedule).length > 0) patch.schedule = schedule;
  const content = buildContentPatch(values, initial.content);
  if (Object.keys(content).length > 0) patch.content = content;
  return patch;
}
