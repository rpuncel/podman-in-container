# Default-deny egress enforced by a per-workspace filtering proxy

Outbound network access from the machine is **default-deny**. The agent may reach only the endpoints on its workspace's **egress policy** allow-list. Enforcement is a **per-workspace filtering forward-proxy** that allow-lists by **hostname / TLS SNI** (supporting wildcard domains such as `*.pythonhosted.org`, `*.npmjs.org`), with the machine firewall (iptables-legacy, per ADR-0002) blocking *all* direct egress so the proxy is the only path out. Package managers and tooling are pointed at the proxy via `HTTP(S)_PROXY` and their own configs. **Only the human tunes the allow-list per workspace — the agent cannot widen its own egress.**

Chosen because the sandbox contains the blast radius of a *rogue local action*, but outbound network is the one channel by which a compromised or mistaken agent could still cause external harm (exfiltration, malicious git push, registry poisoning). Default-deny closes that channel to a small, auditable set.

Rejected: **default-allow** (allow-list only selects which credentials to inject) — leaves exfiltration wide open, defeating much of the sandbox's purpose. Rejected: **IP/CIDR firewalling** — brittle against CDNs and registries whose IPs rotate; hostname/SNI filtering is the right granularity.

Trade-off / friction to expect: transitive dependency fetches hit many hosts, so allow-lists need tuning; tools that ignore proxy env vars or pin TLS bypass the proxy and must be handled case-by-case. If this becomes too much of a slog in practice, the fallback is to relax specific workspaces toward default-allow — a per-workspace policy knob, not an architecture change.
