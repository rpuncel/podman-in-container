# Agent runs inside the sandbox

To let the agent harness be granted broad, pre-approved permissions without risking the macOS host, the agent runs *inside* the sandbox rather than on the host delegating container operations inward. The sandbox is the security perimeter: the worst case is a trashed sandbox, not a trashed host — which is what makes pre-granting permissions (even `--dangerously-skip-permissions`) acceptable.

Rejected: agent-on-host delegating only container operations — it leaves the harness with full host access, defeating the entire purpose.
