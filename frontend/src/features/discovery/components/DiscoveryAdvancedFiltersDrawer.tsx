"use client";

import type { ReactNode } from "react";
import { Button, Drawer, Input, Select } from "@/components/ui/primitives";
import type { DiscoveryParams } from "../types/api";

export function DiscoveryAdvancedFiltersDrawer({
  open,
  params,
  onClose,
  onChange,
  onApply,
  onReset,
}: {
  open: boolean;
  params: DiscoveryParams;
  onClose: () => void;
  onChange: (patch: Partial<DiscoveryParams>) => void;
  onApply: () => void;
  onReset: () => void;
}) {
  return (
    <Drawer
      open={open}
      onClose={onClose}
      title="فلاتر متقدمة"
      aria-label="فلاتر الاكتشاف المتقدمة"
      footer={
        <div className="flex flex-wrap gap-2">
          <Button type="button" variant="outline" className="flex-1" onClick={onReset}>
            إعادة تعيين
          </Button>
          <Button
            type="button"
            className="flex-1"
            onClick={() => {
              onApply();
              onClose();
            }}
          >
            تطبيق الفلاتر
          </Button>
        </div>
      }
    >
      <div className="space-y-5">
        <Field label="كلمات مضمّنة" htmlFor="adv-keywords">
          <Input
            id="adv-keywords"
            value={params.keywords ?? ""}
            onChange={(event) => onChange({ keywords: event.target.value || undefined })}
            placeholder="مثلاً wireless earbuds"
          />
        </Field>

        <Field label="كلمات مستبعدة" htmlFor="adv-exclude">
          <Input
            id="adv-exclude"
            value={params.exclude_keywords ?? ""}
            disabled
            onChange={(event) => onChange({ exclude_keywords: event.target.value || undefined })}
          />
          <p className="mt-1 text-xs text-muted-foreground">قريبًا</p>
        </Field>

        <div className="grid grid-cols-2 gap-3">
          <Field label="أدنى طلبات" htmlFor="adv-min-orders">
            <Input
              id="adv-min-orders"
              type="number"
              min={0}
              value={params.min_orders ?? ""}
              onChange={(event) =>
                onChange({
                  min_orders: event.target.value === "" ? undefined : Number(event.target.value),
                })
              }
            />
          </Field>
          <Field label="أقصى طلبات" htmlFor="adv-max-orders">
            <Input
              id="adv-max-orders"
              type="number"
              min={0}
              value={params.max_orders ?? ""}
              disabled
              onChange={(event) =>
                onChange({
                  max_orders: event.target.value === "" ? undefined : Number(event.target.value),
                })
              }
            />
            <p className="mt-1 text-xs text-muted-foreground">قريبًا</p>
          </Field>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <Field label="أدنى خصم %" htmlFor="adv-min-discount">
            <Input
              id="adv-min-discount"
              type="number"
              min={0}
              max={100}
              value={params.min_discount ?? ""}
              onChange={(event) =>
                onChange({
                  min_discount: event.target.value === "" ? undefined : Number(event.target.value),
                })
              }
            />
          </Field>
          <Field label="أقصى خصم %" htmlFor="adv-max-discount">
            <Input
              id="adv-max-discount"
              type="number"
              min={0}
              max={100}
              value={params.max_discount ?? ""}
              disabled
              onChange={(event) =>
                onChange({
                  max_discount: event.target.value === "" ? undefined : Number(event.target.value),
                })
              }
            />
            <p className="mt-1 text-xs text-muted-foreground">قريبًا</p>
          </Field>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <Field label="أدنى عمولة %" htmlFor="adv-min-commission">
            <Input
              id="adv-min-commission"
              type="number"
              min={0}
              value={params.min_commission ?? ""}
              onChange={(event) =>
                onChange({
                  min_commission: event.target.value === "" ? undefined : Number(event.target.value),
                })
              }
            />
            <p className="mt-1 text-xs text-muted-foreground">عرض فقط حاليًا</p>
          </Field>
          <Field label="أقصى عمولة %" htmlFor="adv-max-commission">
            <Input
              id="adv-max-commission"
              type="number"
              min={0}
              value={params.max_commission ?? ""}
              disabled
              onChange={(event) =>
                onChange({
                  max_commission: event.target.value === "" ? undefined : Number(event.target.value),
                })
              }
            />
            <p className="mt-1 text-xs text-muted-foreground">قريبًا</p>
          </Field>
        </div>

        <Field label="بلد الشحن" htmlFor="adv-shipping-country">
          <Input
            id="adv-shipping-country"
            maxLength={2}
            placeholder="US"
            value={params.shipping_country ?? ""}
            onChange={(event) =>
              onChange({
                shipping_country: event.target.value.trim().toUpperCase() || undefined,
              })
            }
          />
        </Field>

        <Field label="تقييم المتجر" htmlFor="adv-store-rating">
          <Input
            id="adv-store-rating"
            type="number"
            min={0}
            max={5}
            step={0.1}
            value={params.store_rating ?? ""}
            disabled
            onChange={(event) =>
              onChange({
                store_rating: event.target.value === "" ? undefined : Number(event.target.value),
              })
            }
          />
          <p className="mt-1 text-xs text-muted-foreground">قريبًا</p>
        </Field>

        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={Boolean(params.free_shipping)}
            onChange={(event) => onChange({ free_shipping: event.target.checked || undefined })}
          />
          شحن مجاني
        </label>

        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={Boolean(params.choice_only)}
            onChange={(event) => onChange({ choice_only: event.target.checked || undefined })}
          />
          منتجات Choice فقط
        </label>

        <Field label="حجم الصفحة" htmlFor="adv-page-size">
          <Select
            id="adv-page-size"
            value={String(params.page_size ?? 20)}
            onChange={(event) => onChange({ page_size: Number(event.target.value), page: 1 })}
          >
            {[10, 20, 30, 50].map((size) => (
              <option key={size} value={size}>
                {size}
              </option>
            ))}
          </Select>
        </Field>
      </div>
    </Drawer>
  );
}

function Field({
  label,
  htmlFor,
  children,
}: {
  label: string;
  htmlFor: string;
  children: ReactNode;
}) {
  return (
    <div>
      <label className="mb-1.5 block text-sm" htmlFor={htmlFor}>
        {label}
      </label>
      {children}
    </div>
  );
}
