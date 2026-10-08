import { ChevronLeft, ChevronRight } from "lucide-react";
import { useMemo, useState } from "react";

import type { Order } from "./types";

type CalendarProps = {
  orders: Order[];
  selectedOrderId: number | null;
  onOpenOrder: (orderId: number) => void;
};

const weekDays = ["一", "二", "三", "四", "五", "六", "日"];

const statusLabels: Record<Order["status"], string> = {
  collecting: "收集中",
  pending_confirmation: "待确认",
  confirmed: "已确认",
  preparing: "制作中",
  ready: "可取货",
  completed: "已完成",
  cancelled: "已取消",
};

function dateKey(value: string | null): string {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value.slice(0, 10);
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${date.getFullYear()}-${month}-${day}`;
}

function localDateKey(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(
    date.getDate(),
  ).padStart(2, "0")}`;
}

function orderDate(order: Order): string {
  return dateKey(order.scheduled_at) || order.business_date || "";
}

function formatDayTitle(key: string): string {
  const [, month, day] = key.split("-");
  return `${Number(month)}月${Number(day)}日`;
}

export function OrderCalendar({
  orders,
  selectedOrderId,
  onOpenOrder,
}: CalendarProps) {
  const today = new Date();
  const [month, setMonth] = useState(
    () => new Date(today.getFullYear(), today.getMonth(), 1),
  );
  const [selectedDate, setSelectedDate] = useState(
    () => localDateKey(today),
  );

  const counts = useMemo(() => {
    const result = new Map<string, number>();
    orders.forEach((order) => {
      const key = orderDate(order);
      if (key) result.set(key, (result.get(key) ?? 0) + 1);
    });
    return result;
  }, [orders]);

  const cells = useMemo(() => {
    const first = new Date(month.getFullYear(), month.getMonth(), 1);
    const leading = (first.getDay() + 6) % 7;
    const days = new Date(
      month.getFullYear(),
      month.getMonth() + 1,
      0,
    ).getDate();
    return [
      ...Array.from({ length: leading }, () => null),
      ...Array.from({ length: days }, (_, index) => index + 1),
    ];
  }, [month]);

  const selectedOrders = orders.filter(
    (order) => orderDate(order) === selectedDate,
  );

  function moveMonth(offset: number) {
    const next = new Date(month.getFullYear(), month.getMonth() + offset, 1);
    setMonth(next);
    setSelectedDate(
      `${next.getFullYear()}-${String(next.getMonth() + 1).padStart(2, "0")}-01`,
    );
  }

  return (
    <section className="calendar-panel">
      <div className="calendar-heading">
        <div>
          <span>订单日历</span>
          <strong>
            {month.getFullYear()}年{month.getMonth() + 1}月
          </strong>
        </div>
        <div className="calendar-nav">
          <button
            aria-label="上个月"
            className="icon-button"
            onClick={() => moveMonth(-1)}
            type="button"
          >
            <ChevronLeft size={17} />
          </button>
          <button
            aria-label="下个月"
            className="icon-button"
            onClick={() => moveMonth(1)}
            type="button"
          >
            <ChevronRight size={17} />
          </button>
        </div>
      </div>

      <div className="calendar-grid">
        {weekDays.map((day) => (
          <span className="calendar-weekday" key={day}>
            {day}
          </span>
        ))}
        {cells.map((day, index) => {
          if (day === null) {
            return <span className="calendar-empty" key={`empty-${index}`} />;
          }
          const key = `${month.getFullYear()}-${String(
            month.getMonth() + 1,
          ).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
          const count = counts.get(key) ?? 0;
          return (
            <button
              className={`calendar-day${selectedDate === key ? " selected" : ""}${count ? " has-orders" : ""}`}
              key={key}
              onClick={() => setSelectedDate(key)}
              type="button"
            >
              <span>{day}</span>
              {count ? <strong>{count}</strong> : null}
            </button>
          );
        })}
      </div>

      <div className="calendar-day-orders">
        <div className="subsection-heading">
          <h3>{formatDayTitle(selectedDate)}订单</h3>
          <span>{selectedOrders.length} 单</span>
        </div>
        <div className="table-wrap compact">
          <table>
            <thead>
              <tr>
                <th>订单</th>
                <th>客户</th>
                <th>状态</th>
              </tr>
            </thead>
            <tbody>
              {selectedOrders.map((order) => (
                <tr
                  className={selectedOrderId === order.id ? "selected" : ""}
                  key={order.id}
                  onClick={() => onOpenOrder(order.id)}
                >
                  <td>
                    {order.business_date
                      ? `${order.business_date.slice(5)}-${String(
                          order.order_number ?? 0,
                        ).padStart(4, "0")}`
                      : `#${order.id}`}
                  </td>
                  <td>{order.conversation_name || order.conversation_id}</td>
                  <td>
                    <span className={`status status-${order.status}`}>
                      {statusLabels[order.status]}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {selectedOrders.length === 0 ? (
            <div className="empty-state">当天暂无订单</div>
          ) : null}
        </div>
      </div>
    </section>
  );
}
