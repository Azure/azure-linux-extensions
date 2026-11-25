---
applyTo: "VMAccess/**"
---

# VMAccess extension review guidance

VMAccess resets passwords, SSH keys, and `sshd_config`, creates or removes
users, and checks or repairs disks. It runs as root via the Azure Guest Agent,
so mistakes can lock customers out of their VMs.

- **Python compatibility:** `extension_shim.sh` picks whichever Python is installed, so `vmaccess.py` must stay compatible with both Python 2.7 and Python 3. Flag f-strings, type hints, `print` without parentheses, and Python-3-only standard library APIs.
- **Shared utilities:** `vmaccess.py` imports the repository-root `Utils` package (`handlerutil2`, `extensionutils`, `distroutils`, `logger`). Changes there affect other extensions; prefer changes local to VMAccess.
- **Lockout safety:** Changes to `sshd_config`, `sudoers`, PAM, iptables, or account handling must back up before modifying, validate the result, and restore on failure. Never weaken security (e.g. enable password auth or root login) unless the customer explicitly requested it.
- **Distro coverage:** Behavior must work across supported distros using `resources/*_default` and `distroutils`. Flag distro-specific assumptions about paths, service names, or commands.
- **Secrets:** Never log passwords, private keys, or protected settings. Write keys and config with least-privilege permissions and correct ownership.
- **Idempotency:** Enable can be re-run with the same settings. Repeated runs must not duplicate users, keys, firewall rules, or config entries.
- **Tests:** Add or update `unittest` cases in `VMAccess/test`, mocking system calls instead of changing the test machine.

Report only actionable findings with file, line, impact, and a concrete fix.
