---
description: >
  Step-by-step guide to set up PostgreSQL database in userver services.
  Includes: database configuration, connection pooling, migrations setup,
  SQL queries, transactions, error handling.
  Trigger: add postgresql, setup database, database connection, postgres config,
  SQL queries, database migrations, pg cache.
name: postgresql-setup
---

# PostgreSQL Database Setup in Userver

Complete procedure for integrating PostgreSQL databases with userver microservices.

## 1. Add PostgreSQL Component to CMakeLists.txt

Ensure PostgreSQL client is included in your service dependencies:

```cmake
# In service's CMakeLists.txt
find_package(userver REQUIRED COMPONENTS
    core
    postgresql
    ...
)

# Add PostgreSQL include directories
include_directories(${userver_POSTGRESQL_INCLUDE_DIRS})
```

## 2. Configure PostgreSQL in static_config.yaml

Add PostgreSQL component configuration:

```yaml
components:
  postgresql-sample:
    dbconnection: &dbconnection
      host: localhost
      port: 5432
      dbname: your_database
      user: your_user
      password: your_password
      connecting_limit: 5
      max_pool_size: 10
      max_queue_size: 100
      blocking: false

    dbs: # Multiple database configurations
      main:
        <<: *dbconnection
        dbname: main_database
      analytics:
        <<: *dbconnection
        dbname: analytics_database
        connecting_limit: 3
```

## 3. Create Database Connection Class

Define a component for database access:

```cpp
#pragma once

#include <userver/components/component_list.hpp>
#include <userver/storages/postgres/component.hpp>
#include <userver/storages/postgres/cluster.hpp>

namespace your_service {

class DatabaseComponent final {
public:
    static constexpr std::string_view kName = "database-component";

    DatabaseComponent(const components::ComponentConfig& config,
                      const components::ComponentContext& context);

    storages::postgres::ClusterPtr GetCluster() const { return cluster_; }

private:
    storages::postgres::ClusterPtr cluster_;
};

} // namespace your_service
```

## 4. Implement Database Component

```cpp
#include "database_component.hpp"

namespace your_service {

DatabaseComponent::DatabaseComponent(const components::ComponentConfig& config,
                                     const components::ComponentContext& context)
    : components::LoggableComponentBase(config, context),
      cluster_(context.FindComponent<storages::postgres::Component>()
                   .GetCluster(config["dbs"]["main"]["dbname"].As<std::string>())) {
}

} // namespace your_service
```

## 5. Add Component to Main

Register the database component:

```cpp
// In main.cpp
#include "src/database_component.hpp"

int main(int argc, char* argv[]) {
    auto component_list = components::MinimalServerComponentList()
        .Append<your_service::DatabaseComponent>()
        .Append<storages::postgres::Component>()
        .Append<clients::dns::Component>()
        .AppendComponentList(clients::http::ComponentList());

    return utils::DaemonMain(argc, argv, component_list);
}
```

## 6. Execute SQL Queries

Create a repository class for data access:

```cpp
#pragma once

#include <userver/storages/postgres/cluster.hpp>
#include <userver/storages/postgres/result_set.hpp>

#include "models.hpp"

namespace your_service {

class UserRepository {
public:
    explicit UserRepository(storages::postgres::ClusterPtr cluster)
        : cluster_(std::move(cluster)) {}

    // Create user
    std::optional<User> CreateUser(const User& user) {
        try {
            auto result = cluster_->Execute(
                storages::postgres::ClusterHostType::kMaster,
                "INSERT INTO users (login, name, email, password_hash) "
                "VALUES ($1, $2, $3, $4) "
                "RETURNING id, login, name, email, created_at",
                user.login, user.name, user.email, user.password_hash);

            if (result.IsEmpty()) {
                return std::nullopt;
            }

            return result.AsSingleRow<User>();
        } catch (const storages::postgres::UniqueViolation&) {
            // Handle duplicate key
            return std::nullopt;
        }
    }

    // Get user by login
    std::optional<User> GetUserByLogin(const std::string& login) {
        auto result = cluster_->Execute(
            storages::postgres::ClusterHostType::kSlave,
            "SELECT id, login, name, email, created_at FROM users "
            "WHERE login = $1",
            login);

        if (result.IsEmpty()) {
            return std::nullopt;
        }

        return result.AsSingleRow<User>();
    }

    // Update user
    bool UpdateUser(const User& user) {
        auto result = cluster_->Execute(
            storages::postgres::ClusterHostType::kMaster,
            "UPDATE users SET name = $1, email = $2 "
            "WHERE login = $3",
            user.name, user.email, user.login);

        return result.RowsAffected() > 0;
    }

    // Delete user
    bool DeleteUser(const std::string& login) {
        auto result = cluster_->Execute(
            storages::postgres::ClusterHostType::kMaster,
            "DELETE FROM users WHERE login = $1",
            login);

        return result.RowsAffected() > 0;
    }

    // List users with pagination
    std::vector<User> ListUsers(int offset, int limit) {
        auto result = cluster_->Execute(
            storages::postgres::ClusterHostType::kSlave,
            "SELECT id, login, name, email, created_at FROM users "
            "ORDER BY created_at DESC "
            "OFFSET $1 LIMIT $2",
            offset, limit);

        return result.AsContainer<std::vector<User>>();
    }

private:
    storages::postgres::ClusterPtr cluster_;
};

} // namespace your_service
```

## 7. Define Database Models

Create models for database entities:

```cpp
#pragma once

#include <userver/storages/postgres/io/row_types.hpp>
#include <userver/storages/postgres/io/user_types.hpp>

#include <string>
#include <chrono>

namespace your_service {

struct User {
    int id;
    std::string login;
    std::string name;
    std::string email;
    std::string password_hash;
    std::chrono::system_clock::time_point created_at;
};

} // namespace your_service

// PostgreSQL type mappings
namespace userver::storages::postgres::io {

template <>
struct CppToUserPg<your_service::User> {
    static constexpr DBTypeName postgres_name = "users";
};

} // namespace userver::storages::postgres::io
```

## 8. Create Database Migrations

Set up migration system:

```sql
-- migrations/001_initial_schema.sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    login VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(200) NOT NULL,
    email VARCHAR(200) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_login ON users(login);
CREATE INDEX idx_users_email ON users(email);

-- migrations/002_add_status.sql
ALTER TABLE users ADD COLUMN status VARCHAR(50) DEFAULT 'active';
CREATE INDEX idx_users_status ON users(status);
```

## 9. Implement Transactions

Use transactions for atomic operations:

```cpp
storages::postgres::Transaction transaction = cluster_->Begin(
    "transaction_name",
    storages::postgres::ClusterHostType::kMaster,
    storages::postgres::Transaction::RW);

try {
    // Multiple operations
    auto result1 = transaction.Execute("INSERT INTO table1 ...");
    auto result2 = transaction.Execute("UPDATE table2 ...");
    
    // Commit if all successful
    transaction.Commit();
    
} catch (const std::exception& e) {
    // Rollback on error
    transaction.Rollback();
    throw;
}
```

## 10. Configure Connection Pooling

Optimize pool settings in configuration:

```yaml
components:
  postgresql-sample:
    dbconnection: &dbconnection
      host: ${POSTGRES_HOST}
      port: ${POSTGRES_PORT}
      dbname: ${POSTGRES_DB}
      user: ${POSTGRES_USER}
      password: ${POSTGRES_PASSWORD}
      connecting_limit: 10      # Maximum simultaneous connection attempts
      max_pool_size: 20        # Maximum connections in pool
      max_queue_size: 200      # Maximum queries waiting for connection
      blocking: false          # Don't block when pool exhausted
      sync_start: true         # Wait for connections on start
      dns_resolver: async      # Use async DNS resolution
      persistent-prepared-statements: true  # Cache prepared statements
```

## 11. Handle Database Errors

Proper error handling:

```cpp
try {
    auto result = cluster_->Execute(...);
    
} catch (const storages::postgres::UniqueViolation& e) {
    // Handle duplicate key (login, email, etc.)
    return ToJson(V1Error{"duplicate", "Resource already exists", std::nullopt});
    
} catch (const storages::postgres::ForeignKeyViolation& e) {
    // Handle foreign key constraint
    return ToJson(V1Error{"foreign_key", "Referenced resource not found", std::nullopt});
    
} catch (const storages::postgres::CheckViolation& e) {
    // Handle check constraint
    return ToJson(V1Error{"check_constraint", "Data validation failed", std::nullopt});
    
} catch (const storages::postgres::ConnectionInterrupted& e) {
    // Handle connection issues
    LOG_ERROR() << "Database connection interrupted: " << e.what();
    throw; // Let handler return 500
    
} catch (const storages::postgres::ConnectionTimeout& e) {
    // Handle timeout
    LOG_ERROR() << "Database connection timeout: " << e.what();
    throw;
}
```

## 12. Implement Database Health Check

Add health check endpoint:

```cpp
std::string HealthHandler::HandleRequest(server::http::HttpRequest& request,
                                         server::request::RequestContext&) const {
    try {
        // Simple query to check database connectivity
        auto result = db_cluster_->Execute(
            storages::postgres::ClusterHostType::kSlave,
            "SELECT 1");
            
        if (!result.IsEmpty()) {
            request.GetHttpResponse().SetStatus(server::http::HttpStatus::kOk);
            return ToJson(HealthResponse{"healthy", "Database connected"});
        }
        
    } catch (const std::exception& e) {
        request.GetHttpResponse().SetStatus(server::http::HttpStatus::kServiceUnavailable);
        return ToJson(HealthResponse{"unhealthy", e.what()});
    }
    
    request.GetHttpResponse().SetStatus(server::http::HttpStatus::kServiceUnavailable);
    return ToJson(HealthResponse{"unhealthy", "Database check failed"});
}
```

## Troubleshooting

### Connection errors
- Verify PostgreSQL is running and accessible
- Check host, port, database name, username, and password
- Ensure firewall allows connections on PostgreSQL port (default 5432)

### Pool exhaustion
- Increase `max_pool_size` if seeing "pool exhausted" errors
- Check for connection leaks (not returning connections to pool)
- Review `max_queue_size` and `blocking` settings

### Performance issues
- Use connection pooling effectively
- Implement query timeouts
- Add database indexes for frequently queried columns
- Use prepared statements for repeated queries

### Migration issues
- Ensure migration files are applied in correct order
- Check PostgreSQL user has necessary permissions
- Test migrations in development before production

## Best Practices

1. **Use connection pooling**: Never create new connections for each request
2. **Separate read/write operations**: Use kSlave for reads, kMaster for writes
3. **Implement retry logic**: For transient connection errors
4. **Use prepared statements**: For security and performance
5. **Monitor connection metrics**: Track pool usage, queue sizes, error rates
6. **Implement circuit breakers**: Prevent cascade failures during database outages
7. **Use transactions appropriately**: For atomic operations spanning multiple tables
8. **Validate data before insertion**: Reduce database-level constraint violations