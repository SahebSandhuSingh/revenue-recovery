import React, { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { getComplianceRecords } from "../api";
import LoadingState from "../components/LoadingState";
import ErrorState from "../components/ErrorState";
import { pageTransition } from "../motion";
import { ShieldAlert, UserX, AlertOctagon, ShieldCheck } from "lucide-react";

export default function Compliance({ refreshTrigger }) {
  const [records, setRecords] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchCompliance = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await getComplianceRecords(true);
      setRecords(res.items || []);
    } catch (err) {
      console.error("Failed to load compliance records:", err);
      setError(err.response?.data?.detail || err.message || "Failed to load compliance records");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCompliance();
  }, [refreshTrigger]);

  return (
    <motion.div {...pageTransition}>
      <div className="page-header">
        <motion.h1
          className="page-title"
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.4 }}
        >
          Compliance & Frequency Caps
        </motion.h1>
        <motion.p
          className="page-subtitle"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.15 }}
        >
          Hard compliance stopping rules gating AI outreach. Customers hitting contact caps (max 3) or broken promise limits (max 1) are blocked.
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
            background: records.length > 0 ? "rgba(255, 92, 114, 0.06)" : "rgba(52, 217, 154, 0.06)",
            border: `1px solid ${records.length > 0 ? "rgba(255, 92, 114, 0.15)" : "rgba(52, 217, 154, 0.15)"}`,
            borderRadius: "var(--radius-md)",
            marginBottom: "20px",
            fontSize: "13px",
          }}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
        >
          {records.length > 0 ? (
            <>
              <ShieldAlert size={16} color="#ff5c72" />
              <span style={{ color: "var(--danger)" }}>
                <strong>{records.length}</strong> customers blocked from automated outreach
              </span>
            </>
          ) : (
            <>
              <ShieldCheck size={16} color="#34d99a" />
              <span style={{ color: "var(--success)" }}>
                All accounts within safe contact guardrails
              </span>
            </>
          )}
        </motion.div>
      )}

      {loading ? (
        <LoadingState message="Auditing customer contact caps and escalation registers..." />
      ) : error ? (
        <ErrorState error={error} onRetry={fetchCompliance} />
      ) : records.length === 0 ? (
        <motion.div
          className="state-box"
          initial={{ opacity: 0, scale: 0.96 }}
          animate={{ opacity: 1, scale: 1 }}
        >
          <ShieldCheck size={36} color="#34d99a" />
          <div className="state-title">No Blocked Customers</div>
          <div className="state-desc">All customer accounts are within safe contact frequency guardrails.</div>
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
                <th>Contacts</th>
                <th>Broken Promises</th>
                <th>Escalation Reason</th>
                <th>Status</th>
                <th>Last Contact</th>
              </tr>
            </thead>
            <tbody>
              {records.map((r, idx) => (
                <motion.tr
                  key={r.id}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: idx * 0.02 }}
                >
                  <td>
                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                      <UserX size={14} color="#ff5c72" />
                      <span style={{ fontWeight: "700", color: "var(--danger)" }}>{r.customer_id}</span>
                    </div>
                  </td>
                  <td>
                    <div style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "6px",
                    }}>
                      {/* Mini progress bar */}
                      <div style={{
                        width: "40px",
                        height: "4px",
                        background: "rgba(100, 120, 180, 0.1)",
                        borderRadius: "2px",
                        overflow: "hidden",
                      }}>
                        <motion.div
                          style={{
                            height: "100%",
                            background: r.contact_count >= 3 ? "var(--danger)" : "var(--accent)",
                            borderRadius: "2px",
                          }}
                          initial={{ width: 0 }}
                          animate={{ width: `${Math.min((r.contact_count / 3) * 100, 100)}%` }}
                          transition={{ delay: 0.3 + idx * 0.03, duration: 0.5 }}
                        />
                      </div>
                      <span style={{
                        fontWeight: "700",
                        fontFamily: "var(--font-mono)",
                        fontSize: "12px",
                        color: r.contact_count >= 3 ? "var(--danger)" : "var(--text-secondary)",
                      }}>
                        {r.contact_count}/3
                      </span>
                    </div>
                  </td>
                  <td>
                    <span style={{
                      fontWeight: "700",
                      fontFamily: "var(--font-mono)",
                      fontSize: "12px",
                      color: r.broken_promises_count >= 1 ? "var(--danger)" : "var(--text-secondary)",
                    }}>
                      {r.broken_promises_count || 0}
                    </span>
                  </td>
                  <td style={{
                    color: "#fca5a5",
                    fontSize: "12px",
                    maxWidth: "420px",
                    lineHeight: "1.5",
                  }}>
                    {r.escalation_reason || "Contact cap or broken promise limit reached"}
                  </td>
                  <td>
                    <span className="badge badge-blocked">
                      <AlertOctagon size={10} />
                      <span>Blocked</span>
                    </span>
                  </td>
                  <td style={{
                    color: "var(--text-dim)",
                    fontSize: "12px",
                    fontFamily: "var(--font-mono)",
                  }}>
                    {r.last_contact_at
                      ? new Date(r.last_contact_at).toLocaleString()
                      : "Never"}
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
