---
description: Validate project skills using the agentskills standard
---

This workflow sets up the `agentskills` reference implementation and runs the validator on the current project's `skills/` directory.

## Prerequisites
- Python 3.9+
- Activated virtual environment (recommended)

## Steps

1. **Clone Agentskills Repo** (if not present)
   ```bash
   # Clone to a temporary or utility location
   git clone https://github.com/agentskills/agentskills.git tools/agentskills
   ```

2. **Install skills-ref**
   ```bash
   # Note: Patch pyproject.toml if on Python < 3.11 (see research notes)
   pip install ./tools/agentskills/skills-ref
   ```

3. **Run Validation**
   // turbo
   ```bash
   if [ -d "skills" ]; then
       echo "Validating skills directory..."
       for d in skills/*; do
           if [ -d "$d" ]; then
               echo ">>> Validating $(basename "$d")"
               skills-ref validate "$d"
               echo "<<<"
           fi
       done
   else
       echo "No 'skills/' directory found in project root."
   fi
   ```
