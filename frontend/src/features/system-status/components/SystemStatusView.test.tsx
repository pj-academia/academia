import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SystemStatusView } from "./SystemStatusView";

describe("SystemStatusView", () => {
  it("shows a loading state while the backend is being checked", () => {
    render(<SystemStatusView state={{ kind: "loading" }} />);

    expect(screen.getByText("Checking backend…")).toBeInTheDocument();
  });

  it("reports an unreachable backend", () => {
    render(<SystemStatusView state={{ kind: "unreachable" }} />);

    expect(screen.getByText("Backend unreachable")).toBeInTheDocument();
  });

  it("lists every dependency when the backend is degraded", () => {
    render(
      <SystemStatusView
        state={{
          kind: "loaded",
          report: { status: "degraded", checks: { postgres: "ok", chroma: "down" } },
        }}
      />,
    );

    expect(screen.getByText("Backend degraded")).toBeInTheDocument();
    expect(screen.getByText("postgres:")).toBeInTheDocument();
    expect(screen.getByText("down")).toHaveAttribute("data-tone", "error");
  });
});
