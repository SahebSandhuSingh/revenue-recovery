import React, { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { getCaseDetail, markPromiseKept } from "../api";
import LoadingState from "../components/LoadingState";
import ErrorState from "../components/ErrorState";
import { pageTransition } from "../motion";
import {
  ArrowLeft,
  CheckCircle2,
  Clock,
  MessageSquare,
  Zap,
  Bot,
  Handshake,
  UserCheck,
} from "lucide-react";

export default function CaseDetail() {
  const { event_id } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [overrideLoading, setOverrideLoading] = useState(false);
  const [overrideMessage, setOverrideMessage] = useState(null);

  const fetchCase = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await getCaseDetail(event_id);
      setData(res);
    } catch (err) {
      console.error("Failed to load case detail:", err);
      setError(err.response?.data?.detail || err.message || "Failed to load case details");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCase();
  }, [event_id]);

  const handleMarkKept = async (promiseId) => {
    try {
      setOverrideLoading(true);
      setOverrideMessage(null);
      const res = await markPromiseKept(promiseId);
      setOverrideMessage(res.message || "Promise marked as kept.");
      await fetchCase();
    } catch (err) {
      console.error("Manual override failed:", err);
      alert(err.response?.data?.detail || "Failed to execute manual demo override.");
    } finally {
      setOverrideLoading(false);
    }
  };

  if (loading) return <LoadingState message="Fetching case history, intervention plan, and audit timeline..." />;
  if (error) return <ErrorState error={error} onRetry={fetchCase} />;
  if (!data) return null;

  const { event, diagnosis, action, promise, inbound_messages, audit_log } = data;

  const formatINR = (val) =>
    new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
      maximumFractionDigits: 2,
    }).format(val);

  return (
    <motion.div {...pageTransition}>
      {/* Back button */}
      <motion.div
        style={{ marginBottom: "18px" }}
        initial={{ opacity: 0, x: -12 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.3 }}
      >
        <motion.button
          className="btn-refresh"
          onClick={() => navigate("/cases")}
          style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}
          whileHover={{ x: -3 }}
          whileTap={{ scale: 0.96 }}
        >
          <ArrowLeft size={14} />
          <span>Back to Case Explorer</span>
        </motion.button>
      </motion.div>

      {/* Case Header Banner */}
      <motion.div
        className="panel"
        style={{
          marginBottom: "22px",
          borderLeft: "3px solid var(--accent)",
          position: "relative",
          overflow: "hidden",
        }}
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
      >
        {/* Subtle gradient overlay */}
        <div style={{
          position: "absolute",
          top: 0,
          right: 0,
          width: "40%",
          height: "100%",
          background: "radial-gradient(ellipse at right center, rgba(108, 140, 255, 0.04) 0%, transparent 70%)",
          pointerEvents: "none",
        }} />

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "14px", position: "relative" }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "8px" }}>
              <h1 style={{ fontSize: "22px", fontWeight: "800", color: "#fff", letterSpacing: "-0.02em" }}>
                {event.customer_id}
              </h1>
              <span className="badge badge-planned" style={{ textTransform: "uppercase", fontSize: "10px" }}>
                {event.source_type}
              </span>
            </div>
            <div style={{
              fontSize: "11px",
              color: "var(--text-dim)",
              fontFamily: "var(--font-mono)",
              background: "rgba(10, 15, 30, 0.4)",
              display: "inline-block",
              padding: "3px 8px",
              borderRadius: "4px",
            }}>
              {event.id}
            </div>
          </div>

          <motion.div
            style={{ textAlign: "right" }}
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.25, type: "spring", stiffness: 200 }}
          >
            <div style={{
              fontSize: "10px",
              color: "var(--text-muted)",
              textTransform: "uppercase",
              letterSpacing: "0.08em",
              marginBottom: "4px",
            }}>
              Amount at Risk
            </div>
            <div style={{
              fontSize: "28px",
              fontWeight: "800",
              color: "var(--accent-bright)",
              letterSpacing: "-0.03em",
              fontFamily: "var(--font-mono)",
            }}>
              {formatINR(event.amount)}
            </div>
          </motion.div>
        </div>
      </motion.div>

      {/* Override Success Alert */}
      <AnimatePresence>
        {overrideMessage && (
          <motion.div
            className="honesty-banner"
            style={{ background: "rgba(52, 217, 154, 0.08)", borderColor: "rgba(52, 217, 154, 0.3)", borderLeftColor: "var(--success)" }}
            initial={{ opacity: 0, y: -8, height: 0, marginBottom: 0 }}
            animate={{ opacity: 1, y: 0, height: "auto", marginBottom: 28 }}
            exit={{ opacity: 0, y: -8, height: 0, marginBottom: 0 }}
            transition={{ duration: 0.3 }}
          >
            <CheckCircle2 size={18} color="#34d99a" />
            <div className="honesty-banner-text" style={{ color: "#a7f3d0" }}>
              {overrideMessage}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Core Case Facts Grid */}
      <motion.div
        className="panel-grid"
        style={{ marginBottom: "22px" }}
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
      >
        {/* Left: Diagnosis & Action */}
        <div className="panel">
          <div className="panel-header">
            <div className="panel-title">
              <div style={{
                background: "rgba(108, 140, 255, 0.12)",
                borderRadius: "6px",
                padding: "6px",
                display: "flex",
                alignItems: "center",
              }}>
                <Zap size={15} color="#8da8ff" />
              </div>
              <span>AI Diagnosis & Recovery Plan</span>
            </div>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "14px", fontSize: "13px" }}>
            <div>
              <span style={{
                color: "var(--text-muted)",
                display: "block",
                marginBottom: "4px",
                fontSize: "10px",
                textTransform: "uppercase",
                letterSpacing: "0.08em",
                fontWeight: "600",
              }}>
                Diagnosed Root Cause
              </span>
              {diagnosis ? (
                <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                  <span className="badge badge-cash-flow" style={{ fontSize: "12px" }}>
                    {diagnosis.root_cause.replace(/_/g, " ")}
                  </span>
                  <span style={{
                    color: "var(--text-dim)",
                    fontSize: "11px",
                    fontFamily: "var(--font-mono)",
                  }}>
                    {(diagnosis.confidence * 100).toFixed(0)}% confidence
                  </span>
                </div>
              ) : (
                <span style={{ color: "var(--text-dim)" }}>Undiagnosed</span>
              )}
            </div>

            {diagnosis?.reasoning && (
              <motion.div
                style={{
                  background: "rgba(10, 15, 30, 0.5)",
                  padding: "12px",
                  borderRadius: "8px",
                  fontSize: "12px",
                  color: "var(--text-secondary)",
                  borderLeft: "2px solid rgba(108, 140, 255, 0.3)",
                  lineHeight: "1.6",
                }}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.3 }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "6px", color: "var(--text-muted)", fontSize: "10px", textTransform: "uppercase", letterSpacing: "0.06em" }}>
                  <Bot size={12} />
                  Agent Reasoning
                </div>
                {diagnosis.reasoning}
              </motion.div>
            )}

            <div style={{ borderTop: "1px solid var(--border-subtle)", paddingTop: "14px" }}>
              <span style={{
                color: "var(--text-muted)",
                display: "block",
                marginBottom: "6px",
                fontSize: "10px",
                textTransform: "uppercase",
                letterSpacing: "0.08em",
                fontWeight: "600",
              }}>
                Planned Intervention
              </span>
              {action ? (
                <div>
                  <div style={{ display: "flex", gap: "8px", alignItems: "center", marginBottom: "8px", flexWrap: "wrap" }}>
                    <strong style={{ color: "#fff", fontSize: "13px" }}>{action.action_type.replace(/_/g, " ")}</strong>
                    <span className="badge badge-planned">{action.channel}</span>
                    <span className="badge badge-sent">{action.status}</span>
                  </div>
                  {action.message_draft && (
                    <div style={{
                      background: "rgba(10, 15, 30, 0.5)",
                      border: "1px dashed rgba(100, 120, 180, 0.15)",
                      padding: "12px",
                      borderRadius: "8px",
                      fontSize: "12px",
                      color: "var(--text-secondary)",
                      fontStyle: "italic",
                      lineHeight: "1.5",
                    }}>
                      <div style={{ fontSize: "10px", color: "var(--text-dim)", marginBottom: "6px", fontStyle: "normal", textTransform: "uppercase", letterSpacing: "0.06em" }}>
                        Drafted Outreach
                      </div>
                      "{action.message_draft}"
                    </div>
                  )}
                </div>
              ) : (
                <span style={{ color: "var(--text-dim)" }}>No intervention planned</span>
              )}
            </div>
          </div>
        </div>

        {/* Right: Promise & Replies */}
        <div className="panel">
          <div className="panel-header">
            <div className="panel-title">
              <div style={{
                background: "rgba(52, 217, 154, 0.12)",
                borderRadius: "6px",
                padding: "6px",
                display: "flex",
                alignItems: "center",
              }}>
                <Handshake size={15} color="#34d99a" />
              </div>
              <span>Customer Commitment & Replies</span>
            </div>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "16px", fontSize: "13px" }}>
            {promise ? (
              <motion.div
                style={{
                  background: "rgba(15, 22, 40, 0.5)",
                  border: "1px solid var(--border-color)",
                  padding: "16px",
                  borderRadius: "10px",
                }}
                initial={{ opacity: 0, scale: 0.97 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: 0.25 }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px" }}>
                  <span style={{ fontWeight: "700", color: "#fff", fontSize: "14px" }}>Promise to Pay</span>
                  <span className={`badge ${promise.status === "kept" ? "badge-kept" : promise.status === "broken" ? "badge-broken" : "badge-pending"}`}>
                    {promise.status}
                  </span>
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px", marginBottom: "12px" }}>
                  <div>
                    <div style={{ fontSize: "10px", color: "var(--text-dim)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: "2px" }}>Amount</div>
                    <div style={{ fontWeight: "700", color: "#fff", fontFamily: "var(--font-mono)" }}>
                      {promise.promised_amount ? formatINR(promise.promised_amount) : "Full Balance"}
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: "10px", color: "var(--text-dim)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: "2px" }}>Due Date</div>
                    <div style={{ fontWeight: "600", color: "#fff" }}>
                      {promise.promised_date || "Not specified"}
                    </div>
                  </div>
                </div>

                {/* Demo Override */}
                {promise.status === "pending" && (
                  <div style={{ borderTop: "1px solid var(--border-subtle)", paddingTop: "12px" }}>
                    <div style={{
                      fontSize: "10px",
                      color: "#fbbf24",
                      marginBottom: "8px",
                      textTransform: "uppercase",
                      letterSpacing: "0.06em",
                      fontWeight: "600",
                    }}>
                      Demo Resolution Override
                    </div>
                    <motion.button
                      className="btn-demo-action"
                      onClick={() => handleMarkKept(promise.id)}
                      disabled={overrideLoading}
                      whileHover={{ scale: 1.03 }}
                      whileTap={{ scale: 0.97 }}
                    >
                      <CheckCircle2 size={14} />
                      <span>{overrideLoading ? "Updating..." : "Mark as Kept (Demo)"}</span>
                    </motion.button>
                  </div>
                )}

                {promise.status === "kept" && (
                  <motion.div
                    style={{
                      fontSize: "11px",
                      color: "var(--success)",
                      marginTop: "8px",
                      display: "flex",
                      alignItems: "center",
                      gap: "6px",
                    }}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                  >
                    <UserCheck size={13} />
                    Confirmed via {promise.reconciliation_source || "reconciliation"}
                  </motion.div>
                )}
              </motion.div>
            ) : (
              <div style={{ color: "var(--text-dim)", fontSize: "12px", padding: "12px 0" }}>
                No promise commitment recorded for this case.
              </div>
            )}

            {/* Inbound Messages */}
            {inbound_messages && inbound_messages.length > 0 && (
              <div>
                <span style={{
                  color: "var(--text-muted)",
                  display: "block",
                  marginBottom: "8px",
                  fontSize: "10px",
                  textTransform: "uppercase",
                  letterSpacing: "0.08em",
                  fontWeight: "600",
                }}>
                  Customer Responses ({inbound_messages.length})
                </span>
                <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                  {inbound_messages.map((msg, idx) => (
                    <motion.div
                      key={msg.id}
                      style={{
                        background: "rgba(10, 15, 30, 0.5)",
                        padding: "12px",
                        borderRadius: "8px",
                        border: "1px solid var(--border-subtle)",
                      }}
                      initial={{ opacity: 0, x: 8 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: 0.3 + idx * 0.06 }}
                    >
                      <div style={{
                        display: "flex",
                        justifyContent: "space-between",
                        marginBottom: "6px",
                        fontSize: "10px",
                        color: "var(--text-dim)",
                        fontFamily: "var(--font-mono)",
                      }}>
                        <span style={{ textTransform: "uppercase" }}>via {msg.channel}</span>
                        <span>{new Date(msg.received_at).toLocaleString()}</span>
                      </div>
                      <div style={{ color: "var(--text-secondary)", fontSize: "12px", fontStyle: "italic", lineHeight: "1.5" }}>
                        "{msg.raw_text}"
                      </div>
                    </motion.div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </motion.div>

      {/* Audit Trail Timeline */}
      <motion.div
        className="panel"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.35 }}
      >
        <div className="panel-header">
          <div className="panel-title">
            <div style={{
              background: "rgba(167, 139, 250, 0.12)",
              borderRadius: "6px",
              padding: "6px",
              display: "flex",
              alignItems: "center",
            }}>
              <Clock size={15} color="#a78bfa" />
            </div>
            <span>Audit Trail ({audit_log.length} events)</span>
          </div>
          <span style={{ fontSize: "11px", color: "var(--text-dim)", fontStyle: "italic" }}>
            Immutable agent reasoning log
          </span>
        </div>

        {audit_log.length === 0 ? (
          <div style={{ color: "var(--text-dim)", padding: "20px 0", textAlign: "center" }}>
            No audit log entries recorded.
          </div>
        ) : (
          <div className="timeline">
            {audit_log.map((entry, idx) => {
              const isManual = entry.agent_name === "manual_demo_override";
              return (
                <motion.div
                  key={entry.id}
                  className={`timeline-item ${isManual ? "manual" : ""}`}
                  initial={{ opacity: 0, x: -16 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.4 + idx * 0.08 }}
                >
                  <div className="timeline-header">
                    <span className={`agent-tag ${isManual ? "manual" : "ai"}`}>
                      {isManual ? "MANUAL OVERRIDE" : entry.agent_name.replace(/_/g, " ")}
                    </span>
                    <span className="timeline-time">
                      {new Date(entry.timestamp).toLocaleString()}
                    </span>
                  </div>
                  <div className="timeline-decision">
                    Decision: <code>{entry.decision}</code>
                  </div>
                  <div className="timeline-reasoning">
                    {entry.reasoning}
                  </div>
                </motion.div>
              );
            })}
          </div>
        )}
      </motion.div>
    </motion.div>
  );
}
