import React, { useState } from "react";
import { motion } from "framer-motion";
import { simulateCase } from "../api";
import {
  Zap,
  X,
  Bot,
  ShieldCheck,
  ArrowRight,
  CheckCircle2,
  AlertCircle,
  Building2,
  CreditCard,
  RefreshCw,
  FileText,
  Copy,
  Check,
  Sparkles,
  Send,
} from "lucide-react";
import { useNavigate } from "react-router-dom";

const SCENARIO_PRESETS = [
  {
    id: "b2b_cash_crunch",
    title: "B2B Overdue Invoice (Liquidity Crunch)",
    icon: Building2,
    source_type: "invoice",
    customer_id: "CUST-PUNE-SUPPLIES-22",
    amount: 145000,
    days_overdue: 28,
    failure_reason: "Invoice is 28 days overdue against net-30 terms. Customer's last 2 payments were delayed by 15+ days.",
    expected_cause: "cash_flow_distress",
    color: "#fbbf24",
  },
  {
    id: "saas_sub_soft_decline",
    title: "SaaS Subscription Payment Glitch",
    icon: CreditCard,
    source_type: "subscription",
    customer_id: "USER-SAAS-ENTERPRISE-89",
    amount: 14999,
    days_overdue: 0,
    failure_reason: "Payment gateway returned error 'bank_switch_timeout' during automated recurring monthly billing.",
    expected_cause: "soft_decline",
    color: "#22d3ee",
  },
  {
    id: "b2b_disputed_goods",
    title: "Disputed Retail Goods Delivery",
    icon: FileText,
    source_type: "invoice",
    customer_id: "CUST-DELHI-KIRANA-MART",
    amount: 92000,
    days_overdue: 14,
    failure_reason: "Customer filed formal dispute claiming 3 cartons of FMCG cooking oil were received broken upon delivery.",
    expected_cause: "dispute",
    color: "#a78bfa",
  },
  {
    id: "consumer_upi_mandate",
    title: "UPI AutoPay Mandate Expired",
    icon: RefreshCw,
    source_type: "mandate",
    customer_id: "CUST-UPI-MANDATE-402",
    amount: 3500,
    days_overdue: 0,
    failure_reason: "Mandate debit failed with NPCI response code 'MANDATE_EXPIRED_OR_REVOKED'.",
    expected_cause: "hard_decline_or_expired",
    color: "#f87171",
  },
];

export default function AgentSimulatorModal({ isOpen, onClose, onCaseCreated }) {
  const navigate = useNavigate();
  const [selectedPreset, setSelectedPreset] = useState(SCENARIO_PRESETS[0]);
  const [customerId, setCustomerId] = useState(SCENARIO_PRESETS[0].customer_id);
  const [amount, setAmount] = useState(SCENARIO_PRESETS[0].amount);
  const [sourceType, setSourceType] = useState(SCENARIO_PRESETS[0].source_type);
  const [failureReason, setFailureReason] = useState(SCENARIO_PRESETS[0].failure_reason);
  const [daysOverdue, setDaysOverdue] = useState(SCENARIO_PRESETS[0].days_overdue);

  const [executing, setExecuting] = useState(false);
  const [executionStep, setExecutionStep] = useState(0); // 1: Diagnosis, 2: Intervention, 3: Compliance
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [copied, setCopied] = useState(false);

  const handleSelectPreset = (preset) => {
    setSelectedPreset(preset);
    setCustomerId(preset.customer_id);
    setAmount(preset.amount);
    setSourceType(preset.source_type);
    setFailureReason(preset.failure_reason);
    setDaysOverdue(preset.days_overdue);
    setResult(null);
    setError(null);
  };

  const handleRunAgent = async () => {
    try {
      setExecuting(true);
      setError(null);
      setResult(null);
      setExecutionStep(1);

      // UI progression through the agent assembly line
      const stepTimer1 = setTimeout(() => setExecutionStep(2), 1200);
      const stepTimer2 = setTimeout(() => setExecutionStep(3), 2400);

      const payload = {
        customer_id: customerId.trim() || "SIM-CUSTOMER-01",
        amount: Number(amount) || 5000,
        source_type: sourceType,
        currency: "INR",
        scenario_title: selectedPreset ? selectedPreset.title : "Custom Simulation",
        failure_reason: failureReason,
        days_overdue: sourceType === "invoice" ? Number(daysOverdue) : 0,
      };

      const res = await simulateCase(payload);

      clearTimeout(stepTimer1);
      clearTimeout(stepTimer2);
      setExecutionStep(3);
      setTimeout(() => {
        setResult(res);
        setExecuting(false);
        if (onCaseCreated) onCaseCreated(res);
      }, 600);
    } catch (err) {
      console.error("Agent simulation failed:", err);
      setError(err.response?.data?.detail || err.message || "Simulation failed to execute");
      setExecuting(false);
    }
  };

  const handleCopyDraft = (text) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (!isOpen) return null;

  const formatINR = (val) =>
    new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
      maximumFractionDigits: 0,
    }).format(val);

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <motion.div
        className="simulator-modal"
        onClick={(e) => e.stopPropagation()}
        initial={{ opacity: 0, scale: 0.95, y: 20 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 20 }}
        transition={{ duration: 0.25 }}
      >
        {/* Modal Header */}
        <div className="simulator-header">
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <div className="agent-icon-badge">
              <Zap size={18} color="#8da8ff" />
            </div>
            <div>
              <h2 className="simulator-title">Live Agent Simulator</h2>
              <p className="simulator-subtitle">
                Inject a payment failure and watch the multi-agent assembly line diagnose & draft resolution in real time.
              </p>
            </div>
          </div>
          <button className="btn-close" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        <div className="simulator-body">
          {/* Preset Scenario Selector */}
          {!result && (
            <div className="scenario-selector-section">
              <div className="section-label">1. Choose a Test Scenario or Customize:</div>
              <div className="presets-grid">
                {SCENARIO_PRESETS.map((preset) => {
                  const Icon = preset.icon;
                  const isSelected = selectedPreset?.id === preset.id;
                  return (
                    <button
                      key={preset.id}
                      type="button"
                      className={`preset-card ${isSelected ? "selected" : ""}`}
                      onClick={() => handleSelectPreset(preset)}
                    >
                      <div className="preset-card-header">
                        <Icon size={16} color={preset.color} />
                        <span className="preset-badge" style={{ color: preset.color, borderColor: `${preset.color}40` }}>
                          {preset.source_type}
                        </span>
                      </div>
                      <div className="preset-card-title">{preset.title}</div>
                      <div className="preset-card-meta">
                        <span>{formatINR(preset.amount)}</span>
                        <span>•</span>
                        <span>{preset.customer_id.slice(0, 16)}</span>
                      </div>
                    </button>
                  );
                })}
              </div>

              {/* Editable Fields */}
              <div className="simulator-form">
                <div className="form-row">
                  <div className="form-group">
                    <label>Customer Identifier</label>
                    <input
                      type="text"
                      className="sim-input"
                      value={customerId}
                      onChange={(e) => setCustomerId(e.target.value)}
                      placeholder="e.g. CUST-ENTERPRISE-01"
                      disabled={executing}
                    />
                  </div>
                  <div className="form-group">
                    <label>Amount (INR ₹)</label>
                    <input
                      type="number"
                      className="sim-input"
                      value={amount}
                      onChange={(e) => setAmount(e.target.value)}
                      placeholder="Amount at risk"
                      disabled={executing}
                    />
                  </div>
                  <div className="form-group">
                    <label>Source Type</label>
                    <select
                      className="sim-input"
                      value={sourceType}
                      onChange={(e) => setSourceType(e.target.value)}
                      disabled={executing}
                    >
                      <option value="invoice">B2B Invoice</option>
                      <option value="subscription">Subscription</option>
                      <option value="checkout">Checkout</option>
                      <option value="mandate">UPI AutoPay</option>
                    </select>
                  </div>
                  {sourceType === "invoice" && (
                    <div className="form-group">
                      <label>Days Overdue</label>
                      <input
                        type="number"
                        className="sim-input"
                        value={daysOverdue}
                        onChange={(e) => setDaysOverdue(e.target.value)}
                        disabled={executing}
                      />
                    </div>
                  )}
                </div>

                <div className="form-group" style={{ marginTop: "12px" }}>
                  <label>Failure Context / Telemetry Payload</label>
                  <textarea
                    className="sim-input sim-textarea"
                    value={failureReason}
                    onChange={(e) => setFailureReason(e.target.value)}
                    rows={2}
                    placeholder="Enter error code, customer status, or context notes..."
                    disabled={executing}
                  />
                </div>
              </div>
            </div>
          )}

          {/* Execution Stepper Animation */}
          {executing && (
            <motion.div
              className="stepper-box"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
            >
              <div className="stepper-title">
                <Sparkles size={16} color="#8da8ff" className="spin-slow" />
                <span>AI Agents Processing Case Live...</span>
              </div>
              <div className="stepper-steps">
                <div className={`step-item ${executionStep >= 1 ? "active" : ""}`}>
                  <div className="step-num">{executionStep > 1 ? "✓" : "1"}</div>
                  <div className="step-content">
                    <div className="step-name">Root-Cause Detective Agent</div>
                    <div className="step-desc">Analyzing failure telemetry, error codes & customer payment history</div>
                  </div>
                </div>

                <div className={`step-item ${executionStep >= 2 ? "active" : ""}`}>
                  <div className="step-num">{executionStep > 2 ? "✓" : "2"}</div>
                  <div className="step-content">
                    <div className="step-name">Intervention Router Agent</div>
                    <div className="step-desc">Determining optimal recovery strategy & drafting personalized outreach</div>
                  </div>
                </div>

                <div className={`step-item ${executionStep >= 3 ? "active" : ""}`}>
                  <div className="step-num">{executionStep >= 3 ? "✓" : "3"}</div>
                  <div className="step-content">
                    <div className="step-name">Compliance Guardian Gate</div>
                    <div className="step-desc">Verifying fair debt collection limits & contact caps before dispatch</div>
                  </div>
                </div>
              </div>
            </motion.div>
          )}

          {/* Error display */}
          {error && (
            <div className="sim-error">
              <AlertCircle size={16} color="#ff5c72" />
              <span>{error}</span>
            </div>
          )}

          {/* Structured Result Display */}
          {result && !executing && (
            <motion.div
              className="sim-result-card"
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3 }}
            >
              <div className="result-banner">
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <CheckCircle2 size={18} color="#34d99a" />
                  <span style={{ fontWeight: "700", color: "#6ee7b7", fontSize: "14px" }}>
                    Agent Execution Complete
                  </span>
                </div>
                <span className="case-id-tag">Case ID: {result.event_id.slice(0, 8)}...</span>
              </div>

              {/* Two Column Result Presentation */}
              <div className="result-grid">
                {/* Left: Diagnosis */}
                <div className="result-card">
                  <div className="card-label">
                    <Bot size={14} color="#8da8ff" />
                    <span>Diagnosed Root Cause</span>
                  </div>
                  {result.diagnosis ? (
                    <div>
                      <div style={{ display: "flex", alignItems: "center", gap: "8px", margin: "8px 0" }}>
                        <span className="badge badge-cash-flow" style={{ fontSize: "13px", padding: "4px 10px" }}>
                          {result.diagnosis.root_cause.replace(/_/g, " ")}
                        </span>
                        <span className="confidence-pill">
                          {((result.diagnosis.confidence || 0) * 100).toFixed(0)}% Confidence
                        </span>
                      </div>
                      <p className="reasoning-text">
                        "{result.diagnosis.reasoning}"
                      </p>
                    </div>
                  ) : (
                    <span style={{ color: "var(--text-dim)" }}>No diagnosis returned</span>
                  )}
                </div>

                {/* Right: Intervention */}
                <div className="result-card">
                  <div className="card-label">
                    <Send size={14} color="#34d99a" />
                    <span>Recovery Action & Channel</span>
                  </div>
                  {result.action ? (
                    <div>
                      <div style={{ display: "flex", alignItems: "center", gap: "8px", margin: "8px 0", flexWrap: "wrap" }}>
                        <strong style={{ color: "#fff", fontSize: "13px" }}>
                          {result.action.action_type.replace(/_/g, " ")}
                        </strong>
                        <span className="badge badge-planned" style={{ textTransform: "uppercase", fontSize: "10px" }}>
                          via {result.action.channel}
                        </span>
                        <span className="badge badge-sent" style={{ fontSize: "10px" }}>
                          Priority: {result.action.priority}
                        </span>
                      </div>
                      <div style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "11px", color: "var(--text-dim)" }}>
                        <ShieldCheck size={13} color={result.compliance_status === "passed" ? "#34d99a" : "#fbbf24"} />
                        <span>Compliance Gate: <strong style={{ color: "#fff" }}>{result.compliance_status}</strong></span>
                      </div>
                    </div>
                  ) : (
                    <span style={{ color: "var(--text-dim)" }}>No action returned</span>
                  )}
                </div>
              </div>

              {/* Drafted Outreach Message Box */}
              {result.action?.message_draft && (
                <div className="draft-preview-box">
                  <div className="draft-header">
                    <span style={{ fontSize: "11px", fontWeight: "600", textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--text-muted)" }}>
                      AI-Drafted Customer Outreach
                    </span>
                    <button
                      className="btn-copy"
                      onClick={() => handleCopyDraft(result.action.message_draft)}
                    >
                      {copied ? <Check size={12} color="#34d99a" /> : <Copy size={12} />}
                      <span>{copied ? "Copied" : "Copy Draft"}</span>
                    </button>
                  </div>
                  <div className="draft-content">
                    {result.action.message_draft}
                  </div>
                </div>
              )}

              {/* Action Buttons */}
              <div className="result-actions">
                <button
                  className="btn-secondary"
                  onClick={() => {
                    setResult(null);
                    setExecutionStep(0);
                  }}
                >
                  <RefreshCw size={13} />
                  <span>Run Another Test</span>
                </button>
                <button
                  className="btn-primary"
                  onClick={() => {
                    onClose();
                    navigate(`/cases/${result.event_id}`);
                  }}
                >
                  <span>Inspect Full Case & Audit Trail</span>
                  <ArrowRight size={14} />
                </button>
              </div>
            </motion.div>
          )}
        </div>

        {/* Modal Footer (When not completed) */}
        {!result && (
          <div className="simulator-footer">
            <button className="btn-secondary" onClick={onClose} disabled={executing}>
              Cancel
            </button>
            <button
              className="btn-primary btn-run-agent"
              onClick={handleRunAgent}
              disabled={executing}
            >
              <Zap size={14} />
              <span>{executing ? "Running Multi-Agent Pipeline..." : "Execute Agent Pipeline"}</span>
            </button>
          </div>
        )}
      </motion.div>
    </div>
  );
}
