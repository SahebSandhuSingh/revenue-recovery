import React, { useState } from "react";
import { BrowserRouter, Routes, Route, useLocation } from "react-router-dom";
import { AnimatePresence } from "framer-motion";
import Navbar from "./components/Navbar";
import Overview from "./pages/Overview";
import CaseExplorer from "./pages/CaseExplorer";
import CaseDetail from "./pages/CaseDetail";
import Exceptions from "./pages/Exceptions";
import Compliance from "./pages/Compliance";

function AnimatedRoutes({ refreshTrigger }) {
  const location = useLocation();

  return (
    <AnimatePresence mode="wait">
      <Routes location={location} key={location.pathname}>
        <Route path="/" element={<Overview refreshTrigger={refreshTrigger} />} />
        <Route path="/cases" element={<CaseExplorer refreshTrigger={refreshTrigger} />} />
        <Route path="/cases/:event_id" element={<CaseDetail />} />
        <Route path="/exceptions" element={<Exceptions refreshTrigger={refreshTrigger} />} />
        <Route path="/compliance" element={<Compliance refreshTrigger={refreshTrigger} />} />
      </Routes>
    </AnimatePresence>
  );
}

export default function App() {
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const handleRefresh = () => {
    setIsRefreshing(true);
    setRefreshTrigger((prev) => prev + 1);
    setTimeout(() => setIsRefreshing(false), 600);
  };

  return (
    <BrowserRouter>
      <div className="app-container">
        <Navbar onRefresh={handleRefresh} isRefreshing={isRefreshing} />
        <main className="main-content">
          <AnimatedRoutes refreshTrigger={refreshTrigger} />
        </main>
      </div>
    </BrowserRouter>
  );
}
