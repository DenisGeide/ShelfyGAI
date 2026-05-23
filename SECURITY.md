# Security Policy

## Supported Versions

ShelfyGAI is currently pre-1.0. Security fixes are provided on the default branch until a stable release support policy is published.

## Reporting a Vulnerability

Please report suspected vulnerabilities privately by opening a GitHub security advisory, or by contacting the maintainers through the project's published security contact once one is available.

Do not include exploit details in public issues. A good report includes:

- Affected version or commit
- Windows version
- Reproduction steps
- Expected and observed behavior
- Any logs needed to understand the issue

Please remove private window titles, local file paths, process names, usernames, and document names from shared logs unless they are essential to the report.

## Security Model

ShelfyGAI is a local desktop utility. It does not run a privileged service, does not expose a network listener, and does not send telemetry. It interacts with user-session windows through the Windows desktop APIs available to the current user.

The application should not be run elevated unless a user specifically needs to manage elevated windows.

## Out Of Scope For Public Issues

- Requests to add telemetry, analytics, ads, or cloud sync.
- Reports that require publishing another user's private window titles, logs, or local paths.
- Vulnerabilities in third-party applications that ShelfyGAI happens to enumerate.

## Expected Response

For the first public release, maintainers should acknowledge valid private reports within seven days when possible, triage severity, and publish a fix or mitigation note before discussing technical details publicly.
