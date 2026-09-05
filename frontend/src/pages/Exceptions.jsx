import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { getRecoverySummary } from "../api";
import LoadingState from "../components/LoadingState";
import ErrorState from "../components/ErrorState";
import { pageTransition, staggerContainer, fadeInUp } from "../motion";
import { AlertTriangle, ArrowUpRight, ShieldAlert, CheckCircle } from "lucide-react";

export default function Exceptions({ refreshTrigger }) {
  const navigate = useNavigate();
  const [exceptions, setExceptions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchExceptions = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await getRecoverySummary();
      setExceptions(res.exception_list || []);
    } catch (err) {
      console.error("Failed to load exception list:", err);
      setError(err.response?.data?.detail || err.message || "Failed to load exceptions");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchExceptions();
  }, [refreshTrigger]);

  const formatINR = (val) =>
    new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
      maximumFractionDigits: 0,
    }).format(val);

  const getRootCauseBadgeClass = (rc) => {
    switch (rc) {
      case "soft_decline": return "badge-soft-decline";
      case "hard_decline_or_expired": return "badge-hard-decline";
      case "dispute": return "badge-dispute";
      case "cash_flow_distress": return "badge-cash-flow";
      case "forgetfulness": return "badge-forgetfulness";
      default: return "badge-planned";
    }
  };

  return (
    <motion.div {...pageTransition}>
      <div className="page-header">
        <motion.h1
          className="page-title"
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.4 }}
        >
          Exception & At-Risk Escalations
        </motion.h1>
        <motion.p
          className="page-subtitle"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.15 }}
        >
          High-priority cases: broken commitments, compliance blocks, and unresponsive outreach.
        </motion.p>
      </div>

      {/* Summary stat */}
      {!loading && !error && (
        <motion.div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "10px",
            padding: "10px 16px",
            background: exceptions.length > 0 ? "rgba(255, 92, 114, 0.06)" : "rgba(52, 217, 154, 0.06)",
            border: `1px solid ${exceptions.length > 0 ? "rgba(255, 92, 114, 0.15)" : "rgba(52, 217, 154, 0.15)"}`,
            borderRadius: "var(--radius-md)",
            marginBottom: "20px",
            fontSize: "13px",
          }}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
        >
          {exceptions.length > 0 ? (
            <>
              <ShieldAlert size={16} color="#ff5c72" />
              <span style={{ color: "var(--danger)" }}>
                <strong>{exceptions.length}</strong> active exceptions requiring attention
              </span>
            </>
          ) : (
            <>
              <CheckCircle size={16} color="#34d99a" />
              <span style={{ color: "var(--success)" }}>
                All recovery workflows operating normally
              </span>
            </>
          )}
        </motion.div>
      )}

      {loading ? (
        <LoadingState message="Scanning active exceptions and blocked actions..." />
      ) : error ? (
        <ErrorState error={error} onRetry={fetchExceptions} />
      ) : exceptions.length === 0 ? (
        <motion.div
          className="state-box"
          initial={{ opacity: 0, scale: 0.96 }}
          animate={{ opacity: 1, scale: 1 }}
        >
          <CheckCircle size={36} color="#34d99a" />
          <div className="state-title">No Active Exceptions</div>
          <div className="state-desc">All customer recovery workflows are within healthy parameters.</div>
        </motion.div>
      ) : (
        <motion.div
          className="table-container"
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15, duration: 0.4 }}
        >
          <table>
            <thead>
              <tr>
                <th>Customer</th>
                <th>Amount at Risk</th>
                <th>Root Cause</th>
                <th>Exception Reason</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {exceptions.map((ex, idx) => (
                <motion.tr
                  key={ex.event_id}
                  onClick={() => navigate(`/cases/${ex.event_id}`)}
                  style={{ cursor: "pointer" }}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: idx * 0.015 }}
                >
                  <td>
                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                      <div style={{
                        width: "6px",
                        height: "6px",
                        borderRadius: "50%",
                        background: "var(--danger)",
                        boxShadow: "0 0 8px var(--danger-glow)",
                        flexShrink: 0,
                      }} />
                      <span style={{ fontWeight: "600", color: "var(--danger)" }}>{ex.customer_id}</span>
                    </div>
                  </td>
                  <td style={{ fontWeight: "700", color: "#fff", fontFamily: "var(--font-mono)" }}>
                    {formatINR(ex.amount)}
                  </td>
                  <td>
                    {ex.root_cause ? (
                      <span className={`badge ${getRootCauseBadgeClass(ex.root_cause)}`}>
                        {ex.root_cause.replace(/_/g, " ")}
                      </span>
                    ) : (
                      <span style={{ color: "var(--text-dim)" }}>—</span>
                    )}
                  </td>
                  <td style={{ color: "#fca5a5", fontSize: "12px", maxWidth: "480px", lineHeight: "1.5" }}>
                    {ex.reason}
                  </td>
                  <td>
                    <motion.button
                      className="btn-primary"
                      style={{
                        padding: "5px 10px",
                        fontSize: "11px",
                        background: "linear-gradient(135deg, #dc2626, #b91c1c)",
                        boxShadow: "0 2px 8px rgba(220, 38, 38, 0.3)",
                      }}
                      onClick={(e) => {
                        e.stopPropagation();
                        navigate(`/cases/${ex.event_id}`);
                      }}
                      whileHover={{ scale: 1.06 }}
                      whileTap={{ scale: 0.94 }}
                    >
                      <span>Inspect</span>
                      <ArrowUpRight size={11} />
                    </motion.button>
                  </td>
                </motion.tr>
              ))}
            </tbody>
          </table>
        </motion.div>
      )}
    </motion.div>
  );
}
