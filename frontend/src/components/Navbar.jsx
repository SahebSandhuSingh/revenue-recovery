import React from "react";
import { NavLink } from "react-router-dom";
import { motion } from "framer-motion";
import { LayoutDashboard, Layers, AlertTriangle, ShieldCheck, RefreshCw } from "lucide-react";

export default function Navbar({ onRefresh, isRefreshing }) {
  return (
    <header className="navbar">
      <div className="navbar-inner">
        <div className="brand-group">
          <motion.div
            className="brand-logo"
            whileHover={{ scale: 1.08, rotate: 2 }}
            whileTap={{ scale: 0.95 }}
            transition={{ type: "spring", stiffness: 400, damping: 12 }}
          >
            R
          </motion.div>
          <span className="brand-title">Recoup</span>
          <span className="brand-badge">Audit & Recovery</span>
        </div>

        <nav className="nav-links">
          <NavLink
            to="/"
            className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`}
            end
          >
            <LayoutDashboard size={15} />
            <span>Overview</span>
          </NavLink>

          <NavLink
            to="/cases"
            className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`}
          >
            <Layers size={15} />
            <span>Case Explorer</span>
          </NavLink>

          <NavLink
            to="/exceptions"
            className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`}
          >
            <AlertTriangle size={15} />
            <span>Exceptions</span>
          </NavLink>

          <NavLink
            to="/compliance"
            className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`}
          >
            <ShieldCheck size={15} />
            <span>Compliance</span>
          </NavLink>
        </nav>

        <motion.button
          className="btn-refresh"
          onClick={onRefresh}
          disabled={isRefreshing}
          title="Refresh dashboard data"
          whileHover={{ scale: 1.03 }}
          whileTap={{ scale: 0.97 }}
        >
          <motion.div
            animate={isRefreshing ? { rotate: 360 } : { rotate: 0 }}
            transition={isRefreshing ? { repeat: Infinity, duration: 0.8, ease: "linear" } : { duration: 0 }}
            style={{ display: "flex", alignItems: "center" }}
          >
            <RefreshCw size={14} />
          </motion.div>
          <span>{isRefreshing ? "Refreshing…" : "Refresh"}</span>
        </motion.button>
      </div>
    </header>
  );
}
