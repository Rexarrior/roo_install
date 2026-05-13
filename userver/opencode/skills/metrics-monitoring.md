---
description: >
  Comprehensive guide to metrics collection and monitoring in userver services.
  Includes: metrics types, Prometheus integration, Grafana dashboards,
  alerting, distributed tracing, logging, performance monitoring.
  Trigger: metrics, monitoring, Prometheus, Grafana, alerting, tracing,
  logging, performance metrics, observability.
name: metrics-monitoring
---

# Metrics and Monitoring for Userver Services

Complete guide to implementing observability in userver microservices.

## 1. Metrics Types and Collection

### Basic Metrics

Userver provides built-in metrics support:

```cpp
#include <userver/components/statistics_storage.hpp>
#include <userver/utils/statistics/metric_tag.hpp>
#include <userver/utils/statistics/histogram.hpp>

namespace your_service {

class ServiceMetrics {
public:
    ServiceMetrics() {
        // Register metrics
        statistics_holder_ = utils::statistics::Register(
            "your_service",
            [this](auto& builder) { ExtendMetrics(builder); });
    }
    
    ~ServiceMetrics() {
        statistics_holder_.Unregister();
    }
    
    void RecordRequest(const std::string& endpoint, bool success, 
                       std::chrono::milliseconds duration) {
        requests_total_.Increment();
        
        if (!success) {
            errors_total_.Increment();
        }
        
        auto& histogram = duration_histograms_[endpoint];
        histogram.Account(duration.count());
    }
    
    void RecordCacheHit(bool hit) {
        if (hit) {
            cache_hits_.Increment();
        } else {
            cache_misses_.Increment();
        }
    }
    
private:
    void ExtendMetrics(utils::statistics::Writer& writer) {
        writer["requests_total"] = requests_total_;
        writer["errors_total"] = errors_total_;
        writer["cache_hits"] = cache_hits_;
        writer["cache_misses"] = cache_misses_;
        
        for (const auto& [endpoint, histogram] : duration_histograms_) {
            writer["duration"][endpoint] = histogram;
        }
    }
    
    utils::statistics::MetricTag<utils::statistics::Rate> requests_total_{"requests_total"};
    utils::statistics::MetricTag<utils::statistics::Rate> errors_total_{"errors_total"};
    utils::statistics::MetricTag<utils::statistics::Rate> cache_hits_{"cache_hits"};
    utils::statistics::MetricTag<utils::statistics::Rate> cache_misses_{"cache_misses"};
    
    std::unordered_map<std::string, utils::statistics::Histogram> duration_histograms_;
    utils::statistics::Entry statistics_holder_;
};

} // namespace your_service
```

### Histogram Configuration

Configure histogram buckets for latency metrics:

```cpp
utils::statistics::Histogram CreateLatencyHistogram() {
    // Buckets in milliseconds: 1, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000
    return utils::statistics::Histogram({
        1, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000
    });
}
```

## 2. Prometheus Integration

### Expose Metrics Endpoint

Create HTTP handler for Prometheus metrics:

```cpp
// metrics_handler.hpp
#pragma once

#include <userver/server/handlers/http_handler_base.hpp>
#include <userver/components/statistics_storage.hpp>

namespace your_service {

class MetricsHandler final : public server::handlers::HttpHandlerBase {
public:
    static constexpr std::string_view kName = "handler-metrics";

    MetricsHandler(const components::ComponentConfig& config,
                   const components::ComponentContext& context);
    
    std::string HandleRequest(server::http::HttpRequest& request,
                              server::request::RequestContext&) const override;

private:
    const components::StatisticsStorage& statistics_storage_;
};

} // namespace your_service
```

```cpp
// metrics_handler.cpp
#include "metrics_handler.hpp"
#include <userver/formats/json.hpp>
#include <userver/utils/statistics/prometheus.hpp>

namespace your_service {

MetricsHandler::MetricsHandler(const components::ComponentConfig& config,
                               const components::ComponentContext& context)
    : HttpHandlerBase(config, context),
      statistics_storage_(context.FindComponent<components::StatisticsStorage>()) {
}

std::string MetricsHandler::HandleRequest(server::http::HttpRequest& request,
                                          server::request::RequestContext&) const {
    // Set content type for Prometheus
    request.GetHttpResponse().SetContentType("text/plain; version=0.0.4");
    
    // Get all metrics in Prometheus format
    auto metrics = utils::statistics::ToPrometheusFormat(
        utils::statistics::Request(statistics_storage_, utils::statistics::Format::kPrometheus));
    
    return metrics;
}

} // namespace your_service
```

### Configure Handler

Add to `static_config.yaml`:

```yaml
components:
  handler-metrics:
    path: /metrics
    method: GET
    task_processor: main-task-processor
```

## 3. Grafana Dashboards

### Dashboard Configuration

Create Grafana dashboard JSON for userver services:

```json
{
  "dashboard": {
    "title": "Userver Service Dashboard",
    "panels": [
      {
        "title": "Request Rate",
        "targets": [{
          "expr": "rate(your_service_requests_total[5m])",
          "legendFormat": "{{endpoint}}"
        }]
      },
      {
        "title": "Error Rate",
        "targets": [{
          "expr": "rate(your_service_errors_total[5m])",
          "legendFormat": "{{endpoint}}"
        }]
      },
      {
        "title": "Request Latency",
        "targets": [{
          "expr": "histogram_quantile(0.95, rate(your_service_duration_bucket[5m]))",
          "legendFormat": "{{endpoint}} p95"
        }]
      },
      {
        "title": "Cache Hit Ratio",
        "targets": [{
          "expr": "rate(your_service_cache_hits[5m]) / (rate(your_service_cache_hits[5m]) + rate(your_service_cache_misses[5m]))",
          "legendFormat": "Hit Ratio"
        }]
      }
    ]
  }
}
```

### Alert Rules

Configure Prometheus alert rules:

```yaml
groups:
  - name: userver_alerts
    rules:
      - alert: HighErrorRate
        expr: rate(your_service_errors_total[5m]) / rate(your_service_requests_total[5m]) > 0.05
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High error rate detected"
          description: "Error rate is {{ $value }} for service {{ $labels.service }}"
      
      - alert: HighLatency
        expr: histogram_quantile(0.95, rate(your_service_duration_bucket[5m])) > 1000
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High latency detected"
          description: "95th percentile latency is {{ $value }}ms for endpoint {{ $labels.endpoint }}"
```

## 4. Distributed Tracing

### Jaeger Integration

Configure distributed tracing with Jaeger:

```yaml
# static_config.yaml
components:
  tracing:
    service-name: your-service
    tracer: jaeger
    
  jaeger-tracer:
    endpoint: http://jaeger:14268/api/traces
    http-transport: curl
```

### Manual Tracing

Create spans for custom operations:

```cpp
#include <userver/tracing/span.hpp>
#include <userver/tracing/tags.hpp>

void ProcessRequest(const Request& req) {
    // Create a span for this operation
    tracing::Span span("process_request");
    
    // Add tags to the span
    span.AddTag("request_id", req.id);
    span.AddTag("user_id", req.user_id);
    span.AddTag(tracing::kHttpMethod, "POST");
    span.AddTag(tracing::kHttpUrl, "/api/process");
    
    try {
        // Business logic
        span.AddTag("status", "success");
    } catch (const std::exception& e) {
        span.AddTag("error", true);
        span.AddTag("error_message", e.what());
        span.AddTag(tracing::kErrorFlag, true);
        throw;
    }
}

// Nested spans
void ComplexOperation() {
    tracing::Span outer_span("complex_operation");
    
    {
        tracing::Span inner_span("sub_operation_1");
        // Do work
        inner_span.AddTag("result", "success");
    }
    
    {
        tracing::Span inner_span("sub_operation_2");
        // Do more work
        inner_span.AddTag("result", "success");
    }
}
```

### Trace Context Propagation

Pass trace context between services:

```cpp
// Client side
void CallExternalService() {
    auto span = tracing::Span::CurrentSpan();
    
    // Get trace context
    auto trace_id = span.GetTraceId();
    auto span_id = span.GetSpanId();
    auto parent_span_id = span.GetParentId();
    
    // Add headers for external call
    headers::HeaderMap headers;
    headers["X-Trace-Id"] = trace_id;
    headers["X-Span-Id"] = span_id;
    headers["X-Parent-Span-Id"] = parent_span_id;
    
    // Make HTTP request with headers
    auto response = http_client_.CreateRequest()
        .headers(std::move(headers))
        .post("http://external-service/api")
        .timeout(std::chrono::seconds(5))
        .perform();
}
```

## 5. Structured Logging

### JSON Logging Configuration

Configure structured JSON logging:

```yaml
# static_config.yaml
components:
  logging:
    format: tskv
    level: debug
    file-path: /var/log/your-service/service.log
    
    # Optional: log to stdout for containers
    logger-name: default
    
  loggers:
    access:
      file-path: /var/log/your-service/access.log
      format: tskv
      level: info
```

### Contextual Logging

Add context to logs:

```cpp
#include <userver/logging/log.hpp>

void HandleRequest(const Request& req) {
    // Create log context
    logging::LogExtra extra{
        {"request_id", req.id},
        {"user_id", req.user_id},
        {"endpoint", "/api/process"},
        {"correlation_id", tracing::Span::CurrentSpan().GetTraceId()}
    };
    
    LOG_INFO() << "Processing request" << extra;
    
    try {
        // Business logic
        LOG_DEBUG() << "Request processing complete" << extra;
    } catch (const std::exception& e) {
        LOG_ERROR() << "Request failed: " << e.what() << extra;
        throw;
    }
}
```

### Custom Log Attributes

Add custom attributes to all logs in a scope:

```cpp
class ScopedLogAttributes {
public:
    ScopedLogAttributes(std::initializer_list<std::pair<std::string, std::string>> attributes) {
        for (const auto& [key, value] : attributes) {
            logging::LogFlush::GetLogger()->AddTag(key, value);
        }
    }
    
    ~ScopedLogAttributes() {
        // Tags are automatically removed when scope exits
    }
};

void ProcessWithContext() {
    ScopedLogAttributes attrs{
        {"operation", "batch_process"},
        {"batch_id", "12345"},
        {"priority", "high"}
    };
    
    LOG_INFO() << "Starting batch processing";
    // All logs in this scope will include the attributes
}
```

## 6. Health Checks

### Liveness and Readiness Probes

Implement health check endpoints:

```cpp
// health_handler.hpp
#pragma once

#include <userver/server/handlers/http_handler_base.hpp>
#include <userver/components/component_context.hpp>

namespace your_service {

class HealthHandler final : public server::handlers::HttpHandlerBase {
public:
    static constexpr std::string_view kName = "handler-health";

    HealthHandler(const components::ComponentConfig& config,
                  const components::ComponentContext& context);
    
    std::string HandleRequest(server::http::HttpRequest& request,
                              server::request::RequestContext&) const override;

private:
    bool CheckDatabase() const;
    bool CheckCache() const;
    bool CheckExternalService() const;
    
    const components::ComponentContext& context_;
};

} // namespace your_service
```

```cpp
// health_handler.cpp
#include "health_handler.hpp"
#include <userver/formats/json.hpp>
#include <userver/clients/http/component.hpp>
#include <userver/storages/postgres/component.hpp>

namespace your_service {

HealthHandler::HealthHandler(const components::ComponentConfig& config,
                             const components::ComponentContext& context)
    : HttpHandlerBase(config, context),
      context_(context) {
}

std::string HealthHandler::HandleRequest(server::http::HttpRequest& request,
                                         server::request::RequestContext&) const {
    request.GetHttpResponse().SetContentType(http::content_type::kApplicationJson);
    
    bool is_healthy = true;
    std::vector<std::string> failures;
    
    // Check database
    if (!CheckDatabase()) {
        is_healthy = false;
        failures.push_back("database");
    }
    
    // Check cache
    if (!CheckCache()) {
        is_healthy = false;
        failures.push_back("cache");
    }
    
    // Check external service
    if (!CheckExternalService()) {
        is_healthy = false;
        failures.push_back("external_service");
    }
    
    formats::json::ValueBuilder response;
    response["status"] = is_healthy ? "healthy" : "unhealthy";
    response["timestamp"] = std::chrono::system_clock::now().time_since_epoch().count();
    
    if (!failures.empty()) {
        response["failures"] = failures;
    }
    
    if (!is_healthy) {
        request.GetHttpResponse().SetStatus(http::HttpStatus::kServiceUnavailable);
    }
    
    return formats::json::ToString(response.ExtractValue());
}

bool HealthHandler::CheckDatabase() const {
    try {
        auto& pg = context_.FindComponent<storages::postgres::Component>();
        auto cluster = pg.GetCluster();
        
        // Simple query to check connectivity
        auto result = cluster->Execute(storages::postgres::ClusterHostType::kMaster,
                                       "SELECT 1");
        return true;
    } catch (const std::exception&) {
        return false;
    }
}

} // namespace your_service
```

### Kubernetes Health Checks

Configure Kubernetes probes:

```yaml
# kubernetes deployment.yaml
spec:
  containers:
  - name: your-service
    livenessProbe:
      httpGet:
        path: /health
        port: 8080
      initialDelaySeconds: 30
      periodSeconds: 10
      timeoutSeconds: 5
      failureThreshold: 3
    
    readinessProbe:
      httpGet:
        path: /health
        port: 8080
      initialDelaySeconds: 5
      periodSeconds: 5
      timeoutSeconds: 3
      successThreshold: 1
      failureThreshold: 3
```

## 7. Performance Monitoring

### Resource Metrics

Monitor CPU, memory, and other resources:

```cpp
#include <sys/resource.h>
#include <unistd.h>

class ResourceMonitor {
public:
    struct ResourceUsage {
        double cpu_usage_percent;
        size_t memory_usage_kb;
        size_t open_files;
        size_t threads_count;
    };
    
    ResourceUsage GetCurrentUsage() const {
        ResourceUsage usage;
        
        // Get CPU usage
        struct rusage ru;
        getrusage(RUSAGE_SELF, &ru);
        usage.cpu_usage_percent = (ru.ru_utime.tv_sec + ru.ru_stime.tv_sec) * 100.0 /
                                  sysconf(_SC_CLK_TCK);
        
        // Get memory usage from /proc
        std::ifstream status("/proc/self/status");
        std::string line;
        while (std::getline(status, line)) {
            if (line.find("VmRSS:") == 0) {
                std::istringstream iss(line);
                std::string key;
                size_t value;
                iss >> key >> value;
                usage.memory_usage_kb = value;
            } else if (line.find("Threads:") == 0) {
                std::istringstream iss(line);
                std::string key;
                size_t value;
                iss >> key >> value;
                usage.threads_count = value;
            }
        }
        
        return usage;
    }
};
```

### Garbage Collection Metrics

Monitor garbage collection in userver:

```cpp
class GcMonitor {
public:
    void RecordGcEvent(std::chrono::milliseconds duration, size_t bytes_freed) {
        gc_events_total_.Increment();
        gc_duration_histogram_.Account(duration.count());
        gc_bytes_freed_total_.Add(bytes_freed);
        
        LOG_DEBUG() << fmt::format(
            "GC event: freed {} bytes in {} ms", bytes_freed, duration.count());
    }
    
private:
    utils::statistics::MetricTag<utils::statistics::Rate> gc_events_total_{"gc_events_total"};
    utils::statistics::MetricTag<utils::statistics::Rate> gc_bytes_freed_total_{"gc_bytes_freed_total"};
    utils::statistics::Histogram gc_duration_histogram_{{1, 5, 10, 50, 100, 500, 1000}};
};
```

## 8. Custom Metrics Export

### Export Metrics to Multiple Backends

```cpp
class MultiBackendMetricsExporter {
public:
    void ExportToPrometheus() {
        auto metrics = utils::statistics::ToPrometheusFormat(
            utils::statistics::Request(storage_, utils::statistics::Format::kPrometheus));
        
        // Write to file for node_exporter
        std::ofstream file("/var/lib/node_exporter/textfile_collector/userver.prom");
        file << metrics;
    }
    
    void ExportToStatsD(const std::string& host, int port) {
        auto metrics = utils::statistics::ToStatsdFormat(
            utils::statistics::Request(storage_, utils::statistics::Format::kStatsd));
        
        // Send via UDP to StatsD
        boost::asio::io_service io_service;
        boost::asio::ip::udp::socket socket(io_service);
        boost::asio::ip::udp::endpoint endpoint(
            boost::asio::ip::address::from_string(host), port);
        
        socket.open(boost::asio::ip::udp::v4());
        socket.send_to(boost::asio::buffer(metrics), endpoint);
    }
    
    void ExportToOpenTelemetry() {
        // Convert to OpenTelemetry format
        auto metrics = utils::statistics::ToJsonFormat(
            utils::statistics::Request(storage_, utils::statistics::Format::kJson));
        
        // Send to OpenTelemetry collector
        // Implementation depends on OpenTelemetry C++ SDK
    }
    
private:
    components::StatisticsStorage& storage_;
};
```

## 9. Alerting Integration

### Alert Manager Webhook

Receive alerts from Alertmanager:

```cpp
// alert_handler.hpp
#pragma once

#include <userver/server/handlers/http_handler_base.hpp>

namespace your_service {

class AlertHandler final : public server::handlers::HttpHandlerBase {
public:
    static constexpr std::string_view kName = "handler-alerts";

    AlertHandler(const components::ComponentConfig& config,
                 const components::ComponentContext& context);
    
    std::string HandleRequest(server::http::HttpRequest& request,
                              server::request::RequestContext&) const override;

private:
    void ProcessAlert(const formats::json::Value& alert) const;
    void NotifyTeam(const std::string& alert_name, const std::string& severity) const;
};

} // namespace your_service
```

```cpp
// alert_handler.cpp
#include "alert_handler.hpp"
#include <userver/formats/json.hpp>
#include <userver/clients/http/component.hpp>

namespace your_service {

AlertHandler::AlertHandler(const components::ComponentConfig& config,
                           const components::ComponentContext& context)
    : HttpHandlerBase(config, context) {
}

std::string AlertHandler::HandleRequest(server::http::HttpRequest& request,
                                        server::request::RequestContext&) const {
    auto body = formats::json::FromString(request.RequestBody());
    
    for (const auto& alert : body["alerts"]) {
        ProcessAlert(alert);
    }
    
    return "{}"; // Empty JSON response
}

void AlertHandler::ProcessAlert(const formats::json::Value& alert) const {
    std::string status = alert["status"].As<std::string>();
    std::string alert_name = alert["labels"]["alertname"].As<std::string>();
    std::string severity = alert["labels"]["severity"].As<std::string>();
    
    LOG_WARNING() << fmt::format(
        "Alert received: name={}, status={}, severity={}", 
        alert_name, status, severity);
    
    if (status == "firing") {
        NotifyTeam(alert_name, severity);
    }
}

} // namespace your_service
```

## 10. Troubleshooting

### Common Issues

#### Metrics Not Appearing in Prometheus
- Check metrics endpoint is accessible: `curl http://localhost:8080/metrics`
- Verify Prometheus scrape configuration
- Check metric names match Prometheus naming conventions (snake_case)

#### High Memory Usage
- Enable memory profiling: `HEAPPROFILE=/tmp/heap.prof`
- Check for memory leaks in long-lived objects
- Monitor garbage collection frequency

#### Tracing Not Working
- Verify Jaeger/OpenTelemetry collector is running
- Check trace sampling rate configuration
- Ensure trace context is propagated between services

### Debugging Tools

1. **pprof** for CPU profiling:
   ```bash
   # Start profiling
   curl http://localhost:8080/debug/pprof/profile?seconds=30 > profile.prof
   
   # Analyze
   go tool pprof -http=:8081 profile.prof
   ```

2. **valgrind** for memory leaks:
   ```bash
   valgrind --leak-check=full ./your_service
   ```

3. **strace** for system calls:
   ```bash
   strace -p $(pidof your_service) -f -tt -T
   ```

## Best Practices

1. **Use consistent metric naming**: Follow Prometheus conventions
2. **Add labels judiciously**: Too many labels cause high cardinality
3. **Set appropriate histogram buckets**: For your service's latency profile
4. **Monitor saturation metrics**: Queue lengths, error rates, resource usage
5. **Implement distributed tracing**: For debugging cross-service issues
6. **Use structured logging**: For easier parsing and analysis
7. **Set up alerts**: But avoid alert fatigue
8. **Test monitoring in development**: Ensure alerts work before production
9. **Document dashboards**: Include descriptions and usage instructions
10. **Regularly review metrics**: Remove unused metrics, adjust thresholds