# Reference Manifest

## Copied From `D:\FinceptTerminal`

- `research/2026-05-22-platform-test/*` -> `docs/reference/fincept-platform-test/`
- `screenshots/*` -> `docs/reference/root-captures/screenshots/`
- `fincept-current-window.png` -> `docs/reference/root-captures/fincept-current-window.png`
- `app/components.xml` -> `docs/reference/install-metadata/components.xml`
- `app/InstallationLog.txt` -> `docs/reference/install-metadata/InstallationLog.txt`
- `app/Licenses/license.txt` -> `docs/reference/install-metadata/license.txt`

## Deliberately Not Copied

- `D:\FinceptTerminal\app\FinceptTerminal.exe`
- Qt/runtime DLLs and static libraries
- installer binaries under `downloads/`
- `app/scripts/` implementation code
- user-data caches and temporary files
- OMX session state

## Rationale

The new project should start from observed requirements and evidence. It should not start by inheriting the installed application's runtime, branding, or live-trading script surface.
