import { StatusBadge } from "@/components/ui/StatusBadge";
import type { HealthReport } from "@/lib/api/health";

export type SystemStatusState =
  { kind: "loading" } | { kind: "unreachable" } | { kind: "loaded"; report: HealthReport };

interface SystemStatusViewProps {
  state: SystemStatusState;
}

export function SystemStatusView({ state }: SystemStatusViewProps) {
  return (
    <section aria-labelledby="system-status-title">
      <h2 id="system-status-title">System status</h2>
      {state.kind === "loading" && <StatusBadge tone="neutral" label="Checking backend…" />}
      {state.kind === "unreachable" && <StatusBadge tone="error" label="Backend unreachable" />}
      {state.kind === "loaded" && (
        <>
          <StatusBadge
            tone={state.report.status === "ok" ? "ok" : "warning"}
            label={state.report.status === "ok" ? "Backend OK" : "Backend degraded"}
          />
          <ul>
            {Object.entries(state.report.checks).map(([name, status]) => (
              <li key={name}>
                {name}: <StatusBadge tone={status === "ok" ? "ok" : "error"} label={status} />
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
