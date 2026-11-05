import logging
from contextlib import closing
import pyodbc
from Persistence.Claims.order_claims import *

log = logging.getLogger("repository")

def is_duplicate_key(ex:pyodbc.IntegrityError) -> bool:
    message = str(ex.args[1]) if len(ex.args) > 1 else str(ex)
    return any(code in message for code in ("(2627)", "(2601)"))

class OrderRepository:
    def __init__(self, _conn_str: str, stale_minutes: int = 5) -> None:
        self._conn_str = _conn_str
        self._stale_minutes = stale_minutes

    def _connect(self):
        return closing(pyodbc.connect(self._conn_str))

    def _finish(self, sql: str, value: str, order_id: str) -> None:
        with self._connect() as conn, conn:
            if conn.execute(sql, value, order_id).rowcount != 1:
                log.warning("ticket %s was no longer ours when finishing", order_id)

    def try_claim(self, order_id: str) -> ClaimResult:
        with self._connect() as conn:
            try:
                with conn:
                    conn.execute(CLAIM_INSERT, order_id)
                return ClaimResult.CLAIMED
            except pyodbc.IntegrityError as ex:
                if not is_duplicate_key(ex):
                    raise
                log.info("ticket %s already has a claim row", order_id)

            with conn:
                taken = conn.execute(CLAIM_UPDATE, order_id, -self._stale_minutes).rowcount == 1
            if taken:
                return ClaimResult.CLAIMED

            row = conn.execute(SELECT_STATUS, order_id).fetchone()
            if row is not None and row.status == "ordered":
                return ClaimResult.ALREADY_DONE
            return ClaimResult.IN_PROGRESS

    def mark_done(self, order_id: str, operator_ref: str) -> None:
        self._finish(MARK_SUCCESS, operator_ref, order_id)

    def mark_failed(self, order_id: str, error: str) -> None:
        self._finish(MARK_FAIL, error[:400], order_id)