# dbt DAG Navigator

An MCP (Model Context Protocol) server that enables LLMs to efficiently navigate dbt DAGs by indexing manifest.json and catalog.json files. This solves the problem of these files being too large (catalog can be 10MB+) to parse in regular workflows.

## Why This Exists

dbt projects generate `manifest.json` and `catalog.json` files that contain complete metadata about your data models, but:

- **They're huge**: Catalog files can be 10MB+ of text
- **Not LLM-friendly**: Too large to include in context windows
- **Slow to parse**: Searching through them in real-time is inefficient

This MCP server solves these problems by:

1. **Pre-indexing** the DAG structure for instant lookups
2. **Providing structured tools** for common queries
3. **Caching** the parsed data in memory for fast access
4. **Exposing efficient APIs** for upstream/downstream navigation and column lineage

## Features

### Core Capabilities

- **Upstream Dependencies**: Find all models and sources that a given model depends on (direct and transitive)
- **Downstream Dependencies**: Identify all models that depend on a given model
- **Column Lineage**: Check if a column is used in any downstream models
- **Model Search**: Search models by name, description, or tags
- **Model Details**: Get comprehensive information about a specific model
- **Fast Indexing**: Pre-processes large files into efficient in-memory data structures

### Inspired By

This project draws inspiration from [dbt-kg](https://github.com/ponderedw/dbt-kg), which creates knowledge graphs from dbt metadata using FalkorDB/Neo4j. While dbt-kg uses a graph database approach, this MCP server provides a lightweight, zero-dependency alternative optimized for LLM interaction.

## Installation

### Prerequisites

- Python 3.10 or higher
- An MCP-compatible client (like Claude Desktop, or any tool that supports MCP)

### Install from Source

```bash
cd dag_navigator
pip install -e .
```

Or install dependencies directly:

```bash
pip install -r requirements.txt
```

## Configuration

### For Claude Desktop

Add this to your Claude Desktop MCP configuration file:

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "dbt-dag-navigator": {
      "command": "python",
      "args": [
        "/absolute/path/to/dag_navigator/server.py"
      ]
    }
  }
}
```

### For Other MCP Clients

Use the `mcp_config.json` template provided in this directory as a starting point.

## Usage

### Quick Start

Once configured in your MCP client, you can ask questions like:

1. **Load your dbt project**:
   ```
   Load the dbt DAG from /path/to/dbt/project/target/manifest.json
   ```

2. **Explore dependencies**:
   ```
   What are all the models upstream of customer_orders_summary?
   ```

3. **Check column usage**:
   ```
   Is the email column in the customers model used downstream?
   ```

4. **Search for models**:
   ```
   Find all models related to "orders"
   ```

### Available Tools

The MCP server exposes these tools:

#### 1. `load_dbt_dag`

Load and index dbt manifest and catalog files.

**Parameters**:
- `manifest_path` (required): Path to manifest.json
- `catalog_path` (optional): Path to catalog.json

**Example**:
```json
{
  "manifest_path": "/path/to/target/manifest.json",
  "catalog_path": "/path/to/target/catalog.json"
}
```

#### 2. `get_upstream_models`

Get all upstream dependencies of a model.

**Parameters**:
- `model_name` (required): Name of the model
- `include_sources` (optional): Include source tables (default: true)

**Example**:
```json
{
  "model_name": "customer_orders_summary",
  "include_sources": true
}
```

**Returns**:
```json
{
  "model": "customer_orders_summary",
  "direct_upstream": ["model.sample_project.customers", "model.sample_project.orders"],
  "all_upstream": ["model.sample_project.customers", "model.sample_project.orders", "source.sample_project.raw_db.raw_customers", "source.sample_project.raw_db.raw_orders"],
  "upstream_models": [
    {
      "id": "model.sample_project.customers",
      "name": "customers",
      "schema": "production"
    },
    {
      "id": "model.sample_project.orders",
      "name": "orders",
      "schema": "production"
    }
  ],
  "upstream_sources": [...]
}
```

#### 3. `get_downstream_models`

Get all downstream dependencies of a model.

**Parameters**:
- `model_name` (required): Name of the model

**Example**:
```json
{
  "model_name": "customers"
}
```

#### 4. `check_column_usage`

Check if a column is used in downstream models.

**Parameters**:
- `model_name` (required): Name of the model
- `column_name` (required): Name of the column

**Example**:
```json
{
  "model_name": "customers",
  "column_name": "email"
}
```

**Returns**:
```json
{
  "model": "customers",
  "column": "email",
  "used_in": [
    {
      "model": "customer_orders_summary",
      "id": "model.sample_project.customer_orders_summary"
    }
  ],
  "potentially_used_in": []
}
```

#### 5. `search_models`

Search for models by name, description, or tags.

**Parameters**:
- `query` (required): Search query
- `search_descriptions` (optional): Include descriptions in search (default: true)

**Example**:
```json
{
  "query": "customer",
  "search_descriptions": true
}
```

#### 6. `get_model_details`

Get detailed information about a model.

**Parameters**:
- `model_name` (required): Name of the model

**Example**:
```json
{
  "model_name": "customers"
}
```

#### 7. `list_models`

List all models in the DAG.

**Parameters**:
- `limit` (optional): Maximum number of models to return (default: 50)

**Example**:
```json
{
  "limit": 20
}
```

## Example Queries

Here are some practical questions you can ask an LLM using this MCP server:

### Dependency Analysis

- "What models are upstream of `customer_orders_summary`?"
- "Show me everything that depends on the `customers` model"
- "What's the full dependency chain for `product_sales_summary`?"

### Column Lineage

- "Is the `email` column in `customers` used anywhere downstream?"
- "What downstream models reference the `customer_id` column?"
- "Can I safely remove the `status` column from `orders`?"

### Model Discovery

- "Find all models tagged with `pii`"
- "What models are related to customer data?"
- "Show me all reporting models"

### Impact Analysis

- "If I change the `customers` model, what will be affected?"
- "What's the blast radius of modifying `products`?"
- "Show me all models that would need to be rebuilt if `orders` changes"

## Architecture

### How It Works

1. **Loading Phase**:
   - Reads manifest.json and catalog.json files
   - Extracts model metadata, dependencies, and column information
   - Builds efficient lookup indexes

2. **Indexing Phase**:
   - Creates upstream/downstream dependency maps
   - Indexes models by name for fast lookups
   - Maps column information from catalog

3. **Query Phase**:
   - Uses BFS/DFS for transitive dependency resolution
   - Provides O(1) lookups for direct dependencies
   - Returns structured JSON responses

### Performance

- **Initial Load**: ~1-2 seconds for large projects (1000+ models)
- **Queries**: <100ms for most operations
- **Memory**: Typically 10-50MB for indexed data (much smaller than original files)

### Comparison with dbt-kg

| Feature | dbt DAG Navigator (This) | dbt-kg |
|---------|-------------------------|--------|
| **Approach** | In-memory indexing | Graph database (FalkorDB/Neo4j) |
| **Setup** | Zero dependencies | Requires database setup |
| **Query Speed** | <100ms | Varies (database dependent) |
| **LLM Integration** | Native MCP support | Streamlit UI + LLM APIs |
| **Use Case** | Quick queries, LLM agents | Complex graph analysis, visualization |
| **Deployment** | Lightweight, standalone | Requires infrastructure |

## Development

### Running Tests

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html
```

### Code Formatting

```bash
# Format code
black .

# Lint
ruff check .
```

## Sample Data

The `examples/` directory contains sample manifest and catalog files for testing. These represent a typical e-commerce data model with:

- 6 models: customers, orders, order_items, products, customer_orders_summary, product_sales_summary
- 4 sources: raw_customers, raw_orders, raw_order_items, raw_products
- Realistic dependency relationships
- Column metadata and descriptions

## Troubleshooting

### "DAG not indexed" Error

Make sure to call `load_dbt_dag` first before running other queries:

```
Load the dbt DAG from /path/to/manifest.json
```

### "Model not found" Error

The model name search is case-insensitive and supports partial matching. If you're still getting errors:

1. List all models: "List all available models"
2. Check the exact model name in the list
3. Try searching: "Search for models with 'customer' in the name"

### Performance Issues

For very large projects (2000+ models):

1. Consider loading only the manifest (skip catalog) for faster initialization
2. Use the `limit` parameter in `list_models` to reduce response size
3. Be specific in searches to reduce result sets

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

MIT License - see LICENSE file for details

## Future Enhancements

Potential improvements:

- [ ] Support for exposures and metrics
- [ ] Test coverage analysis
- [ ] Semantic layer integration
- [ ] Column-level lineage tracking
- [ ] Incremental model impact analysis
- [ ] Performance profiling integration
- [ ] Support for dbt Cloud APIs
- [ ] Caching layer for very large projects
- [ ] GraphQL-style query interface

## Related Projects

- [dbt-kg](https://github.com/ponderedw/dbt-kg) - Knowledge graph approach using FalkorDB
- [dbt-core](https://github.com/dbt-labs/dbt-core) - The dbt transformation workflow tool
- [MCP](https://modelcontextprotocol.io) - Model Context Protocol specification

## Support

For issues, questions, or contributions, please open an issue on GitHub.
