<!--
Before opening:

- Bug fixes, documented-feature work and small scoped changes: go ahead.
- New features, sensors, outside services or architecture changes, and any change
  to Core (packages/internet_health_monitor_core/): link a Discussion first.

PRs without a prior Discussion may be closed in favor of starting one.
See CONTRIBUTING.md § Before you file. Reviews happen on weekends, about two
weeks each, one active PR per contributor (SUPPORT.md).
-->

# Description

<!-- What does this PR do, and why? Screenshots for card or settings changes. -->

## Related

<!-- Use "Related to #N", never "Fixes #N" or "Closes #N": GitHub closes issues
     from commit messages on merge (CONTRIBUTING.md § Closing). -->

Related to #

## Testing

<!-- How was it verified? HA version and install type (HA OS, Container,
     Supervised, Core) if it touches the integration. -->

## Checklist

- [ ] A bug fix, documented-feature change or small scoped fix, **or** it links a prior Discussion
- [ ] Specs and docs changed first, then code (CONTRIBUTING.md § How changes are made)
- [ ] A failing test came first; tests are table-driven and use no real network or personal data
- [ ] `CHANGELOG.md` has an entry under `[Unreleased]` for code changes (CI checks it)
- [ ] Every commit is `type(scope): description` (CI checks each one)
- [ ] `make check` and `make test-all` pass locally
