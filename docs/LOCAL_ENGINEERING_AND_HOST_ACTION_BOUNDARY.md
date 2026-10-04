# Local engineering and guarded host-action boundary

## Local authority

Engineering agents may inspect repositories, run tests, create or amend
unpublished local commits, and tend local branches and worktrees.  These are
local, reversible engineering operations.  They neither authenticate the
agent to a host nor publish any material.

## Guarded host actions

Remote publication and account operations are outside local engineering
authority.  This includes `git push`, remote pull-request creation or merge,
Git credential configuration or repair, `gh auth`, and any request to expose
or persist a host token.  A local repair that needs publication must leave a
commit SHA and the exact host action for an authorised operator; it must not
try to obtain credentials or perform a substitute host mutation.

## Provider separation

`OPENAI_API_KEY` is read only at the transport secret boundary.  It is neither
an S0 approval nor evidence of a valid project.  In particular,
`scripts/run_scale_s0.py --preflight` remains provider-free: it validates the
durable Attempt/A3 checkpoint but does not construct a provider client,
create a reservation, or send a request.  Live routing can only proceed after
the existing durable packet, authority, pricing, reservation, and send-gate
checks.  The provider key must never be written to runtime evidence, logs,
reports, or Git.

## Mechanical regression boundary

`tests/contracts/test_local_host_action_boundary.py` scans tracked production
Python sources and entry scripts for direct remote-Git mutation, Git
credential/authentication, and common host-token environment routing.  The
check deliberately permits the documented OpenAI secret boundary; it rejects
host mutation/authentication primitives in product code rather than treating
them as ordinary local engineering.
