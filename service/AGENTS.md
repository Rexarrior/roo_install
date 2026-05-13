# Userver Development Rules MANDATORY

Core principles for developing microservices with userver framework.

# Always include minimal server components
When creating a userver service, you MUST include `components::MinimalServerComponentList()` in your main component list.

# HTTP handler naming convention
HTTP handler component names MUST start with "handler-" prefix (e.g., "handler-auth", "handler-files").

# Configuration file structure
Each service MUST have a `static_config.yaml` file in its directory with proper `components_manager` section and component configurations.

# Component registration
All custom components (handlers, clients, etc.) MUST be appended to the component list in `main.cpp` using `.Append<ComponentType>()`.

# Port configuration
Server listener port MUST be configured in `static_config.yaml` under `components.server.listener.port`.

# Dynamic config defaults
To prevent automatic shutdown, you MUST set `updates-enabled: false` for dynamic-config component unless you specifically need dynamic updates.

# Stack usage monitor in Docker
When running in Docker containers, you MUST set `coro_pool.stack_usage_monitor_enabled: false` in `static_config.yaml` to avoid userfaultfd permission errors.

# JSON response content type
HTTP handlers MUST set response content type to `application/json` for JSON responses using `request.GetHttpResponse().SetContentType(userver::http::content_type::kApplicationJson)`.

# Error handling format
All error responses MUST follow consistent JSON format with "code" and "message" fields. Use structured error objects for all error cases.

# Request validation
HTTP handlers MUST validate all incoming request data (headers, body, path parameters) before processing.

# Thread safety for in-memory storage
When using in-memory data structures across multiple coroutines, you MUST protect them with `engine::Mutex` or use thread-safe containers.

# Logging level
Use appropriate logging levels: `LOG_DEBUG()` for debugging, `LOG_INFO()` for normal operations, `LOG_ERROR()` for errors.

# Path routing patterns
For REST API endpoints, use appropriate path patterns:
- `/v1/resource/{action}` for resource-based actions
- `/v1/*` for wildcard routing with manual path parsing
- `/v1/resource/{id}/subresource` for nested resources

# Authorization header check
When authentication is required, check `Authorization` header exists and has valid format before processing request.

# CMake target naming
CMake targets for services MUST be named with `_service` suffix (e.g., `service1`, `service2`).

# Include order in headers
Header files MUST include userver headers first, then standard library headers, then project-specific headers.

# Namespace organization
Each service MUST use its own namespace (e.g., `service1`, `service2`) to prevent symbol collisions.

# JSON parsing validation
When parsing JSON requests, you MUST handle parsing exceptions and return appropriate error responses.

# HTTP method checking
HTTP handlers MUST check request method (`request.GetMethod()`) and return 405 Method Not Allowed for unsupported methods.

# Response status codes
Use appropriate HTTP status codes:
- 200 OK for successful operations
- 201 Created for resource creation
- 400 Bad Request for invalid input
- 401 Unauthorized for authentication failures
- 404 Not Found for non-existent resources
- 409 Conflict for duplicate resources
- 500 Internal Server Error for unexpected server errors

# Docker image optimization
Use multi-stage Docker builds with pre-built binaries to minimize image size and build time.

# Health check endpoints
Every service SHOULD implement a health check endpoint (e.g., `/healthcheck`) that returns 200 OK when service is healthy.

# Configuration validation
Validate all configuration parameters at service startup and log warnings for missing or invalid values.

# Request timeout handling
Implement appropriate timeout handling for external service calls and database queries.

# Metric collection
Consider adding metrics for request counts, response times, and error rates using userver metrics components.

# Documentation comments
All public APIs, configuration parameters, and non-trivial logic MUST have clear documentation comments.

# Test coverage
Write unit tests for all business logic components and integration tests for HTTP endpoints.

# Build optimization
Use parallel builds (`make -j$(nproc)`) and incremental compilation during development.

# Service discovery
In Docker Compose setups, use service names (not localhost) for inter-service communication.

# Environment variables
Use environment variables for configuration that varies between environments (ports, credentials, feature flags).

# Graceful shutdown
Implement graceful shutdown handling to complete in-flight requests before exiting.

# Request ID tracing
Add correlation IDs to requests for distributed tracing across multiple services.