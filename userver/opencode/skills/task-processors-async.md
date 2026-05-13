---
description: >
  Comprehensive guide to task processors and asynchronous operations in userver.
  Includes: task processor configuration, asynchronous programming, coroutines,
  scheduling, parallel execution, synchronization, performance optimization.
  Trigger: task processor, async, coroutine, concurrent, parallel, scheduling,
  synchronization, future, promise, thread pool.
name: task-processors-async
---

# Task Processors and Asynchronous Operations in Userver

Complete guide to managing concurrency and asynchronous operations in userver microservices.

## 1. Task Processor Configuration

### Basic Configuration

Configure task processors in `static_config.yaml`:

```yaml
task_processors:
  main-task-processor:
    worker_threads: 4
    thread_name: main-worker
    os-scheduling: normal  # or low-priority
    spin-iterations: 5000
    sensor-interval-ms: 100
    
  fs-task-processor:
    worker_threads: 2
    thread_name: fs-worker
    os-scheduling: idle
    worker_threads: ${WORKER_THREADS_FS:-2}
    
  cpu-task-processor:
    worker_threads: ${WORKER_THREADS_CPU:-8}
    thread_name: cpu-worker
    os-scheduling: normal
    spin-iterations: 10000
    
  # Dedicated task processor for blocking operations
  blocking-task-processor:
    worker_threads: 16
    thread_name: blocking-worker
    os-scheduling: normal
    task-trace:
      every: 1000
      max-context-switch-count: 1000
      logger: default
```

### Component Configuration

Assign components to specific task processors:

```yaml
components:
  server:
    listener:
      port: 8080
      task_processor: main-task-processor
    
  handler-api:
    path: /api/v1/*
    task_processor: main-task-processor
    max_requests_in_flight: 100
    
  # Database components
  postgresql:
    task_processor: main-task-processor
    dns_resolver: async
    blocking_task_processor: blocking-task-processor
    
  # HTTP client
  http-client:
    task_processor: main-task-processor
    fs-task-processor: fs-task-processor
```

## 2. Asynchronous Programming with Coroutines

### Basic Coroutine Usage

```cpp
#include <userver/engine/sleep.hpp>
#include <userver/engine/task/task.hpp>
#include <userver/utils/async.hpp>

namespace your_service {

// Simple asynchronous function
engine::TaskWithResult<int> ComputeAsync(int a, int b) {
    // Simulate expensive computation
    co_await engine::SleepFor(std::chrono::milliseconds(100));
    
    co_return a + b;
}

// Coroutine that calls other coroutines
engine::TaskWithResult<std::vector<int>> ProcessBatchAsync(
    const std::vector<std::pair<int, int>>& pairs) {
    
    std::vector<engine::TaskWithResult<int>> tasks;
    tasks.reserve(pairs.size());
    
    // Launch all computations concurrently
    for (const auto& [a, b] : pairs) {
        tasks.push_back(ComputeAsync(a, b));
    }
    
    // Wait for all results
    std::vector<int> results;
    results.reserve(pairs.size());
    
    for (auto& task : tasks) {
        results.push_back(co_await task);
    }
    
    co_return results;
}

} // namespace your_service
```

### Error Handling in Coroutines

```cpp
#include <userver/engine/task/cancel.hpp>

engine::TaskWithResult<std::optional<Data>> FetchDataAsync(const std::string& id) {
    try {
        // Check for cancellation
        engine::current_task::GetCancellationToken().CheckNotCanceled();
        
        // Asynchronous operation that might throw
        auto data = co_await FetchFromDatabaseAsync(id);
        
        if (!data) {
            LOG_WARNING() << "Data not found for id: " << id;
            co_return std::nullopt;
        }
        
        co_return data;
        
    } catch (const engine::TaskCancelledException&) {
        LOG_INFO() << "Task cancelled while fetching data for id: " << id;
        throw; // Re-throw cancellation
        
    } catch (const std::exception& e) {
        LOG_ERROR() << "Failed to fetch data for id " << id << ": " << e.what();
        co_return std::nullopt;
    }
}
```

## 3. Task Scheduling

### Delayed Execution

```cpp
#include <userver/engine/sleep.hpp>
#include <userver/utils/async.hpp>

class Scheduler {
public:
    // Schedule task after delay
    engine::TaskWithResult<void> ScheduleAfter(
        std::chrono::milliseconds delay,
        std::function<void()> callback) {
        
        co_await engine::SleepFor(delay);
        callback();
        
        co_return;
    }
    
    // Schedule periodic task
    engine::TaskWithResult<void> SchedulePeriodic(
        std::chrono::milliseconds interval,
        std::function<bool()> callback) {
        
        while (true) {
            co_await engine::SleepFor(interval);
            
            // Stop if callback returns false
            if (!callback()) {
                break;
            }
            
            // Check for cancellation
            engine::current_task::GetCancellationToken().CheckNotCanceled();
        }
    }
    
    // Schedule at specific time
    engine::TaskWithResult<void> ScheduleAt(
        std::chrono::system_clock::time_point time,
        std::function<void()> callback) {
        
        auto now = std::chrono::system_clock::now();
        if (time > now) {
            co_await engine::SleepFor(time - now);
        }
        
        callback();
        co_return;
    }
};
```

### Task Prioritization

```cpp
#include <userver/engine/task/task_with_result.hpp>

class PriorityScheduler {
public:
    enum class Priority {
        High,
        Normal,
        Low,
        Background
    };
    
    engine::TaskWithResult<void> SubmitWithPriority(
        Priority priority,
        std::function<void()> task) {
        
        // Create task with specific settings based on priority
        switch (priority) {
            case Priority::High:
                return utils::Async("high-priority-task", task);
                
            case Priority::Normal:
                return utils::Async("normal-priority-task", task);
                
            case Priority::Low:
                return utils::Async("low-priority-task", task);
                
            case Priority::Background:
                return utils::Async("background-task", 
                                    engine::current_task::GetTaskProcessor(),
                                    task);
        }
    }
};
```

## 4. Parallel Execution

### Parallel Map Pattern

```cpp
#include <userver/utils/async.hpp>
#include <vector>
#include <algorithm>

template<typename Input, typename Output, typename Transform>
std::vector<Output> ParallelTransform(
    const std::vector<Input>& inputs,
    Transform&& transform,
    size_t max_concurrency = 4) {
    
    std::vector<engine::TaskWithResult<Output>> tasks;
    tasks.reserve(inputs.size());
    
    // Launch tasks
    for (const auto& input : inputs) {
        tasks.push_back(utils::Async("parallel-transform", transform, input));
        
        // Limit concurrency
        if (tasks.size() >= max_concurrency) {
            // Wait for the first task to complete
            auto completed = engine::WaitAny(tasks);
            // Remove completed task (simplified - in reality need to handle differently)
        }
    }
    
    // Wait for all remaining tasks
    std::vector<Output> results;
    results.reserve(inputs.size());
    
    for (auto& task : tasks) {
        results.push_back(task.Get());
    }
    
    return results;
}
```

### Fork-Join Pattern

```cpp
#include <userver/engine/wait_any.hpp>

class ForkJoinExecutor {
public:
    template<typename... Tasks>
    auto ExecuteAll(Tasks&&... tasks) {
        // Start all tasks
        auto task_objects = std::make_tuple(
            std::forward<Tasks>(tasks)...);
        
        // Wait for all to complete
        return WaitAll(task_objects);
    }
    
    template<typename... Tasks>
    auto ExecuteAny(Tasks&&... tasks) {
        // Start all tasks
        std::vector<engine::TaskBase*> task_pointers;
        (task_pointers.push_back(&tasks), ...);
        
        // Wait for any to complete
        auto completed_index = engine::WaitAny(task_pointers);
        
        // Cancel remaining tasks
        CancelAllExcept(task_pointers, completed_index);
        
        return completed_index;
    }
    
private:
    template<typename Tuple>
    auto WaitAll(Tuple& tasks) {
        // Implementation for waiting on tuple of tasks
        return std::apply([](auto&... ts) {
            return std::make_tuple(ts.Get()...);
        }, tasks);
    }
    
    void CancelAllExcept(const std::vector<engine::TaskBase*>& tasks, size_t except_index) {
        for (size_t i = 0; i < tasks.size(); ++i) {
            if (i != except_index) {
                tasks[i]->RequestCancel();
            }
        }
    }
};
```

## 5. Synchronization Primitives

### Mutexes and Locks

```cpp
#include <userver/engine/mutex.hpp>
#include <userver/engine/semaphore.hpp>
#include <userver/engine/condition_variable.hpp>

class ThreadSafeCache {
public:
    std::optional<Value> Get(const Key& key) {
        std::lock_guard<engine::Mutex> lock(mutex_);
        
        auto it = cache_.find(key);
        if (it != cache_.end()) {
            return it->second;
        }
        
        return std::nullopt;
    }
    
    void Set(const Key& key, Value value) {
        std::lock_guard<engine::Mutex> lock(mutex_);
        cache_[key] = std::move(value);
    }
    
    engine::TaskWithResult<Value> GetOrSetAsync(
        const Key& key,
        std::function<Value()> generator) {
        
        // Try with read lock first
        {
            std::lock_guard<engine::Mutex> lock(mutex_);
            auto it = cache_.find(key);
            if (it != cache_.end()) {
                co_return it->second;
            }
        }
        
        // Generate value (outside of lock)
        Value value = generator();
        
        // Store with write lock
        {
            std::lock_guard<engine::Mutex> lock(mutex_);
            cache_[key] = value;
        }
        
        co_return value;
    }
    
private:
    engine::Mutex mutex_;
    std::unordered_map<Key, Value> cache_;
};
```

### Semaphores for Rate Limiting

```cpp
#include <userver/engine/semaphore.hpp>

class RateLimitedService {
public:
    RateLimitedService(size_t max_concurrent_requests)
        : semaphore_(max_concurrent_requests) {}
    
    engine::TaskWithResult<Response> CallWithRateLimit(
        std::function<Response()> operation) {
        
        // Acquire semaphore (wait if too many concurrent requests)
        auto lock = co_await engine::SemaphoreLock::Acquire(semaphore_);
        
        try {
            auto result = operation();
            co_return result;
        } catch (...) {
            // Ensure semaphore is released even on exception
            throw;
        }
        // lock releases semaphore when it goes out of scope
    }
    
private:
    engine::Semaphore semaphore_;
};
```

### Condition Variables

```cpp
#include <userver/engine/condition_variable.hpp>

class AsyncQueue {
public:
    engine::TaskWithResult<Item> Pop() {
        std::unique_lock<engine::Mutex> lock(mutex_);
        
        // Wait until queue is not empty
        co_await not_empty_.Wait(lock, [this] {
            return !queue_.empty();
        });
        
        Item item = std::move(queue_.front());
        queue_.pop_front();
        
        lock.unlock();
        not_full_.NotifyOne();
        
        co_return item;
    }
    
    engine::TaskWithResult<void> Push(Item item) {
        std::unique_lock<engine::Mutex> lock(mutex_);
        
        // Wait until queue is not full
        co_await not_full_.Wait(lock, [this] {
            return queue_.size() < max_size_;
        });
        
        queue_.push_back(std::move(item));
        
        lock.unlock();
        not_empty_.NotifyOne();
        
        co_return;
    }
    
private:
    engine::Mutex mutex_;
    engine::ConditionVariable not_empty_;
    engine::ConditionVariable not_full_;
    std::deque<Item> queue_;
    const size_t max_size_ = 1000;
};
```

## 6. Task Processor Selection

### Choosing the Right Task Processor

```cpp
#include <userver/engine/task/task_processor.hpp>

class TaskProcessorSelector {
public:
    // CPU-bound tasks
    engine::TaskProcessor& GetCpuTaskProcessor() {
        static auto& processor = engine::current_task::GetTaskProcessor();
        // Or get by name: components::GetTaskProcessor("cpu-task-processor");
        return processor;
    }
    
    // I/O-bound tasks
    engine::TaskProcessor& GetIoTaskProcessor() {
        // Use separate task processor for I/O
        return GetTaskProcessorByName("io-task-processor");
    }
    
    // Blocking tasks
    engine::TaskProcessor& GetBlockingTaskProcessor() {
        // Dedicated task processor for blocking operations
        return GetTaskProcessorByName("blocking-task-processor");
    }
    
    // Low-priority background tasks
    engine::TaskProcessor& GetBackgroundTaskProcessor() {
        return GetTaskProcessorByName("background-task-processor");
    }
    
private:
    engine::TaskProcessor& GetTaskProcessorByName(const std::string& name) {
        // Implementation depends on how task processors are managed
        // In userver, typically accessed through component system
        throw std::runtime_error("Not implemented");
    }
};
```

### Task Processor Affinity

```cpp
#include <userver/engine/task/task_processor.hpp>

void SetThreadAffinity() {
    // Set CPU affinity for current thread
    cpu_set_t cpuset;
    CPU_ZERO(&cpuset);
    CPU_SET(0, &cpuset); // Pin to CPU 0
    
    pthread_t current_thread = pthread_self();
    pthread_setaffinity_np(current_thread, sizeof(cpu_set_t), &cpuset);
}

class AffinityTaskProcessor {
public:
    engine::TaskWithResult<void> ExecuteWithAffinity(
        int cpu_id,
        std::function<void()> task) {
        
        // Store task to execute with specific affinity
        return utils::Async("affinity-task", [cpu_id, task = std::move(task)] {
            // Set affinity for this task
            cpu_set_t cpuset;
            CPU_ZERO(&cpuset);
            CPU_SET(cpu_id, &cpuset);
            
            pthread_t current_thread = pthread_self();
            pthread_setaffinity_np(current_thread, sizeof(cpu_set_t), &cpuset);
            
            // Execute task
            task();
        });
    }
};
```

## 7. Performance Optimization

### Avoiding Blocking Operations

```cpp
#include <userver/utils/async.hpp>

class AsyncFileOperations {
public:
    engine::TaskWithResult<std::string> ReadFileAsync(const std::string& path) {
        // Use dedicated task processor for file operations
        return utils::Async("file-read", engine::current_task::GetTaskProcessor(),
            [path]() -> std::string {
                // This runs on file task processor
                std::ifstream file(path);
                if (!file) {
                    throw std::runtime_error("Cannot open file: " + path);
                }
                
                return std::string(std::istreambuf_iterator<char>(file),
                                  std::istreambuf_iterator<char>());
            });
    }
    
    engine::TaskWithResult<void> WriteFileAsync(
        const std::string& path,
        const std::string& content) {
        
        return utils::Async("file-write", GetFileTaskProcessor(),
            [path, content]() {
                std::ofstream file(path);
                if (!file) {
                    throw std::runtime_error("Cannot write file: " + path);
                }
                
                file.write(content.data(), content.size());
            });
    }
};
```

### Batch Processing

```cpp
#include <userver/utils/async.hpp>

class BatchProcessor {
public:
    engine::TaskWithResult<std::vector<Result>> ProcessBatch(
        const std::vector<Item>& items,
        size_t batch_size = 10) {
        
        std::vector<engine::TaskWithResult<std::vector<Result>>> batch_tasks;
        
        // Split into batches
        for (size_t i = 0; i < items.size(); i += batch_size) {
            size_t end = std::min(i + batch_size, items.size());
            std::vector<Item> batch(items.begin() + i, items.begin() + end);
            
            batch_tasks.push_back(ProcessSingleBatch(std::move(batch)));
        }
        
        // Wait for all batches
        std::vector<Result> all_results;
        for (auto& task : batch_tasks) {
            auto batch_results = co_await task;
            all_results.insert(all_results.end(),
                              std::make_move_iterator(batch_results.begin()),
                              std::make_move_iterator(batch_results.end()));
        }
        
        co_return all_results;
    }
    
private:
    engine::TaskWithResult<std::vector<Result>> ProcessSingleBatch(
        std::vector<Item> batch) {
        
        std::vector<Result> results;
        results.reserve(batch.size());
        
        for (auto& item : batch) {
            results.push_back(ProcessItem(std::move(item)));
        }
        
        co_return results;
    }
};
```

## 8. Task Cancellation

### Cooperative Cancellation

```cpp
#include <userver/engine/task/cancel.hpp>

class CancellableOperation {
public:
    engine::TaskWithResult<Data> ExecuteWithCancellation(
        std::function<Data()> operation,
        std::chrono::milliseconds timeout) {
        
        // Create cancellation token with timeout
        auto token = engine::current_task::GetCancellationToken();
        
        // Start operation in separate task
        auto operation_task = utils::Async("operation", operation);
        
        // Wait for either operation completion or timeout
        auto wait_result = engine::WaitAny(
            {&operation_task, &timeout_task_});
        
        if (wait_result == 1) { // Timeout
            operation_task.RequestCancel();
            throw std::runtime_error("Operation timeout");
        }
        
        co_return operation_task.Get();
    }
    
    engine::TaskWithResult<void> ProcessWithCheckpoints(
        std::function<void()> operation) {
        
        auto token = engine::current_task::GetCancellationToken();
        
        // Checkpoint 1
        token.CheckNotCanceled();
        co_await Step1();
        
        // Checkpoint 2
        token.CheckNotCanceled();
        co_await Step2();
        
        // Checkpoint 3
        token.CheckNotCanceled();
        co_await Step3();
        
        co_return;
    }
};
```

### Cleanup on Cancellation

```cpp
#include <userver/engine/task/cancel.hpp>

class ResourceHolder {
public:
    ~ResourceHolder() {
        Cleanup();
    }
    
    engine::TaskWithResult<void> UseResource() {
        auto token = engine::current_task::GetCancellationToken();
        auto guard = MakeGuard([this] { Cleanup(); });
        
        try {
            co_await Initialize();
            token.CheckNotCanceled();
            
            co_await Process();
            token.CheckNotCanceled();
            
            co_await Finalize();
            
        } catch (const engine::TaskCancelledException&) {
            LOG_INFO() << "Operation cancelled, cleaning up";
            throw;
        }
        
        // Release guard - no cleanup needed
        guard.Release();
        co_return;
    }
    
private:
    void Cleanup() {
        // Release resources
    }
    
    class Guard {
    public:
        explicit Guard(std::function<void()> cleanup)
            : cleanup_(std::move(cleanup)) {}
        
        ~Guard() {
            if (cleanup_) {
                cleanup_();
            }
        }
        
        void Release() {
            cleanup_ = nullptr;
        }
        
    private:
        std::function<void()> cleanup_;
    };
    
    Guard MakeGuard(std::function<void()> cleanup) {
        return Guard(std::move(cleanup));
    }
};
```

## 9. Monitoring Task Processors

### Task Processor Metrics

```cpp
#include <userver/components/statistics_storage.hpp>

class TaskProcessorMonitor {
public:
    void RecordMetrics(engine::TaskProcessor& processor) {
        auto stats = processor.GetStats();
        
        // Record queue size
        queue_size_gauge_.Set(stats.task_queue_size);
        
        // Record active tasks
        active_tasks_gauge_.Set(stats.active_tasks);
        
        // Record overloaded state
        if (stats.task_queue_size > stats.worker_threads * 2) {
            overloaded_counter_.Increment();
        }
        
        LOG_DEBUG() << fmt::format(
            "Task processor {}: queue={}, active={}, workers={}",
            processor.GetName(),
            stats.task_queue_size,
            stats.active_tasks,
            stats.worker_threads);
    }
    
private:
    utils::statistics::MetricTag<utils::statistics::Gauge> queue_size_gauge_{"task_processor_queue_size"};
    utils::statistics::MetricTag<utils::statistics::Gauge> active_tasks_gauge_{"task_processor_active_tasks"};
    utils::statistics::MetricTag<utils::statistics::Rate> overloaded_counter_{"task_processor_overloaded"};
};
```

### Deadlock Detection

```cpp
#include <userver/engine/deadline.hpp>

class DeadlockDetector {
public:
    engine::TaskWithResult<void> WatchForDeadlocks(
        std::function<void()> operation,
        std::chrono::milliseconds timeout) {
        
        auto deadline = engine::Deadline::FromDuration(timeout);
        
        auto operation_task = utils::Async("watched-operation", operation);
        
        // Watchdog task
        auto watchdog_task = utils::Async("deadlock-watchdog", [deadline, &operation_task] {
            while (!deadline.IsReached()) {
                engine::SleepFor(std::chrono::milliseconds(100));
                
                if (operation_task.IsFinished()) {
                    return;
                }
            }
            
            // Timeout reached, operation might be deadlocked
            if (!operation_task.IsFinished()) {
                LOG_ERROR() << "Possible deadlock detected, cancelling operation";
                operation_task.RequestCancel();
            }
        });
        
        // Wait for operation to complete
        try {
            co_await operation_task;
        } catch (const engine::TaskCancelledException&) {
            LOG_WARNING() << "Operation cancelled due to possible deadlock";
            throw;
        }
        
        // Cancel watchdog
        watchdog_task.RequestCancel();
        
        co_return;
    }
};
```

## 10. Testing Asynchronous Code

### Unit Tests for Async Functions

```cpp
#include <userver/utest/utest.hpp>
#include <userver/engine/async.hpp>

TEST(TaskProcessorTest, AsyncComputation) {
    // Run test in async context
    RunInCoro([] {
        auto task = utils::Async("test-computation", [] {
            return 42;
        });
        
        EXPECT_EQ(task.Get(), 42);
    });
}

TEST(TaskProcessorTest, Cancellation) {
    RunInCoro([] {
        engine::TaskWithResult<void> task;
        
        {
            engine::TaskCancellationSource source;
            task = utils::Async("cancellable", [token = source.GetToken()] {
                // This should be cancelled
                engine::SleepFor(std::chrono::seconds(10));
            });
            
            // Cancel immediately
            source.RequestCancel();
        }
        
        EXPECT_THROW(task.Get(), engine::TaskCancelledException);
    });
}
```

### Integration Tests

```cpp
#include <userver/utest/utest.hpp>

class AsyncServiceTest : public ::testing::Test {
protected:
    void SetUp() override {
        // Initialize task processors for testing
        task_processor_ = &engine::current_task::GetTaskProcessor();
    }
    
    engine::TaskWithResult<int> TestAsyncOperation(int input) {
        return utils::Async("test-op", *task_processor_, [input] {
            // Simulate async work
            engine::SleepFor(std::chrono::milliseconds(10));
            return input * 2;
        });
    }
    
private:
    engine::TaskProcessor* task_processor_;
};

TEST_F(AsyncServiceTest, ConcurrentOperations) {
    RunInCoro([this] {
        std::vector<engine::TaskWithResult<int>> tasks;
        
        // Launch 100 concurrent operations
        for (int i = 0; i < 100; ++i) {
            tasks.push_back(TestAsyncOperation(i));
        }
        
        // Verify all results
        for (int i = 0; i < 100; ++i) {
            EXPECT_EQ(tasks[i].Get(), i * 2);
        }
    });
}
```

## 11. Troubleshooting

### Common Issues

#### Task Processor Overload
- Symptoms: High queue sizes, slow response times
- Solutions: Increase worker threads, optimize task sizes, implement backpressure

#### Deadlocks
- Symptoms: Tasks stuck indefinitely
- Solutions: Use deadlock detection, avoid locking multiple mutexes, use lock ordering

#### Memory Leaks in Tasks
- Symptoms: Memory growth over time
- Solutions: Ensure tasks complete, use RAII, monitor task lifetime

#### Cancellation Not Working
- Symptoms: Tasks continue after cancellation
- Solutions: Add cancellation checkpoints, use `TaskCancellationToken`

### Debugging Tools

1. **Task traces**: Enable `task-trace` in configuration
2. **GDB debugging**: Attach to process and examine task states
3. **Logging**: Add detailed logs to track task flow
4. **Metrics**: Monitor task processor queue sizes and active tasks

## Best Practices

1. **Choose appropriate task processors**: Separate CPU-bound, I/O-bound, and blocking operations
2. **Use coroutines for async code**: More readable than callbacks or futures
3. **Implement proper cancellation**: Allow long-running tasks to be cancelled
4. **Avoid blocking in coroutines**: Use dedicated task processors for blocking operations
5. **Monitor task processor health**: Track queue sizes and worker utilization
6. **Use synchronization primitives correctly**: Prefer `engine::Mutex` over `std::mutex`
7. **Limit concurrency**: Use semaphores to prevent overload
8. **Test async code thoroughly**: Include cancellation and timeout scenarios
9. **Profile performance**: Identify bottlenecks in task processing
10. **Document task processor assignments**: Keep configuration documented and consistent