import type { ComponentProps } from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Channel } from "@/features/channels/types/api";
import {
  QueueSchedulingDialog,
  type QueuePublishNowSubmitValues,
  type QueueScheduleSubmitValues,
} from "./QueueSchedulingDialog";

afterEach(() => {
  cleanup();
});

const VALID_CHANNEL_ID = "550e8400-e29b-41d4-a716-446655440000";
const FUTURE_LOCAL = "2099-06-15T14:30";
const PAST_LOCAL = "2020-01-15T09:00";
const INVALID_LOCAL = "2099-06-15T14:30:45";

function makeChannel(overrides: Partial<Channel> = {}): Channel {
  return {
    id: VALID_CHANNEL_ID,
    telegram_channel_id: "-100123",
    title: "قناة الاختبار",
    username: "test_channel",
    bot_permission_status: "granted",
    can_post_messages: true,
    can_edit_messages: true,
    can_delete_messages: true,
    permissions_checked_at: null,
    permission_detail: null,
    is_active: true,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function renderDialog(
  overrides: Partial<ComponentProps<typeof QueueSchedulingDialog>> = {},
) {
  const onSchedule = vi.fn<(values: QueueScheduleSubmitValues) => void>();
  const onPublishNow = vi.fn<(values: QueuePublishNowSubmitValues) => void>();
  const onClose = vi.fn();
  const props: ComponentProps<typeof QueueSchedulingDialog> = {
    open: true,
    itemCount: 1,
    defaultValues: { channelId: "", scheduledAt: "" },
    channels: [makeChannel()],
    busy: false,
    onSchedule,
    onPublishNow,
    onClose,
    ...overrides,
  };
  const view = render(<QueueSchedulingDialog {...props} />);
  return {
    ...view,
    onSchedule,
    onPublishNow,
    onClose,
    rerenderDialog: (
      next: Partial<ComponentProps<typeof QueueSchedulingDialog>> = {},
    ) => view.rerender(<QueueSchedulingDialog {...props} {...next} />),
  };
}

describe("QueueSchedulingDialog", () => {
  it("submits a valid schedule payload without calling publish-now", async () => {
    const { onSchedule, onPublishNow } = renderDialog();

    await userEvent.selectOptions(
      screen.getByLabelText("القناة المستهدفة"),
      VALID_CHANNEL_ID,
    );
    fireEvent.change(screen.getByLabelText("تاريخ ووقت مخصص"), {
      target: { value: FUTURE_LOCAL },
    });
    await userEvent.click(screen.getByRole("button", { name: "حفظ الجدولة" }));

    await waitFor(() => {
      expect(onSchedule).toHaveBeenCalledWith({
        intent: "schedule",
        channelId: VALID_CHANNEL_ID,
        scheduledAt: FUTURE_LOCAL,
      });
    });
    expect(onPublishNow).not.toHaveBeenCalled();
  });

  it("shows a channel validation error and does not submit", async () => {
    const { onSchedule, onPublishNow } = renderDialog();

    fireEvent.blur(screen.getByLabelText("القناة المستهدفة"));

    expect(await screen.findByText("القناة المستهدفة مطلوبة")).toBeInTheDocument();
    expect(onSchedule).not.toHaveBeenCalled();
    expect(onPublishNow).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "حفظ الجدولة" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "نشر الآن" })).toBeDisabled();
  });

  it("shows a missing scheduledAt error and does not submit", async () => {
    const { onSchedule } = renderDialog();

    await userEvent.selectOptions(
      screen.getByLabelText("القناة المستهدفة"),
      VALID_CHANNEL_ID,
    );
    fireEvent.blur(screen.getByLabelText("تاريخ ووقت مخصص"));

    expect(await screen.findByText("تاريخ ووقت الجدولة مطلوب")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "حفظ الجدولة" })).toBeDisabled();
    expect(onSchedule).not.toHaveBeenCalled();
  });

  it("shows an invalid scheduledAt error and does not submit", async () => {
    const { onSchedule } = renderDialog();

    await userEvent.selectOptions(
      screen.getByLabelText("القناة المستهدفة"),
      VALID_CHANNEL_ID,
    );
    fireEvent.change(screen.getByLabelText("تاريخ ووقت مخصص"), {
      target: { value: INVALID_LOCAL },
    });
    await userEvent.click(screen.getByRole("button", { name: "حفظ الجدولة" }));

    expect(await screen.findByText("أدخل تاريخًا ووقتًا صحيحين")).toBeInTheDocument();
    expect(onSchedule).not.toHaveBeenCalled();
  });

  it("shows a past scheduledAt error and does not submit", async () => {
    const { onSchedule, onPublishNow } = renderDialog();

    await userEvent.selectOptions(
      screen.getByLabelText("القناة المستهدفة"),
      VALID_CHANNEL_ID,
    );
    fireEvent.change(screen.getByLabelText("تاريخ ووقت مخصص"), {
      target: { value: PAST_LOCAL },
    });
    await userEvent.click(screen.getByRole("button", { name: "حفظ الجدولة" }));

    expect(await screen.findByText("لا يمكن جدولة وقت في الماضي")).toBeInTheDocument();
    expect(onSchedule).not.toHaveBeenCalled();
    expect(onPublishNow).not.toHaveBeenCalled();
  });

  it("submits publish-now with only a channel and no scheduledAt", async () => {
    const { onSchedule, onPublishNow } = renderDialog();

    await userEvent.selectOptions(
      screen.getByLabelText("القناة المستهدفة"),
      VALID_CHANNEL_ID,
    );
    await userEvent.click(screen.getByRole("button", { name: "نشر الآن" }));

    await waitFor(() => {
      expect(onPublishNow).toHaveBeenCalledWith({
        intent: "publish_now",
        channelId: VALID_CHANNEL_ID,
      });
    });
    expect(onSchedule).not.toHaveBeenCalled();
  });

  it("keeps submit callbacks from firing while the mutation is busy", async () => {
    const { onSchedule, onPublishNow } = renderDialog({
      busy: true,
      defaultValues: { channelId: VALID_CHANNEL_ID, scheduledAt: FUTURE_LOCAL },
    });

    expect(screen.getByRole("button", { name: "حفظ الجدولة" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "نشر الآن" })).toBeDisabled();
    expect(onSchedule).not.toHaveBeenCalled();
    expect(onPublishNow).not.toHaveBeenCalled();
  });

  it("clears validation errors when a new dialog session opens", async () => {
    const view = renderDialog();

    await userEvent.selectOptions(
      screen.getByLabelText("القناة المستهدفة"),
      VALID_CHANNEL_ID,
    );
    fireEvent.change(screen.getByLabelText("تاريخ ووقت مخصص"), {
      target: { value: PAST_LOCAL },
    });
    await userEvent.click(screen.getByRole("button", { name: "حفظ الجدولة" }));
    expect(await screen.findByText("لا يمكن جدولة وقت في الماضي")).toBeInTheDocument();

    view.rerenderDialog({ open: false });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

    view.rerenderDialog({
      open: true,
      defaultValues: { channelId: VALID_CHANNEL_ID, scheduledAt: FUTURE_LOCAL },
    });

    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });
    expect(screen.queryByText("لا يمكن جدولة وقت في الماضي")).not.toBeInTheDocument();
    expect(screen.getByLabelText("القناة المستهدفة")).toHaveValue(VALID_CHANNEL_ID);
    expect(screen.getByLabelText("تاريخ ووقت مخصص")).toHaveValue(FUTURE_LOCAL);
  });

  it("fills scheduledAt from a preset and clears a prior date error", async () => {
    const { onSchedule } = renderDialog();

    await userEvent.selectOptions(
      screen.getByLabelText("القناة المستهدفة"),
      VALID_CHANNEL_ID,
    );
    fireEvent.change(screen.getByLabelText("تاريخ ووقت مخصص"), {
      target: { value: PAST_LOCAL },
    });
    await userEvent.click(screen.getByRole("button", { name: "حفظ الجدولة" }));
    expect(await screen.findByText("لا يمكن جدولة وقت في الماضي")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "بعد ساعة" }));

    await waitFor(() => {
      expect(screen.queryByText("لا يمكن جدولة وقت في الماضي")).not.toBeInTheDocument();
    });
    expect((screen.getByLabelText("تاريخ ووقت مخصص") as HTMLInputElement).value).toMatch(
      /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/,
    );

    await userEvent.click(screen.getByRole("button", { name: "حفظ الجدولة" }));
    await waitFor(() => {
      expect(onSchedule).toHaveBeenCalledTimes(1);
    });
    expect(onSchedule.mock.calls[0][0]).toMatchObject({
      intent: "schedule",
      channelId: VALID_CHANNEL_ID,
    });
  });
});
