---
description: >
  Comprehensive testing strategies for userver microservices.
  Includes: unit testing, integration testing, component testing,
  end-to-end testing, test fixtures, mocking, test configuration.
  Trigger: write tests, unit testing, integration tests, component tests,
  test fixtures, mock services, test coverage, testing strategy.
name: testing-strategies
---

# Testing Strategies for Userver Services

Complete guide to testing userver microservices with various testing approaches.

## 1. Unit Testing Business Logic

Test pure business logic without framework dependencies:

```cpp
// calculator.hpp
#pragma once

namespace your_service {

class Calculator {
public:
    int Add(int a, int b) const { return a + b; }
    int Multiply(int a, int b) const { return a * b; }
    double Divide(double a, double b) const {
        if (b == 0.0) {
            throw std::invalid_argument("Division by zero");
        }
        return a / b;
    }
};

} // namespace your_service
```

Corresponding tests:

```cpp
// test_calculator.cpp
#include <gtest/gtest.h>
#include "calculator.hpp"

namespace your_service::test {

TEST(CalculatorTest, AddReturnsSum) {
    Calculator calc;
    EXPECT_EQ(calc.Add(2, 3), 5);
    EXPECT_EQ(calc.Add(-1, 1), 0);
    EXPECT_EQ(calc.Add(0, 0), 0);
}

TEST(CalculatorTest, MultiplyReturnsProduct) {
    Calculator calc;
    EXPECT_EQ(calc.Multiply(2, 3), 6);
    EXPECT_EQ(calc.Multiply(-1, 5), -5);
    EXPECT_EQ(calc.Multiply(0, 100), 0);
}

TEST(CalculatorTest, DivideReturnsQuotient) {
    Calculator calc;
    EXPECT_DOUBLE_EQ(calc.Divide(10.0, 2.0), 5.0);
    EXPECT_DOUBLE_EQ(calc.Divide(5.0, 2.0), 2.5);
}

TEST(CalculatorTest, DivideByZeroThrows) {
    Calculator calc;
    EXPECT_THROW(calc.Divide(10.0, 0.0), std::invalid_argument);
}

} // namespace your_service::test
```

## 2. Component Testing with Userver Test Framework

Test components with userver test infrastructure:

```cpp
// test_auth_handler.cpp
#include <userver/utest/utest.hpp>
#include <userver/components/component_list.hpp>
#include <userver/components/minimal_component_list.hpp>
#include <userver/utils/daemon_run.hpp>

#include "auth_handler.hpp"

namespace your_service::test {

namespace http = userver::http;
using server::handlers::HttpHandlerBase;

// Test fixture for auth handler
class ExampleHandlerTest : public ::testing::Test {
protected:
    void SetUp() override {
        // Create component list with minimal dependencies
        component_list_ = components::MinimalComponentList()
            .Append<example_service::ExampleHandler>();
        
        // Create component context
        // (Simplified - in real tests use components::RunOnce)
    }
    
    void TearDown() override {
        // Cleanup
    }
    
    components::ComponentList component_list_;
};

// Test authentication endpoint
UTEST_F(ExampleHandlerTest, RegistrationSuccess) {
    // Create mock request
    server::http::MockHttpRequest request;
    request.SetMethod(http::HttpMethod::kPost);
    request.SetPath("/v1/user/registration");
    request.SetRequestBody(R"({
        "login": "testuser",
        "name": "Test User",
        "email": "test@example.com",
        "phone": "123456789",
        "password": "password123"
    })");
    
    // Create handler instance
    auto handler = std::make_unique<example_service::ExampleHandler>(
        components::ComponentConfig("handler-auth", {}),
        components::ComponentContext());
    
    // Execute handler
    server::request::RequestContext context;
    auto response = handler->HandleRequest(request, context);
    
    // Validate response
    EXPECT_EQ(request.GetHttpResponse().GetStatus(), http::HttpStatus::kOk);
    
    // Parse response JSON
    auto json = formats::json::FromString(response);
    EXPECT_TRUE(json.HasMember("current_user"));
    EXPECT_TRUE(json["current_user"].HasMember("token"));
    EXPECT_EQ(json["current_user"]["login"].As<std::string>(), "testuser");
}

UTEST_F(ExampleHandlerTest, RegistrationDuplicateUser) {
    // First registration
    {
        server::http::MockHttpRequest request;
        request.SetMethod(http::HttpMethod::kPost);
        request.SetPath("/v1/user/registration");
        request.SetRequestBody(R"({"login": "user1", "name": "User1", /* ... */ })");
        
        auto handler = CreateHandler();
        server::request::RequestContext context;
        handler->HandleRequest(request, context);
    }
    
    // Second registration with same login
    {
        server::http::MockHttpRequest request;
        request.SetMethod(http::HttpMethod::kPost);
        request.SetPath("/v1/user/registration");
        request.SetRequestBody(R"({"login": "user1", "name": "User1", /* ... */ })");
        
        auto handler = CreateHandler();
        server::request::RequestContext context;
        auto response = handler->HandleRequest(request, context);
        
        EXPECT_EQ(request.GetHttpResponse().GetStatus(), http::HttpStatus::kConflict);
        
        auto json = formats::json::FromString(response);
        EXPECT_EQ(json["code"].As<std::string>(), "user_exists");
    }
}

} // namespace your_service::test
```

## 3. Integration Testing with Real HTTP Server

Test endpoints with actual HTTP server:

```cpp
// test_auth_integration.cpp
#include <userver/utest/utest.hpp>
#include <userver/http/client.hpp>
#include <userver/utils/async.hpp>

#include <userver/utest/http_client.hpp>
#include <userver/utest/http_server_mock.hpp>

namespace your_service::test {

// Start actual server for integration tests
UTEST(AuthIntegration, FullRegistrationFlow) {
    // Start test server
    constexpr int kTestPort = 8181;
    auto server = utest::StartHttpServer(kTestPort);
    
    // Register handler
    server.RegisterHandler("/v1/user/registration",
        [](const server::http::HttpRequest& request,
           server::request::RequestContext& context) {
            example_service::ExampleHandler handler;
            return handler.HandleRequest(request, context);
        });
    
    // Create HTTP client
    auto http_client = utest::CreateHttpClient();
    
    // Send registration request
    auto response = http_client.CreateRequest()
        .post(fmt::format("http://localhost:{}/v1/user/registration", kTestPort))
        .header("Content-Type", "application/json")
        .body(R"({
            "login": "integration_user",
            "name": "Integration Test",
            "email": "integration@test.com",
            "phone": "5551234567",
            "password": "testpass123"
        })")
        .timeout(std::chrono::seconds(5))
        .perform();
    
    // Verify response
    EXPECT_EQ(response->status_code(), 200);
    
    auto json = formats::json::FromString(response->body());
    EXPECT_TRUE(json.HasMember("current_user"));
    EXPECT_TRUE(json["current_user"].HasMember("token"));
    
    // Test authorization with received token
    auto token = json["current_user"]["token"].As<std::string>();
    
    auto auth_response = http_client.CreateRequest()
        .post(fmt::format("http://localhost:{}/v1/user/authorization", kTestPort))
        .header("Content-Type", "application/json")
        .header("Authorization", token)
        .body(R"({
            "login": "integration_user",
            "password": "testpass123"
        })")
        .perform();
    
    EXPECT_EQ(auth_response->status_code(), 200);
}

} // namespace your_service::test
```

## 4. Database Testing with Test Containers

Test database interactions:

```cpp
// test_user_repository.cpp
#include <userver/utest/utest.hpp>
#include <userver/storages/postgres/io/row_types.hpp>

#include "user_repository.hpp"

namespace your_service::test {

// PostgreSQL test container fixture
class DatabaseTest : public ::testing::Test {
protected:
    static void SetUpTestSuite() {
        // Start PostgreSQL test container
        testcontainers::PostgreSQL postgres{"postgres:15-alpine"};
        postgres.start();
        
        connection_string_ = postgres.getConnectionString();
        
        // Create test database schema
        auto conn = storages::postgres::Connection(connection_string_);
        conn.Execute(R"(
            CREATE TABLE users (
                id SERIAL PRIMARY KEY,
                login VARCHAR(100) UNIQUE NOT NULL,
                name VARCHAR(200) NOT NULL,
                email VARCHAR(200) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        )");
    }
    
    static void TearDownTestSuite() {
        // Stop container
    }
    
    void SetUp() override {
        // Create fresh connection for each test
        cluster_ = std::make_shared<storages::postgres::Cluster>(
            connection_string_);
        repository_ = std::make_unique<UserRepository>(cluster_);
        
        // Clear table before each test
        cluster_->Execute(
            storages::postgres::ClusterHostType::kMaster,
            "TRUNCATE TABLE users RESTART IDENTITY");
    }
    
    static std::string connection_string_;
    storages::postgres::ClusterPtr cluster_;
    std::unique_ptr<UserRepository> repository_;
};

std::string DatabaseTest::connection_string_;

UTEST_F(DatabaseTest, CreateUserSuccess) {
    User user{
        .login = "testuser",
        .name = "Test User",
        .email = "test@example.com"
    };
    
    auto created = repository_->CreateUser(user);
    ASSERT_TRUE(created.has_value());
    EXPECT_GT(created->id, 0);
    EXPECT_EQ(created->login, "testuser");
    EXPECT_EQ(created->name, "Test User");
    EXPECT_EQ(created->email, "test@example.com");
}

UTEST_F(DatabaseTest, CreateUserDuplicateFails) {
    User user1{.login = "user1", .name = "User1", .email = "user1@test.com"};
    User user2{.login = "user1", .name = "User2", .email = "user2@test.com"};
    
    auto result1 = repository_->CreateUser(user1);
    EXPECT_TRUE(result1.has_value());
    
    auto result2 = repository_->CreateUser(user2);
    EXPECT_FALSE(result2.has_value()); // Should fail due to duplicate login
}

UTEST_F(DatabaseTest, GetUserByLogin) {
    User user{.login = "findme", .name = "Find Me", .email = "find@me.com"};
    
    auto created = repository_->CreateUser(user);
    ASSERT_TRUE(created.has_value());
    
    auto found = repository_->GetUserByLogin("findme");
    ASSERT_TRUE(found.has_value());
    EXPECT_EQ(found->login, "findme");
    EXPECT_EQ(found->name, "Find Me");
    
    auto not_found = repository_->GetUserByLogin("nonexistent");
    EXPECT_FALSE(not_found.has_value());
}

UTEST_F(DatabaseTest, UpdateUser) {
    User user{.login = "toupdate", .name = "Old Name", .email = "old@email.com"};
    
    auto created = repository_->CreateUser(user);
    ASSERT_TRUE(created.has_value());
    
    User updated = *created;
    updated.name = "New Name";
    updated.email = "new@email.com";
    
    bool success = repository_->UpdateUser(updated);
    EXPECT_TRUE(success);
    
    auto fetched = repository_->GetUserByLogin("toupdate");
    ASSERT_TRUE(fetched.has_value());
    EXPECT_EQ(fetched->name, "New Name");
    EXPECT_EQ(fetched->email, "new@email.com");
}

UTEST_F(DatabaseTest, DeleteUser) {
    User user{.login = "todelete", .name = "Delete Me", .email = "delete@me.com"};
    
    auto created = repository_->CreateUser(user);
    ASSERT_TRUE(created.has_value());
    
    bool deleted = repository_->DeleteUser("todelete");
    EXPECT_TRUE(deleted);
    
    auto found = repository_->GetUserByLogin("todelete");
    EXPECT_FALSE(found.has_value());
}

} // namespace your_service::test
```

## 5. Mocking External Services

Mock external HTTP services for testing:

```cpp
// test_external_service.cpp
#include <userver/utest/utest.hpp>
#include <userver/http/mock_http_client.hpp>

#include "external_service_client.hpp"

namespace your_service::test {

class ExternalServiceTest : public ::testing::Test {
protected:
    void SetUp() override {
        mock_client_ = std::make_shared<http::MockHttpClient>();
        client_ = std::make_unique<ExternalServiceClient>(mock_client_);
    }
    
    std::shared_ptr<http::MockHttpClient> mock_client_;
    std::unique_ptr<ExternalServiceClient> client_;
};

UTEST_F(ExternalServiceTest, SuccessfulApiCall) {
    // Mock successful response
    mock_client_->AddMockResponse(
        http::HttpMethod::kGet,
        "https://api.external.com/v1/data",
        http::HttpStatus::kOk,
        R"({"result": "success", "data": {"value": 42}})",
        {{"Content-Type", "application/json"}});
    
    auto result = client_->GetData();
    EXPECT_TRUE(result.has_value());
    EXPECT_EQ(result->value, 42);
}

UTEST_F(ExternalServiceTest, ApiCallTimeout) {
    // Mock timeout
    mock_client_->AddMockResponse(
        http::HttpMethod::kGet,
        "https://api.external.com/v1/data",
        std::nullopt, // No response (simulates timeout)
        std::chrono::seconds(10)); // Delay
    
    auto result = client_->GetData();
    EXPECT_FALSE(result.has_value());
    EXPECT_TRUE(client_->LastError().find("timeout") != std::string::npos);
}

UTEST_F(ExternalServiceTest, ApiCallServerError) {
    // Mock server error
    mock_client_->AddMockResponse(
        http::HttpMethod::kGet,
        "https://api.external.com/v1/data",
        http::HttpStatus::kInternalServerError,
        R"({"error": "Internal server error"})");
    
    auto result = client_->GetData();
    EXPECT_FALSE(result.has_value());
    EXPECT_TRUE(client_->LastError().find("500") != std::string::npos);
}

} // namespace your_service::test
```

## 6. Component Testing with Dependency Injection

Test components with injected dependencies:

```cpp
// test_example_service.cpp
#include <userver/utest/utest.hpp>
#include <gmock/gmock.h>

#include "example_service.hpp"
#include "user_repository_mock.hpp"

namespace your_service::test {

class MockUserRepository : public UserRepository {
public:
    MOCK_METHOD(std::optional<User>, GetUserByLogin, (const std::string&), (override));
    MOCK_METHOD(std::optional<User>, CreateUser, (const User&), (override));
    MOCK_METHOD(bool, UpdateUser, (const User&), (override));
    MOCK_METHOD(bool, DeleteUser, (const std::string&), (override));
};

class AuthServiceTest : public ::testing::Test {
protected:
    void SetUp() override {
        mock_repo_ = std::make_shared<MockUserRepository>();
        example_service_ = std::make_unique<AuthService>(mock_repo_);
    }
    
    std::shared_ptr<MockUserRepository> mock_repo_;
    std::unique_ptr<AuthService> example_service_;
};

UTEST_F(AuthServiceTest, AuthenticateValidUser) {
    User user{
        .login = "testuser",
        .name = "Test User",
        .email = "test@example.com",
        .password_hash = "hashed_password"
    };
    
    EXPECT_CALL(*mock_repo_, GetUserByLogin("testuser"))
        .WillOnce(::testing::Return(user));
    
    auto result = example_service_->Authenticate("testuser", "password123");
    EXPECT_TRUE(result.has_value());
    EXPECT_EQ(result->login, "testuser");
}

UTEST_F(AuthServiceTest, AuthenticateInvalidUser) {
    EXPECT_CALL(*mock_repo_, GetUserByLogin("nonexistent"))
        .WillOnce(::testing::Return(std::nullopt));
    
    auto result = example_service_->Authenticate("nonexistent", "password");
    EXPECT_FALSE(result.has_value());
}

UTEST_F(AuthServiceTest, RegisterNewUser) {
    User new_user{
        .login = "newuser",
        .name = "New User",
        .email = "new@example.com"
    };
    
    User created_user = new_user;
    created_user.id = 1;
    created_user.created_at = std::chrono::system_clock::now();
    
    EXPECT_CALL(*mock_repo_, GetUserByLogin("newuser"))
        .WillOnce(::testing::Return(std::nullopt));
    
    EXPECT_CALL(*mock_repo_, CreateUser(::testing::_))
        .WillOnce(::testing::Return(created_user));
    
    auto result = example_service_->Register(new_user, "password123");
    EXPECT_TRUE(result.has_value());
    EXPECT_EQ(result->login, "newuser");
}

UTEST_F(AuthServiceTest, RegisterExistingUser) {
    User existing_user{
        .login = "existing",
        .name = "Existing User",
        .email = "existing@example.com"
    };
    
    EXPECT_CALL(*mock_repo_, GetUserByLogin("existing"))
        .WillOnce(::testing::Return(existing_user));
    
    auto result = example_service_->Register(existing_user, "password");
    EXPECT_FALSE(result.has_value()); // Should fail - user exists
}

} // namespace your_service::test
```

## 7. End-to-End Testing with Docker Compose

Create Docker-based E2E tests:

```yaml
# docker-compose.test.yaml
version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: test_db
      POSTGRES_USER: test_user
      POSTGRES_PASSWORD: test_password
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U test_user"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5

  auth-service:
    build:
      context: .
      dockerfile: example_service/Dockerfile.test
    environment:
      POSTGRES_HOST: postgres
      POSTGRES_PORT: 5432
      POSTGRES_DB: test_db
      POSTGRES_USER: test_user
      POSTGRES_PASSWORD: test_password
      REDIS_HOST: redis
      REDIS_PORT: 6379
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    ports:
      - "8001:8001"

  test-runner:
    build:
      context: .
      dockerfile: tests/Dockerfile
    depends_on:
      auth-service:
        condition: service_started
    environment:
      AUTH_SERVICE_URL: http://auth-service:8001
    command: ["./run_tests.sh"]
```

Test runner script:

```bash
#!/bin/bash
# run_tests.sh

# Wait for services to be ready
echo "Waiting for auth service..."
until curl -f http://auth-service:8001/healthcheck >/dev/null 2>&1; do
  sleep 1
done

echo "Running tests..."

# Run different test types
./run_unit_tests
./run_integration_tests --service-url=http://auth-service:8001
./run_e2e_tests --auth-url=http://auth-service:8001

# Check test results
if [ $? -eq 0 ]; then
  echo "All tests passed!"
  exit 0
else
  echo "Tests failed!"
  exit 1
fi
```

## 8. Performance and Load Testing

Add performance tests:

```cpp
// test_performance.cpp
#include <userver/utest/utest.hpp>
#include <userver/utils/statistics/testing.hpp>

#include "auth_handler.hpp"

namespace your_service::test {

UTEST_P(ExampleHandlerPerformance, RegistrationThroughput) {
    const int iterations = GetParam();
    
    auto handler = CreateHandler();
    auto metrics_before = utils::statistics::Snapshot();
    
    for (int i = 0; i < iterations; ++i) {
        server::http::MockHttpRequest request;
        request.SetMethod(http::HttpMethod::kPost);
        request.SetPath("/v1/user/registration");
        request.SetRequestBody(fmt::format(R"({{
            "login": "perfuser{}",
            "name": "Performance User {}",
            "email": "perf{}@test.com",
            "phone": "1234567890",
            "password": "password123"
        }})", i, i, i));
        
        server::request::RequestContext context;
        handler->HandleRequest(request, context);
        
        EXPECT_EQ(request.GetHttpResponse().GetStatus(), http::HttpStatus::kOk);
    }
    
    auto metrics_after = utils::statistics::Snapshot();
    auto duration = metrics_after.GetTime() - metrics_before.GetTime();
    
    double throughput = iterations / duration.count();
    std::cout << "Throughput: " << throughput << " req/sec" << std::endl;
    
    // Assert minimum throughput requirement
    EXPECT_GT(throughput, 100.0); // At least 100 req/sec
}

INSTANTIATE_UTEST_SUITE_P(
    ExampleHandlerPerformanceSuite,
    ExampleHandlerPerformance,
    ::testing::Values(100, 500, 1000));

} // namespace your_service::test
```

## 9. Test Configuration Management

Create test-specific configuration:

```yaml
# config/test.yaml
components_manager:
    components:
        logging:
            loggers:
                default:
                    level: warning  # Less verbose during tests
                    file_path: '@null'  # Discard logs
        
        server:
            listener:
                port: 0  # Let OS choose port
        
        postgresql:
            dbconnection: &testdb
                host: localhost
                port: 5432
                dbname: test_db
                user: test_user
                password: test_password
                connecting_limit: 2
                max_pool_size: 5
            
            dbs:
                main:
                    <<: *testdb
        
        # Mock external services
        http-client:
            fs-task-processor: fs-task-processor
            testsuite-enabled: true  # Enable test suite mode
            testsuite-timeout: 5s
```

## 10. Continuous Integration Setup

Example GitHub Actions workflow:

```yaml
# .github/workflows/tests.yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:15-alpine
        env:
          POSTGRES_DB: test_db
          POSTGRES_USER: test_user
          POSTGRES_PASSWORD: test_password
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432
      
      redis:
        image: redis:7-alpine
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 6379:6379
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Install dependencies
      run: |
        sudo apt-get update
        sudo apt-get install -y cmake g++ libssl-dev
    
    - name: Configure and build
      run: |
        mkdir build && cd build
        cmake .. -DCMAKE_BUILD_TYPE=Debug -DBUILD_TESTING=ON
        make -j$(nproc)
    
    - name: Run unit tests
      run: |
        cd build
        ctest --output-on-failure -L unit
    
    - name: Run integration tests
      run: |
        cd build
        ctest --output-on-failure -L integration
      env:
        POSTGRES_HOST: localhost
        POSTGRES_PORT: 5432
        POSTGRES_DB: test_db
        POSTGRES_USER: test_user
        POSTGRES_PASSWORD: test_password
    
    - name: Run E2E tests
      run: |
        cd build
        ./run_e2e_tests
      env:
        AUTH_SERVICE_URL: http://localhost:8001
    
    - name: Upload test results
      if: always()
      uses: actions/upload-artifact@v3
      with:
        name: test-results
        path: |
          build/Testing/**/*.xml
          build/*.log
```

## Troubleshooting

### Tests failing intermittently
- Add retry logic for flaky tests
- Increase timeouts for slow environments
- Use test containers instead of shared databases

### Memory leaks in tests
- Run tests with address sanitizer
- Check for missing cleanup in test fixtures
- Monitor memory usage during test runs

### Slow test execution
- Parallelize test execution
- Use in-memory databases for unit tests
- Mock external dependencies instead of real connections

### Configuration issues in tests
- Use separate test configuration files
- Ensure test environment variables are set
- Clean up test data after each test

## Best Practices

1. **Test pyramid**: More unit tests, fewer integration tests, even fewer E2E tests
2. **Fast feedback**: Keep test execution time under 5 minutes
3. **Isolation**: Each test should be independent and not rely on other tests
4. **Cleanup**: Always clean up test data to prevent test pollution
5. **Meaningful assertions**: Test behavior, not implementation details
6. **Coverage metrics**: Aim for 80%+ code coverage, focus on critical paths
7. **Continuous testing**: Run tests on every commit
8. **Test documentation**: Document what each test verifies
9. **Failure investigation**: Make test failures easy to diagnose
10. **Performance testing**: Include performance tests in CI pipeline