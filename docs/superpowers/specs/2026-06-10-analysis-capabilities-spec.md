# 遗留系统分析能力说明书 v0.2

> 理想状态下，`legacy-scan` 对任意代码仓库应产出的完整分析报告。
> 本说明书定义每个维度的分析目标、检测方法和预期输出格式。
> 实施时从 Java/Spring Boot 开始，逐步覆盖其他语言。

---

## 一、代码分析

### 1.1 规模统计

**目标：** 量化代码体量，建立全局感知。

| 指标 | 检测方法 | 输出示例 |
|------|----------|----------|
| 总文件数 | `find / rglob` 统计（排除 .git/node_modules/target） | `1,247 files` |
| 总代码行 | 逐文件 `read_text()` 统计非空行 | `142,000 LOC` |
| 语言分布 | 按扩展名分组统计 | `Java 78% / XML 12% / YAML 6% / SQL 4%` |
| 提交历史 | `git log` 统计提交数、贡献者数 | `1,832 commits by 14 authors since 2019-03` |
| 活跃度 | 近 30/90/180 天提交频率 | `30d: 42 commits / 90d: 156 commits` |
| 热力图 | 哪些目录/文件变更最频繁 | `src/main/java/.../service/ (312 commits)` |

### 1.2 代码质量

**目标：** 识别潜在维护风险。

| 指标 | 检测方法 | 输出示例 |
|------|----------|----------|
| 圈复杂度 | 统计 `if/for/while/switch/case/catch` 分支数 | `avg: 4.2 / max: 38 (BdmsBackupPolicyServiceImpl.java)` |
| 嵌套深度 | 最大缩进层级 | `avg: 1.8 / max: 7` |
| 重复代码 | 哈希相邻 N 行，检测重复块 | `23 duplicated blocks (3.2%)` |
| 注释覆盖率 | 注释行 / 总行 | `12.4% (偏低，建议 >20%)` |
| 文件大小分布 | 按 LOC 分桶 | `0-100: 68% / 100-500: 24% / 500-1000: 6% / >1000: 2%` |

### 1.3 包/模块层级树

**目标：** 可视化项目结构。

**检测方法：**
- Java: 从 `package com.xxx.yyy;` 声明构建树
- Python: 从目录 + `__init__.py` 构建
- Go: 从 `go.mod` module 名 + 目录构建
- 通用: 解析 import/include 语句建立父子关系

**输出格式：**
```yaml
modules:
  - name: com.financialtech.backupdatamanagement
    type: root
    children:
      - name: controller
        files: 8
        loc: 1240
        role: REST_API_LAYER
      - name: service
        children:
          - name: impl
            files: 6
            loc: 3840
            role: BUSINESS_LOGIC
      - name: repository
        files: 5
        loc: 320
        role: DATA_ACCESS
      - name: config
        files: 4
        loc: 180
        role: CONFIGURATION
      - name: dto
        files: 12
        loc: 480
        role: DATA_TRANSFER
```

### 1.4 类级分析

**目标：** 找出需要重构的类和方法。

| 检测项 | 阈值 | 检测方法 |
|--------|------|----------|
| 上帝类 | LOC > 500 | 统计每个 .java 文件行数 |
| 长方法 | 方法体 > 50 行 | 正则匹配方法声明→下一个方法/类结尾，统计行数 |
| 参数过多 | 方法参数 > 5 个 | 正则匹配方法签名中的参数列表 |
| 单例滥用 | 类名含 Singleton 或静态工厂 | 模式匹配 |
| 工具类过多 | 类名以 Util/Helper/Utils 结尾 | 模式匹配，标记为潜在设计问题 |

**输出格式：**
```yaml
god_classes:
  - file: BdmsBackupPolicyServiceImpl.java
    loc: 1247
    methods: 34
    risk: "单类承载过多职责，建议按业务边界拆分"
long_methods:
  - class: BackupService
    method: executeFullBackup
    loc: 87
    file: BackupServiceImpl.java:142
```

### 1.5 废弃代码

| 检测项 | 方法 |
|--------|------|
| @Deprecated 注解 | 正则匹配 Java `@Deprecated` / Python `@deprecated` |
| 注释掉的代码块 | 连续 5+ 行以 `//` 或 `#` 开头且含代码关键词 |
| 未使用的 import | 匹配 `import X` 但全文未出现 `X` 的类名 |
| 空方法/空类 | 方法体只有 `return null` / `pass` / 空大括号 |

---

## 二、整体架构

### 2.1 架构风格识别

**目标：** 自动判定项目采用的架构模式。

| 风格 | 检测特征 | 置信度信号 |
|------|----------|-----------|
| 分层架构 | controller / service / repository / model 包存在 | 目录名匹配 |
| 微服务 | 多个独立模块各有自己的 `Application.java` / `main.go` | 多 entry point |
| 事件驱动 | 存在 `@EventListener` / `@KafkaListener` / EventBus | 注解/导入匹配 |
| DDD | 包名含 domain / aggregate / entity / valueobject | 目录名匹配 |
| 六边形架构 | 包名含 adapter / port / hexagon | 目录名匹配 |
| CQRS | 有分离的 command / query 包或类 | 目录+类名匹配 |

**输出示例：**
```
架构风格: 分层架构 + 事件驱动 (置信度: 高)
检测依据:
  - 存在 controller → service → repository 标准分层
  - @KafkaListener 注解分布在 3 个类中
  - 有独立的 dto / config / util 包
```

### 2.2 模块边界与职责

**目标：** 画出模块依赖图和职责描述。

**检测方法：**
- 按 package 第一级分组（如 `com.financialtech.backupdatamanagement.*`）
- 统计每个模块的文件数、行数、Spring 注解分布
- 通过 import 语句构建模块间依赖图

**输出格式：**
```yaml
modules:
  - name: backupdatamanagement
    responsibility: "备份数据管理核心模块 — 备份策略、恢复、调度"
    type: core
    spring_components:
      controllers: [BackupPolicyController, RecoveryController]
      services: [BackupPolicyService, RecoveryService, ScheduleService]
      repositories: [BackupPolicyRepository, RecoveryLogRepository]
    depends_on: [bdms-module-biz, bdms-module-api]
    depended_by: [bdms-server, bdms-jk-modules]

  - name: bdms-module-biz
    responsibility: "业务逻辑层 — 客户端管理、任务调度、用量统计"
    type: business
    depends_on: [backupdatamanagement, bdms-module-api]
```

### 2.3 层间调用关系

**目标：** 验证分层规范是否被遵守。

| 检查项 | 规则 | 违规示例 |
|--------|------|----------|
| Controller→Service | ✅ 允许 | import ...service.XxxService |
| Controller→Repository | ❌ 违规 | Controller 直接 import Repository |
| Service→Controller | ❌ 违规 | 反向依赖 |
| Repository→Service | ❌ 违规 | DAO 层不应依赖业务层 |

**输出示例：**
```
分层规范检查:
  ✅ Controller→Service: 12 条调用，合规
  ❌ Controller→Repository: 2 条违规
    - BackupPolicyController.java:45 → BackupPolicyRepository
    - RecoveryController.java:78 → RecoveryLogRepository
    建议: 通过 Service 层封装数据访问
  ❌ Service→Controller: 1 条违规
    - AuthService.java:120 → LoginController
    建议: 使用事件或回调解耦
```

### 2.4 循环依赖检测

**检测方法：** DFS 遍历 import 图，检测环。

```
循环依赖检测:
  ❌ bdms-module-api ⇄ bdms-module-biz (双向 import)
    - bdms-module-api → bdms-module-biz (ApiConfig.java:12)
    - bdms-module-biz → bdms-module-api (BizService.java:8)
    建议: 提取公共接口到 shared 模块
```

### 2.5 入口点识别

| 入口类型 | 检测方法 |
|----------|----------|
| main() 方法 | 正则 `public static void main` |
| @SpringBootApplication | 注解匹配 |
| @RestController | 注解 + @RequestMapping 路径收集 |
| 消息消费者入口 | @KafkaListener / @RabbitListener |
| 定时任务入口 | @Scheduled / @EnableScheduling |
| 过滤器/拦截器 | @WebFilter / HandlerInterceptor |

---

## 三、接口

### 3.1 REST API 全量清单

**目标：** 生成完整的 API 文档。

**检测方法：**
- Java: 解析 `@RestController` → `@RequestMapping/@GetMapping/@PostMapping/@PutMapping/@DeleteMapping`
- Python: 解析 `@app.route()` / `@router.get()` (FastAPI/Flask)
- Go: 解析 `r.GET()` / `router.Handle()` (Gin/Echo)
- 提取注解中的路径、方法、produces/consumes
- 提取方法签名中的参数（`@RequestParam/@PathVariable/@RequestBody`）
- 提取返回类型

**输出格式：**
```yaml
endpoints:
  - method: POST
    path: /api/v1/backup/policies
    controller: BackupPolicyController
    method_name: createPolicy
    parameters:
      - name: policy
        type: BackupPolicyDTO
        location: body
        required: true
    responses:
      - status: 200
        type: Result<BackupPolicyVO>
      - status: 400
        type: ErrorResult
    auth_required: true
    rate_limited: false
    description: "创建备份策略"

  - method: GET
    path: /api/v1/backup/policies/{policyId}
    controller: BackupPolicyController
    parameters:
      - name: policyId
        type: Long
        location: path
    responses:
      - status: 200
        type: Result<BackupPolicyVO>

summary:
  total_endpoints: 47
  by_method: {GET: 18, POST: 15, PUT: 8, DELETE: 6}
  auth_required: 42
  deprecated: 3
```

### 3.2 RPC / gRPC 接口

| 检测项 | 方法 |
|--------|------|
| gRPC | 解析 `.proto` 文件 → 提取 service/rpc/message 定义 |
| Dubbo | 解析 `@DubboService` / `@DubboReference` 注解 |
| Feign | 解析 `@FeignClient` 注解 + 接口方法 |
| WebClient/RestTemplate | 搜索 `new RestTemplate()` / `WebClient.create()` 调用 |

### 3.3 消息队列接口

| 检测项 | 方法 |
|--------|------|
| Kafka | 解析 `@KafkaListener(topics="xxx")` → 提取 topic + groupId |
| RabbitMQ | 解析 `@RabbitListener(queues="xxx")` |
| RocketMQ | 解析 `@RocketMQMessageListener` |
| 生产者 | 搜索 `KafkaTemplate.send()` / `RabbitTemplate.convertAndSend()` |

**输出格式：**
```yaml
message_queues:
  - type: KAFKA
    topics:
      - name: backup.task.created
        producers: [BackupTaskService]
        consumers: [TaskExecutorService]
        partitions: 8
      - name: backup.task.completed
        producers: [TaskExecutorService]
        consumers: [NotificationService, LogService]
      - name: backup.recovery.requested
        producers: [RecoveryController]
        consumers: [RecoveryService]
```

### 3.4 对外 SDK / Client

| 检测项 | 方法 |
|--------|------|
| HTTP Client | 搜索 `RestTemplate` / `WebClient` / `OkHttp` / `Retrofit` 调用 |
| SDK 导入 | 从 pom.xml / build.gradle 中筛选 client/sdk 依赖 |
| 外部 API 调用 | 从 `application.yml` 中提取外部 URL/endpoint |

### 3.5 接口变更影响范围

**检测方法：**
- 构建 API → Consumer 的反向索引
- 标记被多个模块依赖的公开接口
- 识别无 Consumer 的接口（可能废弃）

```
接口影响分析:
  /api/v1/backup/policies (被 3 个前端调用 / 2 个微服务)
  /api/v1/internal/health (被 0 个外部调用 → 疑似废弃)
```

---

## 四、业务逻辑

### 4.1 业务域识别

**目标：** 从代码结构推断业务领域。

**检测方法：**
- 从包名/模块名提取关键词 → 映射到业务域
- 从 README / 项目描述推断
- 从 @Entity 表名推断数据域
- 从 @RestController 路径前缀提取 API 域

**输出示例：**
```yaml
business_domains:
  - name: 备份管理
    keywords: [backup, policy, schedule, snapshot]
    modules: [backupdatamanagement]
    entities: [BdmsBackupPolicy, BackupTask, BackupRecord]
    api_prefix: /api/v1/backup

  - name: 恢复管理
    keywords: [recovery, restore, rollback]
    modules: [backupdatamanagement]
    entities: [RecoveryTask, RecoveryLog]
    api_prefix: /api/v1/recovery

  - name: 客户端管理
    keywords: [client, agent, endpoint, host]
    modules: [bdms-module-biz]
    entities: [BdmsClient, ClientConfig, ClientTask]

  - name: 用量统计
    keywords: [usage, quota, statistics, counter]
    modules: [bdms-module-biz]
    entities: [BdmsAutomateCosCounter, UsageRecord]
```

### 4.2 核心业务流程

**目标：** 追踪关键业务流程的调用链。

**检测方法：**
- 从 Controller 入口方法开始，追踪方法调用链
- 遇到 Service → 继续追踪
- 遇到 Repository → 标记数据操作
- 遇到 Kafka/RabbitMQ 发送 → 标记异步事件
- 遇到 @Transactional → 标记事务边界

**输出示例：**
```
业务流程: 创建备份策略并触发首次备份

1. POST /api/v1/backup/policies → BackupPolicyController.createPolicy()
   ├── [校验] PolicyValidator.validate(policyDTO)
   │   ├── 检查策略名称唯一性
   │   ├── 验证备份时间窗口合法性
   │   └── 检查客户端是否存在
   ├── [事务] BackupPolicyService.createPolicy(policyDTO)
   │   ├── policyRepository.save(policy)        → INSERT INTO bdms_backup_policy
   │   ├── scheduleService.createSchedule(policy)→ INSERT INTO bdms_schedule
   │   └── [事件] kafkaTemplate.send("backup.task.created", event)
   └── [异步] TaskExecutorService.onTaskCreated(event)
       ├── backupEngine.createSnapshot(task)     → 调用备份引擎
       ├── taskRepository.updateStatus(task)     → UPDATE bdms_backup_task
       └── [事件] kafkaTemplate.send("backup.task.completed", event)
```

### 4.3 状态机 / 工作流

**检测方法：**
- 搜索 enum 类中包含状态转换逻辑（`if (state == X) → Y`）
- 搜索 `@StateMachine` / `@EnableStateMachine` (Spring Statemachine)
- 搜索 `Flowable` / `Activiti` / `Camunda` 工作流引擎导入
- 从数据库表名推断（`*_workflow`, `*_state`, `*_status`）

**输出示例：**
```
状态机: 备份任务生命周期

  PENDING ──→ RUNNING ──→ COMPLETED
                  │
                  └──→ FAILED ──→ RETRYING ──→ COMPLETED
                                        │
                                        └──→ FAILED (永久)

  状态变更追踪:
    PENDING: BackupTaskService.createTask()
    RUNNING: TaskExecutorService.startExecution()
    COMPLETED: TaskExecutorService.onSuccess()
    FAILED: TaskExecutorService.onFailure() (重试次数<3 → RETRYING)
```

### 4.4 业务规则

**检测方法：**
- 搜索校验逻辑：`if (xxx == null) throw` / `Preconditions.checkNotNull`
- 搜索 `@Valid` / `@Validated` / `Validator`
- 搜索异常处理：`try-catch` / `@ExceptionHandler` / `@ControllerAdvice`
- 搜索自定义 Exception 类

**输出示例：**
```yaml
business_rules:
  - rule: "备份策略名称全局唯一"
    enforced_at: PolicyValidator.validateName()
    error: DUPLICATE_POLICY_NAME

  - rule: "每个客户端最多 10 个活跃备份策略"
    enforced_at: ClientService.validatePolicyLimit()
    error: POLICY_LIMIT_EXCEEDED

  - rule: "备份时间窗口不能与现有任务重叠"
    enforced_at: ScheduleValidator.checkOverlap()
    error: SCHEDULE_OVERLAP

validation_coverage:
  controllers_with_validation: 8/12 (67%)
  custom_validators: 4
  global_exception_handler: GlobalExceptionHandler (23 种异常)
```

### 4.5 数据字典 / 枚举

**检测方法：**
- 搜索 Java `enum` 定义
- 搜索 Python `Enum` 类
- 搜索数据库表 `*_dict` / `*_type` (字典表)

**输出示例：**
```yaml
enums:
  - name: BackupType
    file: BackupType.java
    values:
      - FULL: "全量备份"
      - INCREMENTAL: "增量备份"
      - DIFFERENTIAL: "差异备份"

  - name: BackupStatus
    values:
      - PENDING, RUNNING, COMPLETED, FAILED, CANCELLED

  - name: ClientStatus
    values:
      - ONLINE, OFFLINE, MAINTENANCE, UNKNOWN
```

---

## 五、中间件

### 5.1 数据库

| 检测项 | 方法 |
|--------|------|
| 数据库类型 | 从 `application.yml` jdbc-url 或 `driver-class-name` 推断 |
| ORM 框架 | `spring-boot-starter-data-jpa` → Hibernate; `mybatis` → MyBatis |
| 连接池 | `HikariCP` (默认) / `Druid` / `C3P0` |
| 分库分表 | `ShardingSphere` / `MyCat` 依赖检测 |
| 读写分离 | 搜索 `@ReadOnly` / `@Master` / 多个数据源配置 |
| 慢查询 | 从配置文件检测 `slow-sql-log` 阈值 |
| 迁移工具 | `Flyway` / `Liquibase` 依赖 + `db/migration` 目录 |

**输出示例：**
```yaml
databases:
  - type: MySQL 8.0
    hosts: [10.0.1.12:3306, 10.0.1.13:3306]
    databases: [bdms_prod, bdms_config]
    orm: JPA/Hibernate 5.4
    connection_pool: HikariCP (max: 20, timeout: 30s)
    sharding: ShardingSphere 5.0 (按 client_id 分 8 片)
    migration: Flyway (12 migration files)
    slow_query_threshold: 1000ms
```

### 5.2 缓存

| 检测项 | 方法 |
|--------|------|
| Redis | `spring-boot-starter-data-redis` / `Redisson` / `Jedis` 依赖 |
| 本地缓存 | `Caffeine` / `Guava Cache` / `Ehcache` |
| 缓存注解 | `@Cacheable` / `@CacheEvict` / `@CachePut` |
| 缓存 Key 模式 | 从注解 `key="xxx"` 提取 key 模板 |
| 过期策略 | 从 `@Cacheable` 或 Redis 配置提取 TTL |

**输出示例：**
```yaml
caches:
  - type: Redis Cluster
    nodes: 6
    usage:
      - purpose: "客户端信息缓存"
        keys: [client:{clientId}, client:list]
        ttl: 600s
        pattern: "@Cacheable(value='client', key='#clientId')"

      - purpose: "备份策略缓存"
        keys: [policy:{policyId}, policy:byClient:{clientId}]
        ttl: 1800s

      - purpose: "分布式锁"
        keys: [lock:backup:execute:{taskId}]
        ttl: 120s
        pattern: "Redisson.getLock()"
```

### 5.3 消息队列

（详见 3.3 节接口部分，此处做汇总索引）

```yaml
mq_summary:
  broker: Kafka 2.8
  producers: 5 个服务
  consumers: 8 个消费者组
  topics: 12 个
  dead_letter: bdms.dlq (统一死信队列)
```

### 5.4 搜索引擎

| 检测项 | 方法 |
|--------|------|
| Elasticsearch | `spring-boot-starter-data-elasticsearch` / `RestHighLevelClient` |
| 索引定义 | 搜索 `@Document(indexName="xxx")` |
| 查询构建 | 搜索 `QueryBuilders` / `BoolQueryBuilder` |

### 5.5 定时任务

**检测方法：**
- 搜索 `@Scheduled(cron="xxx")` / `@Schedules`
- 搜索 `@EnableScheduling`
- 搜索 `TaskScheduler` / `ThreadPoolTaskScheduler`
- 搜索 `xxl-job` / `Quartz` / `Elastic-Job` 依赖

**输出格式：**
```yaml
scheduled_jobs:
  - name: syncClientStatus
    cron: "0 */5 * * * *"
    class: ClientStatusSyncJob
    description: "每 5 分钟同步客户端在线状态"
    thread_pool: scheduledPool (core: 4)

  - name: cleanExpiredBackups
    cron: "0 0 2 * * *"
    class: BackupCleanupJob
    description: "每天凌晨 2 点清理过期备份"

  - name: reportDailyUsage
    cron: "0 30 8 * * *"
    class: UsageReportJob
    description: "每天 8:30 发送用量日报"
```

### 5.6 配置中心

| 检测项 | 方法 |
|--------|------|
| Nacos | `nacos-config-spring-boot-starter` / `@NacosValue` |
| Apollo | `apollo-client` / `@ApolloConfig` |
| Consul | `spring-cloud-starter-consul-config` |
| Spring Cloud Config | `spring-cloud-config-client` |

---

## 六、部署运维

### 6.1 构建工具

| 检测项 | 方法 |
|--------|------|
| Maven | `pom.xml` → 提取 groupId/artifactId/version |
| Gradle | `build.gradle` → 提取 project 名 |
| 构建配置 | 提取 `<properties>` / `ext` 中的版本变量 |
| Profile | 提取 `<profiles>` 或 `application-{profile}.yml` |

### 6.2 容器化

| 检测项 | 方法 |
|--------|------|
| Dockerfile | 解析 FROM/EXPOSE/CMD/COPY 指令 |
| docker-compose | 解析 services/volumes/networks |
| 镜像仓库 | 从 Dockerfile FROM 或 CI 配置提取 |
| 资源限制 | 从 docker-compose mem_limit / K8s resources 提取 |

**输出示例：**
```yaml
containerization:
  dockerfiles:
    - path: Dockerfile
      base_image: openjdk:11-jre-slim
      exposed_ports: [8080, 9090]
      entrypoint: java -jar app.jar
  docker_compose:
    services: [bdms-server, mysql, redis, kafka, zookeeper]
    volumes: [/data/bdms:/data, ./logs:/app/logs]
  kubernetes:
    detected: true
    manifests: 8 YAML files
    namespaces: [bdms-prod, bdms-staging]
```

### 6.3 CI/CD

| 检测项 | 方法 |
|--------|------|
| Jenkins | `Jenkinsfile` 存在 |
| GitHub Actions | `.github/workflows/*.yml` |
| GitLab CI | `.gitlab-ci.yml` |
| 部署步骤 | 解析 pipeline 中的 stage/job/step |

### 6.4 健康检查

| 检测项 | 方法 |
|--------|------|
| Spring Actuator | `spring-boot-starter-actuator` 依赖 |
| 健康端点 | `/actuator/health`, `/health`, `/ready` |
| 自定义指标 | `@RequestMapping("/health")` 或 `HealthIndicator` 实现 |
| 就绪探针 | `management.endpoint.health.probes.enabled=true` |

### 6.5 日志

| 检测项 | 方法 |
|--------|------|
| 日志框架 | `logback-spring.xml` → Logback; `log4j2.xml` → Log4j2 |
| 日志级别 | 从 XML/YML 提取各 package 的 level |
| 日志输出 | 控制台/文件/ELK/Kafka appender |
| MDC 字段 | 搜索 `MDC.put` 调用 |
| Trace ID | 搜索 `traceId` / `TraceId` 模式 |

**输出示例：**
```yaml
logging:
  framework: Logback 1.2
  config: src/main/resources/logback-spring.xml
  levels:
    root: INFO
    com.financialtech: DEBUG
    org.springframework: WARN
  appenders:
    - type: CONSOLE
    - type: FILE
      path: /app/logs/bdms.log
      rolling: daily, max 30 days
    - type: KAFKA
      topic: bdms.logs
  trace_id: MDC.put("traceId", ...)
```

### 6.6 监控

| 检测项 | 方法 |
|--------|------|
| Prometheus | `micrometer-registry-prometheus` 依赖 |
| 自定义指标 | `@Timed` / `Counter` / `Gauge` 注解 |
| 告警规则 | `prometheus-alerts.yml` / `alertmanager.yml` |
| Grafana | 检测 `grafana/dashboards/` 目录 |
| APM | `skywalking` / `pinpoint` / `elastic-apm` 依赖 |

### 6.7 配置文件清单

**检测方法：** 搜索 `application*.yml/yaml/properties`，按 profile 分类。

**输出格式：**
```yaml
config_files:
  - file: application.yml
    profile: default
    keys: [server.port, spring.application.name, spring.profiles.active]
  - file: application-prod.yml
    profile: prod
    keys: [spring.datasource.*, spring.redis.*, spring.kafka.*]
    warnings:
      - "spring.datasource.password 包含明文密码 → 建议使用环境变量或密钥管理"
      - "server.port=8080 使用默认端口"
```

---

## 七、安全

### 7.1 认证

| 检测项 | 方法 |
|--------|------|
| JWT | 搜索 `JwtTokenProvider` / `JwtUtils` / `jjwt` 依赖 |
| OAuth2 | `spring-security-oauth2` / `@EnableOAuth2Sso` |
| Session | `spring-session` / `@EnableRedisHttpSession` |
| Basic Auth | `httpBasic()` 在 SecurityConfig 中 |
| 自定义认证 | 搜索 `AuthenticationProvider` / `UserDetailsService` 实现 |

**输出示例：**
```yaml
authentication:
  type: JWT + OAuth2
  token:
    issuer: bdms-auth-service
    algorithm: RS256
    expiry: 7200s (2h)
    refresh: 604800s (7d)
  login_endpoint: POST /api/v1/auth/login
  token_storage: Redis (key: token:{userId}:{jti})
```

### 7.2 鉴权

| 检测项 | 方法 |
|--------|------|
| Spring Security | `SecurityConfig` → 解析 `.antMatchers()` / `.hasRole()` |
| 方法级鉴权 | `@PreAuthorize("hasRole('ADMIN')")` / `@Secured` |
| RBAC 模型 | 搜索 `Role` / `Permission` 实体类 |
| 数据级鉴权 | 搜索 `@PostFilter` / `DataScope` |

**输出示例：**
```yaml
authorization:
  model: RBAC (Role-Based Access Control)
  roles: [ADMIN, OPERATOR, VIEWER]
  permissions:
    - name: BACKUP_CREATE
      roles: [ADMIN, OPERATOR]
      endpoints: [POST /api/v1/backup/*]
    - name: BACKUP_VIEW
      roles: [ADMIN, OPERATOR, VIEWER]
      endpoints: [GET /api/v1/backup/*]
    - name: SYSTEM_CONFIG
      roles: [ADMIN]
      endpoints: [GET|PUT /api/v1/system/*]
```

### 7.3 敏感数据

| 检测项 | 方法 |
|--------|------|
| 加密 | 搜索 `AES` / `RSA` / `Cipher` / `Encryptor` |
| 脱敏 | 搜索 `@Sensitive` / `Desensitize` / `mask` |
| 密钥管理 | 搜索 `KeyStore` / `Vault` / `KMS` |
| 敏感字段 | 从日志脱敏配置或加密注解推断 |

### 7.4 漏洞检测

| 漏洞类型 | 检测方法 |
|----------|----------|
| SQL 注入 | 搜索字符串拼接 SQL / `Statement` (非 PreparedStatement) |
| XSS | 搜索未转义的 `@ResponseBody` + 用户输入 |
| CSRF | 检查是否 `csrf().disable()` |
| SSRF | 搜索用户可控的 URL 请求参数 |
| 路径遍历 | 搜索 `../../` 或未校验的文件路径参数 |
| 反序列化 | 搜索 `ObjectInputStream` / `readObject` |
| 硬编码密钥 | 搜索 `API_KEY =` / `password = "xxx"` / `secret = "xxx"` |

**输出格式：**
```yaml
vulnerabilities:
  - type: HARDCODED_SECRET
    severity: CRITICAL
    file: application-prod.yml:23
    evidence: "spring.datasource.password: MyProdP@ss123"
    recommendation: "使用 ${DB_PASSWORD} 环境变量"

  - type: CSRF_DISABLED
    severity: MEDIUM
    file: SecurityConfig.java:45
    evidence: ".csrf().disable()"
    recommendation: "评估是否确实需要禁用 CSRF"

  - type: SSRF_RISK
    severity: HIGH
    file: WebhookService.java:67
    evidence: "RestTemplate.getForEntity(userInputUrl, ...)"
    recommendation: "校验 URL 白名单，禁止内网地址"
```

### 7.5 依赖安全

**检测方法：**
- 从 `pom.xml` / `build.gradle` 提取所有依赖及其版本
- 与已知 CVE 数据库交叉比对（需要外接 CVE 数据源）
- 标记有已知漏洞的依赖版本

**输出格式：**
```yaml
dependency_vulnerabilities:
  - artifact: log4j-core:2.14.0
    cve: CVE-2021-44228 (Log4Shell)
    severity: CRITICAL
    fixed_version: 2.17.0
    recommendation: "立即升级到 2.17.0+"
  - artifact: jackson-databind:2.13.0
    cve: CVE-2022-42003
    severity: HIGH
    fixed_version: 2.13.4
```

### 7.6 许可证合规

**检测方法：**
- Maven: `mvn license:aggregate-add-third-party` 或解析 `pom.xml` licenses
- 标记 GPL/AGPL 依赖（对企业项目有风险）

**输出格式：**
```yaml
license_issues:
  - artifact: mysql-connector-java
    license: GPL-2.0
    risk: "GPL 传染性——评估是否可替换为 MIT 授权的 MariaDB 驱动"
```

---

## 八、数据流

### 8.1 请求链路

**目标：** 追踪一个请求从入口到数据库的完整路径。

**检测方法：**
- 从 Controller → Service → Repository 调用链构建
- 识别中间经过的过滤器、拦截器、AOP 切面

**输出格式：**
```
请求链路: GET /api/v1/backup/policies/{id}

Client
 │  HTTP GET
 ▼
[Tomcat 8080]
 │
 ▼
[AuthFilter] → JWT 验证 → 注入 UserContext
 │
 ▼
[RateLimitInterceptor] → Redis 计数器检查
 │
 ▼
[BackupPolicyController.getPolicy(id)]
 │  @PreAuthorize("hasRole('OPERATOR')")
 │
 ▼
[BackupPolicyService.getPolicyDetail(id)]
 │  @Cacheable(value="policy", key="#id")
 │  ── Redis 命中? → 直接返回
 │  ── 未命中 →
 │
 ▼
[BackupPolicyRepository.findById(id)]
 │
 ▼
[MySQL bdms_prod.bdms_backup_policy]
 │  SELECT * FROM bdms_backup_policy WHERE id = ?
 │
 ▼
返回 → 写入 Redis 缓存 → 序列化 JSON → HTTP 200
```

### 8.2 持久化路径

**检测方法：** 追踪所有 `repository.save()` / `repository.insert()` 调用。

```yaml
persistence_flows:
  - entity: BackupPolicy
    writes: BackupPolicyRepository.save() (3 个调用点)
    reads: BackupPolicyRepository.findById/ findByClientId/ findAll (8 个调用点)
    cache: Redis policy:{id} (TTL: 1800s)
    table: bdms_backup_policy (预计 100K 行)
```

### 8.3 异步处理链路

**检测方法：** 追踪 `@Async` / `@EventListener` / 线程池提交。

```yaml
async_flows:
  - trigger: POST /api/v1/backup/execute/{policyId}
    flow:
      - BackupController.executeBackup() → 返回 202 Accepted
      - [线程池 backup-executor] TaskExecutorService.startBackup()
      - [@Async] NotificationService.sendNotification()
      - [@KafkaListener] LogService.recordBackupLog()
```

### 8.4 数据同步

**检测方法：**
- 搜索 Canal / Debezium / Maxwell CDC 工具依赖
- 搜索定时同步任务
- 搜索跨库查询

---

## 九、测试覆盖

### 9.1 测试框架

| 检测项 | 方法 |
|--------|------|
| 单元测试框架 | `junit` / `testng` 依赖 |
| Mock 框架 | `mockito` / `powermock` / `easymock` |
| 集成测试 | `@SpringBootTest` / `@DataJpaTest` / Testcontainers |
| BDD 框架 | `cucumber` / `spock` / `jbehave` |

### 9.2 测试覆盖率

**检测方法：**
- 搜索 `jacoco` / `cobertura` 依赖
- 从 `jacoco.xml` 或 `pom.xml` jacoco 配置提取覆盖率目标
- 统计测试文件数 / 源文件数比例

### 9.3 测试类型分布

```yaml
test_summary:
  framework: JUnit 5 + Mockito 3
  test_files: 87
  test_to_source_ratio: 0.42 (87 tests / 207 source files)
  types:
    unit: 68 (78%)
    integration: 15 (17%)
    e2e: 4 (5%)
  coverage_target: "jacoco: 80% line / 70% branch"
```

### 9.4 关键路径测试覆盖

**检测方法：**
- 找出调用频率最高的 Controller 方法
- 检查是否有对应的测试类

```yaml
critical_path_coverage:
  - endpoint: POST /api/v1/backup/policies
    test: ✅ BackupPolicyControllerTest.testCreatePolicy()
  - endpoint: POST /api/v1/backup/execute
    test: ❌ 无测试
    risk: "核心执行接口无测试覆盖 — 高风险"
  - endpoint: GET /api/v1/recovery/status
    test: ❌ 无测试
    risk: "恢复状态查询无测试覆盖"
```

### 9.5 Mock 使用分析

```yaml
mock_analysis:
  heavily_mocked_classes: [ExternalApiClient, KafkaTemplate, S3Client]
  never_mocked: [BackupPolicyRepository, RecoveryService]
  concern: "ExternalApiClient 在 12 个测试中被 mock，建议增加集成测试验证真实交互"
```

---

## 附录 A：分析维度优先级矩阵

| 维度 | 对遗产接管的价值 | 实现难度 | 建议优先级 |
|------|:---:|:---:|:---:|
| 三、接口（API 清单） | ⭐⭐⭐⭐⭐ | ⭐⭐ | **P0** — 接手系统第一件事就是知道有哪些接口 |
| 二、架构（模块边界） | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | **P0** — 了解系统骨架 |
| 五、中间件（DB/缓存/MQ） | ⭐⭐⭐⭐ | ⭐⭐ | **P0** — 运维必知 |
| 七、安全（CVE/密钥） | ⭐⭐⭐⭐ | ⭐⭐⭐ | **P1** — 合规风险 |
| 四、业务（流程/规则） | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | **P1** — 需要深度语义分析 |
| 六、部署（Docker/CICD） | ⭐⭐⭐ | ⭐⭐ | **P1** — 构建部署必知 |
| 一、代码分析（质量/规模） | ⭐⭐⭐ | ⭐⭐ | **P2** — 锦上添花 |
| 八、数据流（请求链路） | ⭐⭐⭐ | ⭐⭐⭐⭐ | **P2** — 需要动态追踪 |
| 九、测试（覆盖率） | ⭐⭐ | ⭐ | **P2** — 快速获取 |

---

## 附录 B：各语言分析能力对照

| 维度 | Java/Spring | Python/FastAPI | Go/Gin | TypeScript/NestJS | C#/.NET | C/C++ |
|------|:---:|:---:|:---:|:---:|:---:|:---:|
| 包结构 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 依赖图 | ✅ import | ✅ import | ✅ import | ✅ import | ✅ using | ✅ #include |
| Spring 注解 | ✅ | — | — | — | — | — |
| REST API | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| JPA Entity | ✅ | ✅ SQLAlchemy | ✅ GORM | ✅ Prisma/TypeORM | ✅ EF | — |
| 消息队列 | ✅ @KafkaListener | — | — | — | — | — |
| 配置分析 | ✅ yml/properties | ✅ pyproject | ✅ go.mod | ✅ package.json | ✅ appsettings | ✅ Makefile |
| CVE 扫描 | ✅ Maven | ✅ pip | ✅ go mod | ✅ npm | ✅ NuGet | — |

> `✅` = 已支持或可快速实现 | `—` = 该语言生态中不适用或无标准模式

---

*文档版本: v0.2 | 生成日期: 2026-06-10 | 项目: legacy-takeover*
