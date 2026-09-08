# Security policy and boundaries

The 0.1.x release line receives fixes as maintainers are able. This alpha has not undergone an independent security audit.

## Reporting

If private vulnerability reporting is enabled, use the repository's **Security → Report a vulnerability** flow. If unavailable, open a minimal issue requesting a private contact channel without posting exploit details, documents, tokens or private filesystem paths.

## Threat model

FolioQueue is for trusted local documents in a directory controlled by the user. It does not configure LLM/cloud clients, enable third-party MarkItDown plugins, call a shell or accept URL inputs. Optional parsers and their transitive dependencies are still part of the trusted computing base. Ordinary process isolation is not a security sandbox or a network firewall.

Input/output checksums, a cooperative writer lock, path checks, input snapshots, atomic output replacement, timeouts and admission limits reduce common operational failures. They do not protect against a compromised parser, malicious local process, filesystem race, resource exhaustion inside a parser, or a deliberately modified ledger.

The worker runs with the user's account permissions. Run untrusted documents only inside a separate sandbox with OS-enforced filesystem, network, CPU and memory limits. Markdown output can contain untrusted links or raw markup; review it before rendering in another application.

## Data retained locally

- Converted Markdown contains document text.
- The private ledger contains the absolute input root, relative paths and hashes.
- Reports contain relative filenames and error codes, but omit body text and raw parser exceptions.
- Temporary snapshots are normally removed after each job. Forced termination may leave copies in `.folioqueue/work`; remove that directory only after confirming no run is active.

Do not publish your output directory without reviewing it. The project itself has no telemetry or analytics code.
