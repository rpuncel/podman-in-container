# Credentials resolved on the host, never stored in the machine

Secrets reach the machine through a **host-side resolver** run at machine launch, never by moving a master key or secret store into the machine. A per-workspace **secret manifest** maps each needed credential to a *reference* in whatever store the user already runs — `pass:`, `op://`, `gh` (via `gh auth token`), `keychain:`, or `env:`. At launch the resolver fetches the referenced values **on the host** — which triggers the user's existing interactive unlock (GPG pinentry for `pass`, `op signin` for 1Password) — and injects only the resolved values into the machine's **tmpfs**, wired to their consumers: the git credential helper, containers `auth.json`, `.npmrc`/`pip.conf`, and `ANTHROPIC_API_KEY`.

Chosen because the machine is the blast radius (ADR-0001): a compromised agent must not be able to read the user's *entire* secret store or a reusable master key. Resolving on the host keeps GPG/1Password keys on the host, puts exactly the allow-listed credential set (and nothing more) inside the machine, bakes no secret into the image, and lets a reset wipe the tmpfs clean. It also reuses the user's existing secret tooling rather than reinventing storage.

Rejected: **bind-mounting host credential files or `~`** — exposes far more than the minimal set and risks persistence. Rejected: **a dedicated new secret store** — reinvents `pass`/`op`/Keychain, which the user already operates.

Git push specifically uses a **dedicated per-workspace fine-grained PAT** (least-privilege, consistent with default-deny egress in ADR-0005) rather than reusing the host `gh` token's full scope; host-token reuse remains an easy path for throwaway/personal workspaces.

Trade-off: launch requires an interactive unlock when the store is locked (acceptable — it mirrors the user's current alias workflow), and the resolver must support each backend the user relies on.
