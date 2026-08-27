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

# Action lifecycle statuses
ACTION_STATUSES = [
    "planned",                    # intervention planned but not yet dispatched
    "dispatched",                 # message sent / retry initiated
    "delivered",                  # channel confirmed delivery (simulated in Step 5)
    "failed",                     # dispatch attempt failed
    "blocked_pending_review",     # compliance gate blocked this action
    "disputed_followup_needed",   # customer replied with a dispute
]

# Dispatch result codes from channel stubs
DISPATCH_RESULTS = [
    "success",       # channel accepted and delivered
    "queued",        # channel accepted, delivery pending
    "failed",        # channel rejected or errored
]

# Payment reconciliation sources
RECONCILIATION_SOURCES = [
    "webhook",       # real payment gateway webhook (future)
    "manual",        # manual confirmation by ops team
    "simulated",     # synthetic test data (Step 5)
]
