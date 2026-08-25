# Hermes setup

The repository root `AGENTS.md` is the authoritative always-on contract. Project-specific skill material is optional/on-demand and can be installed into Hermes's skill catalog.

## Automated setup

Linux/macOS/WSL:

```bash
bash scripts/setup-hermes.sh
```

Windows PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup-hermes.ps1
```

The scripts:

1. verify `hermes` exists;
2. install/enable Ponytail from its upstream Hermes plugin;
3. install the project skill under the active Hermes config home;
4. do not overwrite global memory/personality files;
5. run the harness context validator.

Restart Hermes after plugin installation.

## Ponytail

The upstream Hermes installation command used by this harness is:

```bash
hermes plugins install DietrichGebert/ponytail --enable
```

Ponytail exposes `/ponytail`, `/ponytail-review`, `/ponytail-audit`, `/ponytail-debt`, `/ponytail-gain`, and `/ponytail-help` in current releases. Use `full` for normal work.

## Recommended public Hermes skills
When available, prefer Hermes's maintained Git/GitHub PR workflow and planning/testing skills instead of copying equivalent procedural text into every project. The local skill here only teaches project-specific constraints.

## GitHub Projects caveat
Issue/PR access and Project v2 access can require different token scopes. If `gh project` cannot read/update the board, fix credentials or record the limitation; do not create a duplicate Project.
