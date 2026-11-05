from enum import StrEnum

CLAIM_INSERT= """
INSERT INTO dbo.order_claims (order_id, status, attempts) VALUES (?, 'ordering', 1);
"""

CLAIM_UPDATE="""
UPDATE dbo.order_claims
SET status = 'ordering',
    attempts = attempts + 1,
    last_error = NULL,
    updated_at =SYSUTCDATETIME()
WHERE order_id = ? AND (status = 'failed' OR (status = 'ordering' AND updated_at < DATEADD(minute, ?, SYSUTCDATETIME())));
"""

SELECT_STATUS="""
SELECT status, attempts FROM dbo.order_claims WHERE order_id = ?;"""

MARK_SUCCESS="""
UPDATE dbo.order_claims
SET status = 'ordered', operator_ref = ?, updated_at = SYSUTCDATETIME()
WHERE order_id = ? AND status = 'ordering';
"""

MARK_FAIL="""
UPDATE dbo.order_claims
SET status = 'failed', operator_ref = ?, updated_at = SYSUTCDATETIME()
WHERE order_id = ? AND status = 'ordering';
"""

class ClaimResult(StrEnum):
    CLAIMED = "claimed"
    ALREADY_DONE = "already_done"
    IN_PROGRESS = "in_progress"