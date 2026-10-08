本文件用于记录每次修改&更新后的不同，以便定位bug或者后续优化。同时列出原项目和最终项目的架构对比。

# Version Update

## 版本编号规则

- `0.x`：聚餐组织 Agent 的历史版本，保留原有编号和记录方式。
- `1.x`：蛋糕订单 / 小微商户订单接待 Agent，从 `1.0` 开始计数。
- 原临时使用的 `0.23` 订单内容，统一整理为 `1.0`。

## 1.6 - 2026-10-07

### 版本说明

本版本把订单接待从“客户确认需求”推进到完整的店主报价、客户确认报价、
定金收取和履约交付流程。管理台也从只读订单列表升级为店主可操作的今日工作台。

### 当前完成内容

1. 增加按日重置的四位订单号
   - 格式为 `10.07-0001`
   - 数据库保留全局 `Order.id`
   - 业务唯一键为 `(business_date, order_number)`
   - 使用数据库原子 upsert 分配每日序号

2. 增加报价工作流
   - 客户下单时保存客户预期价格
   - 店主可以填写最终报价
   - 店主也可以直接接受客户预期价格
   - 每次报价保留版本和完整历史
   - 即使接受客户预期价格，也必须由客户再次确认
   - 客户可以确认报价，也可以拒绝并要求店主重新报价

3. 增加定金规则
   - 取货日期距离下单日期超过 5 个自然日
   - 且最终确认报价高于 200 元
   - 定金为最终报价的 20%
   - 使用 `Decimal` 和高精度字段，不取整
   - 例如 `228 × 20% = 45.6`
   - 店主线下收款后在管理台标记“已收定金”

4. 增加履约状态
   - `collecting`
   - `pending_confirmation`
   - `confirmed`
   - `preparing`
   - `ready`
   - `completed`
   - `cancelled`
   - 无需定金时，客户确认报价后自动进入 `preparing`
   - 需要定金时，店主确认收款后自动进入 `preparing`
   - 店主只需要确认“已收定金”和“蛋糕已做好”

5. 增加客户通知链路
   - 店主报价后通过 `active` Outbox 主动发给客户
   - 客户确认或拒绝报价时通知店主
   - 订单做好、完成等节点继续通过 Outbox 追踪发送状态

6. 升级管理台
   - 今日工作台展示待店主报价、待客户确认价格、待收定金、制作中、可取货和今日完成
   - 20 秒轮询刷新
   - 月历展示每天订单量，点击日期查看当天订单
   - 订单详情展示客户预期价、店主报价、报价历史、定金和履约状态
   - 增加报价、接受预期价、已收定金、已做好和已完成操作

7. 扩展订单 Dify 契约
   - 增加 `customer_expected_price`
   - 增加 `customer_expected_price_text`
   - 增加 `order_reference`
   - 增加 `confirm_quote`
   - 增加 `reject_quote`
   - mock 评测集扩展到 11 条用例

8. 修复多笔报价确认歧义
   - 同一直聊有多笔待确认报价时不再默认确认最新一笔
   - 支持回复 `0006`、`10.07-0006`、`订单号 6`
   - 未指定订单号时返回待确认报价列表

9. 修复管理台旧缓存
   - HTML 和首页禁止缓存
   - 页面标题改为订单 Agent
   - 侧边栏显示 1.6 版本

10. 增加报价沟通备注
   - 店主报价时可以附带给客户的备注
   - 客户拒绝报价或讨价还价时，原话转给店主
   - 客户在报价阶段发送“备注/留言”时转给店主

11. 增加附加字段中文化
   - `candles` 转换为“蜡烛数量”
   - 常见附加要求使用中文保存和展示
   - 历史数据在管理台通过字段映射显示中文

12. 修复报价阶段误取消订单
   - 报价待客户确认时，非明确确认或取消的消息统一视为客户反馈
   - 客户反馈会记录为 `quote_feedback`
   - 店主重新报价前可在订单确认记录中看到客户原话
   - “太贵”“好贵”等议价消息不会被 `cancel_order` 误伤

13. 增加安抚回复
   - 客户议价时回复“小的试着逼店主一把，给您个骨折价，您先消消气哈，小的这就去找店主”

14. 修复相对日期计算
   - 支持“五天后”“三天后”“3天后”
   - 配合下午/上午时间计算完整日期时间

15. 修复新订单复用旧草稿
   - 明确 `create_order` 会创建新订单，不再合并到旧草稿
   - 增加“清除记忆”“清除记录”“删除记录”等上下文重置命令
   - 清理旧草稿后重新开始收集

16. 修复红丝绒套盒表达
   - 保留“红丝绒”口味
   - 将 `pieces_per_box` 转换为“规格：一套四个”
   - 小蛋糕产品名保留为“红丝绒小蛋糕”

17. 增加取消订单后的恢复和店主留言
   - 店主可在已取消订单详情中向客户发送留言
   - 客户带订单号询问已取消订单时，机器人提示恢复或修改
   - 明确“恢复订单”会恢复订单状态
   - 明确“修改订单”会重新打开订单，等待客户补充备注或规格

18. 增加无关问题兜底话术
   - 无相关订单上下文时回复蛋糕店引导语

19. 增加无意义商品拦截
   - 拦截“混凝土蛋糕”“水泥蛋糕”等明显不符合常识的需求
   - 在进入 Dify 前完成本地判断，避免生成错误订单
   - 统一使用蛋糕店兜底话术回复

20. 移除旧聚餐业务入口并清理历史数据
   - 管理台移除“活动”导航和活动页面
   - 新增 scripts/cleanup_legacy_data.py
   - 清理 6 条没有订单号的旧订单
   - 清理旧聚餐活动、参与者、方案、投票和活动 Outbox

21. 修复报价确认和菜单优先级
   - 统一使用一套报价确认判断，修复“报价可以”被覆盖的问题
   - “接受不了”“不太能接受”等否定表达统一判为拒绝
   - 带“你好”的确认、取消、恢复、修改等操作不再被菜单回复打断
   - 补充“帮我做一个蛋糕”等新订单表达
   - 避免“南极路”等真实地址被误判为不可配送

### 本次主要变化

- 修改 models.py、schemas/order.py、schemas/activity.py
- 修改 services/orders.py、services/order_flow.py、services/admin.py
- 修改 services/order_requirements.py、clients/dify.py
- 新增 migrations/versions/2a3b4c5d6e7f_add_quote_workflow.py
- 新增 tests/test_order_quote_flow.py
- 扩展 tests/test_order_flow.py、test_order_state_machine.py、test_wecom_aibot.py
- 新增前端 OrderCalendar.tsx 和 OrderActions.tsx
- 更新 Nginx 首页缓存策略
- 更新 README 和订单 Dify 文档

### 验证结果

- 后端全量测试通过
- Alembic upgrade head 和 downgrade base 通过
- 订单 Dify mock 评测 11/11 通过
- 前端 TypeScript 检查和 Vite 生产构建通过

### 后续计划

1. 将本地 Dify Workflow 更新到 1.6 输出契约并跑真实模型评测
2. 用真实企业微信客户和店主账号验证报价、定金、取货通知
3. 增加管理台操作审计和权限方案
4. 后续再接入微信支付或更完整的收款状态

## 1.5 - 2026-10-06

### 版本说明

本版本完善客户下单体验和店主通知信息：补充相对日期、询问蛋糕留言/备注，并允许客户私聊机器人下单。

### 当前完成内容

1. 增加当前时间上下文
   - 增加 APP_TIMEZONE，默认 Asia/Hong_Kong
   - 识别今天、明天、后天、大后天
   - 识别周几并计算对应日期
   - 通知店主前把“今天下午五点”补充为“(10.6)今天下午五点”

2. 增加蛋糕留言/备注询问
   - 基本信息完整后生成确认文本
   - 确认文本中间询问是否需要蛋糕留言或备注
   - 客户可以继续补充，也可以直接确认下单

3. 支持客户私聊机器人
   - 单聊消息不再要求 @ 机器人
   - 群聊仍然要求 @ 机器人
   - 客户可以私聊 Bot 完成下单和确认

4. 明确客户侧和店主侧
   - Bot 面向客户，负责接待、追问和确认
   - 自建应用面向店主，负责订单通知和后续管理入口

### 本次主要变化

- 修改 services/order_requirements.py
- 修改 services/dify.py
- 修改 services/wecom_aibot.py
- 修改 config.py、.env.example 和 docker-compose.yml
- 新增 tests/test_order_requirements.py
- 扩展 tests/test_order_dify_mock.py 和 tests/test_wecom_aibot.py
- 更新 README 和订单 Dify 文档

## 1.4 - 2026-10-05

### 版本说明

本版本把客户姓名和联系电话提升为蛋糕订单必填字段，避免订单确认后无法联系客户。

### 当前完成内容

1. 扩展蛋糕订单必填字段
   - customer_name
   - phone
   - product_name
   - quantity
   - size
   - flavor
   - pickup_time

2. 完善 mock 字段抽取
   - 支持“我叫张三”
   - 支持“姓名是张三”
   - 支持“我是张三”
   - 支持 11 位手机号

3. 完善追问和确认文本
   - 缺少姓名时询问客户姓名
   - 缺少电话时询问联系电话
   - 确认文本包含客户姓名和电话

### 本次主要变化

- 修改 services/order_requirements.py
- 修改 clients/dify.py
- 修改 tests/test_order_dify_mock.py
- 修改 tests/test_order_flow.py
- 修改 tests/test_wecom_aibot.py
- 修改 docs/order-dify-test-cases.json
- 修改 docs/order-dify-workflow.md

## 1.3 - 2026-10-05

### 版本说明

本版本修补订单外部发送策略。企业微信智能机器人主动单聊持续返回 `846607` 时，不再只依赖 aibot active send，而是按可配置通道回退。

### 当前完成内容

1. 增加订单通知通道配置
   - `ORDER_NOTIFICATION_CHANNEL=auto`
   - 支持 `app`、`webhook`、`active`
   - `auto` 优先自建应用 API，其次群 Webhook，最后智能机器人主动单聊

2. 扩展 worker 分发策略
   - `app` 通过自建应用 `message/send`
   - `webhook` 通过群机器人 Webhook
   - `active` 通过智能机器人 `send_message`
   - `reply` 仍使用原始回调 frame，不进入后台重试

3. 失败通知切换通道
   - 历史失败通知可以改为 `dispatch_channel=app`
   - worker 后台重试按通道重新发送
   - 避免继续被 aibot active send 的 `846607` 卡死

### 本次主要变化

- 修改 config.py 和 .env.example
- 修改 docker-compose.yml
- 修改 services/order_flow.py
- 修改 services/outbox.py
- 修改 services/wecom_aibot.py
- 修改 tests/test_order_flow.py
- 修改 tests/test_wecom_aibot.py

### 验证结果

- 后端全量测试通过
- worker 通道分发单元测试通过

## 1.2 - 2026-10-04

### 版本说明

本版本增加 Outbox 主动消息重试能力，解决企业微信智能机器人主动发送触发 `846607 aibot send msg frequency limit exceeded` 后店主通知无法送达的问题。

### 当前完成内容

1. 扩展 Outbox 发送语义
   - `dispatch_channel=reply`：必须依赖原始回调 frame 回复
   - `dispatch_channel=active`：可通过长连接主动 `send_message`
   - 增加 `next_attempt_at`，记录下一次重试时间

2. 增加失败退避
   - 频率限制 `846607` 默认 30 秒起退避
   - 其他发送失败默认 10 秒起退避
   - 指数退避，最大 300 秒
   - 达到最大重试次数后标记为 failed

3. 增加 worker 后台重试
   - worker 启动后周期性扫描待重试的 active Outbox
   - 等待 WebSocket 认证完成后再启动重试循环
   - 通过同一条企业微信智能机器人长连接重新发送
   - 成功后标记 sent
   - 失败后更新 retry_count、last_error 和 next_attempt_at
   - 店主通知单独使用最多 10 次重试

4. 数据迁移
   - 新增 `dispatch_channel`
   - 新增 `next_attempt_at`
   - 把历史“新订单已确认”和“客户取消订单”通知回填为 active

### 本次主要变化

- 修改 models.py
- 修改 schemas/activity.py
- 修改 services/outbox.py
- 修改 services/order_flow.py
- 修改 services/wecom_aibot.py
- 修改 tests/test_outbox.py
- 修改 tests/test_wecom_aibot.py
- 新增 migrations/versions/8d4e5f6a7b8c_add_outbox_retry.py

### 验证结果

- 后端全量测试：`69 passed`
- Alembic upgrade head 通过
- Alembic downgrade base 通过

## 1.1 - 2026-10-04

### 版本说明

本版本完成蛋糕订单 Agent 的 Docker 资源改名和生产运行配置收敛，把原先沿用聚餐时期的 `dinner` 命名统一迁移到 `cake`，同时保留 PostgreSQL 数据。

### 当前完成内容

1. Docker 项目改名
   - Compose project：`wecom-dinner-agent` -> `wecom-cake-agent`
   - 容器：`wecom-cake-agent-app/web/db/aibot-worker-1`
   - 镜像：`wecom-cake-agent-app/web/aibot-worker`
   - 网络：`wecom-cake-agent_default`
   - 数据卷：`wecom-cake-agent_postgres_data`

2. PostgreSQL 数据迁移
   - 数据库名：`wecom_dinner` -> `wecom_cake`
   - 旧卷数据复制到新卷
   - 新服务验证旧消息、活动和投票数据仍存在
   - 验证后删除旧 dinner 容器、网络、镜像和数据卷

3. 运行配置修复
   - app 和 worker 补齐订单 Dify 配置
   - app 和 worker 补齐智能机器人配置
   - app 和 worker 补齐 `WECOM_OWNER_USER_ID`
   - 增加 `AGENT_SCENARIO=order`

4. 命名和应用标识更新
   - Python 包名改为 `wecom-cake-agent`
   - 应用健康检查名称改为 `wecom-cake-agent`
   - 前端包名改为 `wecom-cake-admin`
   - 文档和调试脚本统一使用 cake 命名

### 验证结果

- 后端全量测试：`67 passed`
- `wecom-cake-agent` 容器全部运行
- `app` 健康检查返回 `wecom-cake-agent`
- PostgreSQL 旧业务数据保留
- 只保留 `wecom-cake-agent_postgres_data` 数据卷

## 1.0 - 2026-10-04

### 版本说明

本版本在原有企业微信接入层、Dify、SQLAlchemy、Outbox、长连接 worker、React 管理台和 Docker 的基础上，完成一次业务方向调整，而不是重做接入层。

### 业务方向变化

- 项目从“企业微信群聚餐组织 Agent”扩展为“面向小微商户的企业微信订单接待 Agent”。
- 第一个正式落地场景为蛋糕店订单确认。
- 聚餐业务不再作为主场景，但保留为 `AGENT_SCENARIO=dinner` 的兼容模式。
- 订单业务不只为蛋糕店设计，而是使用通用订单骨架，后续可以扩展花店、维修店、蛋糕定制、打印店等类似场景。
- 业务目标从“群内讨论和投票”转为“客户需求收集、订单确认、店主通知和订单管理”。

### 架构变化

原有技术栈保持不变：

- FastAPI 负责 API、业务服务和状态机。
- Dify 负责自然语言意图识别和字段抽取。
- SQLAlchemy + Alembic 负责订单持久化和迁移。
- Outbox 负责客户回复和店主通知的可追踪发送。
- 企业微信智能机器人长连接负责接收群聊/单聊消息。
- React + TypeScript 管理台负责订单查看。
- Docker Compose 负责生产部署。

新增的核心架构变化：

```text
企业微信智能机器人长连接
  -> frame 标准化
  -> AGENT_SCENARIO 路由
  -> order_flow
  -> Dify 订单意图与字段抽取
  -> order_requirements 本地缺失字段判断
  -> Order 状态机
  -> Outbox
       -> 客户回复
       -> 店主通知
  -> React 订单管理台
```

- 增加 `scenario` 字段和 `requirements` JSON，避免每增加一个行业就重做订单表。
- 增加 `Customer`、`Order`、`OrderConfirmation` 三张核心业务表。
- 增加订单状态机，明确 `collecting`、`pending_confirmation`、`confirmed`、`cancelled` 的流转边界。
- 将订单 Dify 配置与聚餐 Dify 配置解耦，支持 `mock`、`real` 和 `auto`。
- 增加长连接订单模式，worker 同时负责客户回复和店主通知。
- 增加订单管理接口和管理台视图。

| 维度 | 0.22 聚餐 Agent | 0.23 订单 Agent |
| --- | --- | --- |
| 主业务 | 群聚餐组织、方案和投票 | 客户订单接待和确认 |
| 消息路由 | 固定聚餐流程 | `AGENT_SCENARIO` 路由 order/dinner |
| 核心模型 | DinnerActivity、Participant、Vote | Customer、Order、OrderConfirmation |
| 场景扩展 | 聚餐字段固定 | `scenario + requirements JSON` |
| Dify | 聚餐 Workflow 为主 | 订单 Workflow 独立配置 |
| 发送链路 | 客户回复/提醒为主 | 客户回复 + 店主通知 |
| 管理台 | 活动和消息 | 订单列表、订单详情、确认记录和活动兼容 |

### 当前完成内容

1. 设计订单领域模型
   - Customer 客户模型
   - Order 通用订单模型
   - OrderConfirmation 订单确认记录
   - scenario 区分 cake、flower、repair 等业务场景
   - requirements 使用 JSON 保存场景差异化字段

2. 实现订单状态机
   - collecting -> pending_confirmation -> confirmed
   - collecting -> cancelled
   - pending_confirmation -> cancelled
   - confirmed 和 cancelled 为终态

3. 增加数据库迁移
   - 新增 customers、orders、order_confirmations 三张表
   - 增加订单状态、场景和关联索引
   - 验证 upgrade head 和 downgrade base

4. 增加订单 Dify 输出模型
   - create_order
   - provide_requirement
   - update_requirement
   - confirm_order
   - cancel_order
   - unknown

5. 增加订单字段抽取和缺失字段判断
   - 蛋糕场景支持商品、数量、尺寸、口味、留言、取货/配送时间、地址、电话和预算
   - 本地按场景字段规则判断缺失项
   - 缺失字段生成逐项追问

6. 增加订单确认文本
   - 字段完整后生成订单确认文本
   - 提示客户回复“确认下单”
   - mock Dify 支持订单意图和字段抽取

7. 增加订单会话流程
   - create_order 创建订单
   - provide_requirement 合并字段
   - update_requirement 修改字段
   - confirm_order 写入 confirmed 状态和确认记录
   - cancel_order 写入 cancelled 状态

8. 增加店主通知 Outbox
   - 客户确认订单后创建店主通知 Outbox
   - 店主目标使用 WECOM_OWNER_USER_ID
   - 通知内容包含完整订单快照

9. 接入企业微信长连接 worker
   - 增加 AGENT_SCENARIO 配置
   - order 模式走订单会话流程
   - dinner 模式保留原聚餐流程
   - 客户回复通过原始回调 frame 发送
   - 店主通知通过长连接 send_message 发送

10. 增加订单管理台
   - 新增订单列表和订单详情接口
   - 总览增加订单统计
   - React 管理台增加订单视图
   - 展示订单字段、待补充字段和确认记录

11. 拆分订单 Dify 配置
   - ORDER_DIFY_MODE=auto 优先复用通用 Dify Key
   - ORDER_DIFY_MODE=mock 使用本地规则解析
   - ORDER_DIFY_MODE=real 使用独立订单 Workflow
   - 增加 DIFY_ORDER_API_BASE、DIFY_ORDER_API_KEY
   - 增加订单 Dify 配置状态展示
   - 增加 docs/order-dify-workflow.md 提示词和输出规范

12. 增加订单 Dify 评测
   - 增加 docs/order-dify-test-cases.json
   - 增加 scripts/evaluate_order_dify_cases.py
   - mock 模式 7/7 用例通过
   - 真实 wecom-cake Workflow 7/7 用例通过
   - 支持 auto 模式复用 DIFY_API_KEY

13. 完成订单生产验证
   - 真实 Dify HttpDifyClient 联调通过
   - 订单字段归一化处理
   - unknown 意图不再被说明性 notes 误覆盖
   - 后端全量测试 67 passed
   - app、web、aibot-worker Docker 镜像构建通过

14. 完善说明文档
   - README 更新为订单 Agent 当前定位
   - 增加订单 Dify Workflow 配置文档
   - 增加订单 Dify 评测用例
   - 补充长连接、订单模式和店主通知说明

### 本次代码与文件变动

- 修改 models.py
- 新增 services/orders.py
- 新增 services/order_requirements.py
- 新增 services/order_flow.py
- 新增 tests/test_order_state_machine.py
- 新增 tests/test_order_dify_mock.py
- 新增 tests/test_order_flow.py
- 修改 schemas/dify.py
- 修改 clients/dify.py
- 修改 services/dify.py
- 修改 services/wecom_aibot.py
- 修改 api/admin.py
- 修改 services/admin.py
- 修改 schemas/activity.py
- 新增 schemas/order.py
- 修改 apps/admin-web 订单视图和类型
- 新增 docs/order-dify-workflow.md
- 新增 docs/order-dify-test-cases.json
- 新增 scripts/evaluate_order_dify_cases.py
- 新增 scripts/create_wecom_group.py
- 新增 migrations/versions/7a1c2b3d4e5f_add_order_domain.py

### 以后的方向

1. 使用真实企业微信完成蛋糕订单端到端联调，覆盖下单、追问、确认、店主通知和订单查询。
2. 增加店主通知失败重试、发送状态查看和人工补发。
3. 增加订单操作按钮，支持人工修改字段、重新确认和取消订单。
4. 增加订单完成、取货提醒、归档和简单经营统计。
5. 抽象第二和第三个场景，优先验证花店订单和维修预约。
6. 将订单字段规则从代码常量逐步配置化，支持不同商户自定义必填字段。
7. 增加多商户、多门店、权限和审计能力，为后续真实生产使用做准备。
8. 增加日志、指标、告警和发送回执，提升可观测性和可靠性。

## 0.22 - 2026-10-03

### 版本说明

本版本进入企业微信真实环境联调，按小步骤推进，先强化回调接收边界，避免真实消息格式导致接口报错和被企微重试。

### 当前完成内容

1. 回调消息兼容事件与非文本类型
   - 企业微信回调中的 event 消息直接确认，不进入 Dify
   - 图片、语音等非文本消息直接确认，不进入业务状态机
   - 只有 text 消息继续走消息幂等、Dify 和聚餐流程

2. 增加自建应用发送调试脚本
   - token：获取并脱敏显示 access_token
   - send：向群聊或单聊发送测试消息
   - 群聊 target 使用 chat_id
   - 单聊 target 使用 direct-{user_id}

3. 增加公网 HTTPS 隧道启动脚本
   - 优先使用 cloudflared
   - 其次使用 ngrok
   - 用于本地真实回调联调

4. 改进单聊自然语言流程
   - 没有活动时，直接提供时间、口味、预算会先自动创建活动
   - 随后继续把该消息记录为发起人的偏好
   - 避免单聊首次说“周六晚上我想吃火锅”被直接拒绝

5. 明确企业微信群聊能力边界
   - 自建应用回调可以接收单聊消息
   - 普通群聊消息不会默认推送到自建应用回调
   - 群聊实时接收需要智能机器人长连接或会话内容存档
   - 文档补充企业可信 IP 的 60020 和无效 chatid 的 86001 排查

6. 增加智能机器人长连接接入
   - 增加 wecom-aibot-sdk 依赖
   - 增加 WECOM_AIBOT_ID、WECOM_AIBOT_SECRET、WECOM_AIBOT_WS_URL、WECOM_AIBOT_NAME
   - 增加 frame 标准化和长连接 worker
   - 长连接消息复用现有 Dify、活动和 Outbox 流程
   - worker 使用原始 frame 回复，支持群聊实时消息
   - 默认只处理 @ 机器人消息，避免普通群聊被误触发

7. 修复群聊生成方案没有返回方案内容
   - 生成方案后直接回复 1/2/3 方案列表
   - 生成后自动进入 voting 状态
   - 用户可以直接回复“我选1”完成投票

8. 增加投票汇总和最终确认
   - 支持“总结”“汇总”“整理一下”等本地命令
   - 返回每个方案的票数和当前领先方案
   - 支持“确认方案”后生成最终确认结果
   - 阻止“另一个成员选3”被错误记成发言人的投票

9. 修复其他成员首次投票失败
   - 新成员回复“我选择方案一”“我选1”时先自动加入活动
   - 加入成功后继续记录投票
   - 解决 active participant not found 导致的新成员投票失败

### 本次主要变化

- 修改 services/wecom_callback.py
- 修改 api/wecom_callback.py
- 修改 clients/wecom.py
- 修改 services/processing.py
- 新增 scripts/debug_wecom_sender.py
- 新增 scripts/start_wecom_tunnel.ps1
- 新增 scripts/run_wecom_aibot_worker.py
- 新增 services/wecom_aibot.py
- 新增 tests/test_wecom_aibot.py
- 扩展 tests/test_proposals.py
- 修改 services/proposals.py 和 services/processing.py
- 扩展 tests/test_wecom_callback.py
- 扩展 tests/test_preference_extraction.py
- 更新 README 和 docs/wecom-integration-checklist.md

### 后续计划

1. 配置真实智能机器人凭据并完成群消息联调
2. 增加长连接心跳和 worker 状态展示
3. 记录真实企业微信联调结果
4. 处理 Dify 耗时、长连接回复超时和失败重试

## 0.2 - 2026-09-28

### 版本说明

这是重新从零搭建的第二版，因此版本号从 0.2 开始记录。项目定位为企业微信群聊聚餐组织 Agent，目标是学习 Agent 项目开发，同时保留企业项目的工程边界。

### 当前完成内容

1. 初始化项目骨架
   - 创建 Git 仓库并配置 GitHub 远端
   - 添加 README、.gitignore、.env.example

2. FastAPI 基础服务
   - 使用 FastAPI 创建应用入口
   - 增加 /health 健康检查
   - 使用 pydantic-settings 管理环境配置
   - 使用 pytest 添加基础测试

3. Mock 企业微信消息接入
   - 增加 POST /wecom/messages 消息接收接口
   - 定义企微消息请求和响应结构
   - 使用 SQLAlchemy 将消息持久化到 SQLite
   - 按 wecom_msg_id 实现消息幂等去重
   - 对并发写入导致的唯一约束冲突做回滚处理

### 当前技术栈

- Python 3.14
- FastAPI
- Pydantic v2
- pydantic-settings
- SQLAlchemy 2
- SQLite
- pytest
- uvicorn

### 当前架构

```text
HTTP 请求
  -> API 路由层
  -> Pydantic 校验层
  -> Service 业务层
  -> SQLAlchemy Model 层
  -> SQLite 数据库
```

```text
src/app/
├── main.py
├── config.py
├── db.py
├── models.py
├── api/
│   └── wecom.py
├── schemas/
│   └── wecom.py
└── services/
    └── inbound.py
```

### 当前请求链路

```text
POST /wecom/messages
  -> schemas/wecom.py 校验请求
  -> services/inbound.py 查询 wecom_msg_id
  -> 不存在则写入 inbound_messages
  -> 已存在则返回 duplicate=true
```

### 关键设计决策

- 当前使用 SQLite 和单进程服务，适合本地开发与 mock 演示。
- 后续进入 Outbox、真实企微接入或并发写入阶段时，再切换到 PostgreSQL。
- Dify 负责意图识别、信息抽取和方案生成，FastAPI 负责状态机和数据持久化。
- 当前只做一个垂直场景：单群、单活动、文本消息的聚餐组织。
- 原项目 wecom-mind 仅作为工程边界和模块设计的参考答案，不直接复制。

### 原项目与最终项目架构对比

| 模块 | wecom-mind 原项目 | 本项目的预期最终版本 |
| --- | --- | --- |
| 消息入口 | 企微长连接 + MCP 历史补漏 | 企微官方回调或长连接 + mock 适配器 |
| 消息处理 | 标准化、幂等、任务触发 | 标准化、幂等、意图路由、活动状态机 |
| 数据库 | SQLAlchemy 业务数据库 | PostgreSQL + SQLAlchemy 2 + Alembic |
| Agent 编排 | Dify 知识问答与分析 | Dify Workflow，支持真实和 mock 模式 |
| 输出校验 | Pydantic 校验 Dify 返回结果 | Pydantic Schema + 领域状态校验 |
| 发送链路 | Outbox + 发送状态与回执 | Outbox + pending/sent/failed + 重试 |
| 会话记忆 | 会话切分、用户画像 | 活动上下文 + 参与者偏好缓存 |
| 管理后台 | React 管理后台 | React + TypeScript + Ant Design |

### 后续计划

1. 增加 Dify mock 适配层
2. 校验 Dify 返回的结构化 JSON
3. 实现聚餐活动状态机
4. 增加参与者偏好和候选方案
5. 实现投票和最终方案确认
6. 增加 Outbox 发送链路
7. 增加活动提醒
8. 增加简单的管理查询或后台

## 0.3 - 2026-09-28

### 当前完成内容

1. 增加 Dify 客户端边界
   - 定义 DifyClient 抽象接口
   - 实现 MockDifyClient
   - 根据配置选择 mock 或真实客户端

2. 增加 Dify 结构化输出
   - 定义 DifyWorkflowResult
   - 定义 DinnerDifyOutput
   - 对 Dify 返回结果进行 Pydantic 校验

3. 接入消息处理流程
   - 消息首次入库后调用 Dify 分析
   - 重复消息不重复调用 Dify
   - Dify 解析失败时返回 dify_error

### 本次主要变化

- API 响应增加 analysis 和 dify_error 字段
- 新增 clients/dify.py
- 新增 schemas/dify.py
- 新增 services/dify.py
- 新增 services/processing.py

### 当前请求链路

```text
POST /wecom/messages
  -> 幂等入库
  -> 首次消息调用 Dify mock
  -> Pydantic 校验 Dify 输出
  -> 返回 analysis 或 dify_error
```

### 后续计划

1. 实现真实 Dify HTTP 客户端
2. 实现聚餐活动状态机
3. 增加参与者偏好和候选方案
4. 实现投票和最终方案确认

## 0.4 - 2026-09-28

### 当前完成内容

1. 增加聚餐活动模型
   - 新增 DinnerActivity 数据表
   - 记录群组、发起人、标题、状态、时间等信息
   - 支持 updated_at 自动更新

2. 增加活动状态机
   - collecting -> proposing -> voting -> confirmed -> completed
   - 支持取消状态
   - 非法状态流转返回 409

3. 接入消息创建活动
   - create_dinner 识别结果会创建活动
   - 同一群组只保留一个进行中的活动
   - 消息响应增加 activity 字段

4. 增加活动接口
   - GET /activities/{group_id}/active
   - POST /activities/{activity_id}/transition

### 本次主要变化

- 新增 models.DinnerActivity
- 新增 schemas/activity.py
- 新增 services/activities.py
- 新增 api/activities.py
- 消息处理流程增加活动创建

### 后续计划

1. 增加参与者模型和加入退出功能
2. 收集参与者偏好
3. 生成候选方案
4. 实现投票与最终方案确认
5. 增加 Outbox 发送链路

## 0.5 - 2026-09-28

### 当前完成内容

1. 增加参与者模型
   - 新增 ActivityParticipant 数据表
   - 同一活动内用户唯一
   - 支持加入时间和退出时间

2. 活动创建时自动加入发起人
   - 发起人作为首个参与者写入
   - 活动与参与者保持关联

3. 增加参与者接口
   - POST /activities/{activity_id}/participants
   - GET /activities/{activity_id}/participants
   - PUT /activities/{activity_id}/participants/{user_id}
   - POST /activities/{activity_id}/participants/{user_id}/leave

4. 支持参与者偏好
   - 可记录可参加时间
   - 可记录口味偏好
   - 可记录预算上限
   - 可记录备注

### 本次主要变化

- 新增 models.ActivityParticipant
- 新增 services/participants.py
- 新增 api/participants.py
- 活动创建逻辑增加发起人写入

### 后续计划

1. 从自然语言消息中自动抽取参与者偏好
2. 生成候选方案
3. 实现投票与最终方案确认
4. 增加 Outbox 发送链路
5. 增加活动提醒

## 0.6 - 2026-09-29

### 当前完成内容

1. 扩展 Dify mock 意图识别
   - 支持 create_dinner
   - 支持 provide_preference
   - 支持 unknown

2. 增加自然语言偏好抽取
   - 抽取可参加时间
   - 抽取口味偏好
   - 抽取预算上限
   - 抽取忌口备注

3. 偏好自动更新参与者
   - 有活动进行中时，按 sender_id 更新对应参与者
   - 参与者不存在时自动加入
   - 消息响应增加 participant 字段

### 本次主要变化

- 扩展 clients/dify.py
- 扩展 schemas/dify.py
- 新增 services/participants.apply_preferences_from_message
- 消息处理流程增加偏好分支

### 后续计划

1. 生成候选方案
2. 实现投票与最终方案确认
3. 增加 Outbox 发送链路
4. 增加活动提醒
5. 增加真实 Dify HTTP 客户端

## 0.7 - 2026-09-29

### 当前完成内容

1. 增加候选方案模型
   - 新增 DinnerProposal 数据表
   - 根据参与者时间、口味和预算生成方案
   - 默认生成三个候选方案

2. 增加投票模型
   - 新增 Vote 数据表
   - 同一用户在同一活动内只能保留一条投票
   - 重复投票会更新原选择

3. 扩展 Dify mock
   - 支持 generate_proposals
   - 支持 vote
   - 支持从“我选 2”中抽取方案编号

4. 增加方案与投票接口
   - POST /activities/{activity_id}/generate-proposals
   - GET /activities/{activity_id}/proposals
   - POST /activities/{activity_id}/start-voting
   - POST /activities/{activity_id}/votes
   - POST /activities/{activity_id}/confirm

5. 接入自然语言流程
   - “生成方案”自动生成候选方案
   - “我选 1”自动记录投票
   - 确认接口根据票数选择最终方案

### 本次主要变化

- 新增 models.DinnerProposal
- 新增 models.Vote
- 新增 services/proposals.py
- 新增 api/proposals.py
- 扩展 Dify mock 和消息处理流程

### 后续计划

1. 增加 Outbox 发送与回复
2. 增加活动提醒
3. 增加真实 Dify HTTP 客户端
4. 增加管理查询或后台
5. PostgreSQL + Alembic + Docker Compose

## 0.8 - 2026-09-30

### 当前完成内容

1. 增加 Outbox 模型
   - 新增 OutboxMessage 数据表
   - 支持 pending、sent、failed 状态
   - 记录重试次数、错误信息、发送时间和 provider 消息 ID

2. 增加企微发送客户端
   - 定义 WeComSender 抽象接口
   - 实现 MockWeComSender
   - 根据 wecom_sender_mode 选择发送客户端

3. 接入机器人回复
   - 消息处理成功后自动创建 Outbox 记录
   - 重复消息不会重复创建回复
   - 业务错误会回复固定提示

4. 增加 Outbox 管理接口
   - POST /outbox
   - GET /outbox
   - POST /outbox/{message_id}/dispatch
   - POST /outbox/dispatch-pending
   - POST /outbox/{message_id}/retry

### 本次主要变化

- 新增 models.OutboxMessage
- 新增 clients/wecom.py
- 新增 services/outbox.py
- 新增 api/outbox.py
- 消息响应增加 outbox 字段

### 后续计划

1. 增加活动提醒
2. 增加真实企微发送客户端
3. 增加真实 Dify HTTP 客户端
4. 增加管理查询或后台
5. PostgreSQL + Alembic + Docker Compose

## 0.9 - 2026-09-30

### 当前完成内容

1. 增加提醒模型
   - 新增 Reminder 数据表
   - 支持 pending、sent、failed、cancelled 状态
   - 记录提醒类型、计划时间、发送时间和错误

2. 增加 APScheduler 调度器
   - 开发环境按固定间隔扫描到期提醒
   - 测试环境不启动后台线程
   - 应用退出时停止调度器

3. 提醒通过 Outbox 发送
   - 到期提醒创建 Outbox 记录
   - 复用发送、失败和重试机制
   - 提醒发送结果回写 Reminder

4. 增加默认提醒计划
   - 投票截止前提醒
   - 活动开始前提醒

5. 增加提醒接口
   - POST /activities/{activity_id}/reminders
   - GET /activities/{activity_id}/reminders
   - POST /activities/{activity_id}/schedule-reminders
   - POST /reminders/dispatch-due
   - POST /reminders/{reminder_id}/cancel

### 本次主要变化

- 新增 models.Reminder
- 新增 services/reminders.py
- 新增 scheduler.py
- 新增 api/reminders.py
- 配置增加 reminder_scheduler_enabled 和 reminder_poll_seconds

### 后续计划

1. 增加真实 Dify HTTP 客户端
2. 增加真实企微发送客户端
3. 增加管理查询或后台
4. PostgreSQL + Alembic + Docker Compose

## 0.10 - 2026-09-30

### 当前完成内容

1. 增加真实 Dify 客户端
   - 实现 HttpDifyClient
   - 调用 Dify Workflow blocking API
   - 解析 data.outputs

2. 增加客户端模式切换
   - mock 模式继续使用 MockDifyClient
   - real 或 http 模式使用 HttpDifyClient
   - 缺少 API 地址或 Key 时给出明确错误

3. 增加配置项
   - DIFY_USER
   - DIFY_TIMEOUT_SECONDS

4. 增加 HTTP 客户端测试
   - 成功返回结构化 outputs
   - HTTP 失败时返回错误结果

### 本次主要变化

- 扩展 clients/dify.py
- 扩展 config.py 和 .env.example
- 新增 tests/test_dify_http.py
- README 增加真实 Dify 接入说明

### 后续计划

1. 增加真实企微发送客户端
2. 增加管理查询或后台
3. PostgreSQL + Alembic + Docker Compose
4. 增加端到端演示脚本

## 0.11 - 2026-09-30

### 当前完成内容

1. 增加企业微信 Webhook 发送客户端
   - 实现 WebhookWeComSender
   - 发送 text 类型群消息
   - 解析企业微信 errcode 和 errmsg

2. 增加发送模式切换
   - mock 模式使用 MockWeComSender
   - webhook 或 real 模式使用 WebhookWeComSender
   - 缺少 Webhook URL 时给出明确错误

3. 增加配置项
   - WECOM_WEBHOOK_URL
   - WECOM_SENDER_TIMEOUT_SECONDS

4. 增加 Webhook 测试
   - 校验 POST 请求体和地址
   - 校验企业微信错误码处理

### 本次主要变化

- 扩展 clients/wecom.py
- 扩展 config.py 和 .env.example
- 新增 tests/test_wecom_webhook.py
- README 增加企业微信发送接入说明

### 后续计划

1. 增加管理查询或后台
2. PostgreSQL + Alembic + Docker Compose
3. 增加端到端演示脚本
4. 接入企业微信智能机器人或自建应用回调

## 0.12 - 2026-09-30

### 当前完成内容

1. 增加管理总览
   - 活动总数和进行中活动数
   - 消息、参与者、方案和投票数量
   - Outbox 和提醒状态数量

2. 增加活动详情聚合
   - 活动基本信息
   - 参与者和偏好
   - 候选方案和投票
   - Outbox 消息
   - 提醒计划

3. 增加消息查询
   - 按群组过滤
   - 支持分页

4. 增加管理鉴权
   - 默认本地开放
   - 配置 ADMIN_API_KEY 后要求 X-Admin-Key

5. 增加管理接口
   - GET /admin/overview
   - GET /admin/activities
   - GET /admin/activities/{activity_id}
   - GET /admin/messages

### 本次主要变化

- 新增 services/admin.py
- 新增 api/admin.py
- 扩展 Outbox 查询支持 activity_id
- 配置增加 admin_api_key

### 后续计划

1. PostgreSQL + Alembic + Docker Compose
2. 增加端到端演示脚本
3. 接入企业微信智能机器人或自建应用回调
4. 增加简单管理前端

## 0.13 - 2026-09-30

### 当前完成内容

1. 接入 PostgreSQL
   - 增加 psycopg 驱动
   - 支持 postgresql+psycopg 连接串
   - 本地仍默认使用 SQLite

2. 接入 Alembic
   - 增加 alembic.ini
   - 增加 migrations/env.py
   - 生成初始数据库迁移
   - 验证 alembic upgrade head 可独立建表

3. 增加数据库初始化开关
   - AUTO_CREATE_TABLES=true 时保持本地自动建表
   - 容器环境设置为 false，由 Alembic 管理结构

4. 增加 Docker 部署
   - Dockerfile
   - docker-compose.yml
   - PostgreSQL healthcheck
   - 应用启动前执行数据库迁移
   - .dockerignore

### 本次主要变化

- pyproject.toml 增加 alembic 和 psycopg
- 新增 migrations 目录和初始迁移
- 新增 Dockerfile 和 docker-compose.yml
- README 增加数据库迁移和 Docker 使用说明

### 后续计划

1. 增加端到端演示脚本
2. 接入企业微信智能机器人或自建应用回调
3. 增加简单管理前端
4. 增加部署配置示例和运行文档

## 0.14 - 2026-09-30

### 当前完成内容

1. 增加端到端演示脚本
   - 健康检查
   - 创建活动
   - 收集偏好
   - 生成方案
   - 开始投票
   - 成员投票
   - 确认最终方案
   - 创建并发送提醒
   - 查询管理详情

2. 修复投票序号映射
   - “我选 1”不再直接当作全局 proposal_id
   - 按当前活动的方案顺序映射真实 proposal_id
   - 增加历史数据场景测试

3. 增加演示输出
   - 打印候选方案
   - 打印最终方案
   - 打印 Outbox 状态
   - 打印提醒状态

### 本次主要变化

- 新增 scripts/demo_dinner_flow.py
- 扩展 tests/test_proposals.py
- README 增加端到端演示说明

### 后续计划

1. 接入企业微信智能机器人或自建应用回调
2. 增加简单管理前端
3. 增加部署配置示例和运行文档
4. 增加真实环境联调检查清单

## 0.15 - 2026-09-30

### 当前完成内容

1. 增加企业微信回调加密模块
   - SHA1 签名校验
   - AES-256-CBC 解密
   - AES-256-CBC 加密
   - EncodingAESKey 和 corp_id 校验

2. 增加企业微信回调接口
   - GET /wecom/callback 验证 URL
   - POST /wecom/callback 接收消息
   - 解析 text 消息 XML
   - 复用现有消息处理和 Outbox 链路

3. 增加回调配置
   - WECOM_CORP_ID
   - WECOM_CALLBACK_TOKEN
   - WECOM_ENCODING_AES_KEY

4. 增加回调测试
   - 加解密往返测试
   - URL 验证测试
   - 加密消息创建活动测试

### 本次主要变化

- 新增 clients/wecom_crypto.py
- 新增 services/wecom_callback.py
- 新增 api/wecom_callback.py
- 新增 tests/test_wecom_callback.py
- 依赖增加 cryptography

### 当前边界

- 回调接收已实现，群机器人 Webhook 发送已实现。
- 自建应用回调后的应用消息发送仍需后续实现。
- 回调地址需要公网可访问的 HTTPS 地址。

### 后续计划

1. 增加自建应用消息发送客户端
2. 增加简单管理前端
3. 增加真实环境联调检查清单
4. 增加生产部署和反向代理说明

## 0.16 - 2026-09-30

### 当前完成内容

1. 增加企业微信自建应用发送客户端
   - 获取并缓存 access_token
   - appchat/send 发送群聊消息
   - message/send 发送单聊消息
   - 解析 errcode、errmsg 和 msgid

2. 增加发送模式
   - mock
   - webhook
   - app 或 real

3. 增加应用发送配置
   - WECOM_API_BASE
   - WECOM_CORP_ID
   - WECOM_AGENT_ID
   - WECOM_APP_SECRET
   - WECOM_SENDER_TIMEOUT_SECONDS

4. 增加应用发送测试
   - 群聊 appchat/send
   - 单聊 message/send
   - access_token 错误处理

### 本次主要变化

- 扩展 clients/wecom.py
- 扩展 config.py、.env.example 和 docker-compose.yml
- 新增 tests/test_wecom_app.py
- README 增加自建应用发送说明

### 后续计划

1. 增加简单管理前端
2. 增加真实环境联调检查清单
3. 增加生产部署和反向代理说明
4. 增加本地回调调试工具

## 0.17 - 2026-09-30

### 当前完成内容

1. 增加联调状态接口
   - GET /admin/integration-status
   - 检查企微发送配置
   - 检查企微回调配置
   - 检查 Dify 配置
   - 返回数据库类型
   - 不返回任何密钥内容

2. 增加回调调试脚本
   - roundtrip：本地加解密验证
   - verify：模拟企业微信 URL 验证
   - post：模拟加密消息回调
   - 支持 --base-url、--content、--group-id 等参数

3. 增加联调检查清单
   - 企业微信后台所需配置
   - 本地回调验证步骤
   - 常见错误排查
   - 安全检查

### 本次主要变化

- 新增 services/integration_status.py
- 扩展 api/admin.py
- 新增 scripts/debug_wecom_callback.py
- 新增 docs/wecom-integration-checklist.md

### 后续计划

1. 增加简单管理前端
2. 增加生产部署和反向代理说明
3. 增加真实环境联调执行记录
4. 增加回调消息幂等和重放保护说明

## 0.18 - 2026-09-30

### 当前完成内容

1. 增加 React 管理前端
   - React + TypeScript + Vite
   - Lucide 图标
   - 响应式管理台布局

2. 增加总览页面
   - 活动、消息、参与者、方案和投票统计
   - Outbox 和提醒状态统计

3. 增加活动页面
   - 按群组和状态筛选
   - 活动详情聚合
   - 参与者偏好、候选方案、投票、Outbox 和提醒

4. 增加消息和联调状态页面
   - 查看入站消息
   - 查看企微发送、回调、Dify 和数据库状态
   - 支持配置浏览器会话级管理密钥

### 本次主要变化

- 新增 apps/admin-web
- 增加 Vite 到 FastAPI 的 /api 代理
- README 增加前端启动说明
- 前端生产构建验证通过

### 后续计划

1. 增加生产部署和反向代理说明
2. 增加真实环境联调执行记录
3. 增加前端 API Key 失效提示和自动刷新
4. 增加活动操作按钮和确认流程

## 0.19 - 2026-10-01

### 当前完成内容

1. 改进事务 Outbox
   - 关键业务写入支持暂不提交
   - 业务数据和 Outbox 在同一事务中提交
   - 提交成功后再执行网络发送
   - 发送失败保留 Outbox 状态用于重试

2. 增加回调时间窗口
   - 校验回调 timestamp
   - 超过允许时间窗口返回 400
   - 新增 WECOM_CALLBACK_MAX_AGE_SECONDS

3. 增加提醒防重复派发
   - 增加 processing 中间状态
   - 使用条件更新原子认领提醒
   - 已被其他调度器认领的提醒不会重复发送

4. 增加请求 ID
   - 每个 HTTP 响应返回 X-Request-ID
   - 为后续日志追踪提供统一标识

5. 增加可靠性测试
   - 重复消息不创建重复 Outbox
   - 提醒只派发一次
   - 过期回调时间戳被拒绝

### 本次主要变化

- 修改 services/processing.py 和关键业务服务
- 修改 services/reminders.py
- 修改 api/wecom_callback.py
- 修改 main.py
- 扩展可靠性测试

### 后续计划

1. 增加真实 Dify Workflow DSL 和质量评估
2. 增加生产部署和反向代理说明
3. 增加真实环境联调执行记录
4. 增加管理台写入操作

## 0.20 - 2026-10-02

### 当前完成内容

1. 增加 Dify Workflow 测试集
   - 14 条固定输入
   - 覆盖 create_dinner
   - 覆盖 provide_preference
   - 覆盖 generate_proposals
   - 覆盖 vote
   - 覆盖 unknown

2. 增加真实 Dify 评测脚本
   - 支持完整运行
   - 支持 --only 单条运行
   - 支持 --fail-fast
   - 比较核心结构化字段
   - 校验 reply 关键词

3. 完成云 Dify 联调
   - 真实模式配置验证通过
   - 投票多 JSON 解析问题已修复
   - 饮食限制与口味字段区分已修复
   - missing_fields 时间字段规则已修复
   - 最终 14/14 全部通过

### 本次主要变化

- 新增 docs/dify-workflow-test-cases.json
- 新增 scripts/evaluate_dify_cases.py
- README 增加 Dify 评测说明

### 后续计划

1. 生产部署：前端容器、Nginx、HTTPS 和反向代理
2. 真实企业微信联调
3. 管理台写入操作
4. 增加监控和日志收集

## 0.21 - 2026-10-02

### 当前完成内容

1. 增加管理前端生产镜像
   - 多阶段 Node 构建
   - Nginx 静态服务
   - 排除 node_modules 和 dist

2. 增加 Nginx 反向代理
   - /api/ 转发到 FastAPI
   - /wecom/ 转发到 FastAPI
   - /health 转发到 FastAPI
   - 静态资源缓存
   - gzip 压缩

3. 增加 HTTPS 部署
   - TLS 证书挂载
   - HTTP 到 HTTPS 跳转
   - docker-compose.https.yml

4. 增加部署配置
   - APP_DOMAIN
   - TLS_CERT_PATH
   - TLS_KEY_PATH
   - deploy/nginx/README.md

### 本次主要变化

- 新增 apps/admin-web/Dockerfile
- 新增 deploy/nginx/default.conf.template
- 新增 deploy/nginx/https.conf.template
- 新增 docker-compose.https.yml
- 更新 docker-compose.yml

### 后续计划

1. 企业微信真实环境联调
2. 管理台写入操作
3. 增加监控和日志收集
4. 增加生产环境启动检查脚本
