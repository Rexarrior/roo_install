---
description: >
  Comprehensive guide to authentication and authorization in userver services.
  Includes: token-based authentication, JWT validation, permission systems,
  role-based access control, API key authentication, OAuth2 integration.
  Trigger: authentication, authorization, JWT, token validation, RBAC,
  access control, API keys, OAuth2, secure endpoints.
name: authentication-authorization
---

# Authentication and Authorization in Userver

Complete guide to implementing secure authentication and authorization in userver microservices.

## 1. Token-Based Authentication

Basic token authentication with in-memory storage:

```cpp
// auth_middleware.hpp
#pragma once

#include <userver/server/handlers/http_handler_base.hpp>
#include <string>
#include <unordered_map>
#include <mutex>
#include <optional>

namespace your_service::auth {

struct UserInfo {
    std::string user_id;
    std::string login;
    std::string name;
    std::vector<std::string> roles;
    std::chrono::system_clock::time_point token_issued_at;
    std::chrono::system_clock::time_point token_expires_at;
};

class AuthMiddleware {
public:
    static std::optional<UserInfo> ValidateToken(const std::string& token) {
        std::lock_guard<engine::Mutex> lock(mutex_);
        
        auto it = tokens_.find(token);
        if (it == tokens_.end()) {
            return std::nullopt;
        }
        
        // Check token expiration
        if (std::chrono::system_clock::now() > it->second.token_expires_at) {
            tokens_.erase(it);
            return std::nullopt;
        }
        
        return it->second;
    }
    
    static std::string GenerateToken(const UserInfo& user_info) {
        std::lock_guard<engine::Mutex> lock(mutex_);
        
        // Generate random token (in production, use secure random)
        std::string token = GenerateSecureToken();
        
        // Store token with user info
        tokens_[token] = user_info;
        
        // Cleanup expired tokens (optional)
        CleanupExpiredTokens();
        
        return token;
    }
    
    static void InvalidateToken(const std::string& token) {
        std::lock_guard<engine::Mutex> lock(mutex_);
        tokens_.erase(token);
    }
    
    static void InvalidateAllUserTokens(const std::string& user_id) {
        std::lock_guard<engine::Mutex> lock(mutex_);
        
        for (auto it = tokens_.begin(); it != tokens_.end(); ) {
            if (it->second.user_id == user_id) {
                it = tokens_.erase(it);
            } else {
                ++it;
            }
        }
    }

private:
    static std::string GenerateSecureToken() {
        // Use cryptographically secure random generator
        std::random_device rd;
        std::mt19937_64 gen(rd());
        std::uniform_int_distribution<uint64_t> dis;
        
        std::stringstream ss;
        for (int i = 0; i < 4; ++i) {
            ss << std::hex << std::setfill('0') << std::setw(16) << dis(gen);
        }
        
        return ss.str();
    }
    
    static void CleanupExpiredTokens() {
        auto now = std::chrono::system_clock::now();
        
        for (auto it = tokens_.begin(); it != tokens_.end(); ) {
            if (now > it->second.token_expires_at) {
                it = tokens_.erase(it);
            } else {
                ++it;
            }
        }
    }
    
    static std::unordered_map<std::string, UserInfo> tokens_;
    static engine::Mutex mutex_;
};

} // namespace your_service::auth
```

## 2. JWT (JSON Web Token) Authentication

JWT-based authentication with validation:

```cpp
// jwt_auth.hpp
#pragma once

#include <userver/formats/json.hpp>
#include <userver/crypto/base64.hpp>
#include <userver/crypto/hash.hpp>

#include <jwt-cpp/jwt.h>
#include <chrono>
#include <string>
#include <optional>

namespace your_service::auth {

class JwtAuth {
public:
    struct Config {
        std::string secret_key;
        std::string issuer;
        std::chrono::seconds token_lifetime{3600}; // 1 hour
        std::string algorithm{"HS256"};
    };
    
    JwtAuth(const Config& config) : config_(config) {}
    
    std::string CreateToken(const UserInfo& user_info) {
        auto now = std::chrono::system_clock::now();
        auto expires_at = now + config_.token_lifetime;
        
        auto token = jwt::create()
            .set_issuer(config_.issuer)
            .set_subject(user_info.user_id)
            .set_issued_at(now)
            .set_expires_at(expires_at)
            .set_payload_claim("login", jwt::claim(user_info.login))
            .set_payload_claim("name", jwt::claim(user_info.name))
            .set_payload_claim("roles", jwt::claim(user_info.roles))
            .sign(jwt::algorithm::hs256{config_.secret_key});
        
        return token;
    }
    
    std::optional<UserInfo> ValidateToken(const std::string& token) {
        try {
            auto decoded = jwt::decode(token);
            
            // Verify signature
            auto verifier = jwt::verify()
                .allow_algorithm(jwt::algorithm::hs256{config_.secret_key})
                .with_issuer(config_.issuer);
            
            verifier.verify(decoded);
            
            // Check expiration
            auto now = std::chrono::system_clock::now();
            auto exp_claim = decoded.get_expires_at();
            if (now > exp_claim) {
                return std::nullopt;
            }
            
            // Extract user info
            UserInfo user_info;
            user_info.user_id = decoded.get_subject();
            user_info.login = decoded.get_payload_claim("login").as_string();
            user_info.name = decoded.get_payload_claim("name").as_string();
            
            // Extract roles array
            auto roles_claim = decoded.get_payload_claim("roles");
            if (roles_claim.get_type() == jwt::json::type::array) {
                auto roles_json = roles_claim.as_array();
                for (const auto& role : roles_claim.as_array()) {
                    user_info.roles.push_back(role.as_string());
                }
            }
            
            user_info.token_issued_at = decoded.get_issued_at();
            user_info.token_expires_at = exp_claim;
            
            return user_info;
            
        } catch (const jwt::token_verification_exception& e) {
            // Signature verification failed
            return std::nullopt;
        } catch (const jwt::signature_format_error& e) {
            // Token format error
            return std::nullopt;
        } catch (const std::exception& e) {
            // Other errors
            return std::nullopt;
        }
    }
    
    std::string RefreshToken(const std::string& old_token) {
        auto user_info = ValidateToken(old_token);
        if (!user_info) {
            throw std::runtime_error("Invalid token");
        }
        
        // Update issue and expiration times
        return CreateToken(*user_info);
    }

private:
    Config config_;
};

} // namespace your_service::auth
```

## 3. HTTP Handler with Authentication

Secure HTTP handler with authentication middleware:

```cpp
// secure_handler.hpp
#pragma once

#include <userver/server/handlers/http_handler_base.hpp>
#include "auth_middleware.hpp"

namespace your_service {

class SecureHandler : public server::handlers::HttpHandlerBase {
public:
    static constexpr std::string_view kName = "handler-secure";
    
    SecureHandler(const components::ComponentConfig& config,
                  const components::ComponentContext& context);
    
    std::string HandleRequest(server::http::HttpRequest& request,
                              server::request::RequestContext&) const override;

protected:
    // Helper method for authenticated endpoints
    std::optional<auth::UserInfo> GetAuthenticatedUser(
        const server::http::HttpRequest& request) const {
        
        auto auth_header = request.GetHeader("Authorization");
        if (auth_header.empty()) {
            return std::nullopt;
        }
        
        // Check for Bearer token format
        const std::string bearer_prefix = "Bearer ";
        if (auth_header.find(bearer_prefix) != 0) {
            return std::nullopt;
        }
        
        std::string token = auth_header.substr(bearer_prefix.length());
        return auth::AuthMiddleware::ValidateToken(token);
    }
    
    // Require authentication
    std::optional<auth::UserInfo> RequireAuthentication(
        server::http::HttpRequest& request) const {
        
        auto user_info = GetAuthenticatedUser(request);
        if (!user_info) {
            request.GetHttpResponse().SetStatus(
                server::http::HttpStatus::kUnauthorized);
            return std::nullopt;
        }
        
        return user_info;
    }
    
    // Require specific role
    bool RequireRole(server::http::HttpRequest& request,
                     const auth::UserInfo& user_info,
                     const std::string& required_role) const {
        
        auto it = std::find(user_info.roles.begin(),
                           user_info.roles.end(),
                           required_role);
        if (it == user_info.roles.end()) {
            request.GetHttpResponse().SetStatus(
                server::http::HttpStatus::kForbidden);
            return false;
        }
        
        return true;
    }
    
    // Require any of the specified roles
    bool RequireAnyRole(server::http::HttpRequest& request,
                        const auth::UserInfo& user_info,
                        const std::vector<std::string>& required_roles) const {
        
        for (const auto& role : required_roles) {
            if (std::find(user_info.roles.begin(),
                         user_info.roles.end(),
                         role) != user_info.roles.end()) {
                return true;
            }
        }
        
        request.GetHttpResponse().SetStatus(
            server::http::HttpStatus::kForbidden);
        return false;
    }
};

} // namespace your_service
```

Implementation example:

```cpp
// secure_handler.cpp
#include "secure_handler.hpp"

namespace your_service {

SecureHandler::SecureHandler(const components::ComponentConfig& config,
                             const components::ComponentContext& context)
    : HttpHandlerBase(config, context) {
}

std::string SecureHandler::HandleRequest(server::http::HttpRequest& request,
                                         server::request::RequestContext&) const {
    request.GetHttpResponse().SetContentType(
        userver::http::content_type::kApplicationJson);
    
    const auto& path = request.GetRequestPath();
    
    if (path.find("/profile") != std::string::npos) {
        return HandleProfile(request);
    } else if (path.find("/admin") != std::string::npos) {
        return HandleAdmin(request);
    }
    
    request.GetHttpResponse().SetStatus(server::http::HttpStatus::kNotFound);
    return ToJson(V1Error{"not_found", "Endpoint not found", std::nullopt});
}

std::string SecureHandler::HandleProfile(
    server::http::HttpRequest& request) const {
    
    // Require authentication
    auto user_info = RequireAuthentication(request);
    if (!user_info) {
        return ToJson(V1Error{"unauthorized", "Authentication required", std::nullopt});
    }
    
    // Get user profile logic
    try {
        // Fetch user data from database
        UserProfile profile = user_repository_->GetProfile(user_info->user_id);
        
        // Return profile
        return ToJson(profile);
        
    } catch (const std::exception& e) {
        request.GetHttpResponse().SetStatus(
            server::http::HttpStatus::kInternalServerError);
        return ToJson(V1Error{"internal_error", e.what(), std::nullopt});
    }
}

std::string SecureHandler::HandleAdmin(
    server::http::HttpRequest& request) const {
    
    // Require authentication
    auto user_info = RequireAuthentication(request);
    if (!user_info) {
        return ToJson(V1Error{"unauthorized", "Authentication required", std::nullopt});
    }
    
    // Require admin role
    if (!RequireRole(request, *user_info, "admin")) {
        return ToJson(V1Error{"forbidden", "Admin role required", std::nullopt});
    }
    
    // Admin logic
    try {
        if (request.GetMethod() == server::http::HttpMethod::kGet) {
            // Get admin statistics
            AdminStats stats = admin_repository_->GetStats();
            return ToJson(stats);
        } else if (request.GetMethod() == server::http::HttpMethod::kPost) {
            // Perform admin action
            auto action = ParseAdminAction(request.RequestBody());
            auto result = admin_repository_->PerformAction(action);
            return ToJson(result);
        }
        
    } catch (const std::exception& e) {
        request.GetHttpResponse().SetStatus(
            server::http::HttpStatus::kInternalServerError);
        return ToJson(V1Error{"internal_error", e.what(), std::nullopt});
    }
    
    request.GetHttpResponse().SetStatus(
        server::http::HttpStatus::kMethodNotAllowed);
    return ToJson(V1Error{"method_not_allowed", "Method not allowed", std::nullopt});
}

} // namespace your_service
```

## 4. Rate Limiting with Authentication

Rate limiting based on user identity:

```cpp
// rate_limiter.hpp
#pragma once

#include <userver/utils/statistics/rate_counter.hpp>
#include <unordered_map>
#include <mutex>
#include <chrono>

namespace your_service::auth {

class RateLimiter {
public:
    struct Config {
        size_t max_requests_per_minute;
        size_t max_requests_per_hour;
        size_t burst_size;
    };
    
    RateLimiter(const Config& config) : config_(config) {}
    
    bool AllowRequest(const std::string& user_id) {
        std::lock_guard<engine::Mutex> lock(mutex_);
        
        auto& user_limits = user_limits_[user_id];
        auto now = std::chrono::steady_clock::now();
        
        // Cleanup old requests
        CleanupOldRequests(user_limits.minute_requests, now, std::chrono::minutes(1));
        CleanupOldRequests(user_limits.hour_requests, now, std::chrono::hours(1));
        
        // Check limits
        if (user_limits.minute_requests.size() >= config_.max_requests_per_minute) {
            return false;
        }
        
        if (user_limits.hour_requests.size() >= config_.max_requests_per_hour) {
            return false;
        }
        
        // Add request timestamps
        user_limits.minute_requests.push_back(now);
        user_limits.hour_requests.push_back(now);
        
        return true;
    }
    
    std::optional<std::chrono::seconds> GetRetryAfter(
        const std::string& user_id) {
        
        std::lock_guard<engine::Mutex> lock(mutex_);
        
        auto it = user_limits_.find(user_id);
        if (it == user_limits_.end()) {
            return std::nullopt;
        }
        
        auto& user_limits = it->second;
        auto now = std::chrono::steady_clock::now();
        
        // Check minute limit
        if (user_limits.minute_requests.size() >= config_.max_requests_per_minute) {
            auto oldest = *std::min_element(user_limits.minute_requests.begin(),
                                           user_limits.minute_requests.end());
            auto elapsed = std::chrono::duration_cast<std::chrono::seconds>(
                now - oldest);
            return std::chrono::seconds(60) - elapsed;
        }
        
        // Check hour limit
        if (user_limits.hour_requests.size() >= config_.max_requests_per_hour) {
            auto oldest = *std::min_element(user_limits.hour_requests.begin(),
                                           user_limits.hour_requests.end());
            auto elapsed = std::chrono::duration_cast<std::chrono::seconds>(
                now - oldest);
            return std::chrono::seconds(3600) - elapsed;
        }
        
        return std::nullopt;
    }
    
    void ResetUser(const std::string& user_id) {
        std::lock_guard<engine::Mutex> lock(mutex_);
        user_limits_.erase(user_id);
    }

private:
    struct UserLimits {
        std::vector<std::chrono::steady_clock::time_point> minute_requests;
        std::vector<std::chrono::steady_clock::time_point> hour_requests;
    };
    
    void CleanupOldRequests(std::vector<std::chrono::steady_clock::time_point>& requests,
                           std::chrono::steady_clock::time_point now,
                           std::chrono::seconds window) {
        
        auto cutoff = now - window;
        requests.erase(
            std::remove_if(requests.begin(), requests.end(),
                          [cutoff](const auto& timestamp) {
                              return timestamp < cutoff;
                          }),
            requests.end());
    }
    
    Config config_;
    std::unordered_map<std::string, UserLimits> user_limits_;
    engine::Mutex mutex_;
};

} // namespace your_service::auth
```

Integration with handler:

```cpp
// In secure_handler.cpp
std::string SecureHandler::HandleRequest(server::http::HttpRequest& request,
                                         server::request::RequestContext&) const {
    
    // Get user ID for rate limiting (even for unauthenticated endpoints)
    std::string rate_limit_key = "anonymous";
    if (auto user_info = GetAuthenticatedUser(request)) {
        rate_limit_key = user_info->user_id;
    } else {
        // Use IP address for anonymous users
        rate_limit_key = request.GetHeader("X-Real-IP");
        if (rate_limit_key.empty()) {
            rate_limit_key = "unknown";
        }
    }
    
    // Check rate limit
    if (!rate_limiter_->AllowRequest(rate_limit_key)) {
        request.GetHttpResponse().SetStatus(
            server::http::HttpStatus::kTooManyRequests);
        
        if (auto retry_after = rate_limiter_->GetRetryAfter(rate_limit_key)) {
            request.GetHttpResponse().SetHeader(
                "Retry-After",
                std::to_string(retry_after->count()));
        }
        
        return ToJson(V1Error{"rate_limit_exceeded",
                             "Too many requests",
                             std::nullopt});
    }
    
    // Rest of handler logic...
}
```

## 5. API Key Authentication

API key-based authentication for service-to-service communication:

```cpp
// api_key_auth.hpp
#pragma once

#include <unordered_map>
#include <mutex>
#include <string>
#include <optional>
#include <chrono>

namespace your_service::auth {

struct ApiKeyInfo {
    std::string key_id;
    std::string service_name;
    std::vector<std::string> permissions;
    std::chrono::system_clock::time_point created_at;
    std::chrono::system_clock::time_point expires_at;
    bool is_active;
};

class ApiKeyAuth {
public:
    std::optional<ApiKeyInfo> ValidateApiKey(const std::string& api_key) {
        std::lock_guard<engine::Mutex> lock(mutex_);
        
        auto it = api_keys_.find(api_key);
        if (it == api_keys_.end()) {
            return std::nullopt;
        }
        
        const auto& key_info = it->second;
        
        // Check if key is active
        if (!key_info.is_active) {
            return std::nullopt;
        }
        
        // Check expiration
        if (std::chrono::system_clock::now() > key_info.expires_at) {
            return std::nullopt;
        }
        
        return key_info;
    }
    
    bool HasPermission(const ApiKeyInfo& key_info,
                      const std::string& required_permission) const {
        
        return std::find(key_info.permissions.begin(),
                        key_info.permissions.end(),
                        required_permission) != key_info.permissions.end();
    }
    
    std::string GenerateApiKey(const std::string& service_name,
                              const std::vector<std::string>& permissions,
                              std::chrono::hours validity_hours = std::chrono::hours(24 * 30)) { // 30 days default
        
        std::lock_guard<engine::Mutex> lock(mutex_);
        
        // Generate secure API key
        std::string api_key = GenerateSecureKey();
        std::string key_id = GenerateKeyId();
        
        ApiKeyInfo key_info{
            .key_id = key_id,
            .service_name = service_name,
            .permissions = permissions,
            .created_at = std::chrono::system_clock::now(),
            .expires_at = std::chrono::system_clock::now() + validity_hours,
            .is_active = true
        };
        
        api_keys_[api_key] = key_info;
        
        // Store mapping for lookup by key_id
        key_id_to_api_key_[key_id] = api_key;
        
        return api_key;
    }
    
    void RevokeApiKey(const std::string& key_id) {
        std::lock_guard<engine::Mutex> lock(mutex_);
        
        auto it = key_id_to_api_key_.find(key_id);
        if (it != key_id_to_api_key_.end()) {
            auto api_key_it = api_keys_.find(it->second);
            if (api_key_it != api_keys_.end()) {
                api_key_it->second.is_active = false;
            }
            key_id_to_api_key_.erase(it);
        }
    }
    
    std::vector<ApiKeyInfo> ListApiKeys() const {
        std::lock_guard<engine::Mutex> lock(mutex_);
        
        std::vector<ApiKeyInfo> keys;
        keys.reserve(api_keys_.size());
        
        for (const auto& [api_key, key_info] : api_keys_) {
            keys.push_back(key_info);
        }
        
        return keys;
    }

private:
    std::string GenerateSecureKey() {
        // Generate cryptographically secure random key
        const std::string chars = 
            "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz";
        
        std::random_device rd;
        std::mt19937 gen(rd());
        std::uniform_int_distribution<> dis(0, chars.size() - 1);
        
        std::string key;
        key.reserve(64);
        
        for (int i = 0; i < 64; ++i) {
            key += chars[dis(gen)];
        }
        
        return key;
    }
    
    std::string GenerateKeyId() {
        // Generate unique key ID
        static std::atomic<uint64_t> counter{0};
        return fmt::format("key_{}_{}", 
                          std::chrono::system_clock::now().time_since_epoch().count(),
                          ++counter);
    }
    
    std::unordered_map<std::string, ApiKeyInfo> api_keys_;
    std::unordered_map<std::string, std::string> key_id_to_api_key_;
    mutable engine::Mutex mutex_;
};

} // namespace your_service::auth
```

## 6. OAuth2 Integration

OAuth2 client for third-party authentication:

```cpp
// oauth2_client.hpp
#pragma once

#include <userver/http/client.hpp>
#include <userver/formats/json.hpp>
#include <string>
#include <optional>
#include <chrono>

namespace your_service::auth {

class OAuth2Client {
public:
    struct Config {
        std::string client_id;
        std::string client_secret;
        std::string authorization_endpoint;
        std::string token_endpoint;
        std::string userinfo_endpoint;
        std::string redirect_uri;
        std::vector<std::string> scopes;
    };
    
    OAuth2Client(const Config& config,
                 std::shared_ptr<userver::clients::http::Client> http_client)
        : config_(config)
        , http_client_(std::move(http_client)) {}
    
    std::string GetAuthorizationUrl(const std::string& state) const {
        std::string url = config_.authorization_endpoint;
        url += "?response_type=code";
        url += "&client_id=" + userver::http::UrlEncode(config_.client_id);
        url += "&redirect_uri=" + userver::http::UrlEncode(config_.redirect_uri);
        url += "&scope=" + userver::http::UrlEncode(JoinScopes());
        url += "&state=" + userver::http::UrlEncode(state);
        
        return url;
    }
    
    struct TokenResponse {
        std::string access_token;
        std::string refresh_token;
        std::string token_type;
        std::chrono::seconds expires_in;
        std::string scope;
        std::string id_token; // For OpenID Connect
    };
    
    std::optional<TokenResponse> ExchangeCodeForToken(
        const std::string& authorization_code) {
        
        auto request = http_client_->CreateRequest()
            .post(config_.token_endpoint)
            .form_data({
                {"grant_type", "authorization_code"},
                {"code", authorization_code},
                {"redirect_uri", config_.redirect_uri},
                {"client_id", config_.client_id},
                {"client_secret", config_.client_secret}
            })
            .timeout(std::chrono::seconds(10));
        
        try {
            auto response = request.perform();
            
            if (response->status_code() != 200) {
                LOG_ERROR() << "OAuth2 token exchange failed: "
                           << response->status_code() << " "
                           << response->body();
                return std::nullopt;
            }
            
            auto json = formats::json::FromString(response->body());
            
            TokenResponse token_response{
                .access_token = json["access_token"].As<std::string>(),
                .refresh_token = json["refresh_token"].As<std::string>(),
                .token_type = json["token_type"].As<std::string>(),
                .expires_in = std::chrono::seconds(
                    json["expires_in"].As<int>(3600)),
                .scope = json["scope"].As<std::string>("")
            };
            
            if (json.HasMember("id_token")) {
                token_response.id_token = json["id_token"].As<std::string>();
            }
            
            return token_response;
            
        } catch (const std::exception& e) {
            LOG_ERROR() << "OAuth2 token exchange exception: " << e.what();
            return std::nullopt;
        }
    }
    
    struct UserInfo {
        std::string sub; // Subject identifier
        std::string email;
        std::string name;
        std::string picture;
        bool email_verified{false};
    };
    
    std::optional<UserInfo> GetUserInfo(const std::string& access_token) {
        auto request = http_client_->CreateRequest()
            .get(config_.userinfo_endpoint)
            .header("Authorization", "Bearer " + access_token)
            .timeout(std::chrono::seconds(5));
        
        try {
            auto response = request.perform();
            
            if (response->status_code() != 200) {
                return std::nullopt;
            }
            
            auto json = formats::json::FromString(response->body());
            
            UserInfo user_info{
                .sub = json["sub"].As<std::string>(),
                .email = json["email"].As<std::string>(""),
                .name = json["name"].As<std::string>(""),
                .picture = json["picture"].As<std::string>(""),
                .email_verified = json["email_verified"].As<bool>(false)
            };
            
            return user_info;
            
        } catch (const std::exception& e) {
            LOG_ERROR() << "OAuth2 userinfo exception: " << e.what();
            return std::nullopt;
        }
    }
    
    std::optional<TokenResponse> RefreshToken(
        const std::string& refresh_token) {
        
        auto request = http_client_->CreateRequest()
            .post(config_.token_endpoint)
            .form_data({
                {"grant_type", "refresh_token"},
                {"refresh_token", refresh_token},
                {"client_id", config_.client_id},
                {"client_secret", config_.client_secret}
            })
            .timeout(std::chrono::seconds(10));
        
        try {
            auto response = request.perform();
            
            if (response->status_code() != 200) {
                return std::nullopt;
            }
            
            auto json = formats::json::FromString(response->body());
            
            TokenResponse token_response{
                .access_token = json["access_token"].As<std::string>(),
                .refresh_token = json["refresh_token"].As<std::string>(),
                .token_type = json["token_type"].As<std::string>(),
                .expires_in = std::chrono::seconds(
                    json["expires_in"].As<int>(3600)),
                .scope = json["scope"].As<std::string>("")
            };
            
            return token_response;
            
        } catch (const std::exception& e) {
            LOG_ERROR() << "OAuth2 token refresh exception: " << e.what();
            return std::nullopt;
        }
    }

private:
    std::string JoinScopes() const {
        std::string result;
        for (size_t i = 0; i < config_.scopes.size(); ++i) {
            if (i > 0) result += " ";
            result += config_.scopes[i];
        }
        return result;
    }
    
    Config config_;
    std::shared_ptr<userver::clients::http::Client> http_client_;
};

} // namespace your_service::auth
```

## 7. Security Best Practices

### Token Security
- Use HTTPS for all authentication requests
- Store tokens securely (HttpOnly cookies for web, secure storage for mobile)
- Implement token rotation and refresh mechanisms
- Set appropriate token expiration times
- Revoke tokens on password change or suspicious activity

### Password Security
- Use strong password hashing (bcrypt, Argon2, PBKDF2)
- Implement password complexity requirements
- Rate limit password attempts
- Never log passwords or tokens

### Session Management
- Use secure, random session identifiers
- Implement session timeout and idle timeout
- Allow users to view and revoke active sessions
- Clear sessions on logout

### API Security
- Validate all input and output
- Use parameterized queries to prevent SQL injection
- Implement CORS policies
- Rate limit API endpoints
- Log security events

## 8. Configuration

Authentication configuration in static_config.yaml:

```yaml
components:
  # JWT configuration
  jwt-auth:
    secret-key: ${JWT_SECRET_KEY}
    issuer: ${JWT_ISSUER:-my-service}
    token-lifetime-hours: ${JWT_TOKEN_LIFETIME_HOURS:-24}
    algorithm: HS256
  
  # Rate limiting
  rate-limiter:
    max-requests-per-minute: ${RATE_LIMIT_PER_MINUTE:-60}
    max-requests-per-hour: ${RATE_LIMIT_PER_HOUR:-1000}
    burst-size: ${RATE_LIMIT_BURST:-10}
  
  # OAuth2 configuration
  oauth2-google:
    client-id: ${OAUTH2_GOOGLE_CLIENT_ID}
    client-secret: ${OAUTH2_GOOGLE_CLIENT_SECRET}
    authorization-endpoint: https://accounts.google.com/o/oauth2/v2/auth
    token-endpoint: https://oauth2.googleapis.com/token
    userinfo-endpoint: https://www.googleapis.com/oauth2/v3/userinfo
    redirect-uri: ${OAUTH2_REDIRECT_URI}
    scopes:
      - openid
      - email
      - profile
  
  # API keys storage (could be Redis or database in production)
  api-key-auth:
    storage-type: memory  # or redis, database
    redis-host: ${REDIS_HOST:-localhost}
    redis-port: ${REDIS_PORT:-6379}
```

## 9. Testing Authentication

Authentication tests:

```cpp
TEST(AuthenticationTest, ValidTokenAuthentication) {
    AuthMiddleware auth;
    
    UserInfo user_info{
        .user_id = "user123",
        .login = "testuser",
        .name = "Test User",
        .roles = {"user"},
        .token_issued_at = std::chrono::system_clock::now(),
        .token_expires_at = std::chrono::system_clock::now() + std::chrono::hours(1)
    };
    
    std::string token = auth.GenerateToken(user_info);
    
    auto validated = auth.ValidateToken(token);
    ASSERT_TRUE(validated.has_value());
    EXPECT_EQ(validated->user_id, "user123");
    EXPECT_EQ(validated->login, "testuser");
}

TEST(AuthenticationTest, ExpiredTokenFails) {
    AuthMiddleware auth;
    
    UserInfo user_info{
        .user_id = "user123",
        .token_issued_at = std::chrono::system_clock::now() - std::chrono::hours(2),
        .token_expires_at = std::chrono::system_clock::now() - std::chrono::hours(1)
    };
    
    std::string token = auth.GenerateToken(user_info);
    
    auto validated = auth.ValidateToken(token);
    EXPECT_FALSE(validated.has_value());
}

TEST(AuthenticationTest, InvalidTokenFails) {
    AuthMiddleware auth;
    
    auto validated = auth.ValidateToken("invalid-token");
    EXPECT_FALSE(validated.has_value());
}
```

## 10. Troubleshooting

### Authentication failures
- Check token format and encoding
- Verify token expiration
- Validate signature (for JWT)
- Check clock synchronization (for JWT expiration)

### Authorization failures
- Verify user roles/permissions
- Check API key permissions
- Review rate limiting settings

### Performance issues
- Cache authentication results for frequently accessed tokens
- Use efficient data structures for token storage
- Implement connection pooling for external auth services

### Security issues
- Regularly rotate secrets and keys
- Monitor authentication logs for suspicious activity
- Implement intrusion detection for failed authentication attempts