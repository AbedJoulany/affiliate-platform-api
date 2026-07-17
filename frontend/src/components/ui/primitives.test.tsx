import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Button } from "./primitives";

describe("Button", () => {
  it("is keyboard accessible and invokes its action", async () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>حفظ</Button>);
    const button = screen.getByRole("button", { name: "حفظ" });
    await userEvent.click(button);
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("disables interaction while loading", () => {
    render(<Button loading>حفظ</Button>);
    expect(screen.getByRole("button", { name: "حفظ" })).toBeDisabled();
  });
});
