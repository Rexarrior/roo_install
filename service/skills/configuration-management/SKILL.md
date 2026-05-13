---
description: >
  Comprehensive guide to configuration management in userver services.
  Includes: static configuration, dynamic configuration, environment variables,
  configuration validation, secrets management, multi-environment setup.
  Trigger: service configuration, config management, environment variables,
  dynamic config, secrets, config validation, multi-environment setup.
name: configuration-management
---

# Configuration Management in Userver

Complete guide to managing service configurations in userver microservices.

## 1. Static Configuration (static_config.yaml)

Every service must have a `static_config.yaml` file with this structure:

```yaml
# yaml
components_manager:
    # Task processors configuration
    task_processors:
        main-task-processor:
            worker_threads: 4
        fs-task-processor:
            worker_threads: 1
    default_task_processor: main-task-processor

    # Components configuration
    components:
        # Server component
        server:
            listener:
                port: 8001
                task_processor: main-task-processor
                connection:
                    in_buffer_size: 32768
                    requests_queue_size_threshold: 100
        
        # Logging configuration
        logging:
            fs-task-processor: fs-task-processor
            loggers:
                default:
                    file_path: '@stderr'
                    level: debug
                    overflow_behavior: discard
        
        # Dynamic config (optional)
        dynamic-config:
            updates-enabled: false
            fs-task-processor: fs-task-processor
            defaults: {}
        
        # Your custom handlers
        handler-auth:
            path: /v1/user/{action}
            method: POST,GET
            task_processor: main-task-processor
        
        # Database components
        postgresql-auth:
            dbconnection: &dbconnection
                host: localhost
                port: 5432
                dbname: auth_db
                user: ${POSTGRES_USER}
                password: ${POSTGRES_PASSWORD}
                connecting_limit: 5
                max_pool_size: 10
            
            dbs:
                main:
                    <<: *dbconnection
                    dbname: auth_db
        
        # HTTP client configuration
        http-client:
            fs-task-processor: fs-task-processor
            user-agent: my-service/1.0
    
    # Coroutine pool settings (required for Docker)
    coro_pool:
        stack_usage_monitor_enabled: false
```

## 2. Environment Variables in Configuration

Use environment variables for sensitive or environment-specific values:

```yaml
components:
    postgresql-auth:
        dbconnection: &dbconnection
            host: ${POSTGRES_HOST:-localhost}
            port: ${POSTGRES_PORT:-5432}
            dbname: ${POSTGRES_DB:-auth_db}
            user: ${POSTGRES_USER}
            password: ${POSTGRES_PASSWORD}
            connecting_limit: 5
    
    redis-session:
        host: ${REDIS_HOST:-localhost}
        port: ${REDIS_PORT:-6379}
        password: ${REDIS_PASSWORD}
        db: ${REDIS_DB:-0}
    
    external-api:
        base_url: ${API_BASE_URL:-https://api.example.com}
        api_key: ${API_KEY}
        timeout_ms: ${API_TIMEOUT_MS:-5000}
```

## 3. Dynamic Configuration

For services that need runtime configuration changes:

```yaml
components:
    dynamic-config:
        updates-enabled: true
        fs-task-processor: fs-task-processor
        defaults: {}
        config-service:
            service-url: ${CONFIG_SERVICE_URL:-http://config-service:8080}
            http-timeout-ms: 5000
            update-interval-ms: 30000
        
        # Fallback file for development
        fallback-path: ${DYNAMIC_CONFIG_FALLBACK_PATH:-/etc/dynamic_config_fallback.json}
```

Create a dynamic config fallback file:

```json
{
    "HTTP_CLIENT_CONNECTION_POOL_SIZE": 100,
    "DATABASE_TIMEOUT_MS": 5000,
    "FEATURE_FLAGS": {
        "NEW_AUTH_FLOW": false,
        "ENABLE_METRICS": true
    },
    "RATE_LIMITS": {
        "REQUESTS_PER_MINUTE": 1000,
        "BURST_SIZE": 100
    }
}
```

## 4. Configuration Validation Schema

Create a validation schema for your configuration:

```cpp
#pragma once

#include <userver/dynamic_config/value.hpp>
#include <userver/formats/json/value.hpp>

namespace your_service::config {

struct DatabaseConfig {
    int connection_limit;
    int pool_size;
    std::chrono::milliseconds timeout;
    bool enable_ssl;
};

struct RateLimitConfig {
    int requests_per_minute;
    int burst_size;
    std::chrono::seconds window_size;
};

struct ServiceConfig {
    DatabaseConfig database;
    RateLimitConfig rate_limits;
    std::unordered_map<std::string, bool> feature_flags;
    std::string environment;
};

// Parse from dynamic config
DatabaseConfig ParseDatabaseConfig(const dynamic_config::Value& config) {
    return DatabaseConfig{
        .connection_limit = config["DATABASE_CONNECTION_LIMIT"].As<int>(10),
        .pool_size = config["DATABASE_POOL_SIZE"].As<int>(20),
        .timeout = std::chrono::milliseconds(
            config["DATABASE_TIMEOUT_MS"].As<int>(5000)),
        .enable_ssl = config["DATABASE_ENABLE_SSL"].As<bool>(false)
    };
}

// Validate configuration
void ValidateConfig(const ServiceConfig& config) {
    if (config.database.connection_limit <= 0) {
        throw std::runtime_error("Database connection limit must be positive");
    }
    
    if (config.database.pool_size < config.database.connection_limit) {
        throw std::runtime_error("Pool size must be >= connection limit");
    }
    
    if (config.rate_limits.requests_per_minute <= 0) {
        throw std::runtime_error("Rate limit must be positive");
    }
}

} // namespace your_service::config
```

## 5. Using Dynamic Config in Handlers

Inject and use dynamic configuration:

```cpp
#pragma once

#include <userver/components/component_list.hpp>
#include <userver/dynamic_config/client/component.hpp>
#include <userver/dynamic_config/value.hpp>

namespace your_service {

class ConfigAwareHandler final : public server::handlers::HttpHandlerBase {
public:
    static constexpr std::string_view kName = "handler-config-aware";

    ConfigAwareHandler(const components::ComponentConfig& config,
                       const components::ComponentContext& context);

    std::string HandleRequest(server::http::HttpRequest& request,
                              server::request::RequestContext&) const override;

private:
    dynamic_config::Source config_source_;
    std::shared_ptr<config::ServiceConfig> cached_config_;
};

} // namespace your_service
```

Implementation:

```cpp
#include "config_aware_handler.hpp"
#include "config_schema.hpp"

namespace your_service {

ConfigAwareHandler::ConfigAwareHandler(const components::ComponentConfig& config,
                                       const components::ComponentContext& context)
    : HttpHandlerBase(config, context),
      config_source_(context.FindComponent<dynamic_config::ClientComponent>()
                        .GetSource()) {
    
    // Subscribe to config updates
    config_subscription_ = config_source_.UpdateAndListen(
        this, "config-aware-handler",
        &ConfigAwareHandler::OnConfigUpdate);
}

void ConfigAwareHandler::OnConfigUpdate(
    const dynamic_config::Snapshot& snapshot) {
    
    auto new_config = std::make_shared<config::ServiceConfig>();
    new_config->database = config::ParseDatabaseConfig(snapshot);
    new_config->rate_limits = config::ParseRateLimitConfig(snapshot);
    
    // Validate before applying
    config::ValidateConfig(*new_config);
    
    // Atomically swap config (thread-safe)
    cached_config_.store(std::move(new_config));
}

std::string ConfigAwareHandler::HandleRequest(
    server::http::HttpRequest& request,
    server::request::RequestContext&) const {
    
    auto config = cached_config_.load();
    if (!config) {
        request.GetHttpResponse().SetStatus(server::http::HttpStatus::kServiceUnavailable);
        return ToJson(V1Error{"config_unavailable", "Configuration not loaded", std::nullopt});
    }
    
    // Use config values
    if (config->feature_flags.at("NEW_AUTH_FLOW")) {
        // New flow
    } else {
        // Old flow
    }
    
    // Apply rate limiting based on config
    // ...
}

} // namespace your_service
```

## 6. Secrets Management

For sensitive configuration (passwords, API keys):

### Option 1: Environment Variables (Simplest)

```yaml
components:
    postgresql:
        password: ${DB_PASSWORD}
    
    redis:
        password: ${REDIS_PASSWORD}
    
    external-api:
        api-key: ${API_KEY}
```

### Option 2: Secrets File (Mount in Docker)

```yaml
components:
    postgresql:
        password_file: /run/secrets/db_password
    
    redis:
        password_file: /run/secrets/redis_password
```

Docker Compose example:

```yaml
services:
  app:
    image: my-service
    secrets:
      - db_password
      - redis_password

secrets:
  db_password:
    file: ./secrets/db_password.txt
  redis_password:
    file: ./secrets/redis_password.txt
```

### Option 3: External Secrets Service

```cpp
class SecretsClient {
public:
    virtual std::string GetSecret(const std::string& key) = 0;
};

class VaultSecretsClient : public SecretsClient {
public:
    std::string GetSecret(const std::string& key) override {
        // Implement HashiCorp Vault or similar integration
    }
};
```

## 7. Multi-Environment Configuration

Create environment-specific configs:

```
config/
├── base.yaml           # Common configuration
├── development.yaml    # Development overrides
├── staging.yaml        # Staging overrides
└── production.yaml     # Production overrides
```

Base configuration (`config/base.yaml`):

```yaml
components_manager:
    components:
        logging:
            loggers:
                default:
                    level: info
                    overflow_behavior: discard
        
        server:
            listener:
                connection:
                    in_buffer_size: 32768
```

Environment overrides (`config/development.yaml`):

```yaml
components_manager:
    components:
        logging:
            loggers:
                default:
                    level: debug  # More verbose in development
        
        server:
            listener:
                port: 8001
        
        postgresql:
            host: localhost
```

Merge configurations at runtime:

```bash
# Use yq or similar tool to merge
yq eval-all 'select(fileIndex == 0) * select(fileIndex == 1)' \
    config/base.yaml \
    config/development.yaml \
    > static_config.yaml
```

## 8. Configuration Validation at Startup

Add validation in component constructor:

```cpp
YourComponent::YourComponent(const components::ComponentConfig& config,
                             const components::ComponentContext& context)
    : components::LoggableComponentBase(config, context) {
    
    // Validate required configuration
    if (!config.HasMember("required_setting")) {
        throw components::ComponentConfigError(
            "Missing required configuration: required_setting");
    }
    
    int value = config["required_setting"].As<int>();
    if (value <= 0) {
        throw components::ComponentConfigError(
            "required_setting must be positive");
    }
    
    // Log configuration (excluding secrets)
    LOG_INFO() << "Component configured with:"
               << " setting=" << value
               << " timeout=" << config["timeout_ms"].As<int>(5000);
}
```

## 9. Configuration Reloading

Implement hot reload for certain configs:

```cpp
class ReloadableConfig {
public:
    ReloadableConfig(const std::string& config_path)
        : config_path_(config_path) {
        LoadConfig();
        StartWatcher();
    }
    
    void LoadConfig() {
        std::lock_guard<engine::Mutex> lock(mutex_);
        // Parse and validate config file
        // Update internal state
    }
    
private:
    void StartWatcher() {
        watcher_thread_ = std::thread([this] {
            while (!stop_watcher_) {
                std::this_thread::sleep_for(std::chrono::seconds(30));
                CheckForUpdates();
            }
        });
    }
    
    void CheckForUpdates() {
        auto last_write = GetFileModifiedTime(config_path_);
        if (last_write > last_loaded_) {
            LOG_INFO() << "Configuration file updated, reloading";
            LoadConfig();
        }
    }
    
    std::string config_path_;
    engine::Mutex mutex_;
    std::thread watcher_thread_;
    std::atomic<bool> stop_watcher_{false};
    std::filesystem::file_time_type last_loaded_;
};
```

## 10. Configuration Testing

Write tests for configuration:

```cpp
TEST(ConfigurationTest, ValidConfigParsesSuccessfully) {
    const std::string yaml = R"(
        required_setting: 42
        timeout_ms: 5000
        feature_flags:
            new_ui: true
    )";
    
    auto config = formats::yaml::FromString(yaml);
    
    YourComponent::Config parsed(config);
    EXPECT_EQ(parsed.required_setting, 42);
    EXPECT_EQ(parsed.timeout_ms, 5000);
    EXPECT_TRUE(parsed.feature_flags.at("new_ui"));
}

TEST(ConfigurationTest, MissingRequiredSettingThrows) {
    const std::string yaml = "timeout_ms: 5000";
    auto config = formats::yaml::FromString(yaml);
    
    EXPECT_THROW(YourComponent::Config parsed(config),
                 components::ComponentConfigError);
}

TEST(ConfigurationTest, InvalidValueThrows) {
    const std::string yaml = "required_setting: -1";
    auto config = formats::yaml::FromString(yaml);
    
    EXPECT_THROW(YourComponent::Config parsed(config),
                 components::ComponentConfigError);
}
```

## Troubleshooting

### Configuration not applied
- Check YAML syntax (indentation, colons)
- Verify component names match between config and code
- Check for environment variable substitution failures

### Dynamic config not updating
- Ensure `updates-enabled: true`
- Check config service connectivity
- Verify fallback file exists and is readable

### Secrets not loading
- Check file permissions for secret files
- Verify environment variables are set
- Check Docker secrets mounting

### Performance issues with config
- Cache frequently accessed config values
- Use atomic operations for config updates
- Avoid parsing YAML/JSON on every request

## Best Practices

1. **Validate early**: Validate configuration at startup, not at runtime
2. **Use environment-specific configs**: Different values for dev/staging/prod
3. **Keep secrets separate**: Never commit secrets to version control
4. **Document configuration**: Document all config options and their defaults
5. **Use sensible defaults**: Provide reasonable defaults for optional settings
6. **Monitor config changes**: Log when configuration changes occur
7. **Test configuration parsing**: Unit test config parsing and validation
8. **Use feature flags**: For gradual rollouts and emergency kill switches
9. **Implement circuit breakers**: In configuration for external dependencies
10. **Version your configuration**: Track config changes alongside code changes