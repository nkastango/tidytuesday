# Using dbt DAG Navigator as a Claude Code Skill

While this tool is primarily designed as an MCP server, you can also use it directly within Claude Code sessions as a Python module.

## Quick Integration

### Option 1: Direct Python Import

```python
from dag_navigator import DbtDagNavigator

# Initialize and load
navigator = DbtDagNavigator()
result = navigator.load_and_index(
    "/path/to/manifest.json",
    "/path/to/catalog.json"
)

# Query the DAG
upstream = navigator.get_upstream_models("my_model")
downstream = navigator.get_downstream_models("my_model")
column_usage = navigator.check_column_usage("my_model", "my_column")
```

### Option 2: As an MCP Tool

Configure the server in your MCP client and use it via the Model Context Protocol for the best LLM experience.

## Creating a Custom Claude Code Skill

You can wrap this in a Claude Code skill for your project:

**File**: `.claude/skills/dbt-navigator.md`

```markdown
# dbt DAG Navigator

This skill helps navigate the dbt DAG efficiently.

## Setup

Load the DAG first:
```python
from dag_navigator import DbtDagNavigator

navigator = DbtDagNavigator()
navigator.load_and_index("target/manifest.json", "target/catalog.json")
```

## Available Commands

- Get upstream: `navigator.get_upstream_models("model_name")`
- Get downstream: `navigator.get_downstream_models("model_name")`
- Check column: `navigator.check_column_usage("model_name", "column_name")`
- Search: `navigator.search_models("query")`
- Details: `navigator.get_model_details("model_name")`

## Example Questions

- "What models are upstream of customer_summary?"
- "Is the email column used downstream?"
- "Show me all reporting models"
```

## Integration with dbt Projects

Add this to your dbt project's `.claude/` directory to make it automatically available:

**File**: `<your-dbt-project>/.claude/skills/dag-navigator.md`

```markdown
# dbt DAG Navigator Skill

Navigate this dbt project's DAG efficiently.

## Auto-load DAG

When asked about model dependencies or lineage:

1. Import the navigator
2. Load from `target/manifest.json` and `target/catalog.json`
3. Answer the question using the appropriate method

## Common Patterns

### Dependency Analysis
```python
# Full dependency tree
upstream = navigator.get_upstream_models("model_name", include_sources=True)
downstream = navigator.get_downstream_models("model_name")
```

### Impact Analysis
```python
# What changes if I modify this model?
downstream = navigator.get_downstream_models("model_name")
print(f"Impact: {len(downstream['all_downstream'])} models affected")
```

### Column Lineage
```python
# Is this column used?
usage = navigator.check_column_usage("model_name", "column_name")
if usage['used_in']:
    print("Column is used in:", [m['model'] for m in usage['used_in']])
else:
    print("Column is not used downstream - safe to remove")
```

## Remember

- Always load the DAG first
- Model names are case-insensitive
- Search supports partial matching
- Results include both direct and transitive dependencies
```

## Session Hook Example

You can also add this to your session start hook to auto-load the navigator:

**File**: `<your-dbt-project>/.claude/hooks/session-start.sh`

```bash
#!/bin/bash

# Ensure manifest is up to date
echo "Compiling dbt project for DAG navigation..."
dbt compile --quiet

echo "dbt DAG Navigator ready!"
echo "Available at target/manifest.json and target/catalog.json"
```

Then in Python:

```python
# This will already be compiled from the session start hook
from dag_navigator import DbtDagNavigator

nav = DbtDagNavigator()
nav.load_and_index("target/manifest.json", "target/catalog.json")
```

## Benefits of This Approach

1. **No external services**: Everything runs locally
2. **Fast**: In-memory indexing for quick queries
3. **Integrated**: Works directly in your Claude Code workflow
4. **Offline**: No need for database or network connections

## When to Use MCP vs. Direct Import

### Use MCP Server When:
- You want the best LLM experience
- Working with multiple clients (Claude Desktop, other tools)
- Want automatic tool discovery
- Need standardized interface

### Use Direct Import When:
- Quick scripting or automation
- Custom Python workflows
- Integrating into existing tools
- Want more control over the API

## Example Workflow

```python
#!/usr/bin/env python3
"""
Example: Analyze impact of removing a column
"""
from dag_navigator import DbtDagNavigator

def can_remove_column(model_name: str, column_name: str) -> bool:
    """Check if it's safe to remove a column."""
    nav = DbtDagNavigator()
    nav.load_and_index("target/manifest.json", "target/catalog.json")

    usage = nav.check_column_usage(model_name, column_name)

    if usage['used_in'] or usage['potentially_used_in']:
        print(f"❌ Cannot remove {column_name} from {model_name}")
        print(f"   Used in: {[m['model'] for m in usage['used_in']]}")
        return False
    else:
        print(f"✅ Safe to remove {column_name} from {model_name}")
        return True

if __name__ == "__main__":
    can_remove_column("customers", "email")
```
