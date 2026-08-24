"""Application-wide constants for Recoup."""

# Fixed root cause taxonomy for payment failures and revenue-at-risk events
ROOT_CAUSES = [
    "soft_decline",             # retryable technical failure (bank down, timeout, transient error)
    "hard_decline_or_expired",  # permanently invalid (card expired, mandate revoked, blocked)
    "dispute",                  # customer contests the charge/invoice (quality, terms, pricing)
    "cash_flow_distress",       # pattern indicates genuine financial hardship, repeated delinquency
    "forgetfulness",            # isolated oversight, otherwise clean payment history
]

# Action taxonomy for intervention router
ACTION_TYPES = [
    "silent_retry",                  # retry payment with no customer contact
    "payment_method_update_request", # ask customer to update card/mandate
    "dispute_resolution_draft",      # AI-drafted response to a dispute
    "payment_plan_offer",            # structured installment/deferred offer
    "friendly_nudge",                # simple reminder, low-pressure
]

# Communication channels ("none" is valid only for silent_retry)
CHANNELS = ["none", "email", "whatsapp", "sms", "voice"]

# Intervention priorities
PRIORITIES = ["low", "medium", "high"]

# Inbound message reply types
REPLY_TYPES = [
    "promise_to_pay",
    "dispute",
    "payment_made",
    "other",
]

# Promise-to-pay statuses
PROMISE_STATUSES = [
    "pending",
    "kept",
    "broken",
]

# Compliance & contact frequency guardrail thresholds
MAX_CONTACTS_BEFORE_ESCALATION = 3
MAX_BROKEN_PROMISES_BEFORE_ESCALATION = 1
