# podman-in-container

A sandbox on macOS for running an AI agent harness that manipulates container
workloads. The harness runs *inside* the sandbox, so it can be granted broad
permissions without putting the host at risk: the blast radius of a rogue or
mistaken agent is the sandbox, not your Mac.

The sandbox is a **machine** — a persistent Linux VM booting systemd as PID 1, with
podman running inside it non-nested, as it would on any Linux host. See
[`CONTEXT.md`](CONTEXT.md) for the vocabulary, [`docs/adr/`](docs/adr/) for the
decisions, [`docs/machine-image.md`](docs/machine-image.md) for how the machine
image is put together, and [`docs/workspace-config.md`](docs/workspace-config.md) for
how a workspace declares what it may reach and which credentials it gets.

## Prerequisites

- macOS on Apple silicon, with Apple's [`container`](https://github.com/apple/container)
  CLI installed and its service running (`container system start`).
- [Poetry](https://python-poetry.org/), for the `pic` CLI.

## Using the raw engine commands

What the machine is, without the CLI in the way.

Build the machine image:

```bash
container build -t pic-machine:latest -f images/machine/Containerfile images/machine
```

Create a machine from it and boot it. `--memory` matters: the engine defaults a
machine to 1 GiB, which is not enough for inner podman to build and run workloads:

```bash
container machine create pic-machine:latest --name pic-demo --memory 4G
```

`create` returns before the machine has finished booting — its exec channel comes up
well before its entrypoint has provisioned anything. Wait for the entrypoint's report
before using the machine:

```bash
until container machine run -n pic-demo -- test -f /run/pic/machine-init.json 2>/dev/null; do sleep 2; done
```

Open a shell inside the machine:

```bash
container machine run -n pic-demo
```

Run a workload with inner podman:

```bash
container machine run -n pic-demo -- podman run --rm hello-world
```

See what the entrypoint provisioned at boot — firewall backend, storage driver,
machine users:

```bash
container machine run -n pic-demo -- cat /run/pic/machine-init.json
```

Stop the machine, and delete it along with its persistent storage:

```bash
container machine stop pic-demo
```

```bash
container machine delete pic-demo
```

There is no `container machine start`: `run` boots a stopped machine before running
its command, so `container machine run -n pic-demo -- true` restarts one.

### One sharp edge

`container machine run -- …` joins its arguments and runs them through `bash -c`, so
a quoted shell string gets re-parsed and mangled — `-- sh -c 'echo $HOME'` silently
prints nothing. Pass a plain command instead, or put a script in your home directory
(mounted into the machine at the same path) and run `-- bash /Users/you/foo.sh`.

## Using the `pic` CLI

```bash
poetry install
```

`pic launch` does the build, the create and the wait in one step. Machines are named
`pic-<workspace>`, so this creates `pic-demo`:

```bash
poetry run pic launch --workspace demo
```

`--workspace` is optional and defaults to `global`, giving you `pic-global`. A
[workspace](CONTEXT.md) is a group of related repositories sharing one machine — the
unit of isolation, so workloads in one workspace cannot touch another's.

Tear the machine down, storage and all:

```bash
poetry run pic teardown --workspace demo
```

The CLI does not yet have a command for getting into a machine or running a workload
in it — use `container machine run` from the section above for those.

## Configuring a workspace

A workspace's egress allow-list and its secret manifest live in a YAML config on the
host at `~/.config/pic/workspaces/<name>.yaml`, over a shared base config it
`extends`. Credentials are named by *reference* (`pass:`, `op://`, `gh`,
`keychain:`, `env:`) and resolved on the host at launch, so no master key ever
enters the machine. See [`docs/workspace-config.md`](docs/workspace-config.md).

## Tests

The acceptance tests boot a real machine and check inner podman inside it, then tear
it down, so they need no hand-provisioned machine and take about a minute:

```bash
poetry run pytest
```

The workspace config and credential resolver are host-side, so their tests need no
machine and run in well under a second:

```bash
poetry run pytest tests/test_workspace_config.py tests/test_credentials.py
```
