# Hermes Environment Map

This document serves as the absolute truth for the Agent's physical location and access rights to prevent "path not found" or "physical obstruction" errors.

## Physical Location
- **Root Directory**: `F:\working-project`
- **OS**: Windows 10 Pro
- **Shell**: Bash (via Git Bash / Windows Terminal)

## Critical Paths
- **Meta Evolution System**: `F:\working-project\meta-evolution\`
- **Configuration**: `F:\working-project\.claude\`
- **Soul & Architecture**: `F:\working-project\soul.md`
- **Core Architecture Layers**: 
  - Rules: `F:\working-project\rules\`
  - Skills: `F:\working-project\skills\`
  - Agents: `F:\working-project\agents\`
  - Hooks: `F:\working-project\hooks\`

## Access Protocol
1. **Path Format**: Always use absolute paths starting with `F:/working-project/` (forward slashes are preferred for tool calls).
2. **Verification**: If a file is reported missing, execute `ls -R` on the parent directory before reporting failure.
3. **Permission**: The Agent has full read/write access to the `F:\working-project` tree.
