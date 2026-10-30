# Response to the external security review

This branch addresses concrete gaps; it does not certify AgentReady as secure or
provide a sandbox. The supplied review described tests against the earlier SSRF
branch (2 Node and 7 Python tests), before the privacy changes. Its attack scripts
were not attached, so those exact scripts have not been rerun.

## Addressed in this follow-up

- wake_site uses the same public-only pinned transport as Tester,
  including DNS, port, proxy and redirect checks.
- Fix requests require BOTH the existing repo allowlist and an exact operator-owned
  requester/repo/site-origin enrollment. Unrecognized requesters and mismatched
  sites are refused before queueing. Direct Fixer chat/apply and queued worker
  entry points recheck enrollment. An operator must verify ownership outside chat;
  users cannot enroll themselves by setting chat memory. This is not self-service
  GitHub OAuth/App verification.
- Automatic fix handoffs are disabled by default; an explicit fix request is still supported for enrolled requesters.
- Agent-based merges are disabled at the chat, task and GitHub helper boundaries.
  A human must review and merge in GitHub. Legacy auto-merge flags do not override it.
- Credential filenames including prod.env, .netrc, .git-credentials, service account
  JSON and credential folders are protected. Build/CI/deployment configuration is
  readable where appropriate but cannot be edited through model tools.
- Search is literal, not regex, so user/model patterns cannot cause regex backtracking.
  Read/search skip individual files above 512 KiB.
- Python excludes NAT64, IPv4-compatible and site-local IPv6 alongside the already
  blocked tunnel, private, special and documentation ranges.
- Scan limits use Express's peer-derived req.ip. Forwarding is ignored by default;
  only explicitly configured trusted proxy CIDRs may supply forwarding headers.
- Report unlocks are capped at 5 per client per hour and 3 per normalized recipient
  per hour. Recipient keys are hashed rather than stored as email addresses.
  These controls limit abuse; they do not prove ownership of an email address.
- CORS permits exact configured origins rather than every Vercel tenant.
- URL normalization accepts numeric public subdomains such as 10.example.com while
  still rejecting private literal IPs. Socket-time DNS validation remains mandatory.
- Compatible npm security updates were applied to API and frontend lockfiles.

## Deployment configuration needed

Set FIXER_REQUESTER_BINDINGS identically on the agent services, e.g. a JSON array:
`[{"requester":"authenticated-agent-address","repo":"owner/shop","site":"https://shop.example"}]`.
The operator must verify repository control and the site's association before adding
an enrollment. Exact requester IDs are case-sensitive; repository names are not.
No wildcard requester or repo grants are supported. The existing repo allowlist is
still required. An origin enrollment covers paths on that origin, not other hosts.

Configure FRONTEND_URLS with exact deployed frontend origins. For proxy deployments,
set TRUSTED_PROXY_CIDRS to the actual documented load-balancer source networks and
prevent direct untrusted traffic from pretending to originate there. Do not trust
all IPs or use arbitrary X-Forwarded-For entries. An unset value is fail-closed and
may group users behind a load balancer; configure it before a production rollout.
Rate-limit stores remain process-local: scale-out requires a shared store and edge
limits. Direct authenticated agent scan exemptions retain their existing per-user
agent controls; leaked agent keys must be revoked.

## Still required before claiming an end-to-end safe Fixer

1. A disposable execution service: non-root isolated VM/container, no host mounts or
   credentials, CPU/memory/process/time quotas, controlled dependency installation,
   blocked metadata/private-network egress, and guaranteed cleanup. Environment
   scrubbing alone does not prevent reading host files or making network requests.
2. A per-job capability for Tester to reach exactly that sandbox's assigned local
   origin. No public chat flag, blanket localhost exemption, or global SSRF bypass.
   Redirects and asset fetches must remain constrained to the capability/public policy.
3. Real integration tests covering before/after shopping in the sandbox, blocked
   credential access and private-network sockets, cross-job isolation, expiry and
   teardown. Current unit tests prove deny paths and authorization checks, not sandbox
   isolation or a working local proof loop.
4. Prefer GitHub App least-privilege installations and authenticated user enrollment
   for a multi-tenant product. Enrollment config is a small trusted-operator approach.
5. Complete dependency major-version migrations and rerun the independent attack
   suite. Current audit still reports 4 low API advisories in the Resend email
   dependency chain, and 4 frontend advisories (1 high, 3 moderate) in React Router /
   Vite / esbuild. No --force upgrade was applied without migration validation.
   No Python dependency vulnerability audit was performed in this follow-up.

The build and regression tests do not replace live deployment testing. Do not
advertise the historical 0/5 to 5/5 Fixer demo as supported in the default security
mode. Keep production Fixer execution disabled until the runner work is complete.
