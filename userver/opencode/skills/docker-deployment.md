---
description: >
  Complete guide to Docker containerization and deployment of userver services.
  Includes: Dockerfile creation, Docker Compose orchestration, multi-stage builds,
  container optimization, production deployment, monitoring.
  Trigger: docker container, docker compose, containerization, deployment,
  production deployment, docker optimization, container orchestration.
name: docker-deployment
---

# Docker Deployment for Userver Services

Complete guide to containerizing and deploying userver microservices with Docker.

## 1. Single-Service Dockerfile

Basic Dockerfile for a single userver service:

```dockerfile
# Multi-stage build for smaller images
FROM ghcr.io/userver-framework/ubuntu-24.04-userver-base:latest AS builder

# Set working directory
WORKDIR /app

# Copy source code
COPY . .

# Create build directory and configure
RUN mkdir build && cd build && \
    cmake .. -DCMAKE_BUILD_TYPE=Release -DUSERVER_FROM_SYSTEM=ON && \
    make -j$(nproc) service1

# Runtime stage
FROM ubuntu:24.04

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    libssl3 \
    libcurl4 \
    libpq5 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 appuser
USER appuser

# Copy binary and config from builder
COPY --from=builder --chown=appuser:appuser /app/build/service1/service1 /app/service
COPY --from=builder --chown=appuser:appuser /app/service1/static_config.yaml /app/static_config.yaml

# Set working directory
WORKDIR /app

# Expose port (must match static_config.yaml)
EXPOSE 8001

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8001/healthcheck || exit 1

# Run service
CMD ["./service", "--config", "static_config.yaml"]
```

## 2. Multi-Service Docker Compose Setup

Orchestrate multiple services with Docker Compose:

```yaml
# docker-compose.yml
version: '3.8'

services:
  # PostgreSQL database
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: app_db
      POSTGRES_USER: app_user
      POSTGRES_PASSWORD: app_password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U app_user"]
      interval: 5s
      timeout: 5s
      retries: 5
    networks:
      - app-network

  # Redis for caching/sessions
  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5
    networks:
      - app-network

  # Auth service
  service1:
    build:
      context: .
      dockerfile: Dockerfile
      args:
        SERVICE: service1
        CONFIG_DIR: service1
    environment:
      POSTGRES_HOST: postgres
      POSTGRES_PORT: 5432
      POSTGRES_DB: app_db
      POSTGRES_USER: app_user
      POSTGRES_PASSWORD: app_password
      REDIS_HOST: redis
      REDIS_PORT: 6379
    ports:
      - "8001:8001"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks:
      - app-network
    restart: unless-stopped

  # Messaging service
  service2:
    build:
      context: .
      dockerfile: Dockerfile
      args:
        SERVICE: service2
        CONFIG_DIR: service2
    environment:
      POSTGRES_HOST: postgres
      POSTGRES_PORT: 5432
      POSTGRES_DB: app_db
      POSTGRES_USER: app_user
      POSTGRES_PASSWORD: app_password
    ports:
      - "8002:8002"
    depends_on:
      postgres:
        condition: service_healthy
    networks:
      - app-network
    restart: unless-stopped

  # Notifications service
  service3:
    build:
      context: .
      dockerfile: Dockerfile
      args:
        SERVICE: service3
        CONFIG_DIR: service3
    environment:
      POSTGRES_HOST: postgres
      POSTGRES_PORT: 5432
      POSTGRES_DB: app_db
      POSTGRES_USER: app_user
      POSTGRES_PASSWORD: app_password
    ports:
      - "8003:8003"
    depends_on:
      postgres:
        condition: service_healthy
    networks:
      - app-network
    restart: unless-stopped

  # Nginx reverse proxy
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro
    depends_on:
      - service1
      - service2
      - service3
    networks:
      - app-network
    restart: unless-stopped

  # Frontend
  frontend:
    build:
      context: ./frontend
    ports:
      - "3000:3000"
    networks:
      - app-network
    restart: unless-stopped

  # Monitoring stack (optional)
  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus_data:/prometheus
    ports:
      - "9090:9090"
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.console.libraries=/etc/prometheus/console_libraries'
      - '--web.console.templates=/etc/prometheus/consoles'
      - '--storage.tsdb.retention.time=200h'
      - '--web.enable-lifecycle'
    networks:
      - app-network
    restart: unless-stopped

  grafana:
    image: grafana/grafana:latest
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana_data:/var/lib/grafana
      - ./monitoring/dashboards:/etc/grafana/provisioning/dashboards:ro
      - ./monitoring/datasources:/etc/grafana/provisioning/datasources:ro
    ports:
      - "3001:3000"
    depends_on:
      - prometheus
    networks:
      - app-network
    restart: unless-stopped

# Networks
networks:
  app-network:
    driver: bridge

# Volumes
volumes:
  postgres_data:
  redis_data:
  prometheus_data:
  grafana_data:
```

## 3. Parameterized Dockerfile for Multiple Services

Reusable Dockerfile that builds different services based on build args:

```dockerfile
# Multi-stage build
FROM ghcr.io/userver-framework/ubuntu-24.04-userver-base:latest AS builder

ARG SERVICE
ARG CONFIG_DIR

WORKDIR /app

# Copy only necessary files
COPY CMakeLists.txt .
COPY ${SERVICE}/ ${SERVICE}/

# Build specific service
RUN mkdir build && cd build && \
    cmake .. -DCMAKE_BUILD_TYPE=Release -DUSERVER_FROM_SYSTEM=ON && \
    make -j$(nproc) ${SERVICE}

# Runtime stage
FROM ubuntu:24.04

ARG SERVICE
ARG CONFIG_DIR

# Install minimal runtime dependencies
RUN apt-get update && apt-get install -y \
    libssl3 \
    libcurl4 \
    libpq5 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 appuser
USER appuser

# Copy binary and config
COPY --from=builder --chown=appuser:appuser /app/build/${SERVICE}/${SERVICE} /app/service
COPY --from=builder --chown=appuser:appuser /app/${CONFIG_DIR}/static_config.yaml /app/static_config.yaml

WORKDIR /app

# Default port (override in docker-compose)
EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8001/healthcheck || exit 1

CMD ["./service", "--config", "static_config.yaml"]
```

## 4. Nginx Configuration for Reverse Proxy

Configure nginx to route requests to appropriate services:

```nginx
# nginx/nginx.conf
events {
    worker_connections 1024;
}

http {
    # Upstream services
    upstream service1 {
        server service1:8001;
    }

    upstream service2 {
        server service2:8002;
    }

    upstream service3 {
        server service3:8003;
    }

    upstream service4 {
        server service4:8004;
    }

    upstream service5 {
        server service5:8005;
    }

    upstream service6 {
        server service6:8006;
    }

    upstream frontend {
        server frontend:3000;
    }

    # Main server
    server {
        listen 80;
        server_name localhost;

        # API routing
        location /api/auth/ {
            rewrite ^/api/auth/(.*) /$1 break;
            proxy_pass http://service1/;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_set_header Authorization $http_authorization;
            proxy_pass_header Authorization;
        }

        location /api/messaging/ {
            rewrite ^/api/messaging/(.*) /$1 break;
            proxy_pass http://service2/;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_set_header Authorization $http_authorization;
            proxy_pass_header Authorization;
        }

        location /api/notifications/ {
            rewrite ^/api/notifications/(.*) /$1 break;
            proxy_pass http://service3/;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_set_header Authorization $http_authorization;
            proxy_pass_header Authorization;
        }

        # Frontend
        location / {
            proxy_pass http://frontend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # Health checks
        location /health {
            access_log off;
            add_header Content-Type text/plain;
            return 200 "healthy\n";
        }
    }
}
```

## 5. Production Docker Compose with Secrets

Production-ready Docker Compose with secrets management:

```yaml
# docker-compose.prod.yml
version: '3.8'

x-logging: &default-logging
  logging:
    driver: "json-file"
    options:
      max-size: "10m"
      max-file: "3"

secrets:
  postgres_password:
    file: ./secrets/postgres_password.txt
  redis_password:
    file: ./secrets/redis_password.txt
  jwt_secret:
    file: ./secrets/jwt_secret.txt

services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-app_db}
      POSTGRES_USER: ${POSTGRES_USER:-app_user}
      POSTGRES_PASSWORD_FILE: /run/secrets/postgres_password
    secrets:
      - postgres_password
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./database/init.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-app_user}"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - backend
    <<: *default-logging
    deploy:
      resources:
        limits:
          memory: 512M
        reservations:
          memory: 256M

  redis:
    image: redis:7-alpine
    command: redis-server --requirepass $$(cat /run/secrets/redis_password)
    secrets:
      - redis_password
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "$$(cat /run/secrets/redis_password)", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - backend
    <<: *default-logging
    deploy:
      resources:
        limits:
          memory: 256M
        reservations:
          memory: 128M

  service1:
    build:
      context: .
      dockerfile: Dockerfile
      args:
        SERVICE: service1
        CONFIG_DIR: service1
    environment:
      NODE_ENV: production
      POSTGRES_HOST: postgres
      POSTGRES_PORT: 5432
      POSTGRES_DB: ${POSTGRES_DB:-app_db}
      POSTGRES_USER: ${POSTGRES_USER:-app_user}
      POSTGRES_PASSWORD_FILE: /run/secrets/postgres_password
      REDIS_HOST: redis
      REDIS_PORT: 6379
      REDIS_PASSWORD_FILE: /run/secrets/redis_password
      JWT_SECRET_FILE: /run/secrets/jwt_secret
      LOG_LEVEL: ${LOG_LEVEL:-info}
    secrets:
      - postgres_password
      - redis_password
      - jwt_secret
    ports:
      - "8001:8001"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks:
      - backend
    <<: *default-logging
    deploy:
      replicas: 2
      update_config:
        parallelism: 1
        delay: 10s
      restart_policy:
        condition: on-failure
        delay: 5s
        max_attempts: 3
        window: 120s
      resources:
        limits:
          memory: 256M
          cpus: '0.5'
        reservations:
          memory: 128M
          cpus: '0.25'

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro
      - ./nginx/logs:/var/log/nginx
    depends_on:
      - service1
      - service2
      - service3
    networks:
      - backend
      - frontend
    <<: *default-logging
    deploy:
      resources:
        limits:
          memory: 128M
        reservations:
          memory: 64M

networks:
  frontend:
    driver: bridge
  backend:
    driver: bridge
    internal: true  # Backend services not accessible from outside

volumes:
  postgres_data:
    driver: local
  redis_data:
    driver: local

# Only external volumes in production
```

## 6. Docker Build Optimization

Optimize Docker builds for speed and size:

```dockerfile
# .dockerignore
# Build artifacts
build/
*/build/
*.o
*.a
*.so

# IDE files
.vscode/
.idea/
*.swp
*.swo

# Logs
*.log
logs/

# Temporary files
*.tmp
*.temp

# Dependencies
node_modules/
*.pyc
__pycache__/

# Configuration (except production)
config/development.yaml
config/staging.yaml
secrets/development/
```

```dockerfile
# Dockerfile with optimizations
# Stage 1: Dependencies
FROM ghcr.io/userver-framework/ubuntu-24.04-userver-base:latest AS deps

# Install build dependencies only
RUN apt-get update && apt-get install -y \
    cmake \
    g++ \
    libssl-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy only dependency files first
COPY CMakeLists.txt .
COPY ${SERVICE}/CMakeLists.txt ${SERVICE}/

# Download and cache dependencies
RUN mkdir build && cd build && \
    cmake .. -DCMAKE_BUILD_TYPE=Release -DUSERVER_FROM_SYSTEM=ON \
    && make -j$(nproc) download_deps

# Stage 2: Builder
FROM deps AS builder

ARG SERVICE
ARG CONFIG_DIR

# Copy source code
COPY ${SERVICE}/src/ ${SERVICE}/src/
COPY ${SERVICE}/include/ ${SERVICE}/include/
COPY ${CONFIG_DIR}/static_config.yaml ${CONFIG_DIR}/static_config.yaml

# Build service
RUN cd build && \
    make -j$(nproc) ${SERVICE} && \
    # Strip debug symbols for production
    strip ${SERVICE}/${SERVICE}

# Stage 3: Runtime (distroless for smallest image)
FROM gcr.io/distroless/cc-debian12:nonroot

ARG SERVICE
ARG CONFIG_DIR

# Copy only the binary and config
COPY --from=builder --chown=nonroot:nonroot \
    /app/build/${SERVICE}/${SERVICE} /app/service
COPY --from=builder --chown=nonroot:nonroot \
    /app/${CONFIG_DIR}/static_config.yaml /app/static_config.yaml

WORKDIR /app

EXPOSE 8001

CMD ["./service", "--config", "static_config.yaml"]
```

## 7. Health Checks and Readiness Probes

Implement comprehensive health checks:

```cpp
// health_handler.cpp
#include "health_handler.hpp"

namespace your_service {

HealthHandler::HealthHandler(const components::ComponentConfig& config,
                             const components::ComponentContext& context)
    : HttpHandlerBase(config, context),
      db_cluster_(context.FindComponent<storages::postgres::Component>()
                     .GetCluster("main")),
      redis_client_(context.FindComponent<redis::RedisComponent>()
                       .GetClient()) {
}

std::string HealthHandler::HandleRequest(server::http::HttpRequest& request,
                                         server::request::RequestContext&) const {
    HealthStatus status{
        .status = "healthy",
        .timestamp = std::chrono::system_clock::now(),
        .checks = {}
    };
    
    // Database check
    auto db_start = std::chrono::steady_clock::now();
    try {
        auto result = db_cluster_->Execute(
            storages::postgres::ClusterHostType::kSlave,
            "SELECT 1");
        
        auto db_duration = std::chrono::steady_clock::now() - db_start;
        status.checks["database"] = HealthCheck{
            .status = "healthy",
            .duration_ms = std::chrono::duration_cast<std::chrono::milliseconds>(db_duration).count(),
            .message = "Connected successfully"
        };
        
    } catch (const std::exception& e) {
        status.status = "unhealthy";
        status.checks["database"] = HealthCheck{
            .status = "unhealthy",
            .duration_ms = -1,
            .message = e.what()
        };
    }
    
    // Redis check
    auto redis_start = std::chrono::steady_clock::now();
    try {
        auto reply = redis_client_->Ping();
        
        auto redis_duration = std::chrono::steady_clock::now() - redis_start;
        status.checks["redis"] = HealthCheck{
            .status = "healthy",
            .duration_ms = std::chrono::duration_cast<std::chrono::milliseconds>(redis_duration).count(),
            .message = "Connected successfully"
        };
        
    } catch (const std::exception& e) {
        status.status = "unhealthy";
        status.checks["redis"] = HealthCheck{
            .status = "unhealthy",
            .duration_ms = -1,
            .message = e.what()
        };
    }
    
    // External service check (if any)
    // ...
    
    // Set HTTP status based on overall health
    if (status.status == "healthy") {
        request.GetHttpResponse().SetStatus(server::http::HttpStatus::kOk);
    } else {
        request.GetHttpResponse().SetStatus(server::http::HttpStatus::kServiceUnavailable);
    }
    
    return ToJson(status);
}

} // namespace your_service
```

Docker health check configuration:

```yaml
# In docker-compose.yml
services:
  service1:
    # ...
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8001/health"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 30s
      start_interval: 5s
```

## 8. Monitoring and Logging Configuration

Configure monitoring for Docker containers:

```yaml
# docker-compose.monitoring.yml
version: '3.8'

services:
  prometheus:
    image: prom/prometheus:latest
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.console.libraries=/etc/prometheus/console_libraries'
      - '--web.console.templates=/etc/prometheus/consoles'
      - '--storage.tsdb.retention.time=200h'
      - '--web.enable-lifecycle'
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    ports:
      - "9090:9090"
    networks:
      - monitoring

  grafana:
    image: grafana/grafana:latest
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD:-admin}
      - GF_USERS_ALLOW_SIGN_UP=false
    volumes:
      - grafana_data:/var/lib/grafana
      - ./monitoring/dashboards:/etc/grafana/provisioning/dashboards
      - ./monitoring/datasources:/etc/grafana/provisioning/datasources
    ports:
      - "3001:3000"
    depends_on:
      - prometheus
    networks:
      - monitoring

  node-exporter:
    image: prom/node-exporter:latest
    volumes:
      - /proc:/host/proc:ro
      - /sys:/host/sys:ro
      - /:/rootfs:ro
    command:
      - '--path.procfs=/host/proc'
      - '--path.rootfs=/rootfs'
      - '--path.sysfs=/host/sys'
      - '--collector.filesystem.mount-points-exclude=^/(sys|proc|dev|host|etc)($$|/)'
    ports:
      - "9100:9100"
    networks:
      - monitoring

  cadvisor:
    image: gcr.io/cadvisor/cadvisor:latest
    volumes:
      - /:/rootfs:ro
      - /var/run:/var/run:ro
      - /sys:/sys:ro
      - /var/lib/docker/:/var/lib/docker:ro
      - /dev/disk/:/dev/disk:ro
    devices:
      - /dev/kmsg
    ports:
      - "8080:8080"
    networks:
      - monitoring

networks:
  monitoring:
    driver: bridge

volumes:
  prometheus_data:
  grafana_data:
```

Prometheus configuration:

```yaml
# monitoring/prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'userver-services'
    static_configs:
      - targets:
        - 'service1:8001'
        - 'service2:8002'
        - 'service3:8003'
        - 'service4:8004'
        - 'service5:8005'
        - 'service6:8006'
    metrics_path: '/metrics'
    scrape_interval: 10s

  - job_name: 'node-exporter'
    static_configs:
      - targets: ['node-exporter:9100']

  - job_name: 'cadvisor'
    static_configs:
      - targets: ['cadvisor:8080']

  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']
```

## 9. Deployment Scripts

Create deployment scripts for different environments:

```bash
#!/bin/bash
# deploy.sh

set -e

ENVIRONMENT=${1:-development}
SERVICE=${2:-all}

echo "Deploying to $ENVIRONMENT environment..."

# Load environment variables
export $(grep -v '^#' .env.$ENVIRONMENT | xargs)

# Build services
if [ "$SERVICE" = "all" ] || [ "$SERVICE" = "service1" ]; then
    echo "Building service1..."
    docker build \
        --build-arg SERVICE=service1 \
        --build-arg CONFIG_DIR=service1 \
        -t service1:latest \
        -f Dockerfile .
fi

# More service builds...

# Deploy with Docker Compose
if [ "$ENVIRONMENT" = "production" ]; then
    echo "Deploying to production..."
    docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
elif [ "$ENVIRONMENT" = "staging" ]; then
    echo "Deploying to staging..."
    docker-compose -f docker-compose.yml -f docker-compose.staging.yml up -d
else
    echo "Deploying to development..."
    docker-compose up -d --build
fi

echo "Deployment complete!"
```

## 10. Troubleshooting Docker Deployments

### Container failing to start
- Check logs: `docker logs <container_name>`
- Verify port mappings: `docker ps` and `netstat -tlnp`
- Check environment variables: `docker inspect <container_name>`

### Network connectivity issues
- Verify network exists: `docker network ls`
- Check container IP: `docker inspect -f '{{range.NetworkSettings.Networks}}{{.IPAddress}}{{end}}' <container_name>`
- Test connectivity: `docker exec <container_name> ping <other_service>`

### Resource constraints
- Monitor memory usage: `docker stats`
- Adjust resource limits in docker-compose
- Check ulimits: `docker run --ulimit nofile=65535:65535`

### Build failures
- Clear build cache: `docker builder prune`
- Check Dockerfile syntax
- Verify build context includes all necessary files

## Best Practices

1. **Use multi-stage builds**: Separate build and runtime stages
2. **Non-root users**: Always run containers as non-root
3. **Health checks**: Implement comprehensive health endpoints
4. **Resource limits**: Set memory and CPU limits
5. **Secrets management**: Use Docker secrets or external vault
6. **Logging**: Configure structured JSON logging
7. **Monitoring**: Integrate with Prometheus/Grafana
8. **Immutable containers**: Don't modify running containers
9. **Orchestration**: Use Docker Compose for development, Kubernetes for production
10. **Security scanning**: Scan images for vulnerabilities regularly