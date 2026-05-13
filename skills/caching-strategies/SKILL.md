---
description: >
  Comprehensive guide to caching strategies in userver microservices.
  Includes: Redis caching, in-memory caching, cache invalidation,
  cache patterns, performance optimization, distributed caching.
  Trigger: caching, Redis cache, cache invalidation, cache patterns,
  performance optimization, distributed cache, cache strategies.
name: caching-strategies
---

# Caching Strategies for Userver Services

Complete guide to implementing efficient caching in userver microservices.

## 1. Redis Caching Component

Redis integration for distributed caching:

```cpp
// redis_cache.hpp
#pragma once

#include <userver/components/component_list.hpp>
#include <userver/storages/redis/client.hpp>
#include <userver/storages/redis/component.hpp>
#include <string>
#include <optional>
#include <chrono>

namespace your_service::cache {

class RedisCache {
public:
    RedisCache(std::shared_ptr<storages::redis::Client> redis_client)
        : redis_client_(std::move(redis_client)) {}
    
    // Set value with expiration
    void Set(const std::string& key,
             const std::string& value,
             std::chrono::seconds ttl = std::chrono::seconds(300)) {
        
        redis_client_->Set(key, value, ttl)
            .Get(); // Wait for completion
    }
    
    // Set value with NX (only if not exists)
    bool SetNX(const std::string& key,
               const std::string& value,
               std::chrono::seconds ttl = std::chrono::seconds(300)) {
        
        auto result = redis_client_->SetIfNotExist(key, value, ttl)
            .Get();
        
        return result.value_or(false);
    }
    
    // Get value
    std::optional<std::string> Get(const std::string& key) {
        auto result = redis_client_->Get(key).Get();
        
        if (!result.has_value() || result->IsNull()) {
            return std::nullopt;
        }
        
        return result->Get();
    }
    
    // Get or set with callback
    template<typename Value, typename Generator>
    Value GetOrSet(const std::string& key,
                   std::chrono::seconds ttl,
                   Generator&& generator) {
        
        // Try to get from cache
        auto cached = Get(key);
        if (cached.has_value()) {
            try {
                return Deserialize<Value>(*cached);
            } catch (const std::exception&) {
                // Invalid cache entry, continue to regenerate
            }
        }
        
        // Generate value
        Value value = generator();
        
        // Store in cache
        Set(key, Serialize(value), ttl);
        
        return value;
    }
    
    // Delete key
    void Delete(const std::string& key) {
        redis_client_->Del(key).Get();
    }
    
    // Delete pattern (use with caution)
    void DeletePattern(const std::string& pattern) {
        redis_client_->Keys(pattern)
            .Then([this](storages::redis::Future<std::vector<std::string>> keys_future) {
                auto keys = keys_future.Get();
                if (!keys.empty()) {
                    redis_client_->Del(std::move(keys)).Get();
                }
            })
            .Get();
    }
    
    // Increment counter
    int64_t Increment(const std::string& key,
                     int64_t increment = 1,
                     std::chrono::seconds ttl = std::chrono::seconds(300)) {
        
        auto result = redis_client_->Incr(key, increment).Get();
        
        // Set TTL if this is a new key
        if (result == increment) {
            redis_client_->Expire(key, ttl).Get();
        }
        
        return result;
    }
    
    // Check if key exists
    bool Exists(const std::string& key) {
        auto result = redis_client_->Exists(key).Get();
        return result.value_or(0) > 0;
    }
    
    // Set with tags for invalidation
    void SetWithTags(const std::string& key,
                     const std::string& value,
                     const std::vector<std::string>& tags,
                     std::chrono::seconds ttl = std::chrono::seconds(300)) {
        
        // Store the value
        Set(key, value, ttl);
        
        // Store reverse mapping from tags to keys
        for (const auto& tag : tags) {
            std::string tag_key = "tag:" + tag;
            redis_client_->SAdd(tag_key, key).Get();
            redis_client_->Expire(tag_key, ttl).Get();
        }
    }
    
    // Invalidate by tag
    void InvalidateByTag(const std::string& tag) {
        std::string tag_key = "tag:" + tag;
        
        auto keys = redis_client_->SMembers(tag_key).Get();
        if (!keys.empty()) {
            redis_client_->Del(std::move(keys.value())).Get();
            redis_client_->Del(tag_key).Get();
        }
    }
    
    // Get with stale-while-revalidate
    template<typename Value, typename Generator>
    Value GetWithStaleWhileRevalidate(const std::string& key,
                                      std::chrono::seconds ttl,
                                      std::chrono::seconds stale_ttl,
                                      Generator&& generator) {
        
        auto cached = Get(key);
        if (cached.has_value()) {
            try {
                auto entry = Deserialize<CacheEntry<Value>>(*cached);
                
                auto now = std::chrono::system_clock::now();
                
                // Return cached value if not expired
                if (now < entry.expires_at) {
                    return entry.value;
                }
                
                // If stale but not too old, return stale value and refresh in background
                if (now < entry.expires_at + stale_ttl) {
                    // Refresh in background
                    RefreshInBackground(key, ttl, generator);
                    return entry.value;
                }
            } catch (const std::exception&) {
                // Invalid cache entry
            }
        }
        
        // Generate fresh value
        Value value = generator();
        
        CacheEntry<Value> entry{
            .value = value,
            .expires_at = std::chrono::system_clock::now() + ttl
        };
        
        Set(key, Serialize(entry), ttl + stale_ttl);
        
        return value;
    }

private:
    template<typename T>
    struct CacheEntry {
        T value;
        std::chrono::system_clock::time_point expires_at;
    };
    
    template<typename T>
    std::string Serialize(const T& value) {
        // Implement serialization (JSON, MessagePack, etc.)
        formats::json::ValueBuilder builder;
        builder["value"] = value;
        builder["expires_at"] = std::chrono::duration_cast<std::chrono::milliseconds>(
            value.expires_at.time_since_epoch()).count();
        return formats::json::ToString(builder.ExtractValue());
    }
    
    template<typename T>
    T Deserialize(const std::string& str) {
        auto json = formats::json::FromString(str);
        
        T entry;
        entry.value = json["value"].As<typename T::value_type>();
        entry.expires_at = std::chrono::system_clock::time_point(
            std::chrono::milliseconds(json["expires_at"].As<int64_t>()));
        
        return entry;
    }
    
    template<typename Generator>
    void RefreshInBackground(const std::string& key,
                            std::chrono::seconds ttl,
                            Generator&& generator) {
        
        // Execute generator in background
        utils::Async("cache-refresh", [this, key, ttl, generator] {
            try {
                auto value = generator();
                CacheEntry<decltype(value)> entry{
                    .value = value,
                    .expires_at = std::chrono::system_clock::now() + ttl
                };
                Set(key, Serialize(entry), ttl * 2); // Double TTL for safety
            } catch (const std::exception& e) {
                LOG_ERROR() << "Cache refresh failed for key " << key
                           << ": " << e.what();
            }
        }).Detach();
    }
    
    std::shared_ptr<storages::redis::Client> redis_client_;
};

} // namespace your_service::cache
```

## 2. In-Memory LRU Cache

Thread-safe LRU cache for frequently accessed data:

```cpp
// lru_cache.hpp
#pragma once

#include <optional>
#include <shared_mutex>
#include <list>
#include <unordered_map>
#include <chrono>

namespace your_service::cache {

template<typename Key, typename Value>
class LruCache {
public:
    LruCache(size_t max_size) : max_size_(max_size) {}
    
    std::optional<Value> Get(const Key& key) {
        std::shared_lock lock(mutex_);
        
        auto it = items_map_.find(key);
        if (it == items_map_.end()) {
            return std::nullopt;
        }
        
        // Move to front (most recently used)
        items_list_.splice(items_list_.begin(), items_list_, it->second);
        
        return it->second->second;
    }
    
    void Put(const Key& key, const Value& value) {
        std::unique_lock lock(mutex_);
        
        auto it = items_map_.find(key);
        if (it != items_map_.end()) {
            // Update existing value
            it->second->second = value;
            items_list_.splice(items_list_.begin(), items_list_, it->second);
            return;
        }
        
        // Check if we need to evict
        if (items_list_.size() >= max_size_) {
            auto last = items_list_.end();
            last--;
            items_map_.erase(last->first);
            items_list_.pop_back();
        }
        
        // Insert new item at front
        items_list_.emplace_front(key, value);
        items_map_[key] = items_list_.begin();
    }
    
    bool Remove(const Key& key) {
        std::unique_lock lock(mutex_);
        
        auto it = items_map_.find(key);
        if (it == items_map_.end()) {
            return false;
        }
        
        items_list_.erase(it->second);
        items_map_.erase(it);
        return true;
    }
    
    void Clear() {
        std::unique_lock lock(mutex_);
        items_list_.clear();
        items_map_.clear();
    }
    
    size_t Size() const {
        std::shared_lock lock(mutex_);
        return items_list_.size();
    }
    
    bool Contains(const Key& key) const {
        std::shared_lock lock(mutex_);
        return items_map_.find(key) != items_map_.end();
    }

private:
    size_t max_size_;
    std::list<std::pair<Key, Value>> items_list_;
    std::unordered_map<Key, typename std::list<std::pair<Key, Value>>::iterator> items_map_;
    mutable std::shared_mutex mutex_;
};

// Time-based expiration cache
template<typename Key, typename Value>
class TimedCache {
public:
    TimedCache(std::chrono::seconds default_ttl)
        : default_ttl_(default_ttl) {}
    
    std::optional<Value> Get(const Key& key) {
        std::unique_lock lock(mutex_);
        
        auto it = cache_.find(key);
        if (it == cache_.end()) {
            return std::nullopt;
        }
        
        auto& entry = it->second;
        
        // Check expiration
        if (std::chrono::steady_clock::now() > entry.expires_at) {
            cache_.erase(it);
            return std::nullopt;
        }
        
        return entry.value;
    }
    
    void Put(const Key& key,
             const Value& value,
             std::optional<std::chrono::seconds> ttl = std::nullopt) {
        
        std::unique_lock lock(mutex_);
        
        CacheEntry entry{
            .value = value,
            .expires_at = std::chrono::steady_clock::now() + (ttl.value_or(default_ttl_))
        };
        
        cache_[key] = entry;
        
        // Cleanup expired entries occasionally
        if (cache_.size() > cleanup_threshold_) {
            CleanupExpired();
        }
    }
    
    void CleanupExpired() {
        auto now = std::chrono::steady_clock::now();
        
        for (auto it = cache_.begin(); it != cache_.end(); ) {
            if (now > it->second.expires_at) {
                it = cache_.erase(it);
            } else {
                ++it;
            }
        }
    }
    
    size_t Size() const {
        std::unique_lock lock(mutex_);
        return cache_.size();
    }

private:
    struct CacheEntry {
        Value value;
        std::chrono::steady_clock::time_point expires_at;
    };
    
    std::chrono::seconds default_ttl_;
    std::unordered_map<Key, CacheEntry> cache_;
    mutable std::mutex mutex_;
    size_t cleanup_threshold_{1000};
};

} // namespace your_service::cache
```

## 3. Cache-Aside Pattern

Implement cache-aside pattern with database:

```cpp
// cached_user_repository.hpp
#pragma once

#include "user_repository.hpp"
#include "redis_cache.hpp"
#include <memory>
#include <chrono>

namespace your_service {

class CachedUserRepository : public UserRepository {
public:
    CachedUserRepository(std::shared_ptr<UserRepository> db_repository,
                         std::shared_ptr<cache::RedisCache> cache)
        : db_repository_(std::move(db_repository))
        , cache_(std::move(cache)) {}
    
    std::optional<User> GetUserById(const std::string& user_id) override {
        std::string cache_key = "user:" + user_id;
        
        // Try cache first
        auto cached = cache_->Get(cache_key);
        if (cached.has_value()) {
            try {
                return Deserialize<User>(*cached);
            } catch (const std::exception&) {
                // Cache corruption, continue to database
            }
        }
        
        // Cache miss, read from database
        auto user = db_repository_->GetUserById(user_id);
        if (!user.has_value()) {
            return std::nullopt;
        }
        
        // Store in cache
        cache_->Set(cache_key, Serialize(*user), std::chrono::minutes(5));
        
        return user;
    }
    
    std::optional<User> GetUserByLogin(const std::string& login) override {
        // For non-ID lookups, use a secondary index cache
        std::string login_cache_key = "user_login:" + login;
        
        auto user_id = cache_->Get(login_cache_key);
        if (user_id.has_value()) {
            // We have the ID, get user by ID (which will use cache)
            return GetUserById(*user_id);
        }
        
        // Cache miss, read from database
        auto user = db_repository_->GetUserByLogin(login);
        if (!user.has_value()) {
            return std::nullopt;
        }
        
        // Store in caches
        std::string id_cache_key = "user:" + user->id;
        cache_->Set(id_cache_key, Serialize(*user), std::chrono::minutes(5));
        cache_->Set(login_cache_key, user->id, std::chrono::minutes(5));
        
        return user;
    }
    
    std::optional<User> CreateUser(const User& user) override {
        // Create in database
        auto created = db_repository_->CreateUser(user);
        if (!created.has_value()) {
            return std::nullopt;
        }
        
        // Invalidate caches
        InvalidateUserCaches(*created);
        
        return created;
    }
    
    bool UpdateUser(const User& user) override {
        // Update in database
        bool success = db_repository_->UpdateUser(user);
        if (!success) {
            return false;
        }
        
        // Invalidate caches
        InvalidateUserCaches(user);
        
        return true;
    }
    
    bool DeleteUser(const std::string& user_id) override {
        // Get user first to know what to invalidate
        auto user = db_repository_->GetUserById(user_id);
        
        // Delete from database
        bool success = db_repository_->DeleteUser(user_id);
        if (!success) {
            return false;
        }
        
        // Invalidate caches
        if (user.has_value()) {
            InvalidateUserCaches(*user);
        }
        
        return true;
    }

private:
    void InvalidateUserCaches(const User& user) {
        std::string id_cache_key = "user:" + user.id;
        std::string login_cache_key = "user_login:" + user.login;
        
        cache_->Delete(id_cache_key);
        cache_->Delete(login_cache_key);
        
        // Invalidate related caches
        cache_->DeletePattern("user_list:*");
        cache_->DeletePattern("search:*" + user.login + "*");
    }
    
    std::string Serialize(const User& user) {
        formats::json::ValueBuilder builder;
        builder["id"] = user.id;
        builder["login"] = user.login;
        builder["name"] = user.name;
        builder["email"] = user.email;
        builder["created_at"] = std::chrono::duration_cast<std::chrono::milliseconds>(
            user.created_at.time_since_epoch()).count();
        return formats::json::ToString(builder.ExtractValue());
    }
    
    User Deserialize(const std::string& str) {
        auto json = formats::json::FromString(str);
        
        User user;
        user.id = json["id"].As<std::string>();
        user.login = json["login"].As<std::string>();
        user.name = json["name"].As<std::string>();
        user.email = json["email"].As<std::string>();
        user.created_at = std::chrono::system_clock::time_point(
            std::chrono::milliseconds(json["created_at"].As<int64_t>()));
        
        return user;
    }
    
    std::shared_ptr<UserRepository> db_repository_;
    std::shared_ptr<cache::RedisCache> cache_;
};

} // namespace your_service
```

## 4. Write-Through Cache Pattern

Write-through cache for consistency:

```cpp
// write_through_cache.hpp
#pragma once

#include <functional>
#include <memory>
#include <string>
#include <optional>

namespace your_service::cache {

template<typename Key, typename Value>
class WriteThroughCache {
public:
    using ReadFunction = std::function<std::optional<Value>(const Key&)>;
    using WriteFunction = std::function<bool(const Key&, const Value&)>;
    
    WriteThroughCache(std::shared_ptr<RedisCache> cache,
                      ReadFunction read_func,
                      WriteFunction write_func,
                      std::chrono::seconds default_ttl = std::chrono::seconds(300))
        : cache_(std::move(cache))
        , read_func_(std::move(read_func))
        , write_func_(std::move(write_func))
        , default_ttl_(default_ttl) {}
    
    std::optional<Value> Get(const Key& key) {
        std::string cache_key = MakeCacheKey(key);
        
        // Try cache first
        auto cached = cache_->Get(cache_key);
        if (cached.has_value()) {
            try {
                return Deserialize<Value>(*cached);
            } catch (const std::exception&) {
                // Cache corruption, continue to source
            }
        }
        
        // Cache miss, read from source
        auto value = read_func_(key);
        if (!value.has_value()) {
            return std::nullopt;
        }
        
        // Store in cache
        cache_->Set(cache_key, Serialize(*value), default_ttl_);
        
        return value;
    }
    
    bool Put(const Key& key, const Value& value) {
        // Write to source first
        bool success = write_func_(key, value);
        if (!success) {
            return false;
        }
        
        // Write to cache
        std::string cache_key = MakeCacheKey(key);
        cache_->Set(cache_key, Serialize(value), default_ttl_);
        
        return true;
    }
    
    bool Delete(const Key& key) {
        // Delete from source
        // (Assuming write_func_ can handle deletion with null value)
        bool success = write_func_(key, Value{});
        if (!success) {
            return false;
        }
        
        // Delete from cache
        std::string cache_key = MakeCacheKey(key);
        cache_->Delete(cache_key);
        
        return true;
    }
    
    void Invalidate(const Key& key) {
        std::string cache_key = MakeCacheKey(key);
        cache_->Delete(cache_key);
    }

private:
    std::string MakeCacheKey(const Key& key) {
        return "cache:" + std::to_string(std::hash<Key>{}(key));
    }
    
    template<typename T>
    std::string Serialize(const T& value) {
        formats::json::ValueBuilder builder;
        builder = value; // Assuming Value has conversion
        return formats::json::ToString(builder.ExtractValue());
    }
    
    template<typename T>
    T Deserialize(const std::string& str) {
        auto json = formats::json::FromString(str);
        return json.As<T>();
    }
    
    std::shared_ptr<RedisCache> cache_;
    ReadFunction read_func_;
    WriteFunction write_func_;
    std::chrono::seconds default_ttl_;
};

} // namespace your_service::cache
```

## 5. Cache Stampede Prevention

Prevent cache stampede with early recomputation and locks:

```cpp
// stampede_protected_cache.hpp
#pragma once

#include <mutex>
#include <unordered_map>
#include <chrono>
#include <optional>
#include <shared_mutex>

namespace your_service::cache {

template<typename Key, typename Value>
class StampedeProtectedCache {
public:
    StampedeProtectedCache(std::chrono::seconds ttl,
                          std::chrono::seconds early_recompute = std::chrono::seconds(30))
        : default_ttl_(ttl)
        , early_recompute_(early_recompute) {}
    
    template<typename Generator>
    Value GetOrCompute(const Key& key, Generator&& generator) {
        std::shared_lock shared_lock(mutex_);
        
        auto it = cache_.find(key);
        if (it != cache_.end()) {
            auto& entry = it->second;
            auto now = std::chrono::steady_clock::now();
            
            // Check if entry is valid
            if (now < entry.expires_at) {
                return entry.value;
            }
            
            // Check if entry is stale but can be used while recomputing
            if (now < entry.expires_at + early_recompute_) {
                // Entry is stale, recompute in background
                shared_lock.unlock();
                RecomputeInBackground(key, std::forward<Generator>(generator));
                return entry.value;
            }
        }
        
        shared_lock.unlock();
        
        // Need to compute
        std::unique_lock unique_lock(mutex_);
        
        // Double-check after acquiring write lock
        it = cache_.find(key);
        if (it != cache_.end()) {
            auto& entry = it->second;
            auto now = std::chrono::steady_clock::now();
            
            if (now < entry.expires_at + early_recompute_) {
                // Someone else already recomputed or entry is still usable
                return entry.value;
            }
        }
        
        // Compute new value
        Value value = generator();
        
        // Store in cache
        CacheEntry entry{
            .value = value,
            .expires_at = std::chrono::steady_clock::now() + default_ttl_,
            .computing = false
        };
        
        cache_[key] = entry;
        
        return value;
    }
    
    void Set(const Key& key, const Value& value) {
        std::unique_lock lock(mutex_);
        
        CacheEntry entry{
            .value = value,
            .expires_at = std::chrono::steady_clock::now() + default_ttl_,
            .computing = false
        };
        
        cache_[key] = entry;
    }
    
    std::optional<Value> Get(const Key& key) {
        std::shared_lock lock(mutex_);
        
        auto it = cache_.find(key);
        if (it == cache_.end()) {
            return std::nullopt;
        }
        
        auto& entry = it->second;
        auto now = std::chrono::steady_clock::now();
        
        if (now >= entry.expires_at) {
            return std::nullopt;
        }
        
        return entry.value;
    }
    
    void Invalidate(const Key& key) {
        std::unique_lock lock(mutex_);
        cache_.erase(key);
    }

private:
    struct CacheEntry {
        Value value;
        std::chrono::steady_clock::time_point expires_at;
        bool computing{false};
    };
    
    template<typename Generator>
    void RecomputeInBackground(const Key& key, Generator&& generator) {
        std::unique_lock lock(background_mutex_);
        
        // Check if already being recomputed
        if (background_tasks_.find(key) != background_tasks_.end()) {
            return;
        }
        
        background_tasks_.insert(key);
        lock.unlock();
        
        // Recompute in background thread
        utils::Async("cache-recompute", [this, key, generator] {
            try {
                Value value = generator();
                
                std::unique_lock cache_lock(mutex_);
                CacheEntry entry{
                    .value = value,
                    .expires_at = std::chrono::steady_clock::now() + default_ttl_,
                    .computing = false
                };
                cache_[key] = entry;
                
            } catch (const std::exception& e) {
                LOG_ERROR() << "Background recompute failed for key " << key
                           << ": " << e.what();
            }
            
            // Clean up task tracking
            std::unique_lock bg_lock(background_mutex_);
            background_tasks_.erase(key);
        }).Detach();
    }
    
    std::chrono::seconds default_ttl_;
    std::chrono::seconds early_recompute_;
    std::unordered_map<Key, CacheEntry> cache_;
    mutable std::shared_mutex mutex_;
    
    std::unordered_set<Key> background_tasks_;
    std::mutex background_mutex_;
};

} // namespace your_service::cache
```

## 6. Two-Layer Cache (L1 + L2)

Two-layer cache with in-memory L1 and Redis L2:

```cpp
// two_layer_cache.hpp
#pragma once

#include "lru_cache.hpp"
#include "redis_cache.hpp"
#include <memory>
#include <chrono>

namespace your_service::cache {

template<typename Key, typename Value>
class TwoLayerCache {
public:
    TwoLayerCache(size_t l1_size,
                  std::shared_ptr<RedisCache> l2_cache,
                  std::chrono::seconds l2_ttl = std::chrono::seconds(300))
        : l1_cache_(l1_size)
        , l2_cache_(std::move(l2_cache))
        , l2_ttl_(l2_ttl) {}
    
    std::optional<Value> Get(const Key& key) {
        // Try L1 cache first
        auto l1_value = l1_cache_.Get(key);
        if (l1_value.has_value()) {
            return l1_value;
        }
        
        // Try L2 cache
        std::string l2_key = MakeL2Key(key);
        auto l2_value = l2_cache_->Get(l2_key);
        if (!l2_value.has_value()) {
            return std::nullopt;
        }
        
        try {
            Value value = Deserialize<Value>(*l2_value);
            
            // Populate L1 cache
            l1_cache_.Put(key, value);
            
            return value;
        } catch (const std::exception&) {
            // Deserialization failed
            return std::nullopt;
        }
    }
    
    template<typename Generator>
    Value GetOrCompute(const Key& key, Generator&& generator) {
        // Try cache first
        auto cached = Get(key);
        if (cached.has_value()) {
            return *cached;
        }
        
        // Compute value
        Value value = generator();
        
        // Store in both caches
        Put(key, value);
        
        return value;
    }
    
    void Put(const Key& key, const Value& value) {
        // Store in L1
        l1_cache_.Put(key, value);
        
        // Store in L2
        std::string l2_key = MakeL2Key(key);
        l2_cache_->Set(l2_key, Serialize(value), l2_ttl_);
    }
    
    void Delete(const Key& key) {
        // Delete from L1
        l1_cache_.Remove(key);
        
        // Delete from L2
        std::string l2_key = MakeL2Key(key);
        l2_cache_->Delete(l2_key);
    }
    
    void Clear() {
        l1_cache_.Clear();
        // Note: Cannot clear entire L2 cache easily
    }

private:
    std::string MakeL2Key(const Key& key) {
        return "cache:" + std::to_string(std::hash<Key>{}(key));
    }
    
    template<typename T>
    std::string Serialize(const T& value) {
        formats::json::ValueBuilder builder;
        builder = value;
        return formats::json::ToString(builder.ExtractValue());
    }
    
    template<typename T>
    T Deserialize(const std::string& str) {
        auto json = formats::json::FromString(str);
        return json.As<T>();
    }
    
    LruCache<Key, Value> l1_cache_;
    std::shared_ptr<RedisCache> l2_cache_;
    std::chrono::seconds l2_ttl_;
};

} // namespace your_service::cache
```

## 7. Cache Metrics and Monitoring

Track cache performance metrics:

```cpp
// cache_metrics.hpp
#pragma once

#include <userver/utils/statistics/metrics_storage.hpp>
#include <atomic>
#include <chrono>

namespace your_service::cache {

class CacheMetrics {
public:
    struct Stats {
        std::atomic<uint64_t> hits{0};
        std::atomic<uint64_t> misses{0};
        std::atomic<uint64_t> sets{0};
        std::atomic<uint64_t> deletes{0};
        std::atomic<uint64_t> errors{0};
        std::atomic<uint64_t> hit_bytes{0};
        std::atomic<uint64_t> miss_bytes{0};
        
        double GetHitRate() const {
            uint64_t total = hits.load() + misses.load();
            return total > 0 ? static_cast<double>(hits.load()) / total : 0.0;
        }
        
        void RecordHit(size_t bytes = 0) {
            hits.fetch_add(1, std::memory_order_relaxed);
            if (bytes > 0) {
                hit_bytes.fetch_add(bytes, std::memory_order_relaxed);
            }
        }
        
        void RecordMiss(size_t bytes = 0) {
            misses.fetch_add(1, std::memory_order_relaxed);
            if (bytes > 0) {
                miss_bytes.fetch_add(bytes, std::memory_order_relaxed);
            }
        }
        
        void RecordSet() {
            sets.fetch_add(1, std::memory_order_relaxed);
        }
        
        void RecordDelete() {
            deletes.fetch_add(1, std::memory_order_relaxed);
        }
        
        void RecordError() {
            errors.fetch_add(1, std::memory_order_relaxed);
        }
    };
    
    CacheMetrics(const std::string& cache_name)
        : cache_name_(cache_name) {
        
        // Register metrics
        metrics_registry_ = utils::statistics::MetricsStorage::GetDefault();
        metrics_registry_->RegisterWriter(
            "cache." + cache_name_,
            [this](utils::statistics::Writer& writer) {
                WriteMetrics(writer);
            });
    }
    
    ~CacheMetrics() {
        if (metrics_registry_) {
            metrics_registry_->UnregisterWriter("cache." + cache_name_);
        }
    }
    
    Stats& GetStats() { return stats_; }
    
private:
    void WriteMetrics(utils::statistics::Writer& writer) {
        writer["hits"] = stats_.hits.load();
        writer["misses"] = stats_.misses.load();
        writer["sets"] = stats_.sets.load();
        writer["deletes"] = stats_.deletes.load();
        writer["errors"] = stats_.errors.load();
        writer["hit_bytes"] = stats_.hit_bytes.load();
        writer["miss_bytes"] = stats_.miss_bytes.load();
        writer["hit_rate"] = stats_.GetHitRate();
        
        if (stats_.hits.load() + stats_.misses.load() > 0) {
            writer["avg_hit_bytes"] = static_cast<double>(stats_.hit_bytes.load()) /
                                      stats_.hits.load();
            writer["avg_miss_bytes"] = static_cast<double>(stats_.miss_bytes.load()) /
                                       stats_.misses.load();
        }
    }
    
    std::string cache_name_;
    Stats stats_;
    utils::statistics::MetricsStoragePtr metrics_registry_;
};

// Instrumented cache wrapper
template<typename Cache>
class InstrumentedCache {
public:
    InstrumentedCache(std::shared_ptr<Cache> cache,
                      std::shared_ptr<CacheMetrics> metrics)
        : cache_(std::move(cache))
        , metrics_(std::move(metrics)) {}
    
    template<typename Key, typename Value>
    std::optional<Value> Get(const Key& key) {
        auto start = std::chrono::steady_clock::now();
        
        try {
            auto value = cache_->Get(key);
            
            auto duration = std::chrono::steady_clock::now() - start;
            metrics_->GetStats().RecordLatency(duration);
            
            if (value.has_value()) {
                metrics_->GetStats().RecordHit(EstimateSize(*value));
            } else {
                metrics_->GetStats().RecordMiss();
            }
            
            return value;
            
        } catch (const std::exception& e) {
            metrics_->GetStats().RecordError();
            throw;
        }
    }
    
    template<typename Key, typename Value>
    void Set(const Key& key, const Value& value) {
        auto start = std::chrono::steady_clock::now();
        
        try {
            cache_->Set(key, value);
            
            auto duration = std::chrono::steady_clock::now() - start;
            metrics_->GetStats().RecordLatency(duration);
            metrics_->GetStats().RecordSet();
            metrics_->GetStats().RecordBytesWritten(EstimateSize(value));
            
        } catch (const std::exception& e) {
            metrics_->GetStats().RecordError();
            throw;
        }
    }

private:
    template<typename T>
    size_t EstimateSize(const T& value) {
        // Implement size estimation
        return sizeof(T);
    }
    
    std::shared_ptr<Cache> cache_;
    std::shared_ptr<CacheMetrics> metrics_;
};

} // namespace your_service::cache
```

## 8. Cache Configuration

Cache configuration in static_config.yaml:

```yaml
components:
  # Redis cache configuration
  redis-cache:
    hosts:
      - host: ${REDIS_HOST:-localhost}
        port: ${REDIS_PORT:-6379}
    password: ${REDIS_PASSWORD}
    sentinels: ${REDIS_SENTINELS}
    master-name: ${REDIS_MASTER_NAME}
    connection-timeout-ms: 1000
    command-timeout-ms: 1000
    pool-size: 10
    threads: 4
  
  # L1 cache configuration
  l1-cache:
    max-size: 10000
    default-ttl-seconds: 60
  
  # User cache configuration
  user-cache:
    enabled: ${USER_CACHE_ENABLED:-true}
    ttl-seconds: ${USER_CACHE_TTL:-300}
    max-size: ${USER_CACHE_MAX_SIZE:-1000}
    stale-while-revalidate-seconds: 30
  
  # Cache metrics
  cache-metrics:
    enabled: true
    export-interval-seconds: 30
  
  # Cache warming
  cache-warmer:
    enabled: ${CACHE_WARMER_ENABLED:-false}
    warm-on-startup: true
    warmup-items:
      - "popular:users"
      - "config:system"
    schedule: "*/5 * * * *"  # Every 5 minutes
```

## 9. Cache Warming

Cache warming on service startup:

```cpp
// cache_warmer.hpp
#pragma once

#include <vector>
#include <functional>
#include <memory>
#include <chrono>

namespace your_service::cache {

class CacheWarmer {
public:
    using WarmupFunction = std::function<void()>;
    
    void AddWarmupTask(const std::string& name,
                       WarmupFunction task,
                       int priority = 0) {
        tasks_.push_back({name, std::move(task), priority});
        
        // Sort by priority (higher priority first)
        std::sort(tasks_.begin(), tasks_.end(),
                 [](const auto& a, const auto& b) {
                     return a.priority > b.priority;
                 });
    }
    
    void Warmup() {
        LOG_INFO() << "Starting cache warmup with " << tasks_.size() << " tasks";
        
        auto start = std::chrono::steady_clock::now();
        size_t successful = 0;
        size_t failed = 0;
        
        for (const auto& task : tasks_) {
            LOG_INFO() << "Warming up: " << task.name;
            
            auto task_start = std::chrono::steady_clock::now();
            
            try {
                task.function();
                successful++;
                
                auto task_duration = std::chrono::steady_clock::now() - task_start;
                LOG_INFO() << "Warmup completed for " << task.name
                          << " in " << std::chrono::duration_cast<std::chrono::milliseconds>(task_duration).count() << "ms";
                
            } catch (const std::exception& e) {
                failed++;
                LOG_ERROR() << "Warmup failed for " << task.name
                           << ": " << e.what();
            }
        }
        
        auto total_duration = std::chrono::steady_clock::now() - start;
        LOG_INFO() << "Cache warmup completed: "
                  << successful << " successful, "
                  << failed << " failed, "
                  << "total time: " << std::chrono::duration_cast<std::chrono::milliseconds>(total_duration).count() << "ms";
    }
    
    void SchedulePeriodicWarmup(std::chrono::seconds interval) {
        if (timer_) {
            timer_->Stop();
        }
        
        timer_ = std::make_unique<utils::PeriodicTask>(
            "cache-warmup",
            [this] { Warmup(); },
            interval);
        
        timer_->Start();
    }

private:
    struct WarmupTask {
        std::string name;
        WarmupFunction function;
        int priority;
    };
    
    std::vector<WarmupTask> tasks_;
    std::unique_ptr<utils::PeriodicTask> timer_;
};

} // namespace your_service::cache
```

## 10. Best Practices

### Cache Key Design
- Use consistent key naming conventions
- Include version in cache keys for schema changes
- Use namespaces to separate different data types
- Avoid overly long cache keys

### TTL Strategy
- Use different TTLs for different data types
- Implement stale-while-revalidate for better performance
- Consider cache warming for frequently accessed data
- Monitor cache hit rates to adjust TTLs

### Memory Management
- Set appropriate size limits for in-memory caches
- Monitor memory usage
- Implement eviction policies (LRU, LFU, TTL-based)
- Use compression for large values

### Consistency
- Implement cache invalidation for data changes
- Use write-through or write-behind patterns for important data
- Consider cache-aside with database for simplicity
- Handle cache stampede with locks or early recomputation

### Monitoring
- Track cache hit/miss rates
- Monitor cache latency
- Alert on cache failures
- Log cache operations for debugging

### Security
- Sanitize cache keys to prevent injection
- Encrypt sensitive data in cache
- Implement cache isolation between tenants
- Regularly rotate cache encryption keys