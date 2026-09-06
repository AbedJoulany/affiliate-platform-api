import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createElement } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ImageSearchPanel } from "./ImageSearchPanel";

afterEach(cleanup);

describe("ImageSearchPanel", () => {
  it("submits a valid image URL", async () => {
    const user = userEvent.setup();
    const onSearch = vi.fn();
    render(createElement(ImageSearchPanel, { searching: false, onSearch }));

    await user.type(screen.getByLabelText("رابط الصورة"), "https://example.com/product.jpg");
    await user.click(screen.getByRole("button", { name: "بحث بالصورة" }));

    expect(onSearch).toHaveBeenCalledWith({
      image_url: "https://example.com/product.jpg",
      page: 1,
      page_size: 20,
    });
  });

  it("rejects an empty query without calling onSearch", async () => {
    const user = userEvent.setup();
    const onSearch = vi.fn();
    render(createElement(ImageSearchPanel, { searching: false, onSearch }));

    await user.click(screen.getByRole("button", { name: "بحث بالصورة" }));

    expect(onSearch).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent("أدخل رابط صورة أو ارفع ملفًا.");
  });

  it("uploads an image file as base64", async () => {
    const user = userEvent.setup();
    const onSearch = vi.fn();
    render(createElement(ImageSearchPanel, { searching: false, onSearch }));

    const file = new File(["fake-bytes"], "shoe.png", { type: "image/png" });
    await user.upload(screen.getByLabelText("رفع صورة"), file);

    await waitFor(() => expect(onSearch).toHaveBeenCalledTimes(1));
    const [payload, uploaded] = onSearch.mock.calls[0];
    expect(payload.image_base64).toEqual(expect.any(String));
    expect(payload.image_base64.length).toBeGreaterThan(0);
    expect(payload.page).toBe(1);
    expect(uploaded).toBe(file);
  });
});
