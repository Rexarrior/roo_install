---
description: >
  Step-by-step guide to create HTTP handlers in userver services.
  Includes: handler class definition, request processing, response formatting,
  error handling, routing configuration.
  Trigger: create http handler, add endpoint, implement API, handle request,
  REST endpoint, HTTP handler, add route.
name: create-http-handler
---

# Create HTTP Handler in Userver

Complete procedure for creating HTTP handlers in userver microservices.

## 1. Create Handler Class

Define a handler class that inherits from `server::handlers::HttpHandlerBase`:

```cpp
#pragma once

#include <userver/components/component_list.hpp>
#include <userver/server/handlers/http_handler_base.hpp>
#include <userver/utest/using_namespace_userver.hpp>

namespace your_service {

class YourHandler final : public server::handlers::HttpHandlerBase {
public:
    static constexpr std::string_view kName = "handler-yourname";

    YourHandler(const components::ComponentConfig& config,
                const components::ComponentContext& context);

    std::string HandleRequest(server::http::HttpRequest& request,
                              server::request::RequestContext&) const override;

private:
    // Helper methods
    std::string HandleAction(const server::http::HttpRequest& request) const;
};

} // namespace your_service
```

## 2. Implement Handler Constructor

In the .cpp file, implement the constructor:

```cpp
#include "your_handler.hpp"

namespace your_service {

YourHandler::YourHandler(const components::ComponentConfig& config,
                         const components::ComponentContext& context)
    : HttpHandlerBase(config, context) {
}

} // namespace your_service
```

## 3. Implement Request Handling

Implement the `HandleRequest` method with routing logic:

```cpp
std::string YourHandler::HandleRequest(server::http::HttpRequest& request,
                                       server::request::RequestContext&) const {
    const auto& method = request.GetMethod();
    const auto& action = request.GetPathArg("action"); // If using path patterns
    
    // Set JSON content type
    request.GetHttpResponse().SetContentType(userver::http::content_type::kApplicationJson);

    if (method == server::http::HttpMethod::kPost) {
        if (action == "create") {
            return HandleCreate(request);
        }
    } else if (method == server::http::HttpMethod::kGet) {
        if (action == "get") {
            return HandleGet(request);
        }
    }

    // Method not allowed or endpoint not found
    request.GetHttpResponse().SetStatus(server::http::HttpStatus::kNotFound);
    return ToJson(V1Error{"not_found", "Endpoint not found", std::nullopt});
}
```

## 4. Implement Handler Methods

Create helper methods for specific actions:

```cpp
std::string YourHandler::HandleCreate(const server::http::HttpRequest& request) const {
    try {
        // Parse request body
        auto req = ParseRequest(request.RequestBody());
        
        // Process request
        // ...
        
        // Return success response
        return ToJson(Response{...});
        
    } catch (const std::exception& e) {
        request.GetHttpResponse().SetStatus(server::http::HttpStatus::kBadRequest);
        return ToJson(V1Error{"bad_request", e.what(), std::nullopt});
    }
}
```

## 5. Add Handler to Component List

In `main.cpp`, append the handler to the component list:

```cpp
#include <userver/components/minimal_server_component_list.hpp>
#include <userver/clients/dns/component.hpp>
#include <userver/clients/http/component.hpp>
#include <userver/clients/http/component_list.hpp>
#include <userver/utils/daemon_run.hpp>

#include "src/your_handler.hpp"

int main(int argc, char* argv[]) {
    auto component_list = components::MinimalServerComponentList()
        .Append<your_service::YourHandler>()
        .Append<clients::dns::Component>()
        .AppendComponentList(clients::http::ComponentList());

    return utils::DaemonMain(argc, argv, component_list);
}
```

## 6. Configure Handler in static_config.yaml

Add handler configuration in the service's `static_config.yaml`:

```yaml
components:
  handler-yourname:
    path: /v1/yourresource/{action}
    method: POST,GET
    task_processor: main-task-processor
```

## 7. Create Request/Response Schemas

Define clear request/response structures:

```cpp
#pragma once
#include <string>
#include <optional>
#include <unordered_map>

namespace your_service {

struct Request {
    std::string field1;
    int field2;
    std::optional<std::string> optional_field;
};

struct Response {
    std::string id;
    std::string status;
    std::string created_at;
};

struct V1Error {
    std::string code;
    std::string message;
    std::optional<std::unordered_map<std::string, std::string>> details;
};

} // namespace your_service
```

## 8. Implement JSON Parsing/Serialization

Create schema parsing functions:

```cpp
#include "schemas.hpp"
#include <userver/formats/json.hpp>

namespace your_service {

namespace json = userver::formats::json;

Request ParseRequest(const std::string& json_str) {
    auto json = json::FromString(json_str);
    Request req{
        .field1 = json["field1"].As<std::string>(),
        .field2 = json["field2"].As<int>()
    };
    
    // Validation
    if (req.field1.empty()) {
        throw std::runtime_error("field1 must not be empty");
    }
    
    return req;
}

std::string ToJson(const Response& response) {
    json::ValueBuilder builder;
    builder["id"] = response.id;
    builder["status"] = response.status;
    builder["created_at"] = response.created_at;
    return json::ToString(builder.ExtractValue());
}

} // namespace your_service
```

## 9. Add Request Validation

Always validate incoming requests:

```cpp
// Check Authorization header
auto auth_header = request.GetHeader("Authorization");
if (auth_header.empty() || auth_header.size() != 128) {
    request.GetHttpResponse().SetStatus(server::http::HttpStatus::kUnauthorized);
    return ToJson(V1Error{"invalid_token", "Invalid token", std::nullopt});
}

// Check required headers
if (!request.HasHeader("X-Request-ID")) {
    request.GetHttpResponse().SetStatus(server::http::HttpStatus::kBadRequest);
    return ToJson(V1Error{"missing_header", "X-Request-ID header required", std::nullopt});
}
```

## 10. Implement Error Handling

Consistent error handling:

```cpp
try {
    // Business logic
} catch (const json::ParseException& e) {
    request.GetHttpResponse().SetStatus(server::http::HttpStatus::kBadRequest);
    return ToJson(V1Error{"invalid_json", "Invalid JSON format", std::nullopt});
} catch (const std::runtime_error& e) {
    request.GetHttpResponse().SetStatus(server::http::HttpStatus::kBadRequest);
    return ToJson(V1Error{"validation_error", e.what(), std::nullopt});
} catch (const std::exception& e) {
    request.GetHttpResponse().SetStatus(server::http::HttpStatus::kInternalServerError);
    LOG_ERROR() << "Unhandled exception: " << e.what();
    return ToJson(V1Error{"internal_error", "Internal server error", std::nullopt});
}
```

## Troubleshooting

### Handler not being called
- Check handler name matches `kName` static member
- Verify path pattern in `static_config.yaml` matches expected URLs
- Ensure handler is appended to component list in `main.cpp`

### JSON parsing errors
- Validate JSON structure matches expected schema
- Check for missing required fields
- Verify JSON is valid (no trailing commas, proper quoting)

### Compilation errors
- Ensure all required headers are included
- Check namespace consistency between .hpp and .cpp files
- Verify userver components are properly linked

### Runtime errors
- Check dynamic-config is configured with `updates-enabled: false`
- Verify port is not already in use
- Check file permissions for logs and configuration

## Best Practices

1. **Keep handlers focused**: One handler per resource or action group
2. **Validate early**: Validate all inputs as soon as possible
3. **Use structured errors**: Consistent error format across all endpoints
4. **Log appropriately**: DEBUG for tracing, INFO for operations, ERROR for failures
5. **Handle all exceptions**: No uncaught exceptions in request processing
6. **Set proper timeouts**: For external calls and database queries
7. **Use const correctness**: Mark methods const when they don't modify state
8. **Document interfaces**: Clear documentation for API endpoints and schemas