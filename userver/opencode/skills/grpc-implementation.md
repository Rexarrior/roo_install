---
description: >
  Complete guide to gRPC implementation in userver microservices.
  Includes: proto file definition, gRPC server setup, gRPC client implementation,
  streaming RPCs, error handling, authentication, performance optimization.
  Trigger: gRPC, protocol buffers, proto file, gRPC server, gRPC client,
  streaming RPC, bidirectional streaming, gRPC authentication.
name: grpc-implementation
---

# gRPC Implementation in Userver

Complete guide to implementing gRPC services and clients in userver microservices.

## 1. Protocol Buffer Definition

Define your service in `.proto` file:

```protobuf
syntax = "proto3";

package example.v1;

service ExampleService {
  // Unary RPC
  rpc GetItem(GetItemRequest) returns (GetItemResponse);
  
  // Server streaming
  rpc ListItems(ListItemsRequest) returns (stream ListItemsResponse);
  
  // Client streaming  
  rpc UploadItems(stream UploadItemsRequest) returns (UploadItemsResponse);
  
  // Bidirectional streaming
  rpc Chat(stream ChatMessage) returns (stream ChatMessage);
}

message GetItemRequest {
  string id = 1;
}

message GetItemResponse {
  string id = 1;
  string name = 2;
  int32 value = 3;
}

message ListItemsRequest {
  string filter = 1;
  int32 page_size = 2;
  string page_token = 3;
}

message ListItemsResponse {
  repeated GetItemResponse items = 1;
  string next_page_token = 2;
}

message UploadItemsRequest {
  string id = 1;
  bytes data = 2;
}

message UploadItemsResponse {
  int32 total_count = 1;
  int32 success_count = 2;
}

message ChatMessage {
  string user = 1;
  string text = 2;
  int64 timestamp = 3;
}
```

## 2. Generate C++ Code

Configure code generation in `CMakeLists.txt`:

```cmake
# Find gRPC and Protobuf
find_package(Protobuf REQUIRED)
find_package(gRPC REQUIRED)

# Generate gRPC code
set(PROTO_FILES
    "${CMAKE_CURRENT_SOURCE_DIR}/proto/example.proto"
)

protobuf_generate_cpp(PROTO_SRCS PROTO_HDRS ${PROTO_FILES})
grpc_generate_cpp(GRPC_SRCS GRPC_HDRS ${PROTO_FILES})

# Add to target
add_library(example_proto ${PROTO_SRCS} ${PROTO_HDRS} ${GRPC_SRCS} ${GRPC_HDRS})
target_link_libraries(example_proto PUBLIC
    protobuf::libprotobuf
    gRPC::grpc++
    gRPC::grpc
)
```

## 3. Implement gRPC Server

Create gRPC service implementation:

```cpp
// example_service.hpp
#pragma once

#include <grpcpp/grpcpp.h>
#include "proto/example.grpc.pb.h"

#include <userver/components/component_list.hpp>
#include <userver/components/loggable_component_base.hpp>
#include <userver/engine/task/task.hpp>

namespace example_service {

class ExampleServiceImpl final : public example::v1::ExampleService::Service {
public:
    ::grpc::Status GetItem(
        ::grpc::ServerContext* context,
        const ::example::v1::GetItemRequest* request,
        ::example::v1::GetItemResponse* response) override;
    
    ::grpc::Status ListItems(
        ::grpc::ServerContext* context,
        const ::example::v1::ListItemsRequest* request,
        ::grpc::ServerWriter<::example::v1::ListItemsResponse>* writer) override;
    
    ::grpc::Status UploadItems(
        ::grpc::ServerContext* context,
        ::grpc::ServerReader<::example::v1::UploadItemsRequest>* reader,
        ::example::v1::UploadItemsResponse* response) override;
    
    ::grpc::Status Chat(
        ::grpc::ServerContext* context,
        ::grpc::ServerReaderWriter<::example::v1::ChatMessage, ::example::v1::ChatMessage>* stream) override;

private:
    // Business logic
};
```

## 4. Implement Service Methods

Implement the service methods with userver integration:

```cpp
// example_service.cpp
#include "example_service.hpp"
#include <userver/logging/log.hpp>

namespace example_service {

::grpc::Status ExampleServiceImpl::GetItem(
    ::grpc::ServerContext* context,
    const ::example::v1::GetItemRequest* request,
    ::example::v1::GetItemResponse* response) {
    
    LOG_DEBUG() << "GetItem called for id: " << request->id();
    
    // Validate request
    if (request->id().empty()) {
        return ::grpc::Status(::grpc::StatusCode::INVALID_ARGUMENT, "ID is required");
    }
    
    // Business logic (could be async with userver)
    response->set_id(request->id());
    response->set_name("Example Item");
    response->set_value(42);
    
    return ::grpc::Status::OK;
}

::grpc::Status ExampleServiceImpl::ListItems(
    ::grpc::ServerContext* context,
    const ::example::v1::ListItemsRequest* request,
    ::grpc::ServerWriter<::example::v1::ListItemsResponse>* writer) {
    
    LOG_DEBUG() << "ListItems called with filter: " << request->filter();
    
    // Simulate streaming responses
    for (int i = 0; i < 10; ++i) {
        if (context->IsCancelled()) {
            return ::grpc::Status::CANCELLED;
        }
        
        ::example::v1::ListItemsResponse response;
        auto* item = response.add_items();
        item->set_id("item_" + std::to_string(i));
        item->set_name("Item " + std::to_string(i));
        item->set_value(i * 10);
        
        if (!writer->Write(response)) {
            // Stream broken
            break;
        }
        
        // Simulate delay
        engine::SleepFor(std::chrono::milliseconds(100));
    }
    
    return ::grpc::Status::OK;
}

} // namespace example_service
```

## 5. Create gRPC Server Component

Wrap gRPC server in a userver component:

```cpp
// grpc_server_component.hpp
#pragma once

#include <userver/components/component_base.hpp>
#include <memory>

namespace example_service {

class GrpcServerComponent final : public components::ComponentBase {
public:
    static constexpr std::string_view kName = "grpc-server";

    GrpcServerComponent(const components::ComponentConfig& config,
                        const components::ComponentContext& context);
    
    ~GrpcServerComponent() override;
    
    static yaml_config::Schema GetStaticConfigSchema();

private:
    void Start();
    void Stop();
    
    std::unique_ptr<::grpc::Server> server_;
    std::unique_ptr<ExampleServiceImpl> service_;
};

} // namespace example_service
```

## 6. Configure gRPC Server

Add configuration in `static_config.yaml`:

```yaml
components:
  grpc-server:
    port: 50051
    max-message-size: 4194304  # 4MB
    credentials: plaintext     # or ssl
    worker-threads: 4
    
  # SSL configuration (optional)
  server-ssl:
    cert: /path/to/cert.pem
    key: /path/to/key.pem
    ca: /path/to/ca.pem
```

## 7. Implement gRPC Client

Create gRPC client for inter-service communication:

```cpp
// grpc_client.hpp
#pragma once

#include <memory>
#include <string>
#include <grpcpp/grpcpp.h>
#include "proto/example.grpc.pb.h"

namespace example_service {

class GrpcClient {
public:
    GrpcClient(const std::string& endpoint);
    
    std::optional<::example::v1::GetItemResponse> GetItem(const std::string& id);
    
    std::vector<::example::v1::GetItemResponse> ListItems(const std::string& filter);
    
    bool UploadItems(const std::vector<std::string>& ids, const std::vector<std::string>& data);
    
private:
    std::unique_ptr<::example::v1::ExampleService::Stub> stub_;
};

} // namespace example_service
```

## 8. Client Implementation with Timeouts

```cpp
// grpc_client.cpp
#include "grpc_client.hpp"
#include <userver/engine/async.hpp>
#include <userver/engine/deadline.hpp>
#include <userver/logging/log.hpp>

namespace example_service {

GrpcClient::GrpcClient(const std::string& endpoint) {
    auto channel = ::grpc::CreateChannel(endpoint, ::grpc::InsecureChannelCredentials());
    stub_ = ::example::v1::ExampleService::NewStub(channel);
}

std::optional<::example::v1::GetItemResponse> GrpcClient::GetItem(const std::string& id) {
    ::example::v1::GetItemRequest request;
    request.set_id(id);
    
    ::example::v1::GetItemResponse response;
    ::grpc::ClientContext context;
    
    // Set timeout
    auto deadline = std::chrono::system_clock::now() + std::chrono::seconds(5);
    context.set_deadline(deadline);
    
    // Add metadata
    context.AddMetadata("x-request-id", "12345");
    
    ::grpc::Status status = stub_->GetItem(&context, request, &response);
    
    if (!status.ok()) {
        LOG_ERROR() << "GetItem RPC failed: " << status.error_code() << ": " << status.error_message();
        return std::nullopt;
    }
    
    return response;
}

} // namespace example_service
```

## 9. Streaming Client Implementation

```cpp
// Streaming client for ListItems
std::vector<::example::v1::GetItemResponse> GrpcClient::ListItems(const std::string& filter) {
    ::example::v1::ListItemsRequest request;
    request.set_filter(filter);
    
    ::grpc::ClientContext context;
    auto deadline = std::chrono::system_clock::now() + std::chrono::seconds(30);
    context.set_deadline(deadline);
    
    auto reader = stub_->ListItems(&context, request);
    
    std::vector<::example::v1::GetItemResponse> items;
    ::example::v1::ListItemsResponse response;
    
    while (reader->Read(&response)) {
        for (const auto& item : response.items()) {
            items.push_back(item);
        }
    }
    
    ::grpc::Status status = reader->Finish();
    if (!status.ok()) {
        LOG_ERROR() << "ListItems streaming failed: " << status.error_message();
    }
    
    return items;
}
```

## 10. Error Handling and Retries

Implement resilient gRPC client with retries:

```cpp
class ResilientGrpcClient {
public:
    template<typename Func>
    auto ExecuteWithRetry(Func&& func, int max_retries = 3) {
        for (int attempt = 0; attempt < max_retries; ++attempt) {
            try {
                return func();
            } catch (const std::exception& e) {
                LOG_WARNING() << "gRPC call failed (attempt " << (attempt + 1) 
                             << "/" << max_retries << "): " << e.what();
                
                if (attempt == max_retries - 1) {
                    throw;
                }
                
                // Exponential backoff
                auto delay = std::chrono::milliseconds(100 * (1 << attempt));
                engine::SleepFor(delay);
            }
        }
        throw std::runtime_error("All retries exhausted");
    }
};
```

## 11. Authentication and Security

### SSL/TLS Configuration

```cpp
// Create secure channel
std::shared_ptr<::grpc::ChannelCredentials> CreateSslCredentials(
    const std::string& cert_path,
    const std::string& key_path,
    const std::string& ca_path) {
    
    ::grpc::SslCredentialsOptions ssl_opts;
    ssl_opts.pem_root_certs = ReadFile(ca_path);
    ssl_opts.pem_private_key = ReadFile(key_path);
    ssl_opts.pem_cert_chain = ReadFile(cert_path);
    
    return ::grpc::SslCredentials(ssl_opts);
}
```

### Token-based Authentication

```cpp
// Add token to metadata
void AddAuthToken(::grpc::ClientContext* context, const std::string& token) {
    context->AddMetadata("authorization", "Bearer " + token);
}

// Server-side authentication interceptor
class AuthInterceptor : public ::grpc::experimental::Interceptor {
public:
    void Intercept(::grpc::experimental::InterceptorBatchMethods* methods) override {
        if (methods->QueryInterceptionHookPoint(
                ::grpc::experimental::InterceptionHookPoints::PRE_SEND_INITIAL_METADATA)) {
            
            auto* metadata = methods->GetSendInitialMetadata();
            auto auth_it = metadata->find("authorization");
            if (auth_it == metadata->end()) {
                methods->FailWithError(::grpc::Status(
                    ::grpc::StatusCode::UNAUTHENTICATED, "Missing authorization token"));
            }
        }
    }
};
```

## 12. Performance Optimization

### Connection Pooling

```cpp
class GrpcConnectionPool {
public:
    std::shared_ptr<GrpcClient> GetClient(const std::string& endpoint) {
        std::lock_guard<std::mutex> lock(mutex_);
        
        auto& pool = pools_[endpoint];
        if (pool.empty()) {
            return std::make_shared<GrpcClient>(endpoint);
        }
        
        auto client = std::move(pool.back());
        pool.pop_back();
        return client;
    }
    
    void ReturnClient(const std::string& endpoint, std::shared_ptr<GrpcClient> client) {
        std::lock_guard<std::mutex> lock(mutex_);
        pools_[endpoint].push_back(std::move(client));
    }
    
private:
    std::mutex mutex_;
    std::unordered_map<std::string, std::vector<std::shared_ptr<GrpcClient>>> pools_;
};
```

### Load Balancing

```cpp
// Round-robin load balancer
class LoadBalancedGrpcClient {
public:
    LoadBalancedGrpcClient(const std::vector<std::string>& endpoints) {
        for (const auto& endpoint : endpoints) {
            clients_.push_back(std::make_shared<GrpcClient>(endpoint));
        }
    }
    
    std::shared_ptr<GrpcClient> GetNextClient() {
        size_t index = current_index_.fetch_add(1, std::memory_order_relaxed);
        return clients_[index % clients_.size()];
    }
    
private:
    std::vector<std::shared_ptr<GrpcClient>> clients_;
    std::atomic<size_t> current_index_{0};
};
```

## 13. Monitoring and Metrics

Add metrics for gRPC calls:

```cpp
#include <userver/components/statistics_storage.hpp>
#include <userver/utils/statistics/metric_tag.hpp>

class GrpcMetrics {
public:
    void RecordCall(const std::string& method, ::grpc::StatusCode code, 
                    std::chrono::milliseconds duration) {
        calls_total_.Increment();
        
        if (code != ::grpc::StatusCode::OK) {
            errors_total_.Increment();
        }
        
        auto& histogram = duration_histograms_[method];
        histogram.Account(duration.count());
    }
    
private:
    utils::statistics::MetricTag<utils::statistics::Rate> calls_total_{"grpc_calls_total"};
    utils::statistics::MetricTag<utils::statistics::Rate> errors_total_{"grpc_errors_total"};
    std::unordered_map<std::string, utils::statistics::Histogram> duration_histograms_;
};
```

## 14. Testing gRPC Services

### Unit Tests for gRPC Handlers

```cpp
#include <userver/utest/utest.hpp>
#include <gmock/gmock.h>

class MockExampleService : public ::example::v1::ExampleService::Service {
public:
    MOCK_METHOD(::grpc::Status, GetItem,
                (::grpc::ServerContext*, const ::example::v1::GetItemRequest*,
                 ::example::v1::GetItemResponse*), (override));
};

TEST(GrpcServiceTest, GetItemSuccess) {
    MockExampleService mock_service;
    ::example::v1::GetItemRequest request;
    request.set_id("test123");
    
    ::example::v1::GetItemResponse response;
    EXPECT_CALL(mock_service, GetItem(_, _, _))
        .WillOnce(::testing::DoAll(
            ::testing::SetArgPointee<2>([] {
                ::example::v1::GetItemResponse r;
                r.set_id("test123");
                r.set_name("Test Item");
                return r;
            }()),
            ::testing::Return(::grpc::Status::OK)));
    
    // Test the mock
}
```

### Integration Tests with Test Server

```cpp
class GrpcTestFixture : public ::testing::Test {
protected:
    void SetUp() override {
        // Start test gRPC server
        server_builder_.AddListeningPort("0.0.0.0:0", ::grpc::InsecureServerCredentials());
        server_builder_.RegisterService(&service_);
        server_ = server_builder_.BuildAndStart();
        
        // Create client
        auto channel = ::grpc::CreateChannel(
            server_->GetListeningAddresses()[0],
            ::grpc::InsecureChannelCredentials());
        stub_ = ::example::v1::ExampleService::NewStub(channel);
    }
    
    void TearDown() override {
        server_->Shutdown();
    }
    
    std::unique_ptr<::grpc::Server> server_;
    std::unique_ptr<::example::v1::ExampleService::Stub> stub_;
    ExampleServiceImpl service_;
    ::grpc::ServerBuilder server_builder_;
};
```

## 15. Troubleshooting

### Common Issues

#### Connection Failures
- Check network connectivity: `telnet <host> <port>`
- Verify firewall rules
- Ensure gRPC server is running

#### Performance Issues
- Enable gRPC verbose logging: `export GRPC_VERBOSITY=DEBUG`
- Monitor connection pool usage
- Check for memory leaks in streaming calls

#### Protocol Buffer Errors
- Verify `.proto` file syntax: `protoc --proto_path=. --cpp_out=. example.proto`
- Ensure generated code matches service version
- Check for missing fields in requests

### Debugging Tools

1. **grpcurl**: Command-line gRPC client
   ```bash
   grpcurl -plaintext localhost:50051 describe
   grpcurl -plaintext localhost:50051 example.v1.ExampleService/GetItem -d '{"id": "test"}'
   ```

2. **gRPC Health Checking**
   ```protobuf
   service Health {
     rpc Check(HealthCheckRequest) returns (HealthCheckResponse);
   }
   ```

3. **Prometheus Metrics**
   ```cpp
   #include <grpcpp/grpcpp.h>
   #include <prometheus/exposer.h>
   ```

## Best Practices

1. **Use streaming for large data**: Avoid large unary RPCs (>1MB)
2. **Implement deadlines**: Always set timeouts on client calls
3. **Handle cancellation**: Check `context->IsCancelled()` in streaming methods
4. **Use connection pooling**: Reuse gRPC channels for performance
5. **Implement retries with backoff**: For transient failures
6. **Add comprehensive metrics**: Monitor success rates, latency, error rates
7. **Secure communication**: Always use TLS in production
8. **Validate all inputs**: In both client and server
9. **Use interceptors**: For cross-cutting concerns (auth, logging, metrics)
10. **Test thoroughly**: Include unit, integration, and load tests