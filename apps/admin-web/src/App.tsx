import {
  Activity as ActivityIcon,
  CalendarRange,
  CheckCircle2,
  ClipboardList,
  CircleAlert,
  Database,
  LayoutDashboard,
  MessageSquareText,
  PlugZap,
  RefreshCw,
  Send,
  Store,
  Users,
  Vote as VoteIcon,
} from "lucide-react";
import { useEffect, useState } from "react";

import { apiFetch, getAdminKey, setAdminKey } from "./api";
import type {
  Activity,
  ActivityDetail,
  ActivityStatus,
  InboundMessage,
  IntegrationStatus,
  Order,
  OrderDetail,
  OrderStatus,
  OutboxMessage,
  Overview,
  Reminder,
} from "./types";

type View = "overview" | "orders" | "activities" | "messages" | "integration";

const navItems: Array<{
  id: View;
  label: string;
  icon: typeof LayoutDashboard;
}> = [
  { id: "overview", label: "总览", icon: LayoutDashboard },
  { id: "orders", label: "订单", icon: ClipboardList },
  { id: "activities", label: "活动", icon: CalendarRange },
  { id: "messages", label: "消息", icon: MessageSquareText },
  { id: "integration", label: "联调状态", icon: PlugZap },
];

const statusLabels: Record<ActivityStatus, string> = {
  collecting: "收集偏好",
  proposing: "生成方案",
  voting: "投票中",
  confirmed: "已确认",
  completed: "已完成",
  cancelled: "已取消",
};

const orderStatusLabels: Record<OrderStatus, string> = {
  collecting: "收集中",
  pending_confirmation: "待确认",
  confirmed: "已确认",
  cancelled: "已取消",
};

function formatDate(value: string | null): string {
  if (!value) return "-";
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function StatusBadge({ status }: { status: string }) {
  return <span className={`status status-${status}`}>{status}</span>;
}

function Metric({
  label,
  value,
  icon: Icon,
  tone = "teal",
}: {
  label: string;
  value: number;
  icon: typeof LayoutDashboard;
  tone?: "teal" | "amber" | "red" | "green";
}) {
  return (
    <div className={`metric metric-${tone}`}>
      <div className="metric-icon">
        <Icon size={18} strokeWidth={1.8} />
      </div>
      <div>
        <span>{label}</span>
        <strong>{value}</strong>
      </div>
    </div>
  );
}

function EmptyState({ text }: { text: string }) {
  return <div className="empty-state">{text}</div>;
}

function ActivityDetailPanel({ detail }: { detail: ActivityDetail | null }) {
  if (!detail) {
    return <EmptyState text="选择一条活动查看详情" />;
  }

  const voteCounts = new Map<number, number>();
  detail.votes.forEach((vote) => {
    voteCounts.set(vote.proposal_id, (voteCounts.get(vote.proposal_id) ?? 0) + 1);
  });

  return (
    <section className="detail-panel">
      <div className="detail-heading">
        <div>
          <p className="eyebrow">活动 #{detail.activity.id}</p>
          <h2>{detail.activity.title}</h2>
          <span>{detail.activity.group_name || detail.activity.group_id}</span>
        </div>
        <StatusBadge status={detail.activity.status} />
      </div>

      <div className="detail-summary">
        <div>
          <span>发起人</span>
          <strong>{detail.activity.initiator_name || detail.activity.initiator_id}</strong>
        </div>
        <div>
          <span>最终方案</span>
          <strong>{detail.activity.confirmed_plan || "-"}</strong>
        </div>
        <div>
          <span>创建时间</span>
          <strong>{formatDate(detail.activity.created_at)}</strong>
        </div>
      </div>

      <div className="subsection">
        <div className="subsection-heading">
          <h3>参与者</h3>
          <span>{detail.participants.length} 人</span>
        </div>
        <div className="table-wrap compact">
          <table>
            <thead>
              <tr>
                <th>成员</th>
                <th>时间</th>
                <th>口味</th>
                <th>预算</th>
                <th>备注</th>
              </tr>
            </thead>
            <tbody>
              {detail.participants.map((participant) => (
                <tr key={participant.id}>
                  <td>{participant.user_name || participant.user_id}</td>
                  <td>{participant.available_time || "-"}</td>
                  <td>{participant.cuisine_preference || "-"}</td>
                  <td>{participant.budget_max ?? "-"}</td>
                  <td>{participant.notes || "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="subsection">
        <div className="subsection-heading">
          <h3>候选方案</h3>
          <span>{detail.proposals.length} 个</span>
        </div>
        <div className="proposal-list">
          {detail.proposals.map((proposal) => (
            <div className="proposal-row" key={proposal.id}>
              <div>
                <strong>{proposal.title}</strong>
                <span>{proposal.notes || proposal.cuisine}</span>
              </div>
              <div className="proposal-meta">
                <span>{proposal.proposed_time}</span>
                <span>{proposal.budget_estimate ?? "-"} 元</span>
                <span>{voteCounts.get(proposal.id) ?? 0} 票</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="detail-columns">
        <div className="subsection">
          <div className="subsection-heading">
            <h3>Outbox</h3>
            <span>{detail.outbox_messages.length} 条</span>
          </div>
          <div className="event-list">
            {detail.outbox_messages.slice(0, 6).map((message: OutboxMessage) => (
              <div className="event-row" key={message.id}>
                <StatusBadge status={message.status} />
                <span>{message.content}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="subsection">
          <div className="subsection-heading">
            <h3>提醒</h3>
            <span>{detail.reminders.length} 条</span>
          </div>
          <div className="event-list">
            {detail.reminders.map((reminder: Reminder) => (
              <div className="event-row" key={reminder.id}>
                <StatusBadge status={reminder.status} />
                <span>{reminder.content}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

function OrderDetailPanel({ detail }: { detail: OrderDetail | null }) {
  if (!detail) {
    return <EmptyState text="选择一条订单查看详情" />;
  }

  const { order, customer, confirmations } = detail;
  const requirementEntries = Object.entries(order.requirements ?? {});

  return (
    <section className="detail-panel">
      <div className="detail-heading">
        <div>
          <p className="eyebrow">订单 #{order.id}</p>
          <h2>{order.title}</h2>
          <span>{order.conversation_name || order.conversation_id}</span>
        </div>
        <StatusBadge status={order.status} />
      </div>

      <div className="detail-summary">
        <div>
          <span>客户</span>
          <strong>{customer.name || customer.external_id}</strong>
        </div>
        <div>
          <span>场景</span>
          <strong>{order.scenario}</strong>
        </div>
        <div>
          <span>更新时间</span>
          <strong>{formatDate(order.updated_at)}</strong>
        </div>
      </div>

      <div className="subsection">
        <div className="subsection-heading">
          <h3>订单信息</h3>
          <span>{requirementEntries.length} 项</span>
        </div>
        <div className="proposal-list">
          {requirementEntries.map(([key, value]) => (
            <div className="proposal-row" key={key}>
              <strong>{key}</strong>
              <span>{String(value)}</span>
            </div>
          ))}
          {requirementEntries.length === 0 ? (
            <EmptyState text="还没有收集到订单字段" />
          ) : null}
        </div>
      </div>

      {order.missing_fields.length ? (
        <div className="subsection">
          <div className="subsection-heading">
            <h3>待补充</h3>
            <span>{order.missing_fields.length} 项</span>
          </div>
          <div className="event-list">
            {order.missing_fields.map((field) => (
              <div className="event-row" key={field}>
                <StatusBadge status="pending" />
                <span>{field}</span>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      <div className="subsection">
        <div className="subsection-heading">
          <h3>确认记录</h3>
          <span>{confirmations.length} 条</span>
        </div>
        <div className="event-list">
          {confirmations.map((confirmation) => (
            <div className="event-row" key={confirmation.id}>
              <StatusBadge status="confirmed" />
              <span>{confirmation.confirmation_text || confirmation.confirmation_type}</span>
            </div>
          ))}
          {confirmations.length === 0 ? (
            <EmptyState text="还没有确认记录" />
          ) : null}
        </div>
      </div>
    </section>
  );
}

export function App() {
  const [view, setView] = useState<View>("overview");
  const [overview, setOverview] = useState<Overview | null>(null);
  const [orders, setOrders] = useState<Order[]>([]);
  const [activities, setActivities] = useState<Activity[]>([]);
  const [messages, setMessages] = useState<InboundMessage[]>([]);
  const [integration, setIntegration] = useState<IntegrationStatus | null>(null);
  const [selectedOrderDetail, setSelectedOrderDetail] =
    useState<OrderDetail | null>(null);
  const [selectedOrderId, setSelectedOrderId] = useState<number | null>(null);
  const [selectedDetail, setSelectedDetail] = useState<ActivityDetail | null>(null);
  const [selectedActivityId, setSelectedActivityId] = useState<number | null>(null);
  const [groupFilter, setGroupFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [orderStatusFilter, setOrderStatusFilter] = useState("");
  const [orderScenarioFilter, setOrderScenarioFilter] = useState("");
  const [adminKey, setAdminKeyState] = useState(getAdminKey());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function loadData() {
    setLoading(true);
    setError("");
    try {
      const query = new URLSearchParams();
      if (groupFilter) query.set("group_id", groupFilter);
      if (statusFilter) query.set("status", statusFilter);
      const orderQuery = new URLSearchParams();
      if (orderStatusFilter) orderQuery.set("status", orderStatusFilter);
      if (orderScenarioFilter) orderQuery.set("scenario", orderScenarioFilter);
      const [overviewData, orderData, activityData, messageData, integrationData] =
        await Promise.all([
          apiFetch<Overview>("/admin/overview"),
          apiFetch<Order[]>(`/admin/orders?${orderQuery.toString()}`),
          apiFetch<Activity[]>(`/admin/activities?${query.toString()}`),
          apiFetch<InboundMessage[]>(
            `/admin/messages?${groupFilter ? `group_id=${encodeURIComponent(groupFilter)}` : ""}`,
          ),
          apiFetch<IntegrationStatus>("/admin/integration-status"),
        ]);
      setOverview(overviewData);
      setOrders(orderData);
      setActivities(activityData);
      setMessages(messageData);
      setIntegration(integrationData);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }

  async function openActivity(activityId: number) {
    setSelectedActivityId(activityId);
    try {
      const detail = await apiFetch<ActivityDetail>(
        `/admin/activities/${activityId}`,
      );
      setSelectedDetail(detail);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "加载失败");
    }
  }

  async function openOrder(orderId: number) {
    setSelectedOrderId(orderId);
    try {
      const detail = await apiFetch<OrderDetail>(`/admin/orders/${orderId}`);
      setSelectedOrderDetail(detail);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "加载失败");
    }
  }

  useEffect(() => {
    void loadData();
  }, [groupFilter, statusFilter, orderStatusFilter, orderScenarioFilter]);

  function updateAdminKey(value: string) {
    setAdminKey(value);
    setAdminKeyState(value);
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">单</div>
          <div>
            <strong>订单 Agent</strong>
            <span>小微商户管理台</span>
          </div>
        </div>
        <nav>
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <button
                className={view === item.id ? "active" : ""}
                key={item.id}
                onClick={() => setView(item.id)}
                type="button"
              >
                <Icon size={18} strokeWidth={1.8} />
                {item.label}
              </button>
            );
          })}
        </nav>
        <div className="key-box">
          <label htmlFor="admin-key">管理密钥</label>
          <input
            id="admin-key"
            type="password"
            value={adminKey}
            onChange={(event) => updateAdminKey(event.target.value)}
            placeholder="未设置"
          />
        </div>
      </aside>

      <main>
        <header className="topbar">
          <div>
            <p className="eyebrow">运行控制台</p>
            <h1>{navItems.find((item) => item.id === view)?.label}</h1>
          </div>
          <button className="icon-button" onClick={() => void loadData()} type="button">
            <RefreshCw size={17} className={loading ? "spin" : ""} />
            刷新
          </button>
        </header>

        {error ? (
          <div className="error-banner">
            <CircleAlert size={16} />
            <span>{error}</span>
          </div>
        ) : null}

        {view === "overview" && overview ? (
          <section className="view-section">
            <div className="metric-grid">
              <Metric label="订单总数" value={overview.total_orders} icon={ClipboardList} />
              <Metric
                label="待确认订单"
                value={overview.pending_confirmation_orders}
                icon={Store}
                tone="amber"
              />
              <Metric
                label="已确认订单"
                value={overview.confirmed_orders}
                icon={CheckCircle2}
                tone="green"
              />
              <Metric label="活动总数" value={overview.total_activities} icon={CalendarRange} />
              <Metric label="进行中" value={overview.active_activities} icon={ActivityIcon} />
              <Metric label="消息" value={overview.inbound_messages} icon={MessageSquareText} />
              <Metric label="参与者" value={overview.participants} icon={Users} />
              <Metric label="候选方案" value={overview.proposals} icon={CheckCircle2} />
              <Metric label="投票" value={overview.votes} icon={VoteIcon} />
              <Metric label="待发送" value={overview.outbox_pending} icon={Send} tone="amber" />
              <Metric label="发送失败" value={overview.outbox_failed} icon={CircleAlert} tone="red" />
            </div>
          </section>
        ) : null}

        {view === "orders" ? (
          <section className="view-section split-layout">
            <div className="table-panel">
              <div className="toolbar">
                <select
                  value={orderScenarioFilter}
                  onChange={(event) => setOrderScenarioFilter(event.target.value)}
                >
                  <option value="">全部场景</option>
                  <option value="cake">蛋糕</option>
                  <option value="flower">花店</option>
                  <option value="repair">维修</option>
                  <option value="other">其他</option>
                </select>
                <select
                  value={orderStatusFilter}
                  onChange={(event) => setOrderStatusFilter(event.target.value)}
                >
                  <option value="">全部状态</option>
                  {Object.entries(orderStatusLabels).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>订单</th>
                      <th>场景</th>
                      <th>会话</th>
                      <th>状态</th>
                      <th>更新时间</th>
                    </tr>
                  </thead>
                  <tbody>
                    {orders.map((order) => (
                      <tr
                        className={selectedOrderId === order.id ? "selected" : ""}
                        key={order.id}
                        onClick={() => void openOrder(order.id)}
                      >
                        <td>#{order.id}</td>
                        <td>{order.title}</td>
                        <td>{order.scenario}</td>
                        <td>{order.conversation_name || order.conversation_id}</td>
                        <td>
                          <StatusBadge status={order.status} />
                        </td>
                        <td>{formatDate(order.updated_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {orders.length === 0 ? <EmptyState text="没有匹配的订单" /> : null}
              </div>
            </div>
            <OrderDetailPanel detail={selectedOrderDetail} />
          </section>
        ) : null}

        {view === "activities" ? (
          <section className="view-section split-layout">
            <div className="table-panel">
              <div className="toolbar">
                <input
                  value={groupFilter}
                  onChange={(event) => setGroupFilter(event.target.value)}
                  placeholder="按群 ID 筛选"
                />
                <select
                  value={statusFilter}
                  onChange={(event) => setStatusFilter(event.target.value)}
                >
                  <option value="">全部状态</option>
                  {Object.entries(statusLabels).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>活动</th>
                      <th>群组</th>
                      <th>状态</th>
                      <th>发起人</th>
                      <th>更新时间</th>
                    </tr>
                  </thead>
                  <tbody>
                    {activities.map((activity) => (
                      <tr
                        className={selectedActivityId === activity.id ? "selected" : ""}
                        key={activity.id}
                        onClick={() => void openActivity(activity.id)}
                      >
                        <td>#{activity.id}</td>
                        <td>{activity.title}</td>
                        <td>{activity.group_name || activity.group_id}</td>
                        <td>
                          <StatusBadge status={activity.status} />
                        </td>
                        <td>{activity.initiator_name || activity.initiator_id}</td>
                        <td>{formatDate(activity.updated_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {activities.length === 0 ? <EmptyState text="没有匹配的活动" /> : null}
              </div>
            </div>
            <ActivityDetailPanel detail={selectedDetail} />
          </section>
        ) : null}

        {view === "messages" ? (
          <section className="view-section table-panel">
            <div className="toolbar">
              <input
                value={groupFilter}
                onChange={(event) => setGroupFilter(event.target.value)}
                placeholder="按群 ID 筛选"
              />
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>时间</th>
                    <th>群组</th>
                    <th>发送者</th>
                    <th>类型</th>
                    <th>内容</th>
                  </tr>
                </thead>
                <tbody>
                  {messages.map((message) => (
                    <tr key={message.id}>
                      <td>{formatDate(message.created_at)}</td>
                      <td>{message.group_name || message.group_id}</td>
                      <td>{message.sender_name || message.sender_id}</td>
                      <td>{message.msg_type}</td>
                      <td className="content-cell">{message.content}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {messages.length === 0 ? <EmptyState text="暂无消息" /> : null}
            </div>
          </section>
        ) : null}

        {view === "integration" && integration ? (
          <section className="view-section integration-grid">
            <div className="integration-item">
              <MessageSquareText size={20} />
              <span>企微发送</span>
              <strong>{integration.wecom_sender_mode}</strong>
              <StatusBadge
                status={integration.wecom_sender_ready ? "sent" : "failed"}
              />
              {integration.missing_wecom_sender_config.length ? (
                <small>{integration.missing_wecom_sender_config.join(", ")}</small>
              ) : null}
            </div>
            <div className="integration-item">
              <PlugZap size={20} />
              <span>企微回调</span>
              <strong>{integration.wecom_callback_url}</strong>
              <StatusBadge
                status={integration.wecom_callback_ready ? "sent" : "failed"}
              />
              {integration.missing_wecom_callback_config.length ? (
                <small>{integration.missing_wecom_callback_config.join(", ")}</small>
              ) : null}
            </div>
            <div className="integration-item">
              <PlugZap size={20} />
              <span>智能机器人长连接</span>
              <strong>{integration.wecom_aibot_ready ? "已配置" : "缺少配置"}</strong>
              <StatusBadge
                status={integration.wecom_aibot_ready ? "sent" : "failed"}
              />
              {integration.missing_wecom_aibot_config.length ? (
                <small>{integration.missing_wecom_aibot_config.join(", ")}</small>
              ) : null}
            </div>
            <div className="integration-item">
              <CheckCircle2 size={20} />
              <span>Dify</span>
              <strong>{integration.dify_client_mode}</strong>
              <StatusBadge status={integration.dify_ready ? "sent" : "failed"} />
              {integration.missing_dify_config.length ? (
                <small>{integration.missing_dify_config.join(", ")}</small>
              ) : null}
            </div>
            <div className="integration-item">
              <ClipboardList size={20} />
              <span>订单 Dify</span>
              <strong>{integration.order_dify_mode}</strong>
              <StatusBadge
                status={integration.order_dify_ready ? "sent" : "failed"}
              />
              {integration.missing_order_dify_config.length ? (
                <small>{integration.missing_order_dify_config.join(", ")}</small>
              ) : null}
            </div>
            <div className="integration-item">
              <Database size={20} />
              <span>数据库</span>
              <strong>{integration.database_dialect}</strong>
              <StatusBadge status="sent" />
            </div>
          </section>
        ) : null}
      </main>
    </div>
  );
}
