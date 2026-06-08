import api from '../api/client';

export type WebSocketEvent =
  | 'processing-log'
  | 'candidate-status-updated'
  | 'processing-summary-updated'
  | 'pong';

export interface WebSocketMessage {
  event: WebSocketEvent;
  data: Record<string, unknown>;
  timestamp: string;
}

type EventHandler = (data: Record<string, unknown>) => void;

/**
 * WebSocket service for real-time batch processing updates.
 * Handles connection, reconnection, heartbeat, and event dispatching.
 *
 * Authentication uses the ticket-based flow:
 * 1. POST /api/v1/ws/ticket (cookie sent automatically) → returns {ticket}
 * 2. Send {"type": "auth", "token": ticket} as first WebSocket message
 */
export class BatchWebSocketService {
  private ws: WebSocket | null = null;
  private batchId: string | null = null;
  private handlers: Map<string, Set<EventHandler>> = new Map();
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 10;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null;
  private intentionalClose = false;

  connect(batchId: string): void {
    this.intentionalClose = false;
    this.batchId = batchId;
    this.reconnectAttempts = 0;
    this._connect();
  }

  disconnect(): void {
    this.intentionalClose = true;
    this._cleanup();
  }

  on(event: WebSocketEvent | string, handler: EventHandler): () => void {
    if (!this.handlers.has(event)) {
      this.handlers.set(event, new Set());
    }
    this.handlers.get(event)!.add(handler);

    // Return unsubscribe function
    return () => {
      this.handlers.get(event)?.delete(handler);
    };
  }

  off(event: WebSocketEvent | string, handler: EventHandler): void {
    this.handlers.get(event)?.delete(handler);
  }

  get connected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  private async _connect(): Promise<void> {
    if (!this.batchId) return;

    // Acquire a short-lived single-use ticket via authenticated HTTP endpoint
    let ticket: string;
    try {
      const response = await api.post<{ ticket: string }>('/ws/ticket');
      ticket = response.data.ticket;
    } catch {
      // If ticket acquisition fails (e.g. session expired), schedule reconnect
      this._scheduleReconnect();
      return;
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const url = `${protocol}//${host}/api/v1/ws/batch/${this.batchId}`;

    try {
      this.ws = new WebSocket(url);

      this.ws.onopen = () => {
        // Authenticate via first message using the single-use ticket
        this.ws?.send(JSON.stringify({ type: 'auth', token: ticket }));
        this.reconnectAttempts = 0;
        this._startHeartbeat();
        this._emit('connected', {});
      };

      this.ws.onmessage = (event: MessageEvent) => {
        try {
          const msg: WebSocketMessage = JSON.parse(event.data);
          if (msg.event) {
            this._emit(msg.event, msg.data || {});
          }
        } catch (err) {
          if (import.meta.env.DEV) {
            console.warn('[WebSocket] Failed to parse message:', err, event.data);
          }
        }
      };

      this.ws.onclose = () => {
        this._stopHeartbeat();
        this._emit('disconnected', {});
        if (!this.intentionalClose) {
          this._scheduleReconnect();
        }
      };

      this.ws.onerror = () => {
        // onclose will fire after onerror
      };
    } catch {
      this._scheduleReconnect();
    }
  }

  private _scheduleReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      this._emit('reconnect-failed', {});
      return;
    }

    // Exponential backoff: 1s, 2s, 4s, 8s, 16s, cap at 30s
    const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);
    this.reconnectAttempts++;

    this.reconnectTimer = setTimeout(() => {
      this._connect();
    }, delay);
  }

  private _startHeartbeat(): void {
    this._stopHeartbeat();
    this.heartbeatTimer = setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ type: 'ping' }));
      }
    }, 30000);
  }

  private _stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  private _emit(event: string, data: Record<string, unknown>): void {
    const handlers = this.handlers.get(event);
    if (handlers) {
      handlers.forEach((handler) => {
        try {
          handler(data);
        } catch {
          // Don't let handler errors crash the service
        }
      });
    }
  }

  private _cleanup(): void {
    this._stopHeartbeat();

    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    if (this.ws) {
      this.ws.onopen = null;
      this.ws.onmessage = null;
      this.ws.onclose = null;
      this.ws.onerror = null;
      if (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING) {
        this.ws.close();
      }
      this.ws = null;
    }

    this.batchId = null;
    this.handlers.clear();
  }
}
