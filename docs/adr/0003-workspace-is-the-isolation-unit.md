# Workspace is the unit of runtime isolation

Runtime state (running containers, volumes, networks, published ports) is isolated per **workspace** — a user-defined group of related repositories that share one machine — not per repository and not globally. The image store remains shared host-globally across all machines.

Chosen because per-repo machines are too heavy (each is a VM defaulting to half system RAM) and easy to forget to stop, while a single global sandbox gives no isolation between unrelated workstreams. A user-managed workspace grouping matches how the user actually works (flitting between repos within a workstream) and places the isolation boundary between workstreams, where it has value.

Trade-off: repos within a workspace share podman's container-name and published-port namespace, so two repos publishing the same host port for preview will collide — rare and easily resolved, since the agent tests workloads over the machine's internal network.
