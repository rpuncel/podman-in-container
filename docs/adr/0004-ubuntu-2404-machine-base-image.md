# Machine base image is Ubuntu 24.04 + systemd

The machine image is built on **Ubuntu 24.04 with systemd as PID 1**, rather than Fedora + systemd.

Chosen because Ubuntu 24.04 is the base of Apple's *tested reference* Dockerfile for `container machine`, minimizing boot/init surprises on the primary outer engine. Fedora ships a newer podman, but that upside does not outweigh straying from the path Apple actually exercises.

Trade-off: Ubuntu's packaged podman lags Fedora's. Revisit Fedora only if Ubuntu's podman version blocks a needed feature (e.g. a rootless-overlay capability the spike surfaces). The image and entrypoint are kept engine-agnostic, so the base image is not entangled with the outer-engine choice.
