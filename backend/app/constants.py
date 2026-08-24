"""Application-wide constants for Recoup."""

# Fixed root cause taxonomy for payment failures and revenue-at-risk events
ROOT_CAUSES = [
    "soft_decline",             # retryable technical failure (bank down, timeout, transient error)
    "hard_decline_or_expired",  # permanently invalid (card expired, mandate revoked, blocked)
    "dispute",                  # customer contests the charge/invoice (quality, terms, pricing)
    "cash_flow_distress",       # pattern indicates genuine financial hardship, repeated delinquency
    "forgetfulness",            # isolated oversight, otherwise clean payment history
]
