# Hermes Environment Map

This document serves as the absolute truth for the Agent's physical location and access rights to prevent "path not found" or "physical obstruction" errors.

## Physical Location
- **Root Directory**: `D:\Agentic-Quant-Trading-System\Agentic-Quant-Trading-System` (auto-detected via `config.py`)
- **OS**: Windows 11 Home China
- **Shell**: Bash (via Git Bash / Windows Terminal)

## Critical Paths
All paths managed centrally via `config.py`. Use `from config import get_path` to resolve.
- **Meta Evolution System**: `{PROJECT_ROOT}/meta-evolution/`
- **Configuration**: `{PROJECT_ROOT}/.claude/`
- **Core Trading Engine**: `{PROJECT_ROOT}/tdx-mcp/`

## Access Protocol
1. **Path Format**: Always use `config.get_path("subdir", "file")` — never hardcode absolute paths.
2. **Verification**: If a file is reported missing, execute `ls -R` on the parent directory before reporting failure.
3. **Project Root**: Set `QUANT_PROJECT_ROOT` env var to override auto-detection.
