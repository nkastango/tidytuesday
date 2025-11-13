# Usage Examples

This document provides detailed examples of how to use the dbt DAG Navigator MCP server.

## Setup

Before running these examples, make sure you've:

1. Installed the dependencies: `pip install -r requirements.txt`
2. Configured your MCP client to use this server (see README.md)
3. Have access to your dbt project's `manifest.json` and `catalog.json` files

## Example Conversations

### Example 1: Understanding Model Dependencies

**User**: "I need to understand the dependencies for my customer_orders_summary model. Can you help?"

**Assistant**: *Uses `load_dbt_dag` first if not already loaded*

*Then uses `get_upstream_models` with model_name="customer_orders_summary"*

**Response**: "The `customer_orders_summary` model has the following dependencies:

**Direct upstream models**:
- `customers` - Customer dimension table
- `orders` - Orders fact table

**All upstream dependencies** (including sources):
- `customers` model
- `orders` model
- `raw_customers` source
- `raw_orders` source

This model pulls customer information and aggregates their order data to create summary metrics."

### Example 2: Impact Analysis

**User**: "I need to make changes to the customers table. What will be impacted?"

**Assistant**: *Uses `get_downstream_models` with model_name="customers"*

**Response**: "Changing the `customers` model will impact:

**Direct downstream models** (1 hop):
- `orders` - Orders fact table
- `customer_orders_summary` - Customer order metrics

**All downstream models** (transitive):
- `orders`
- `customer_orders_summary`
- `order_items` (depends on orders)
- `product_sales_summary` (depends on order_items)

Total impact: 4 models will need to be rebuilt or tested after your changes."

### Example 3: Column Lineage

**User**: "Can I safely remove the 'email' column from the customers model? Is it used downstream?"

**Assistant**: *Uses `check_column_usage` with model_name="customers" and column_name="email"*

**Response**: "The `email` column from the `customers` model IS used downstream:

**Used in**:
- `customer_orders_summary` - This reporting model includes the email column

**Recommendation**: You should NOT remove this column as it's actively used in the `customer_orders_summary` model. If you need to remove it, you'll need to update that downstream model first."

### Example 4: Finding Models

**User**: "What models do we have related to products?"

**Assistant**: *Uses `search_models` with query="product"*

**Response**: "I found 2 models related to 'product':

1. **products** (production.products)
   - Type: table
   - Description: Product dimension table
   - Tags: dimension

2. **product_sales_summary** (production.product_sales_summary)
   - Type: view
   - Description: Summary of product sales metrics
   - Tags: reporting, dashboard"

### Example 5: Exploring Model Details

**User**: "Tell me more about the product_sales_summary model"

**Assistant**: *Uses `get_model_details` with model_name="product_sales_summary"*

**Response**: "Here are the details for `product_sales_summary`:

**Basic Info**:
- Database: analytics
- Schema: production
- Materialization: view
- Tags: reporting, dashboard

**Description**: Summary of product sales metrics

**Columns**:
- `product_id` (integer) - Product identifier
- `product_name` (varchar) - Product name
- `category` (varchar) - Product category
- `total_quantity_sold` (bigint) - Total quantity sold
- `total_revenue` (numeric) - Total revenue from product

**Dependencies**:
- Direct upstream: 2 models
- Direct downstream: 0 models

This is a reporting view that aggregates product sales data."

### Example 6: Understanding Data Flow

**User**: "How does data flow from raw sources to the product_sales_summary?"

**Assistant**: *Uses `get_upstream_models` with model_name="product_sales_summary" and include_sources=true*

**Response**: "Here's the data flow to `product_sales_summary`:

```
raw_products (source)
    ↓
products (table)
    ↓
    → order_items (table) ← orders ← customers ← raw_customers (source)
                               ↑
                         raw_orders (source)
                               ↑
                         raw_order_items (source)
    ↓
product_sales_summary (view)
```

**Flow explanation**:
1. Raw product data comes from `raw_products` source
2. Transformed into `products` dimension table
3. Combined with `order_items` which contains sales transactions
4. Aggregated in `product_sales_summary` to show total quantity and revenue per product

The model has 2 direct dependencies and 4 total upstream dependencies (including sources)."

## Common Workflows

### Workflow 1: Refactoring a Model

When you need to refactor a model, use this sequence:

```
1. "Show me the details for [model_name]"
   → Understand the current structure

2. "What models depend on [model_name]?"
   → Identify what will be affected

3. "Is the [column_name] column used downstream?"
   → Check if you can safely remove columns

4. "What are the upstream dependencies of [model_name]?"
   → Understand data sources
```

### Workflow 2: Adding a New Column

```
1. "What models are downstream of [model_name]?"
   → See what might benefit from the new column

2. "Show me models tagged with 'reporting'"
   → Find reporting models that might need the column

3. "Get details for [downstream_model]"
   → Check if the column would be useful there
```

### Workflow 3: Debugging a Model

```
1. "Show me all upstream dependencies of [failing_model]"
   → Check what feeds into it

2. "Get details for [upstream_model]"
   → Review column definitions

3. "Is [expected_column] used in [failing_model]?"
   → Verify column availability
```

### Workflow 4: Documentation Audit

```
1. "List all models"
   → Get an overview

2. "Search for models with [keyword]"
   → Find specific model groups

3. For each model: "Get details for [model_name]"
   → Review descriptions and column documentation
```

## Advanced Queries

### Understanding Model Layers

**Query**: "What models are in the reporting layer (materialized as views with 'reporting' tag)?"

**Approach**:
1. Search for "reporting" tag
2. Get details for each to confirm materialization type

### Finding Circular Dependencies

**Query**: "Are there any circular dependencies in the DAG?"

**Approach**: The navigator's transitive dependency resolution will handle this, but you can check by:
1. Getting upstream of a model
2. Getting downstream of same model
3. Checking for overlap

### Column Propagation Analysis

**Query**: "Trace the 'customer_id' column from raw sources to final reports"

**Approach**:
1. Find models with 'customer' in name
2. Get upstream deps for each
3. Check column usage at each level

## Tips for Effective Use

### 1. Start Broad, Then Narrow

```
Bad:  "Is column X in model Y used in model Z?"
Good: "What are all downstream uses of column X in model Y?"
      (Then drill into specific models)
```

### 2. Use Search First

```
Bad:  "Get details for stg_customers"
      (Might not exist with that exact name)

Good: "Search for models with 'customer' in the name"
      (Find the exact name first)
```

### 3. Leverage Tags

```
"Search for models tagged with 'pii'"
"Find all 'staging' models"
"Show me 'incremental' models"
```

### 4. Combine Multiple Queries

```
1. Search to find models
2. Get details to understand structure
3. Check dependencies to see relationships
4. Verify column usage before making changes
```

## Sample Questions to Ask

### Dependency Questions
- "What are all the models that depend on [model]?"
- "Show me the complete dependency chain for [model]"
- "What sources feed into [model]?"
- "If I change [model], what else needs to be updated?"

### Column Questions
- "Is [column] in [model] used anywhere?"
- "What downstream models use the [column] column?"
- "Can I remove [column] from [model]?"
- "Where does [column] come from?"

### Discovery Questions
- "What models do we have for customer data?"
- "Show me all incremental models"
- "What models are tagged as PII?"
- "List all models in the [schema] schema"

### Analysis Questions
- "What's the most complex model (most dependencies)?"
- "Which models have no downstream dependencies?"
- "What are the leaf nodes in our DAG?"
- "Show me all staging models"

## Troubleshooting

### "Model not found" Errors

Try:
1. "List all models" - to see what's available
2. "Search for [partial_name]" - to find similar models
3. Check spelling and exact model name

### Slow Queries

For very large projects:
1. Load manifest without catalog first
2. Use specific model names rather than "list all"
3. Be selective about including sources

### Unexpected Results

1. Verify the manifest.json is up to date (run `dbt compile` or `dbt run`)
2. Check that both manifest and catalog are from the same dbt run
3. Reload the DAG if files have been updated

## Integration with Development Workflow

### In Development
```bash
# After making changes to models
dbt compile

# Ask the LLM:
"Reload the DAG from /path/to/target/manifest.json"
"What models are affected by my changes to [model]?"
```

### In Code Review
```
# Reviewer asks:
"What's the impact of changing [model] in this PR?"
"Are any columns being removed that are used downstream?"
"What tests should we run to verify these changes?"
```

### In Production Planning
```
# Before deployment:
"Show me all models that depend on [changed_model]"
"What's the rebuild order for these changes?"
"Which models need their tests updated?"
```
