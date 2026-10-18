import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { getHealth } from "@/lib/api/health";

import { SystemStatusContainer } from "./SystemStatusContainer";

vi.mock("@/lib/api/health", () => ({ getHealth: vi.fn() }));

describe("SystemStatusContainer", () => {
  beforeEach(() => {
    vi.mocked(getHealth).mockReset();
  });

  it("renders the health report returned by the API", async () => {
    vi.mocked(getHealth).mockResolvedValue({
      status: "ok",
      checks: { postgres: "ok", chroma: "ok" },
    });

    render(<SystemStatusContainer />);

    expect(await screen.findByText("Backend OK")).toBeInTheDocument();
  });

  it("renders the unreachable state when the request fails", async () => {
    vi.mocked(getHealth).mockRejectedValue(new TypeError("Failed to fetch"));

    render(<SystemStatusContainer />);

    expect(await screen.findByText("Backend unreachable")).toBeInTheDocument();
  });
});
