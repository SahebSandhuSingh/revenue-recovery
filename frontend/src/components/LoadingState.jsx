import React from "react";
import { motion } from "framer-motion";

export default function LoadingState({ message = "Loading dashboard data..." }) {
  return (
    <motion.div
      className="state-box"
      initial={{ opacity: 0, scale: 0.96 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.3 }}
    >
      <div style={{ position: "relative", width: 44, height: 44, marginBottom: 4 }}>
        {/* Outer glow ring */}
        <motion.div
          style={{
            position: "absolute",
            inset: -4,
            borderRadius: "50%",
            border: "2px solid rgba(108, 140, 255, 0.15)",
          }}
          animate={{ scale: [1, 1.2, 1], opacity: [0.4, 0.1, 0.4] }}
          transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
        />
        {/* Spinner */}
        <div className="spinner" style={{ width: 44, height: 44 }} />
      </div>
      <div className="state-title">Retrieving Live Metrics</div>
      <motion.div
        className="state-desc"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.2 }}
      >
        {message}
      </motion.div>
    </motion.div>
  );
}
