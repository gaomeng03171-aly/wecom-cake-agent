import {
  Activity as ActivityIcon,
  CalendarRange,
  CheckCircle2,
  CircleAlert,
  Database,
  LayoutDashboard,
  MessageSquareText,
  PlugZap,
  RefreshCw,
  Send,
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
  OutboxMessage,
  Overview,
  Reminder,
} from "./types";

type View = "overview" | "activities" | "messages" | "integration";

const navItems: Array<{
  id: View;
  label: string;
  icon: typeof LayoutDashboard;
}> = [
  { id: "overview", label: "总览", icon: LayoutDashboard },
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

export function App() {
  const [view, setView] = useState<View>("overview");
  const [overview, setOverview] = useState<Overview | null>(null);
  const [activities, setActivities] = useState<Activity[]>([]);
  const [messages, setMessages] = useState<InboundMessage[]>([]);
  const [integration, setIntegration] = useState<IntegrationStatus | null>(null);
  const [selectedDetail, setSelectedDetail] = useState<ActivityDetail | null>(null);
  const [selectedActivityId, setSelectedActivityId] = useState<number | null>(null);
  const [groupFilter, setGroupFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
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
      const [overviewData, activityData, messageData, integrationData] =
        await Promise.all([
          apiFetch<Overview>("/admin/overview"),
          apiFetch<Activity[]>(`/admin/activities?${query.toString()}`),
          apiFetch<InboundMessage[]>(
            `/admin/messages?${groupFilter ? `group_id=${encodeURIComponent(groupFilter)}` : ""}`,
          ),
          apiFetch<IntegrationStatus>("/admin/integration-status"),
        ]);
      setOverview(overviewData);
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

  useEffect(() => {
    void loadData();
  }, [groupFilter, statusFilter]);

  function updateAdminKey(value: string) {
    setAdminKey(value);
    setAdminKeyState(value);
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">聚</div>
          <div>
            <strong>聚餐 Agent</strong>
            <span>管理台</span>
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
              <CheckCircle2 size={20} />
              <span>Dify</span>
              <strong>{integration.dify_client_mode}</strong>
              <StatusBadge status={integration.dify_ready ? "sent" : "failed"} />
              {integration.missing_dify_config.length ? (
                <small>{integration.missing_dify_config.join(", ")}</small>
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
