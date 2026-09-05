import React from "react";
import { motion } from "framer-motion";
import { AlertCircle, RefreshCw } from "lucide-react";

export default function ErrorState({ error, onRetry }) {
  return (
    <motion.div
      className="state-box"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
    >
      <motion.div
        initial={{ scale: 0.5, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ type: "spring", stiffness: 300, damping: 15, delay: 0.1 }}
      >
        <AlertCircle size={40} color="#ff5c72" />
      </motion.div>
      <div className="state-title">Unable to Load Data</div>
      <div className="state-desc">
        {error || "An error occurred while connecting to the Recoup backend service."}
      </div>
      {onRetry && (
        <motion.button
          className="btn-primary"
          onClick={onRetry}
          style={{ marginTop: "18px" }}
          whileHover={{ scale: 1.04 }}
          whileTap={{ scale: 0.96 }}
        >
          <RefreshCw size={14} />
          <span>Try Again</span>
        </motion.button>
      )}
    </motion.div>
  );
}
