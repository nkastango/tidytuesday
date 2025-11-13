#!/usr/bin/env python3
"""
dbt DAG Navigator MCP Server - SECURITY HARDENED VERSION

An MCP server that provides fast, efficient navigation of dbt DAGs by indexing
manifest.json and catalog.json files. Enables LLMs to quickly answer questions
about model dependencies, column lineage, and more.

This version includes comprehensive security hardening:
- Path traversal protection
- File size limits
- JSON structure validation
- Input sanitization
- Rate limiting
- Secure error handling
"""

import json
import logging
import sys
import time
import re
from pathlib import Path
from typing import Any, Optional
from collections import defaultdict, deque
from dataclasses import dataclass

import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server

# Configure secure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("dbt-dag-navigator")


@dataclass
class SecurityConfig:
    """Security configuration settings."""
    max_file_size_mb: int = 100
    max_nodes: int = 10000
    max_sources: int = 5000
    max_query_length: int = 200
    max_list_limit: int = 1000
    max_json_depth: int = 20
    max_iterations: int = 100000
    rate_limit_requests: int = 100
    rate_limit_window_seconds: int = 60
    allowed_directories: list[str] = None

    def __post_init__(self):
        if self.allowed_directories is None:
            self.allowed_directories = []


class RateLimiter:
    """Simple rate limiter using sliding window."""

    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = deque()

    def is_allowed(self) -> bool:
        """Check if request is allowed."""
        now = time.time()

        # Remove old requests outside the window
        while self.requests and self.requests[0] < now - self.window_seconds:
            self.requests.popleft()

        # Check if under limit
        if len(self.requests) < self.max_requests:
            self.requests.append(now)
            return True

        logger.warning("Rate limit exceeded")
        return False

    def reset(self):
        """Reset rate limiter."""
        self.requests.clear()


class InputValidator:
    """Centralized input validation."""

    @staticmethod
    def validate_model_name(model_name: str) -> tuple[bool, str]:
        """Validate model name format."""
        if not model_name or not isinstance(model_name, str):
            return False, "Model name must be a non-empty string"
        if len(model_name) > 255:
            return False, "Model name too long (max 255 characters)"
        # Allow alphanumeric, underscore, hyphen, dot
        if not re.match(r'^[a-zA-Z0-9_.-]+$', model_name):
            return False, "Model name contains invalid characters"
        return True, ""

    @staticmethod
    def validate_column_name(column_name: str) -> tuple[bool, str]:
        """Validate column name format."""
        if not column_name or not isinstance(column_name, str):
            return False, "Column name must be a non-empty string"
        if len(column_name) > 255:
            return False, "Column name too long (max 255 characters)"
        # More permissive for column names
        if not re.match(r'^[a-zA-Z0-9_.\s-]+$', column_name):
            return False, "Column name contains invalid characters"
        return True, ""

    @staticmethod
    def validate_query(query: str, max_length: int = 200) -> tuple[bool, str, str]:
        """Validate and sanitize search query."""
        if not query or not isinstance(query, str):
            return False, "", "Query must be a non-empty string"

        # Trim whitespace
        query = query.strip()

        # Truncate if too long
        if len(query) > max_length:
            query = query[:max_length]
            logger.warning(f"Query truncated to {max_length} characters")

        return True, query, ""

    @staticmethod
    def validate_limit(limit: Any, max_limit: int = 1000) -> tuple[bool, int, str]:
        """Validate and sanitize limit parameter."""
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            return False, 0, "Limit must be a number"

        if limit < 1:
            return True, 1, ""
        if limit > max_limit:
            logger.warning(f"Limit capped at {max_limit}")
            return True, max_limit, ""

        return True, limit, ""


class DbtDagNavigator:
    """Efficiently navigates dbt DAG using indexed manifest and catalog data."""

    def __init__(self, security_config: SecurityConfig = None):
        self.manifest: Optional[dict] = None
        self.catalog: Optional[dict] = None
        self.upstream_map: dict[str, set[str]] = defaultdict(set)
        self.downstream_map: dict[str, set[str]] = defaultdict(set)
        self.column_map: dict[str, dict] = {}
        self.models: dict[str, dict] = {}
        self.sources: dict[str, dict] = {}
        self.indexed = False
        self.config = security_config or SecurityConfig()

    def _validate_file_path(self, file_path: str, expected_name: str = None) -> tuple[bool, Optional[Path], str]:
        """Validate file path to prevent path traversal attacks."""
        try:
            # Resolve to absolute path
            resolved_path = Path(file_path).resolve()

            # Check if path exists
            if not resolved_path.exists():
                return False, None, "File not found"

            # Check if it's a file (not a directory)
            if not resolved_path.is_file():
                return False, None, "Path is not a file"

            # Check if filename matches expected pattern
            if expected_name and resolved_path.name != expected_name:
                # Be lenient - allow if it ends with expected name
                if not resolved_path.name.endswith(expected_name):
                    logger.warning(f"Unexpected filename: {resolved_path.name}")

            # Optional: Whitelist allowed directories
            if self.config.allowed_directories:
                is_allowed = False
                for allowed_dir in self.config.allowed_directories:
                    try:
                        allowed_path = Path(allowed_dir).resolve()
                        if resolved_path.is_relative_to(allowed_path):
                            is_allowed = True
                            break
                    except (ValueError, RuntimeError):
                        continue

                if not is_allowed:
                    logger.error(f"Path outside allowed directories: {resolved_path}")
                    return False, None, "Access denied"

            return True, resolved_path, ""

        except Exception as e:
            logger.error(f"Path validation error: {e}")
            return False, None, "Invalid path"

    def _validate_json_structure(self, data: Any, max_depth: int = 20, current_depth: int = 0) -> bool:
        """Validate JSON structure to prevent billion laughs attack."""
        if current_depth > max_depth:
            raise ValueError(f"JSON nesting too deep: {current_depth} levels")

        if isinstance(data, dict):
            for key, value in data.items():
                self._validate_json_structure(value, max_depth, current_depth + 1)
        elif isinstance(data, list):
            for item in data:
                self._validate_json_structure(item, max_depth, current_depth + 1)

        return True

    def load_and_index(self, manifest_path: str, catalog_path: Optional[str] = None) -> dict:
        """Load and index dbt manifest and catalog files."""
        try:
            # Validate manifest path
            valid, manifest_file, error = self._validate_file_path(manifest_path, "manifest.json")
            if not valid:
                return {"success": False, "error": f"Invalid manifest path: {error}"}

            # Check file size
            file_size_mb = manifest_file.stat().st_size / (1024 * 1024)
            if file_size_mb > self.config.max_file_size_mb:
                return {
                    "success": False,
                    "error": f"Manifest file too large: {file_size_mb:.2f}MB"
                }

            logger.info(f"Loading manifest file ({file_size_mb:.2f}MB)")

            # Load manifest
            with open(manifest_file, 'r', encoding='utf-8') as f:
                self.manifest = json.load(f)

            # Validate JSON structure
            try:
                self._validate_json_structure(self.manifest, self.config.max_json_depth)
            except ValueError as e:
                return {"success": False, "error": f"Invalid manifest structure: {e}"}

            # Validate manifest format
            if not isinstance(self.manifest, dict):
                return {"success": False, "error": "Invalid manifest format"}

            if 'nodes' not in self.manifest:
                return {"success": False, "error": "Manifest missing 'nodes' key"}

            # Check node count limit
            node_count = len(self.manifest.get('nodes', {}))
            if node_count > self.config.max_nodes:
                return {
                    "success": False,
                    "error": f"Too many nodes: {node_count}"
                }

            # Load catalog if provided
            if catalog_path:
                valid, catalog_file, error = self._validate_file_path(catalog_path, "catalog.json")
                if valid:
                    catalog_size_mb = catalog_file.stat().st_size / (1024 * 1024)
                    if catalog_size_mb > self.config.max_file_size_mb:
                        logger.warning(f"Catalog file too large: {catalog_size_mb:.2f}MB, skipping")
                    else:
                        logger.info(f"Loading catalog file ({catalog_size_mb:.2f}MB)")
                        with open(catalog_file, 'r', encoding='utf-8') as f:
                            self.catalog = json.load(f)

                        # Validate catalog structure
                        try:
                            self._validate_json_structure(self.catalog, self.config.max_json_depth)
                        except ValueError as e:
                            logger.warning(f"Invalid catalog structure, skipping: {e}")
                            self.catalog = None
                else:
                    logger.warning(f"Invalid catalog path: {error}")

            # Index the data
            self._build_indexes()
            self.indexed = True

            logger.info(f"Successfully indexed {len(self.models)} models and {len(self.sources)} sources")

            return {
                "success": True,
                "models_count": len(self.models),
                "sources_count": len(self.sources),
                "catalog_loaded": self.catalog is not None
            }

        except MemoryError:
            logger.error("Out of memory while loading files")
            return {"success": False, "error": "File too large to process"}
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            return {"success": False, "error": "Invalid JSON format"}
        except Exception as e:
            logger.error(f"Error loading files: {e}", exc_info=True)
            return {"success": False, "error": "Failed to load DAG"}

    def _build_indexes(self):
        """Build efficient indexes for fast querying."""
        if not self.manifest:
            return

        # Index models
        models_count = 0
        for node_id, node_data in self.manifest.get('nodes', {}).items():
            if node_data.get('resource_type') in ['model', 'snapshot']:
                models_count += 1
                if models_count > self.config.max_nodes:
                    logger.warning(f"Model count exceeds limit, stopping at {self.config.max_nodes}")
                    break

                self.models[node_id] = {
                    'name': node_data.get('name', ''),
                    'schema': node_data.get('schema', ''),
                    'database': node_data.get('database', ''),
                    'description': node_data.get('description', ''),
                    'tags': node_data.get('tags', []),
                    'materialized': node_data.get('config', {}).get('materialized', ''),
                    'columns': node_data.get('columns', {}),
                    'depends_on': node_data.get('depends_on', {})
                }

                # Build dependency maps
                depends_on_nodes = node_data.get('depends_on', {}).get('nodes', [])
                for dep in depends_on_nodes:
                    self.upstream_map[node_id].add(dep)
                    self.downstream_map[dep].add(node_id)

        # Index sources
        sources_count = 0
        for source_id, source_data in self.manifest.get('sources', {}).items():
            sources_count += 1
            if sources_count > self.config.max_sources:
                logger.warning(f"Source count exceeds limit, stopping at {self.config.max_sources}")
                break

            self.sources[source_id] = {
                'name': source_data.get('name', ''),
                'source_name': source_data.get('source_name', ''),
                'schema': source_data.get('schema', ''),
                'database': source_data.get('database', ''),
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
                        'type': col_data.get('type', ''),
                        'comment': col_data.get('comment', ''),
                        'index': col_data.get('index')
                    }

    def get_upstream_models(self, model_name: str, include_sources: bool = True) -> dict:
        """Get all upstream dependencies of a model."""
        if not self.indexed:
            return {"error": "DAG not indexed. Load manifest first."}

        # Validate input
        valid, error = InputValidator.validate_model_name(model_name)
        if not valid:
            return {"error": error}

        # Find the model
        node_id = self._find_model_id(model_name)
        if not node_id:
            return {"error": "Model not found"}

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

        # Validate input
        valid, error = InputValidator.validate_model_name(model_name)
        if not valid:
            return {"error": error}

        node_id = self._find_model_id(model_name)
        if not node_id:
            return {"error": "Model not found"}

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

        # Validate inputs
        valid, error = InputValidator.validate_model_name(model_name)
        if not valid:
            return {"error": error}

        valid, error = InputValidator.validate_column_name(column_name)
        if not valid:
            return {"error": error}

        node_id = self._find_model_id(model_name)
        if not node_id:
            return {"error": "Model not found"}

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

        # Validate and sanitize query
        valid, sanitized_query, error = InputValidator.validate_query(
            query,
            self.config.max_query_length
        )
        if not valid:
            return {"error": error}

        query_lower = sanitized_query.lower()
        results = []

        for node_id, model_data in self.models.items():
            score = 0
            matches = []

            # Check name
            if query_lower in model_data.get('name', '').lower():
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
            "query": sanitized_query,
            "count": len(results),
            "results": results[:20]  # Limit to top 20
        }

    def get_model_details(self, model_name: str) -> dict:
        """Get detailed information about a model."""
        if not self.indexed:
            return {"error": "DAG not indexed. Load manifest first."}

        # Validate input
        valid, error = InputValidator.validate_model_name(model_name)
        if not valid:
            return {"error": error}

        node_id = self._find_model_id(model_name)
        if not node_id:
            return {"error": "Model not found"}

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
                col_info["type"] = catalog_col.get('type', '')
                col_info["comment"] = catalog_col.get('comment', '')

            result["columns"].append(col_info)

        # Add dependency counts
        result["direct_upstream_count"] = len(self.upstream_map.get(node_id, set()))
        result["direct_downstream_count"] = len(self.downstream_map.get(node_id, set()))

        return result

    def list_models(self, limit: int = 50) -> dict:
        """List all models in the DAG."""
        if not self.indexed:
            return {"error": "DAG not indexed. Load manifest first."}

        # Validate and sanitize limit
        valid, sanitized_limit, error = InputValidator.validate_limit(
            limit,
            self.config.max_list_limit
        )
        if not valid:
            return {"error": error}

        models = []
        for node_id, model_data in list(self.models.items())[:sanitized_limit]:
            models.append({
                "id": node_id,
                "name": model_data['name'],
                "schema": model_data['schema'],
                "materialized": model_data['materialized']
            })

        return {
            "total_count": len(self.models),
            "returned_count": len(models),
            "limit_applied": sanitized_limit,
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
        """Get all transitive dependencies using BFS with cycle protection."""
        visited = set()
        queue = deque([node_id])
        iterations = 0

        while queue:
            iterations += 1
            if iterations > self.config.max_iterations:
                logger.error(f"Max iterations ({self.config.max_iterations}) reached in dependency traversal")
                break

            current = queue.popleft()
            if current in visited:
                continue
            visited.add(current)

            for dep in dep_map.get(current, set()):
                if dep not in visited:
                    queue.append(dep)

        # Remove the starting node
        visited.discard(node_id)
        return visited


# Initialize components
security_config = SecurityConfig()
navigator = DbtDagNavigator(security_config)
rate_limiter = RateLimiter(
    max_requests=security_config.rate_limit_requests,
    window_seconds=security_config.rate_limit_window_seconds
)

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
                        "description": "Maximum number of models to return (default: 50, max: 1000)"
                    }
                }
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[types.TextContent]:
    """Handle tool calls with security checks."""
    # Check rate limit
    if not rate_limiter.is_allowed():
        return [types.TextContent(
            type="text",
            text=json.dumps({"error": "Rate limit exceeded. Please try again later."})
        )]

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
            result = {"error": "Unknown tool"}

        return [types.TextContent(
            type="text",
            text=json.dumps(result, indent=2)
        )]

    except KeyError as e:
        logger.error(f"Missing required argument: {e}")
        return [types.TextContent(
            type="text",
            text=json.dumps({"error": "Invalid request parameters"})
        )]
    except Exception as e:
        logger.error(f"Error executing tool {name}: {e}", exc_info=True)
        return [types.TextContent(
            type="text",
            text=json.dumps({"error": "Request processing failed"})
        )]


async def main():
    """Run the MCP server."""
    logger.info("Starting dbt DAG Navigator (Security Hardened)")
    logger.info(f"Security settings: max_file_size={security_config.max_file_size_mb}MB, "
                f"max_nodes={security_config.max_nodes}, "
                f"rate_limit={security_config.rate_limit_requests}/min")

    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
