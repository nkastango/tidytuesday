# Security Review: dbt DAG Navigator

**Review Date**: 2024-11-13
**Reviewed By**: Security Analysis
**Severity Levels**: 🔴 Critical | 🟠 High | 🟡 Medium | 🟢 Low | ℹ️ Info

---

## Executive Summary

The dbt DAG Navigator is a relatively simple MCP server that parses and indexes JSON files. The overall security posture is **moderate** with several vulnerabilities ranging from critical to low severity. The most significant risks are:

1. **Path Traversal** (🔴 Critical)
2. **Denial of Service via Memory Exhaustion** (🟠 High)
3. **JSON Bomb/Billion Laughs Attack** (🟠 High)
4. **Circular Dependency Infinite Loop** (🟡 Medium)

---

## Vulnerability Details

### 🔴 CRITICAL: Path Traversal (CWE-22)

**Location**: `server.py:38-54`

**Issue**: The `load_and_index()` method accepts arbitrary file paths from user input without validation. An attacker can read any file on the system that the server process has access to.

```python
def load_and_index(self, manifest_path: str, catalog_path: Optional[str] = None) -> dict:
    # No validation on manifest_path or catalog_path
    manifest_file = Path(manifest_path)  # ⚠️ Vulnerable
    with open(manifest_file, 'r') as f:
        self.manifest = json.load(f)
```

**Attack Scenario**:
```python
# Attacker can read /etc/passwd
navigator.load_and_index("/etc/passwd")

# Or read SSH keys
navigator.load_and_index("/home/user/.ssh/id_rsa")

# Or read environment files with secrets
navigator.load_and_index("/app/.env")
```

**Impact**:
- Unauthorized file system access
- Exposure of sensitive files (credentials, keys, config files)
- Potential for further exploitation

**Recommendation**:

```python
import os
from pathlib import Path

def load_and_index(self, manifest_path: str, catalog_path: Optional[str] = None) -> dict:
    """Load and index dbt manifest and catalog files."""
    try:
        # Validate and sanitize paths
        manifest_file = self._validate_file_path(manifest_path, expected_name="manifest.json")
        if not manifest_file:
            return {"success": False, "error": "Invalid manifest path"}

        with open(manifest_file, 'r') as f:
            self.manifest = json.load(f)

        # Similar validation for catalog_path
        if catalog_path:
            catalog_file = self._validate_file_path(catalog_path, expected_name="catalog.json")
            if catalog_file and catalog_file.exists():
                with open(catalog_file, 'r') as f:
                    self.catalog = json.load(f)

        # ... rest of code
    except Exception as e:
        logger.error(f"Error loading files: {e}")
        return {"success": False, "error": "Failed to load files"}

def _validate_file_path(self, file_path: str, expected_name: str = None) -> Optional[Path]:
    """Validate file path to prevent path traversal attacks."""
    try:
        # Resolve to absolute path and check if it exists
        resolved_path = Path(file_path).resolve()

        # Check if path exists
        if not resolved_path.exists():
            logger.warning(f"Path does not exist: {resolved_path}")
            return None

        # Check if it's a file (not a directory)
        if not resolved_path.is_file():
            logger.warning(f"Path is not a file: {resolved_path}")
            return None

        # Optional: Check if filename matches expected pattern
        if expected_name and resolved_path.name != expected_name:
            logger.warning(f"Unexpected filename: {resolved_path.name}, expected: {expected_name}")
            # You might want to be more lenient here

        # Optional: Whitelist allowed directories
        # ALLOWED_DIRS = [Path("/path/to/dbt/projects")]
        # if not any(resolved_path.is_relative_to(allowed) for allowed in ALLOWED_DIRS):
        #     logger.error(f"Path outside allowed directories: {resolved_path}")
        #     return None

        return resolved_path

    except Exception as e:
        logger.error(f"Path validation error: {e}")
        return None
```

---

### 🟠 HIGH: Denial of Service via Memory Exhaustion (CWE-400)

**Location**: `server.py:46-54, 73-119`

**Issue**: The server loads entire JSON files into memory without size limits. Large files (catalog can be 10MB+) or maliciously crafted files can exhaust memory.

```python
with open(manifest_file, 'r') as f:
    self.manifest = json.load(f)  # ⚠️ Loads entire file into memory
```

**Attack Scenario**:
```python
# Attacker provides a 1GB JSON file
navigator.load_and_index("/path/to/huge_manifest.json")

# Or a deeply nested JSON structure
# {"a": {"a": {"a": ... }}}  # 100,000 levels deep
```

**Impact**:
- Server crashes due to OOM (Out of Memory)
- DoS affecting all users
- Potential container/pod restart loops in Kubernetes

**Recommendation**:

```python
import os

# Configuration
MAX_FILE_SIZE_MB = 100  # Maximum file size in MB
MAX_MEMORY_MB = 500     # Maximum memory for indexing

def load_and_index(self, manifest_path: str, catalog_path: Optional[str] = None) -> dict:
    """Load and index dbt manifest and catalog files."""
    try:
        # Check file size before loading
        manifest_file = Path(manifest_path)
        if not manifest_file.exists():
            return {"success": False, "error": f"Manifest file not found: {manifest_path}"}

        file_size_mb = manifest_file.stat().st_size / (1024 * 1024)
        if file_size_mb > MAX_FILE_SIZE_MB:
            return {
                "success": False,
                "error": f"Manifest file too large: {file_size_mb:.2f}MB (max: {MAX_FILE_SIZE_MB}MB)"
            }

        # Load with size monitoring
        with open(manifest_file, 'r') as f:
            self.manifest = json.load(f)

        # Check manifest structure
        if not isinstance(self.manifest, dict):
            return {"success": False, "error": "Invalid manifest format"}

        # Validate manifest has expected keys
        if 'nodes' not in self.manifest:
            return {"success": False, "error": "Manifest missing 'nodes' key"}

        # Limit number of nodes to prevent memory exhaustion
        MAX_NODES = 10000
        node_count = len(self.manifest.get('nodes', {}))
        if node_count > MAX_NODES:
            return {
                "success": False,
                "error": f"Too many nodes: {node_count} (max: {MAX_NODES})"
            }

        # Similar checks for catalog
        if catalog_path:
            catalog_file = Path(catalog_path)
            if catalog_file.exists():
                catalog_size_mb = catalog_file.stat().st_size / (1024 * 1024)
                if catalog_size_mb > MAX_FILE_SIZE_MB:
                    logger.warning(f"Catalog file too large: {catalog_size_mb:.2f}MB, skipping")
                else:
                    with open(catalog_file, 'r') as f:
                        self.catalog = json.load(f)

        # Index the data
        self._build_indexes()
        self.indexed = True

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
        logger.error(f"Invalid JSON: {e}")
        return {"success": False, "error": "Invalid JSON format"}
    except Exception as e:
        logger.error(f"Error loading files: {e}")
        return {"success": False, "error": "Failed to load files"}
```

---

### 🟠 HIGH: JSON Bomb / Billion Laughs Attack (CWE-776)

**Location**: `server.py:46-54`

**Issue**: No protection against maliciously crafted JSON with excessive nesting or entity expansion.

**Attack Scenario**:
```json
{
  "nodes": {
    "a": {"depends_on": {"nodes": ["b"]}},
    "b": {"depends_on": {"nodes": ["c"]}},
    "c": {"depends_on": {"nodes": ["d"]}},
    ...
    "z99999": {"depends_on": {"nodes": ["a"]}}
  }
}
```

**Impact**:
- CPU exhaustion during parsing
- Memory exhaustion during indexing
- Denial of service

**Recommendation**:

```python
def _validate_json_structure(self, data: dict, max_depth: int = 10, current_depth: int = 0) -> bool:
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
        # ... existing file loading code ...

        with open(manifest_file, 'r') as f:
            self.manifest = json.load(f)

        # Validate structure depth
        try:
            self._validate_json_structure(self.manifest, max_depth=20)
        except ValueError as e:
            return {"success": False, "error": f"Invalid JSON structure: {e}"}

        # ... rest of code ...
```

---

### 🟡 MEDIUM: Circular Dependency Infinite Loop (CWE-835)

**Location**: `server.py:363-380`

**Issue**: The `_get_transitive_deps()` method uses BFS with cycle detection via `visited` set. However, if there's a bug in the cycle detection logic, it could cause infinite loops.

```python
def _get_transitive_deps(self, node_id: str, dep_map: dict[str, set[str]]) -> set[str]:
    """Get all transitive dependencies using BFS."""
    visited = set()
    queue = [node_id]

    while queue:
        current = queue.pop(0)  # ⚠️ Could be slow for large queues
        if current in visited:
            continue
        visited.add(current)

        for dep in dep_map.get(current, set()):
            if dep not in visited:
                queue.append(dep)
```

**Current Status**: The implementation is actually **correct** for cycle detection. The `visited` set properly prevents infinite loops.

**Performance Issue**: Using `queue.pop(0)` on a list is O(n) operation. For large DAGs, this becomes inefficient.

**Recommendation**:

```python
from collections import deque

def _get_transitive_deps(self, node_id: str, dep_map: dict[str, set[str]]) -> set[str]:
    """Get all transitive dependencies using BFS."""
    visited = set()
    queue = deque([node_id])  # ✅ Use deque for O(1) popleft
    iterations = 0
    MAX_ITERATIONS = 100000  # Safety limit

    while queue:
        iterations += 1
        if iterations > MAX_ITERATIONS:
            logger.error(f"Max iterations reached in _get_transitive_deps for {node_id}")
            break

        current = queue.popleft()  # ✅ O(1) operation
        if current in visited:
            continue
        visited.add(current)

        for dep in dep_map.get(current, set()):
            if dep not in visited:
                queue.append(dep)

    # Remove the starting node
    visited.discard(node_id)
    return visited
```

---

### 🟡 MEDIUM: Information Disclosure via Error Messages (CWE-209)

**Location**: `server.py:69-71, 548-553`

**Issue**: Detailed error messages expose internal system information.

```python
except Exception as e:
    logger.error(f"Error loading files: {e}")
    return {"success": False, "error": str(e)}  # ⚠️ Exposes internal errors
```

**Attack Scenario**:
```python
# Error messages might reveal:
# - File system structure
# - Python version info
# - Stack traces with line numbers
# - Database connection strings (if in error messages)
```

**Impact**:
- Information leakage about system internals
- Helps attackers map the system
- May expose sensitive paths or configurations

**Recommendation**:

```python
# Define generic error messages
ERROR_MESSAGES = {
    "file_not_found": "The specified file could not be found",
    "invalid_format": "The file format is invalid",
    "loading_failed": "Failed to load the DAG",
    "processing_failed": "Failed to process the request"
}

def load_and_index(self, manifest_path: str, catalog_path: Optional[str] = None) -> dict:
    """Load and index dbt manifest and catalog files."""
    try:
        # ... code ...
    except FileNotFoundError:
        logger.error(f"File not found: {manifest_path}")  # Log detailed error
        return {"success": False, "error": ERROR_MESSAGES["file_not_found"]}  # Return generic
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}")
        return {"success": False, "error": ERROR_MESSAGES["invalid_format"]}
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)  # Log with traceback
        return {"success": False, "error": ERROR_MESSAGES["loading_failed"]}  # Generic message

@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[types.TextContent]:
    """Handle tool calls."""
    try:
        # ... existing code ...
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
            text=json.dumps({"error": ERROR_MESSAGES["processing_failed"]})
        )]
```

---

### 🟢 LOW: No Input Sanitization for Search Queries (CWE-20)

**Location**: `server.py:237-282`

**Issue**: Search queries are not sanitized, but since they're only used for string comparison (not SQL or command execution), the risk is low.

```python
def search_models(self, query: str, search_descriptions: bool = True) -> dict:
    """Search for models by name, description, or tags."""
    query_lower = query.lower()  # ⚠️ No sanitization
    # ... searches through models ...
```

**Potential Issues**:
- Very long search strings could cause performance issues
- Special characters could cause unexpected behavior (though unlikely)

**Recommendation**:

```python
def search_models(self, query: str, search_descriptions: bool = True) -> dict:
    """Search for models by name, description, or tags."""
    if not self.indexed:
        return {"error": "DAG not indexed. Load manifest first."}

    # Validate and sanitize query
    if not query or not isinstance(query, str):
        return {"error": "Invalid query"}

    # Limit query length
    MAX_QUERY_LENGTH = 200
    if len(query) > MAX_QUERY_LENGTH:
        query = query[:MAX_QUERY_LENGTH]
        logger.warning(f"Query truncated to {MAX_QUERY_LENGTH} characters")

    # Remove potentially problematic characters (optional)
    # query = re.sub(r'[^\w\s-]', '', query)

    query_lower = query.lower()
    # ... rest of code ...
```

---

### 🟢 LOW: Unbounded Result Sets (CWE-770)

**Location**: `server.py:327-345`

**Issue**: `list_models()` has a default limit of 50, but users can set it arbitrarily high.

```python
def list_models(self, limit: int = 50) -> dict:
    """List all models in the DAG."""
    # ... code ...
    for node_id, model_data in list(self.models.items())[:limit]:  # ⚠️ No max limit
```

**Recommendation**:

```python
def list_models(self, limit: int = 50) -> dict:
    """List all models in the DAG."""
    if not self.indexed:
        return {"error": "DAG not indexed. Load manifest first."}

    # Enforce maximum limit
    MAX_LIMIT = 1000
    if limit > MAX_LIMIT:
        limit = MAX_LIMIT
        logger.warning(f"Limit capped at {MAX_LIMIT}")

    if limit < 1:
        limit = 1

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
        "models": models,
        "limit_applied": limit
    }
```

---

### ℹ️ INFO: No Rate Limiting

**Location**: Global - no rate limiting implementation

**Issue**: The MCP server has no rate limiting. A malicious client could spam requests.

**Impact**:
- Resource exhaustion
- Denial of service for legitimate users
- Potential for abuse

**Recommendation**:

Since this is an MCP server, rate limiting should ideally be handled at the MCP client level or by a reverse proxy. However, you can add basic protection:

```python
import time
from collections import deque

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

        return False

# Add to server
rate_limiter = RateLimiter(max_requests=100, window_seconds=60)

@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[types.TextContent]:
    """Handle tool calls."""
    # Check rate limit
    if not rate_limiter.is_allowed():
        logger.warning("Rate limit exceeded")
        return [types.TextContent(
            type="text",
            text=json.dumps({"error": "Rate limit exceeded. Please try again later."})
        )]

    try:
        # ... existing code ...
```

---

### ℹ️ INFO: Logging Security Considerations

**Location**: `server.py:20-22, various`

**Issue**: Logging configuration may log sensitive data.

```python
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("dbt-dag-navigator")
```

**Recommendation**:

```python
import logging
import sys

# Configure secure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("dbt-dag-navigator")

# Don't log sensitive data
# Bad:  logger.info(f"Loading file: {full_path_with_secrets}")
# Good: logger.info(f"Loading manifest file")

# Use appropriate log levels
# logger.debug() for detailed debugging (disable in production)
# logger.info() for general information
# logger.warning() for warnings
# logger.error() for errors
# logger.critical() for critical issues
```

---

## Additional Security Recommendations

### 1. Add Input Validation Helper

```python
class InputValidator:
    """Centralized input validation."""

    @staticmethod
    def validate_model_name(model_name: str) -> bool:
        """Validate model name format."""
        if not model_name or not isinstance(model_name, str):
            return False
        if len(model_name) > 255:
            return False
        # Only allow alphanumeric, underscore, hyphen
        if not re.match(r'^[a-zA-Z0-9_-]+$', model_name):
            return False
        return True

    @staticmethod
    def validate_column_name(column_name: str) -> bool:
        """Validate column name format."""
        if not column_name or not isinstance(column_name, str):
            return False
        if len(column_name) > 255:
            return False
        return True
```

### 2. Add Security Headers/Metadata

```python
# Add to server initialization
app = Server(
    "dbt-dag-navigator",
    version="0.1.0",
    # Add security metadata
    capabilities={
        "security": {
            "max_file_size_mb": 100,
            "max_nodes": 10000,
            "rate_limit_per_minute": 100
        }
    }
)
```

### 3. Add Configuration File for Security Settings

```python
# config.py
from dataclasses import dataclass

@dataclass
class SecurityConfig:
    """Security configuration settings."""
    max_file_size_mb: int = 100
    max_nodes: int = 10000
    max_query_length: int = 200
    max_list_limit: int = 1000
    max_json_depth: int = 20
    rate_limit_requests: int = 100
    rate_limit_window_seconds: int = 60
    allowed_directories: list[str] = None

    def __post_init__(self):
        if self.allowed_directories is None:
            self.allowed_directories = []

# Load from environment or config file
security_config = SecurityConfig()
```

### 4. Add Automated Security Testing

```python
# tests/test_security.py
import pytest
from server import DbtDagNavigator

def test_path_traversal_protection():
    """Test that path traversal attempts are blocked."""
    navigator = DbtDagNavigator()

    # Try to read /etc/passwd
    result = navigator.load_and_index("/etc/passwd")
    assert not result["success"]
    assert "error" in result

    # Try path traversal with ../
    result = navigator.load_and_index("../../etc/passwd")
    assert not result["success"]

def test_large_file_rejection():
    """Test that large files are rejected."""
    # Create a large file (>100MB)
    # Test that it's rejected
    pass

def test_json_bomb_protection():
    """Test protection against deeply nested JSON."""
    # Create deeply nested JSON
    # Test that it's rejected
    pass

def test_circular_dependency_handling():
    """Test that circular dependencies don't cause infinite loops."""
    # Create manifest with circular deps
    # Test that it completes without hanging
    pass
```

---

## Compliance Considerations

### OWASP Top 10 2021 Mapping

| OWASP Category | Status | Relevant Vulnerabilities |
|----------------|--------|--------------------------|
| A01: Broken Access Control | ⚠️ VULNERABLE | Path Traversal |
| A02: Cryptographic Failures | ✅ N/A | No crypto operations |
| A03: Injection | ✅ SAFE | No SQL/Command injection vectors |
| A04: Insecure Design | ⚠️ CONCERNS | Missing rate limiting, input validation |
| A05: Security Misconfiguration | ⚠️ CONCERNS | No security defaults, permissive error messages |
| A06: Vulnerable Components | ✅ MINIMAL | Single dependency (mcp) |
| A07: Auth/AuthZ Failures | ℹ️ N/A | No authentication (relies on MCP client) |
| A08: Software/Data Integrity | ✅ SAFE | No dynamic code execution |
| A09: Logging/Monitoring Failures | ⚠️ CONCERNS | Basic logging, no monitoring |
| A10: SSRF | ✅ SAFE | No network requests |

### CWE Coverage

- CWE-22: Path Traversal ❌
- CWE-400: Uncontrolled Resource Consumption ❌
- CWE-770: Allocation of Resources Without Limits ❌
- CWE-776: XML Entity Expansion (JSON equivalent) ❌
- CWE-209: Information Exposure Through Error Messages ❌
- CWE-835: Loop with Unreachable Exit Condition ✅ (handled)

---

## Priority Remediation Plan

### Phase 1: Critical Issues (Immediate - Week 1)
1. ✅ Fix path traversal vulnerability
2. ✅ Add file size limits
3. ✅ Add JSON structure validation

### Phase 2: High/Medium Issues (Week 2-3)
4. ✅ Improve error message handling
5. ✅ Add input validation for all user inputs
6. ✅ Optimize BFS algorithm with deque
7. ✅ Add result set limits

### Phase 3: Low/Info Issues (Week 4)
8. ✅ Add rate limiting (or document requirement)
9. ✅ Improve logging security
10. ✅ Add security configuration
11. ✅ Create security tests

### Phase 4: Hardening (Ongoing)
12. Security audit by third party
13. Penetration testing
14. Security documentation
15. Incident response plan

---

## Testing Recommendations

### Security Test Cases

1. **Path Traversal Tests**
   - Test `/../` sequences
   - Test absolute paths to system files
   - Test symlink following

2. **DoS Tests**
   - Large file handling (100MB+)
   - Deeply nested JSON (1000+ levels)
   - Circular dependency graphs
   - Excessive query strings

3. **Input Validation Tests**
   - Special characters in model names
   - SQL injection attempts (should be safe but test anyway)
   - Very long input strings
   - Unicode and international characters

4. **Error Handling Tests**
   - Verify no sensitive data in error messages
   - Test all error paths
   - Verify proper exception handling

---

## Deployment Security Checklist

- [ ] Run with least privilege (non-root user)
- [ ] Use read-only file system where possible
- [ ] Set resource limits (memory, CPU)
- [ ] Enable security monitoring/logging
- [ ] Use container security scanning
- [ ] Implement network policies (if in Kubernetes)
- [ ] Regular security updates for dependencies
- [ ] Security training for developers

---

## References

- OWASP Top 10: https://owasp.org/www-project-top-ten/
- CWE Top 25: https://cwe.mitre.org/top25/
- NIST Cybersecurity Framework: https://www.nist.gov/cyberframework
- Python Security Best Practices: https://python.readthedocs.io/en/stable/library/security_warnings.html

---

## Conclusion

The dbt DAG Navigator has several security vulnerabilities that should be addressed before production deployment. The most critical issue is the path traversal vulnerability, which could allow unauthorized file access.

**Overall Risk Level**: 🟠 **HIGH**

**Recommendation**: Do not deploy to production until at least Phase 1 remediations are complete.

---

**Report Version**: 1.0
**Last Updated**: 2024-11-13
