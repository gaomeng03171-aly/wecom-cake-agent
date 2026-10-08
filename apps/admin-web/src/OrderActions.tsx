import {
  CheckCircle2,
  CircleDollarSign,
  MessageSquareText,
  PackageCheck,
  ReceiptText,
} from "lucide-react";
import { useEffect, useState } from "react";

import type { OrderDetail } from "./types";

type Props = {
  detail: OrderDetail;
  busy: boolean;
  onAction: (action: string, body?: Record<string, unknown>) => Promise<void>;
};

export function OrderActions({ detail, busy, onAction }: Props) {
  const { order } = detail;
  const [amount, setAmount] = useState(order.quoted_total ?? "");
  const [note, setNote] = useState("");
  const [ownerMessage, setOwnerMessage] = useState("");

  useEffect(() => {
    setAmount(order.quoted_total ?? "");
    setNote("");
    setOwnerMessage("");
  }, [order.id, order.quoted_total]);

  const canSubmitQuote =
    order.status === "confirmed" &&
    ["pending_owner", "rejected"].includes(order.quote_status);

  return (
    <div className="action-stack">
      {canSubmitQuote ? (
        <div className="action-group">
          <div className="action-heading">
            <ReceiptText size={17} />
            <strong>店主报价</strong>
          </div>
          <div className="quote-inputs">
            <input
              inputMode="decimal"
              min="0.01"
              onChange={(event) => setAmount(event.target.value)}
              placeholder="报价金额"
              step="0.01"
              type="number"
              value={amount}
            />
            <input
              onChange={(event) => setNote(event.target.value)}
              placeholder="给客户的备注（可选）"
              value={note}
            />
          </div>
          <div className="action-buttons">
            <button
              disabled={busy || !amount}
              onClick={() =>
                void onAction("quote", {
                  amount,
                  note: note || null,
                })
              }
              type="button"
            >
              <ReceiptText size={16} />
              发送报价
            </button>
            {order.customer_expected_price ? (
              <button
                disabled={busy}
                onClick={() =>
                  void onAction("quote", {
                    accept_expected_price: true,
                    note: null,
                  })
                }
                type="button"
              >
                <CheckCircle2 size={16} />
                接受预期价
                {order.customer_expected_price}元
              </button>
            ) : null}
          </div>
        </div>
      ) : null}

      {order.quote_status === "pending_customer" ? (
        <div className="action-note">
          <CircleDollarSign size={17} />
          已发送报价，等待客户确认。
        </div>
      ) : null}

      {order.payment_status === "deposit_pending" ? (
        <button
          disabled={busy}
          onClick={() => void onAction("deposit-paid")}
          type="button"
        >
          <CircleDollarSign size={16} />
          已收定金 {order.deposit_amount} 元
        </button>
      ) : null}

      {order.status === "preparing" ? (
        <button
          disabled={busy}
          onClick={() => void onAction("ready")}
          type="button"
        >
          <PackageCheck size={16} />
          蛋糕已做好
        </button>
      ) : null}

      {order.status === "ready" ? (
        <button
          disabled={busy}
          onClick={() => void onAction("completed")}
          type="button"
        >
          <CheckCircle2 size={16} />
          客户已取货
        </button>
      ) : null}

      {order.status === "cancelled" ? (
        <div className="action-group">
          <div className="action-heading">
            <MessageSquareText size={17} />
            <strong>给客户留言</strong>
          </div>
          <input
            onChange={(event) => setOwnerMessage(event.target.value)}
            placeholder="例如：如果方便，我们可以重新为您安排"
            value={ownerMessage}
          />
          <button
            disabled={busy || !ownerMessage.trim()}
            onClick={() =>
              void onAction("message", {
                content: ownerMessage.trim(),
              })
            }
            type="button"
          >
            <MessageSquareText size={16} />
            发送留言
          </button>
        </div>
      ) : null}
    </div>
  );
}
