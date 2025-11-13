#!/usr/bin/env python3
"""
dbt DAG Navigator MCP Server

An MCP server that provides fast, efficient navigation of dbt DAGs by indexing
manifest.json and catalog.json files. Enables LLMs to quickly answer questions
about model dependencies, column lineage, and more.
"""

import json
import logging
from pathlib import Path
from typing import Any, Optional
from collections import defaultdict

import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("dbt-dag-navigator")


class DbtDagNavigator:
    """Efficiently navigates dbt DAG using indexed manifest and catalog data."""

    def __init__(self):
        self.manifest: Optional[dict] = None
        self.catalog: Optional[dict] = None
        self.upstream_map: dict[str, set[str]] = defaultdict(set)
        self.downstream_map: dict[str, set[str]] = defaultdict(set)
        self.column_map: dict[str, dict] = {}
        self.models: dict[str, dict] = {}
        self.sources: dict[str, dict] = {}
        self.indexed = False

    def load_and_index(self, manifest_path: str, catalog_path: Optional[str] = None) -> dict:
        """Load and index dbt manifest and catalog files."""
        try:
            # Load manifest
            manifest_file = Path(manifest_path)
            if not manifest_file.exists():
                return {"success": False, "error": f"Manifest file not found: {manifest_path}"}

            with open(manifest_file, 'r') as f:
                self.manifest = json.load(f)

            # Load catalog if provided
            if catalog_path:
                catalog_file = Path(catalog_path)
                if catalog_file.exists():
                    with open(catalog_file, 'r') as f:
                        self.catalog = json.load(f)
                else:
                    logger.warning(f"Catalog file not found: {catalog_path}")

            # Index the data
            self._build_indexes()
            self.indexed = True

            return {
                "success": True,
                "models_count": len(self.models),
                "sources_count": len(self.sources),
                "catalog_loaded": self.catalog is not None
            }

        except Exception as e:
            logger.error(f"Error loading files: {e}")
            return {"success": False, "error": str(e)}

    def _build_indexes(self):
        """Build efficient indexes for fast querying."""
        if not self.manifest:
            return

        # Index models
        for node_id, node_data in self.manifest.get('nodes', {}).items():
            if node_data.get('resource_type') in ['model', 'snapshot']:
                self.models[node_id] = {
                    'name': node_data.get('name'),
                    'schema': node_data.get('schema'),
                    'database': node_data.get('database'),
                    'description': node_data.get('description', ''),
                    'tags': node_data.get('tags', []),
                    'materialized': node_data.get('config', {}).get('materialized'),
                    'columns': node_data.get('columns', {}),
                    'depends_on': node_data.get('depends_on', {})
                }

                # Build dependency maps
                depends_on_nodes = node_data.get('depends_on', {}).get('nodes', [])
                for dep in depends_on_nodes:
                    self.upstream_map[node_id].add(dep)
                    self.downstream_map[dep].add(node_id)

        # Index sources
        for source_id, source_data in self.manifest.get('sources', {}).items():
            self.sources[source_id] = {
                'name': source_data.get('name'),
                'source_name': source_data.get('source_name'),
                'schema': source_data.get('schema'),
                'database': source_data.get('database'),
                'description': source_data.get('description', ''),
                'columns': source_data.get('columns', {})
            }

        # Index catalog columns if available
        if self.catalog:
            for node_id, node_data in self.catalog.get('nodes', {}).items():
                columns = node_data.get('columns', {})
                self.column_map[node_id] = {}
                for col_name, col_data in columns.items():
                    self.column_map[node_id][col_name.lower()] = {
                        'type': col_data.get('type'),
                        'comment': col_data.get('comment', ''),
                        'index': col_data.get('index')
                    }

    def get_upstream_models(self, model_name: str, include_sources: bool = True) -> dict:
        """Get all upstream dependencies of a model."""
        if not self.indexed:
            return {"error": "DAG not indexed. Load manifest first."}

        # Find the model
        node_id = self._find_model_id(model_name)
        if not node_id:
            return {"error": f"Model not found: {model_name}"}

        # Get all upstream dependencies (transitive)
        upstream = self._get_transitive_deps(node_id, self.upstream_map)

        result = {
            "model": model_name,
            "direct_upstream": list(self.upstream_map.get(node_id, set())),
            "all_upstream": list(upstream),
            "upstream_models": [],
            "upstream_sources": []
        }

        # Categorize upstream nodes
        for dep_id in upstream:
            if dep_id in self.models:
                result["upstream_models"].append({
                    "id": dep_id,
                    "name": self.models[dep_id]['name'],
                    "schema": self.models[dep_id]['schema']
                })
            elif dep_id in self.sources and include_sources:
                result["upstream_sources"].append({
                    "id": dep_id,
                    "name": self.sources[dep_id]['name'],
                    "source": self.sources[dep_id]['source_name'],
                    "schema": self.sources[dep_id]['schema']
                })

        return result

    def get_downstream_models(self, model_name: str) -> dict:
        """Get all downstream dependencies of a model."""
        if not self.indexed:
            return {"error": "DAG not indexed. Load manifest first."}

        node_id = self._find_model_id(model_name)
        if not node_id:
            return {"error": f"Model not found: {model_name}"}

        # Get all downstream dependencies (transitive)
        downstream = self._get_transitive_deps(node_id, self.downstream_map)

        result = {
            "model": model_name,
            "direct_downstream": list(self.downstream_map.get(node_id, set())),
            "all_downstream": list(downstream),
            "downstream_models": []
        }

        # Get model details
        for dep_id in downstream:
            if dep_id in self.models:
                result["downstream_models"].append({
                    "id": dep_id,
                    "name": self.models[dep_id]['name'],
                    "schema": self.models[dep_id]['schema']
                })

        return result

    def check_column_usage(self, model_name: str, column_name: str) -> dict:
        """Check if a column is used in downstream models."""
        if not self.indexed:
            return {"error": "DAG not indexed. Load manifest first."}

        node_id = self._find_model_id(model_name)
        if not node_id:
            return {"error": f"Model not found: {model_name}"}

        # Get downstream models
        downstream = self._get_transitive_deps(node_id, self.downstream_map)

        result = {
            "model": model_name,
            "column": column_name,
            "used_in": [],
            "potentially_used_in": []
        }

        col_lower = column_name.lower()

        # Check each downstream model for column references
        for dep_id in downstream:
            if dep_id not in self.models:
                continue

            model_info = self.models[dep_id]

            # Check if column is explicitly defined in downstream model
            downstream_cols = model_info.get('columns', {})
            if any(col_lower == c.lower() for c in downstream_cols.keys()):
                result["used_in"].append({
                    "model": model_info['name'],
                    "id": dep_id
                })

            # Check catalog data if available
            if self.catalog and dep_id in self.column_map:
                if col_lower in self.column_map[dep_id]:
                    if dep_id not in [m['id'] for m in result["used_in"]]:
                        result["potentially_used_in"].append({
                            "model": model_info['name'],
                            "id": dep_id
                        })

        return result

    def search_models(self, query: str, search_descriptions: bool = True) -> dict:
        """Search for models by name, description, or tags."""
        if not self.indexed:
            return {"error": "DAG not indexed. Load manifest first."}

        query_lower = query.lower()
        results = []

        for node_id, model_data in self.models.items():
            score = 0
            matches = []

            # Check name
            if query_lower in model_data['name'].lower():
                score += 10
                matches.append("name")

            # Check tags
            if any(query_lower in tag.lower() for tag in model_data.get('tags', [])):
                score += 5
                matches.append("tags")

            # Check description
            if search_descriptions and query_lower in model_data.get('description', '').lower():
                score += 3
                matches.append("description")

            if score > 0:
                results.append({
                    "id": node_id,
                    "name": model_data['name'],
                    "schema": model_data['schema'],
                    "description": model_data['description'][:200],
                    "materialized": model_data['materialized'],
                    "matches": matches,
                    "score": score
                })

        # Sort by score
        results.sort(key=lambda x: x['score'], reverse=True)

        return {
            "query": query,
            "count": len(results),
            "results": results[:20]  # Limit to top 20
        }

    def get_model_details(self, model_name: str) -> dict:
        """Get detailed information about a model."""
        if not self.indexed:
            return {"error": "DAG not indexed. Load manifest first."}

        node_id = self._find_model_id(model_name)
        if not node_id:
            return {"error": f"Model not found: {model_name}"}

        model_data = self.models[node_id]
        result = {
            "id": node_id,
            "name": model_data['name'],
            "schema": model_data['schema'],
            "database": model_data['database'],
            "description": model_data['description'],
            "materialized": model_data['materialized'],
            "tags": model_data['tags'],
            "columns": []
        }

        # Add column information
        columns = model_data.get('columns', {})
        for col_name, col_data in columns.items():
            col_info = {
                "name": col_name,
                "description": col_data.get('description', '')
            }

            # Add catalog data if available
            if node_id in self.column_map and col_name.lower() in self.column_map[node_id]:
                catalog_col = self.column_map[node_id][col_name.lower()]
                col_info["type"] = catalog_col.get('type')
                col_info["comment"] = catalog_col.get('comment')

            result["columns"].append(col_info)

        # Add dependency counts
        result["direct_upstream_count"] = len(self.upstream_map.get(node_id, set()))
        result["direct_downstream_count"] = len(self.downstream_map.get(node_id, set()))

        return result

    def list_models(self, limit: int = 50) -> dict:
        """List all models in the DAG."""
        if not self.indexed:
            return {"error": "DAG not indexed. Load manifest first."}

        models = []
        for node_id, model_data in list(self.models.items())[:limit]:
            models.append({
                "id": node_id,
                "name": model_data['name'],
                "schema": model_data['schema'],
                "materialized": model_data['materialized']
            })

        return {
            "total_count": len(self.models),
            "returned_count": len(models),
            "models": models
        }

    def _find_model_id(self, model_name: str) -> Optional[str]:
        """Find a model ID by name (case-insensitive)."""
        model_lower = model_name.lower()

        # Try exact match first
        for node_id, model_data in self.models.items():
            if model_data['name'].lower() == model_lower:
                return node_id

        # Try partial match
        for node_id, model_data in self.models.items():
            if model_lower in model_data['name'].lower():
                return node_id

        return None

    def _get_transitive_deps(self, node_id: str, dep_map: dict[str, set[str]]) -> set[str]:
        """Get all transitive dependencies using BFS."""
        visited = set()
        queue = [node_id]

        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)

            for dep in dep_map.get(current, set()):
                if dep not in visited:
                    queue.append(dep)

        # Remove the starting node
        visited.discard(node_id)
        return visited


# Initialize the navigator
navigator = DbtDagNavigator()

# Create MCP server
app = Server("dbt-dag-navigator")


@app.list_tools()
async def list_tools() -> list[types.Tool]:
    """List available tools."""
    return [
        types.Tool(
            name="load_dbt_dag",
            description="Load and index dbt manifest.json and catalog.json files for fast querying",
            inputSchema={
                "type": "object",
                "properties": {
                    "manifest_path": {
                        "type": "string",
                        "description": "Path to the manifest.json file"
                    },
                    "catalog_path": {
                        "type": "string",
                        "description": "Optional path to the catalog.json file"
                    }
                },
                "required": ["manifest_path"]
            }
        ),
        types.Tool(
            name="get_upstream_models",
            description="Get all upstream dependencies of a dbt model (direct and transitive)",
            inputSchema={
                "type": "object",
                "properties": {
                    "model_name": {
                        "type": "string",
                        "description": "Name of the model"
                    },
                    "include_sources": {
                        "type": "boolean",
                        "description": "Include source tables in results (default: true)"
                    }
                },
                "required": ["model_name"]
            }
        ),
        types.Tool(
            name="get_downstream_models",
            description="Get all downstream dependencies of a dbt model (models that depend on this one)",
            inputSchema={
                "type": "object",
                "properties": {
                    "model_name": {
                        "type": "string",
                        "description": "Name of the model"
                    }
                },
                "required": ["model_name"]
            }
        ),
        types.Tool(
            name="check_column_usage",
            description="Check if a column is used in any downstream models",
            inputSchema={
                "type": "object",
                "properties": {
                    "model_name": {
                        "type": "string",
                        "description": "Name of the model"
                    },
                    "column_name": {
                        "type": "string",
                        "description": "Name of the column to check"
                    }
                },
                "required": ["model_name", "column_name"]
            }
        ),
        types.Tool(
            name="search_models",
            description="Search for dbt models by name, description, or tags",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query"
                    },
                    "search_descriptions": {
                        "type": "boolean",
                        "description": "Include descriptions in search (default: true)"
                    }
                },
                "required": ["query"]
            }
        ),
        types.Tool(
            name="get_model_details",
            description="Get detailed information about a specific dbt model",
            inputSchema={
                "type": "object",
                "properties": {
                    "model_name": {
                        "type": "string",
                        "description": "Name of the model"
                    }
                },
                "required": ["model_name"]
            }
        ),
        types.Tool(
            name="list_models",
            description="List all models in the dbt DAG",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "number",
                        "description": "Maximum number of models to return (default: 50)"
                    }
                }
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[types.TextContent]:
    """Handle tool calls."""
    try:
        if name == "load_dbt_dag":
            result = navigator.load_and_index(
                arguments["manifest_path"],
                arguments.get("catalog_path")
            )
        elif name == "get_upstream_models":
            result = navigator.get_upstream_models(
                arguments["model_name"],
                arguments.get("include_sources", True)
            )
        elif name == "get_downstream_models":
            result = navigator.get_downstream_models(arguments["model_name"])
        elif name == "check_column_usage":
            result = navigator.check_column_usage(
                arguments["model_name"],
                arguments["column_name"]
            )
        elif name == "search_models":
            result = navigator.search_models(
                arguments["query"],
                arguments.get("search_descriptions", True)
            )
        elif name == "get_model_details":
            result = navigator.get_model_details(arguments["model_name"])
        elif name == "list_models":
            result = navigator.list_models(arguments.get("limit", 50))
        else:
            result = {"error": f"Unknown tool: {name}"}

        return [types.TextContent(
            type="text",
            text=json.dumps(result, indent=2)
        )]

    except Exception as e:
        logger.error(f"Error executing tool {name}: {e}")
        return [types.TextContent(
            type="text",
            text=json.dumps({"error": str(e)})
        )]


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
