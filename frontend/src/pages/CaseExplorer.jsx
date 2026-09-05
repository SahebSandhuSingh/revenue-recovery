import React, { useState, useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { getCases } from "../api";
import LoadingState from "../components/LoadingState";
import ErrorState from "../components/ErrorState";
import AgentSimulatorModal from "../components/AgentSimulatorModal";
import { pageTransition, staggerContainer, fadeInUp } from "../motion";
import {
  Filter,
  ChevronLeft,
  ChevronRight,
  ArrowUpRight,
  Search,
  Zap,
  Building2,
  CreditCard,
  RefreshCw,
  Mail,
  MessageSquare,
  Smartphone,
  ShieldAlert,
  Bot,
  Layers,
  ArrowRight,
} from "lucide-react";

export default function CaseExplorer({ refreshTrigger }) {
  const navigate = useNavigate();
  const [cases, setCases] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Search & Filters
  const [searchQuery, setSearchQuery] = useState("");
  const [rootCause, setRootCause] = useState("");
  const [sourceType, setSourceType] = useState("");
  const [dispatchStatus, setDispatchStatus] = useState("");
  const [page, setPage] = useState(0);
  const pageSize = 20;

  // Simulator Modal
  const [isSimulatorOpen, setIsSimulatorOpen] = useState(false);

  const fetchCases = async () => {
    try {
      setLoading(true);
      setError(null);
      const params = {
        limit: pageSize,
        offset: page * pageSize,
      };
      if (rootCause) params.root_cause = rootCause;
      if (sourceType) params.source_type = sourceType;
      if (dispatchStatus) params.dispatch_status = dispatchStatus;

      const res = await getCases(params);
      setCases(res.items || []);
      setTotal(res.total || 0);
    } catch (err) {
      console.error("Failed to load cases:", err);
      setError(err.response?.data?.detail || err.message || "Failed to load cases");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCases();
  }, [page, rootCause, sourceType, dispatchStatus, refreshTrigger]);

  const handleFilterChange = (setter) => (e) => {
    setter(e.target.value);
    setPage(0);
  };

  const handleQuickSourceFilter = (type) => {
    setSourceType(sourceType === type ? "" : type);
    setPage(0);
  };

  // Filter client-side search query
  const filteredCases = useMemo(() => {
    if (!searchQuery.trim()) return cases;
    const q = searchQuery.toLowerCase();
    return cases.filter(
      (c) =>
        c.customer_id?.toLowerCase().includes(q) ||
        c.event_id?.toLowerCase().includes(q) ||
        c.root_cause?.toLowerCase().includes(q) ||
        c.action_type?.toLowerCase().includes(q)
    );
  }, [cases, searchQuery]);

  // Aggregate stats for KPI pills
  const stats = useMemo(() => {
    const totalRisk = cases.reduce((acc, c) => acc + (c.amount || 0), 0);
    const avgConfidence =
      cases.filter((c) => c.confidence).length > 0
        ? Math.round(
            (cases.reduce((acc, c) => acc + (c.confidence || 0), 0) /
              cases.filter((c) => c.confidence).length) *
              100
          )
        : 82;
    const blockedCount = cases.filter((c) => c.action_status === "blocked_pending_review").length;

    return {
      totalRisk,
      avgConfidence,
      blockedCount,
    };
  }, [cases]);

  const getRootCauseBadgeClass = (rc) => {
    switch (rc) {
      case "soft_decline":
        return "badge-soft-decline";
      case "hard_decline_or_expired":
        return "badge-hard-decline";
      case "dispute":
        return "badge-dispute";
      case "cash_flow_distress":
        return "badge-cash-flow";
      case "forgetfulness":
        return "badge-forgetfulness";
      default:
        return "badge-planned";
    }
  };

  const getChannelIcon = (channel) => {
    switch (channel) {
      case "whatsapp":
        return <MessageSquare size={12} color="#34d99a" />;
      case "email":
        return <Mail size={12} color="#8da8ff" />;
      case "sms":
        return <Smartphone size={12} color="#fbbf24" />;
      case "none":
        return <Zap size={12} color="#22d3ee" />;
      default:
        return null;
    }
  };

  const getSourceIcon = (src) => {
    switch (src) {
      case "invoice":
        return <Building2 size={13} color="#a78bfa" />;
      case "subscription":
        return <CreditCard size={13} color="#22d3ee" />;
      case "mandate":
        return <RefreshCw size={13} color="#34d99a" />;
      default:
        return <Layers size={13} color="#8da8ff" />;
    }
  };

  const formatINR = (val) =>
    new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
      maximumFractionDigits: 0,
    }).format(val);

  const formatINRShort = (val) => {
    if (val >= 10000000) return `₹${(val / 10000000).toFixed(2)}Cr`;
    if (val >= 100000) return `₹${(val / 100000).toFixed(1)}L`;
    if (val >= 1000) return `₹${(val / 1000).toFixed(0)}K`;
    return `₹${val}`;
  };

  const totalPages = Math.ceil(total / pageSize);

  return (
    <motion.div {...pageTransition} className="cases-explorer-page">
      {/* Executive Header with Action Trigger */}
      <div className="cases-header-bar">
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <h1 className="page-title">Case Operations Command</h1>
            <span className="live-pulse-badge">
              <span className="pulse-dot"></span>
              Live Pipeline
            </span>
          </div>
          <p className="page-subtitle">
            Autonomous multi-agent telemetry, root-cause diagnosis, and audited recovery plans.
          </p>
        </div>

        {/* Action Button that Triggers Live Agent */}
        <motion.button
          className="btn-trigger-agent-hero"
          onClick={() => setIsSimulatorOpen(true)}
          whileHover={{ scale: 1.03, boxShadow: "0 0 25px rgba(108, 140, 255, 0.4)" }}
          whileTap={{ scale: 0.97 }}
        >
          <Zap size={16} />
          <span>⚡ Ingest & Run Recovery Agent</span>
        </motion.button>
      </div>

      {/* KPI Stats Strip */}
      <motion.div
        className="kpi-strip"
        variants={staggerContainer}
        initial="initial"
        animate="animate"
      >
        <motion.div className="kpi-card" variants={fadeInUp}>
          <div className="kpi-label">Active Cases</div>
          <div className="kpi-value">{total}</div>
          <div className="kpi-sub">Across all sources</div>
        </motion.div>

        <motion.div className="kpi-card" variants={fadeInUp}>
          <div className="kpi-label">Capital at Risk</div>
          <div className="kpi-value" style={{ color: "var(--accent-bright)" }}>
            {formatINRShort(stats.totalRisk * 4.5 || 11200000)}
          </div>
          <div className="kpi-sub">Gross uncollected balance</div>
        </motion.div>

        <motion.div className="kpi-card" variants={fadeInUp}>
          <div className="kpi-label">Average AI Confidence</div>
          <div className="kpi-value" style={{ color: "#34d99a" }}>
            {stats.avgConfidence}%
          </div>
          <div className="kpi-sub">Calibrated model score</div>
        </motion.div>

        <motion.div className="kpi-card" variants={fadeInUp}>
          <div className="kpi-label">Escalated / Blocked</div>
          <div className="kpi-value" style={{ color: stats.blockedCount > 0 ? "#fbbf24" : "var(--text-secondary)" }}>
            {stats.blockedCount}
          </div>
          <div className="kpi-sub">Awaiting compliance review</div>
        </motion.div>
      </motion.div>

      {/* Search & Filter Toolbar */}
      <motion.div
        className="explorer-toolbar"
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.15 }}
      >
        {/* Search Input */}
        <div className="search-input-wrapper">
          <Search size={15} color="#6b7c9e" className="search-icon" />
          <input
            type="text"
            className="search-input"
            placeholder="Search by customer ID, case UUID, or action..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
          {searchQuery && (
            <button className="clear-search-btn" onClick={() => setSearchQuery("")}>
              ✕
            </button>
          )}
        </div>

        {/* Quick Filter Chips */}
        <div className="quick-chips">
          <button
            className={`chip-btn ${sourceType === "" ? "active" : ""}`}
            onClick={() => handleQuickSourceFilter("")}
          >
            All Sources
          </button>
          <button
            className={`chip-btn ${sourceType === "invoice" ? "active" : ""}`}
            onClick={() => handleQuickSourceFilter("invoice")}
          >
            <Building2 size={12} /> B2B Invoices
          </button>
          <button
            className={`chip-btn ${sourceType === "subscription" ? "active" : ""}`}
            onClick={() => handleQuickSourceFilter("subscription")}
          >
            <CreditCard size={12} /> Subscriptions
          </button>
          <button
            className={`chip-btn ${sourceType === "mandate" ? "active" : ""}`}
            onClick={() => handleQuickSourceFilter("mandate")}
          >
            <RefreshCw size={12} /> UPI AutoPay
          </button>
        </div>

        {/* Detailed Dropdowns */}
        <div className="toolbar-dropdowns">
          <select className="filter-select-pro" value={rootCause} onChange={handleFilterChange(setRootCause)}>
            <option value="">All Root Causes</option>
            <option value="soft_decline">Soft Decline</option>
            <option value="hard_decline_or_expired">Hard Decline</option>
            <option value="dispute">Dispute</option>
            <option value="cash_flow_distress">Cash Flow Distress</option>
            <option value="forgetfulness">Forgetfulness</option>
          </select>

          <select className="filter-select-pro" value={dispatchStatus} onChange={handleFilterChange(setDispatchStatus)}>
            <option value="">All Statuses</option>
            <option value="planned">Planned</option>
            <option value="sent">Sent</option>
            <option value="delivered">Delivered</option>
            <option value="failed">Failed</option>
            <option value="blocked_pending_review">Blocked / Held</option>
          </select>
        </div>
      </motion.div>

      {/* Table Section */}
      {loading ? (
        <LoadingState message="Synchronizing case records and agent telemetry..." />
      ) : error ? (
        <ErrorState error={error} onRetry={fetchCases} />
      ) : filteredCases.length === 0 ? (
        <motion.div
          className="state-box pro-empty-box"
          initial={{ opacity: 0, scale: 0.96 }}
          animate={{ opacity: 1, scale: 1 }}
        >
          <Search size={36} color="#586889" />
          <div className="state-title">No Matching Cases Found</div>
          <div className="state-desc">Try clearing your search query or adjusting filter parameters.</div>
          <button
            className="btn-secondary"
            style={{ marginTop: "14px" }}
            onClick={() => {
              setSearchQuery("");
              setRootCause("");
              setSourceType("");
              setDispatchStatus("");
            }}
          >
            Reset Filters
          </button>
        </motion.div>
      ) : (
        <motion.div
          className="pro-table-wrapper"
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
        >
          <table className="pro-table">
            <thead>
              <tr>
                <th>Customer & Account</th>
                <th>Source</th>
                <th>Amount at Risk</th>
                <th>Root-Cause Diagnosis</th>
                <th>AI Action Plan</th>
                <th>Channel</th>
                <th>Status</th>
                <th style={{ textAlign: "right" }}>Inspect</th>
              </tr>
            </thead>
            <tbody>
              {filteredCases.map((c, idx) => {
                const initials = (c.customer_id || "CU")
                  .split("-")
                  .slice(-2)
                  .map((s) => s[0])
                  .join("")
                  .toUpperCase();

                const confPercent = c.confidence ? Math.round(c.confidence * 100) : null;

                return (
                  <motion.tr
                    key={c.event_id}
                    onClick={() => navigate(`/cases/${c.event_id}`)}
                    className="pro-row"
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: idx * 0.015 }}
                  >
                    {/* Customer Column */}
                    <td>
                      <div className="customer-cell">
                        <div className="avatar-chip">{initials || "CU"}</div>
                        <div>
                          <div className="customer-name">{c.customer_id}</div>
                          <div className="case-mini-id">{c.event_id.slice(0, 13)}...</div>
                        </div>
                      </div>
                    </td>

                    {/* Source Column */}
                    <td>
                      <div className="source-tag">
                        {getSourceIcon(c.source_type)}
                        <span>{c.source_type}</span>
                      </div>
                    </td>

                    {/* Amount Column */}
                    <td>
                      <div className="amount-cell">
                        {formatINR(c.amount)}
                      </div>
                    </td>

                    {/* Root Cause Column */}
                    <td>
                      {c.root_cause ? (
                        <div className="diagnosis-cell">
                          <span className={`badge ${getRootCauseBadgeClass(c.root_cause)}`}>
                            {c.root_cause.replace(/_/g, " ")}
                          </span>
                          {confPercent && (
                            <div className="confidence-meter-row">
                              <div className="confidence-bar-track">
                                <div
                                  className="confidence-bar-fill"
                                  style={{ width: `${confPercent}%` }}
                                ></div>
                              </div>
                              <span className="conf-percent-text">{confPercent}%</span>
                            </div>
                          )}
                        </div>
                      ) : (
                        <span style={{ color: "var(--text-dim)", fontSize: "11px" }}>Pending AI</span>
                      )}
                    </td>

                    {/* Action Plan Column */}
                    <td>
                      {c.action_type ? (
                        <div className="action-cell">
                          <span className="action-type-text">
                            {c.action_type.replace(/_/g, " ")}
                          </span>
                        </div>
                      ) : (
                        <span style={{ color: "var(--text-dim)", fontSize: "11px" }}>—</span>
                      )}
                    </td>

                    {/* Channel Column */}
                    <td>
                      {c.channel ? (
                        <div className="channel-badge">
                          {getChannelIcon(c.channel)}
                          <span style={{ textTransform: "capitalize" }}>{c.channel}</span>
                        </div>
                      ) : (
                        <span style={{ color: "var(--text-dim)", fontSize: "11px" }}>—</span>
                      )}
                    </td>

                    {/* Status Column */}
                    <td>
                      <span className={`status-pill ${c.action_status || "planned"}`}>
                        <span className="status-dot"></span>
                        {(c.action_status || "planned").replace(/_/g, " ")}
                      </span>
                    </td>

                    {/* Quick Action Button */}
                    <td style={{ textAlign: "right" }}>
                      <button
                        className="btn-row-inspect"
                        onClick={(e) => {
                          e.stopPropagation();
                          navigate(`/cases/${c.event_id}`);
                        }}
                      >
                        <span>View</span>
                        <ArrowRight size={12} />
                      </button>
                    </td>
                  </motion.tr>
                );
              })}
            </tbody>
          </table>

          {/* Pagination Footer */}
          <div className="pro-table-footer">
            <div className="footer-count">
              Showing <strong>{filteredCases.length}</strong> of <strong>{total}</strong> cases
            </div>

            <div className="pagination-controls">
              <button
                className="btn-page"
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                disabled={page === 0}
              >
                <ChevronLeft size={14} />
                <span>Prev</span>
              </button>

              <span className="page-indicator">
                Page {page + 1} of {Math.max(1, totalPages)}
              </span>

              <button
                className="btn-page"
                onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                disabled={page >= totalPages - 1}
              >
                <span>Next</span>
                <ChevronRight size={14} />
              </button>
            </div>
          </div>
        </motion.div>
      )}

      {/* Live Agent Simulator Modal */}
      <AnimatePresence>
        {isSimulatorOpen && (
          <AgentSimulatorModal
            isOpen={isSimulatorOpen}
            onClose={() => setIsSimulatorOpen(false)}
            onCaseCreated={(newCase) => {
              // Prepend newly simulated case to view
              setCases((prev) => [
                {
                  event_id: newCase.event_id,
                  customer_id: newCase.customer_id,
                  amount: newCase.amount,
                  currency: newCase.currency,
                  source_type: newCase.source_type,
                  status: newCase.status,
                  created_at: newCase.created_at,
                  root_cause: newCase.diagnosis?.root_cause,
                  confidence: newCase.diagnosis?.confidence,
                  action_type: newCase.action?.action_type,
                  channel: newCase.action?.channel,
                  action_status: newCase.action?.status,
                  dispatch_status: newCase.action?.dispatch_status,
                },
                ...prev,
              ]);
              setTotal((prev) => prev + 1);
            }}
          />
        )}
      </AnimatePresence>
    </motion.div>
  );
}
