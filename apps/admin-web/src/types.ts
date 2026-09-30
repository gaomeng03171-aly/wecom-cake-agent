export type ActivityStatus =
  | "collecting"
  | "proposing"
  | "voting"
  | "confirmed"
  | "completed"
  | "cancelled";

export interface Overview {
  total_activities: number;
  active_activities: number;
  inbound_messages: number;
  participants: number;
  proposals: number;
  votes: number;
  outbox_pending: number;
  outbox_sent: number;
  outbox_failed: number;
  reminders_pending: number;
}

export interface Activity {
  id: number;
  group_id: string;
  group_name: string;
  initiator_id: string;
  initiator_name: string;
  title: string;
  status: ActivityStatus;
  suggested_time: string | null;
  deadline: string | null;
  confirmed_plan: string | null;
  created_at: string;
  updated_at: string;
}

export interface Participant {
  id: number;
  activity_id: number;
  user_id: string;
  user_name: string;
  available_time: string | null;
  cuisine_preference: string | null;
  budget_max: number | null;
  notes: string | null;
  joined_at: string;
  left_at: string | null;
}

export interface Proposal {
  id: number;
  activity_id: number;
  title: string;
  proposed_time: string;
  cuisine: string;
  budget_estimate: number | null;
  notes: string | null;
  created_at: string;
}

export interface Vote {
  id: number;
  activity_id: number;
  proposal_id: number;
  user_id: string;
  user_name: string;
  created_at: string;
}

export interface OutboxMessage {
  id: number;
  activity_id: number | null;
  group_id: string;
  content: string;
  status: "pending" | "sent" | "failed";
  retry_count: number;
  max_retries: number;
  last_error: string | null;
  provider_message_id: string | null;
  created_at: string;
  updated_at: string;
  sent_at: string | null;
}

export interface Reminder {
  id: number;
  activity_id: number;
  reminder_type: string;
  content: string;
  scheduled_at: string;
  status: "pending" | "sent" | "failed" | "cancelled";
  last_error: string | null;
  created_at: string;
  sent_at: string | null;
}

export interface InboundMessage {
  id: number;
  wecom_msg_id: string;
  group_id: string;
  group_name: string;
  sender_id: string;
  sender_name: string;
  msg_type: string;
  content: string;
  created_at: string;
}

export interface ActivityDetail {
  activity: Activity;
  participants: Participant[];
  proposals: Proposal[];
  votes: Vote[];
  outbox_messages: OutboxMessage[];
  reminders: Reminder[];
}

export interface IntegrationStatus {
  wecom_sender_mode: string;
  wecom_sender_ready: boolean;
  missing_wecom_sender_config: string[];
  wecom_callback_ready: boolean;
  missing_wecom_callback_config: string[];
  wecom_callback_url: string;
  dify_client_mode: string;
  dify_ready: boolean;
  missing_dify_config: string[];
  database_dialect: string;
}
