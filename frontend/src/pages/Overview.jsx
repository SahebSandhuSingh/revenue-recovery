import React, { useState, useEffect } from "react";
import { motion } from "framer-motion";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  CartesianGrid,
} from "recharts";
import { getRecoverySummary } from "../api";
import HonestyBanner from "../components/HonestyBanner";
import LoadingState from "../components/LoadingState";
import ErrorState from "../components/ErrorState";
import AnimatedCounter from "../components/AnimatedCounter";
import { pageTransition, staggerContainer, fadeInUp } from "../motion";
import { Activity, ShieldAlert, CheckCircle2, TrendingUp, ArrowDownRight, ArrowUpRight } from "lucide-react";

const ROOT_CAUSE_LABELS = {
  soft_decline: "Soft Decline",
  hard_decline_or_expired: "Hard Decline",
  dispute: "Dispute",
  cash_flow_distress: "Cash Flow",
  forgetfulness: "Forgetfulness",
};

const PIE_COLORS = ["#22d3ee", "#ff5c72", "#a78bfa", "#f5a623", "#34d99a"];

const FUNNEL_STAGES = [
  { key: "diagnosed", label: "Diagnosed by Root-Cause Agent", icon: "🔍" },
  { key: "routed", label: "Routed to Recovery Action", icon: "🔀" },
  { key: "dispatched", label: "Dispatched / Executed", icon: "📤" },
  { key: "customer_replied", label: "Customer Inbound Reply", icon: "💬" },
  { key: "promise_made", label: "Promise-to-Pay Extracted", icon: "🤝" },
  { key: "recovered", label: "Revenue Recovered", icon: "✅" },
];

export default function Overview({ refreshTrigger }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await getRecoverySummary();
      setData(res);
    } catch (err) {
      console.error("Failed to load recovery summary:", err);
      setError(err.response?.data?.detail || err.message || "Failed to fetch metrics");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [refreshTrigger]);

  if (loading) return <LoadingState message="Fetching recovery metrics and root-cause breakdown..." />;
  if (error) return <ErrorState error={error} onRetry={fetchData} />;
  if (!data) return null;

  const recoveryRateData = Object.entries(data.by_root_cause || {}).map(([key, val]) => {
    const rate = val.total_amount > 0 ? (val.recovered_amount / val.total_amount) * 100 : 0;
    return {
      name: ROOT_CAUSE_LABELS[key] || key,
      rate: Number(rate.toFixed(1)),
      recovered: val.recovered_amount,
      total: val.total_amount,
      count: val.count,
    };
  });

  const distributionData = Object.entries(data.by_root_cause || {}).map(([key, val]) => ({
    name: ROOT_CAUSE_LABELS[key] || key,
    value: val.count,
  }));

  const formatINR = (val) =>
    new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
      maximumFractionDigits: 0,
    }).format(val);

  const formatINRShort = (val) => {
    if (val >= 10000000) return `₹${(val / 10000000).toFixed(1)}Cr`;
    if (val >= 100000) return `₹${(val / 100000).toFixed(1)}L`;
    if (val >= 1000) return `₹${(val / 1000).toFixed(0)}K`;
    return `₹${val}`;
  };

  const statCards = [
    {
      label: "Total Events",
      value: data.total_events,
      icon: <Activity size={18} />,
      iconBg: "rgba(108, 140, 255, 0.12)",
      iconColor: "#8da8ff",
      sub: "Ingested failure & invoice cases",
    },
    {
      label: "Amount at Risk",
      value: data.total_amount_at_risk,
      formatter: formatINRShort,
      icon: <ShieldAlert size={18} />,
      iconBg: "rgba(245, 166, 35, 0.12)",
      iconColor: "#f5a623",
      valueColor: "#fbbf24",
      sub: "Gross debt balance in pipeline",
    },
    {
      label: "Total Recovered",
      value: data.recovered_amount,
      formatter: formatINRShort,
      icon: <CheckCircle2 size={18} />,
      iconBg: "rgba(52, 217, 154, 0.12)",
      iconColor: "#34d99a",
      valueColor: "#6ee7b7",
      sub: "Via silent retries & kept promises",
    },
    {
      label: "Recovery Rate",
      value: data.overall_recovery_rate * 100,
      suffix: "%",
      icon: <TrendingUp size={18} />,
      iconBg: "rgba(167, 139, 250, 0.12)",
      iconColor: "#a78bfa",
      valueColor: "#c4b5fd",
      sub: "Recovered / amount at risk",
    },
  ];

  const tooltipStyle = {
    background: "rgba(15, 20, 35, 0.95)",
    border: "1px solid rgba(100, 120, 180, 0.2)",
    borderRadius: "8px",
    color: "#eef2ff",
    fontSize: "12px",
    backdropFilter: "blur(8px)",
    boxShadow: "0 4px 20px rgba(0,0,0,0.4)",
  };

  return (
    <motion.div {...pageTransition}>
      {/* Page Header */}
      <div className="page-header">
        <motion.h1
          className="page-title"
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.4 }}
        >
          Executive Recovery Dashboard
        </motion.h1>
        <motion.p
          className="page-subtitle"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.15 }}
        >
          Root-cause diagnosis, automated intervention performance, and audited recovery figures.
        </motion.p>
      </div>

      {/* Stats Cards */}
      <motion.div className="stats-grid" variants={staggerContainer} initial="initial" animate="animate">
        {statCards.map((card, i) => (
          <motion.div
            key={card.label}
            className="stat-card"
            variants={fadeInUp}
            whileHover={{ y: -4, transition: { duration: 0.2 } }}
          >
            <div className="stat-header">
              <span className="stat-label">{card.label}</span>
              <div
                className="stat-icon"
                style={{ background: card.iconBg, color: card.iconColor }}
              >
                {card.icon}
              </div>
            </div>
            <div className="stat-value" style={card.valueColor ? { color: card.valueColor } : {}}>
              <AnimatedCounter
                value={card.value}
                duration={1400}
                formatter={card.formatter}
                suffix={card.suffix || ""}
              />
            </div>
            <div className="stat-sub">{card.sub}</div>
          </motion.div>
        ))}
      </motion.div>

      {/* Honesty Banner */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.35 }}
      >
        <HonestyBanner />
      </motion.div>

      {/* Charts */}
      <motion.div
        className="panel-grid"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4, duration: 0.45 }}
      >
        {/* Bar Chart */}
        <div className="panel">
          <div className="panel-header">
            <div className="panel-title">
              <span>Recovery Rate by Root Cause</span>
            </div>
            <span style={{ fontSize: "11px", color: "var(--text-dim)" }}>% of amount recovered</span>
          </div>
          <div style={{ height: "280px", width: "100%" }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={recoveryRateData} margin={{ top: 10, right: 10, left: -20, bottom: 24 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(100,120,180,0.1)" />
                <XAxis
                  dataKey="name"
                  stroke="#586889"
                  fontSize={11}
                  angle={-12}
                  textAnchor="end"
                  interval={0}
                  tickLine={false}
                />
                <YAxis stroke="#586889" fontSize={11} unit="%" domain={[0, 100]} tickLine={false} />
                <Tooltip
                  contentStyle={tooltipStyle}
                  cursor={{ fill: "rgba(108, 140, 255, 0.06)" }}
                  formatter={(value, name, props) => [
                    `${value}% (${formatINR(props.payload.recovered)} / ${formatINR(props.payload.total)})`,
                    "Recovery Rate",
                  ]}
                />
                <Bar dataKey="rate" radius={[6, 6, 0, 0]} animationDuration={1200} animationEasing="ease-out">
                  {recoveryRateData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={PIE_COLORS[index % PIE_COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Pie Chart */}
        <div className="panel">
          <div className="panel-header">
            <div className="panel-title">
              <span>Event Distribution</span>
            </div>
            <span style={{ fontSize: "11px", color: "var(--text-dim)" }}>by root cause diagnosis</span>
          </div>
          <div style={{ height: "280px", width: "100%", display: "flex", alignItems: "center" }}>
            <ResponsiveContainer width="55%" height="100%">
              <PieChart>
                <Pie
                  data={distributionData}
                  cx="50%"
                  cy="50%"
                  innerRadius={55}
                  outerRadius={90}
                  paddingAngle={3}
                  dataKey="value"
                  animationDuration={1000}
                  animationEasing="ease-out"
                  stroke="none"
                >
                  {distributionData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={PIE_COLORS[index % PIE_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip contentStyle={tooltipStyle} />
              </PieChart>
            </ResponsiveContainer>
            <div style={{ width: "45%", display: "flex", flexDirection: "column", gap: "10px", paddingLeft: "8px" }}>
              {distributionData.map((item, idx) => (
                <motion.div
                  key={item.name}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "10px",
                    fontSize: "12px",
                    padding: "4px 0",
                  }}
                  initial={{ opacity: 0, x: 12 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.5 + idx * 0.06 }}
                >
                  <div
                    style={{
                      width: "10px",
                      height: "10px",
                      borderRadius: "3px",
                      background: PIE_COLORS[idx % PIE_COLORS.length],
                      boxShadow: `0 0 8px ${PIE_COLORS[idx % PIE_COLORS.length]}40`,
                      flexShrink: 0,
                    }}
                  />
                  <span style={{ color: "var(--text-secondary)", flex: 1 }}>{item.name}</span>
                  <span style={{ fontWeight: "700", color: "#fff", fontFamily: "var(--font-mono)", fontSize: "13px" }}>
                    {item.value}
                  </span>
                </motion.div>
              ))}
            </div>
          </div>
        </div>
      </motion.div>

      {/* Recovery Funnel */}
      <motion.div
        className="panel"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.5, duration: 0.45 }}
      >
        <div className="panel-header">
          <div className="panel-title">
            <span>Recovery Funnel Progression</span>
          </div>
          <span style={{ fontSize: "12px", color: "var(--text-dim)" }}>From ingestion → recovered revenue</span>
        </div>
        <div className="funnel-list">
          {FUNNEL_STAGES.map((stage, idx) => {
            const val = data.funnel[stage.key] || 0;
            const isLast = idx === FUNNEL_STAGES.length - 1;
            const prevVal = idx > 0 ? (data.funnel[FUNNEL_STAGES[idx - 1].key] || 0) : val;
            const dropRate = prevVal > 0 ? ((1 - val / prevVal) * 100).toFixed(0) : 0;

            return (
              <motion.div
                key={stage.key}
                className="funnel-item"
                initial={{ opacity: 0, x: -16 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.55 + idx * 0.08 }}
                style={isLast ? {
                  background: "rgba(52, 217, 154, 0.06)",
                  borderColor: "rgba(52, 217, 154, 0.2)",
                } : {}}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                  <span style={{ fontSize: "16px" }}>{stage.icon}</span>
                  <span
                    className="funnel-stage-name"
                    style={isLast ? { color: "#6ee7b7", fontWeight: 700 } : {}}
                  >
                    {idx + 1}. {stage.label}
                  </span>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                  {idx > 0 && dropRate > 0 && !isLast && (
                    <span style={{
                      fontSize: "10px",
                      color: "var(--text-dim)",
                      display: "flex",
                      alignItems: "center",
                      gap: "2px",
                    }}>
                      <ArrowDownRight size={10} />
                      {dropRate}% drop
                    </span>
                  )}
                  <span
                    className="funnel-stage-val"
                    style={isLast ? { color: "#34d99a" } : {}}
                  >
                    <AnimatedCounter value={val} duration={1000 + idx * 150} />
                  </span>
                </div>
              </motion.div>
            );
          })}
        </div>
      </motion.div>
    </motion.div>
  );
}
