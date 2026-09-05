import React from "react";
import { Info } from "lucide-react";

export default function HonestyBanner() {
  return (
    <div className="honesty-banner">
      <Info size={18} className="honesty-banner-icon" />
      <div className="honesty-banner-text">
        <strong>Known Limitation & Verification Note:</strong> Recovery figures include simulated silent-retry outcomes and manually-confirmed payments. Full automated reconciliation requires Razorpay webhook integration (documented as a known limitation).
      </div>
    </div>
  );
}
