import logging
import time
from collections.abc import Callable

import httpx
from pydantic import ValidationError
from tenacity import (
    RetryCallState,
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    stop_after_delay,
    wait_exponential_jitter,
)

from Errors.errors import AuthError
from Errors.errors import PermanentError
from Errors.errors import RateLimitedError
from MQ.order_dto import StoreOrderRequest, WMSOrderRequest

API_URL = "http://localhost:5055"

from Clients.Confirmation import Confirmation
from Errors.errors import TransientError

log = logging.getLogger("wms_client")


def problem_summary(resp: httpx.Response) -> str:
    """ASP.NET returns application/problem+json for errors; use it if present."""
    try:
        body = resp.json()
    except ValueError:
        return resp.text[:200]
    if isinstance(body, dict):
        return str(body.get("detail") or body.get("title") or body.get("errors") or body)[:200]
    return str(body)[:200]

class WMSClient:
    def __init__(
            self,
            client: httpx.Client,
            *,
            max_attempts: int = 5,
            max_total_seconds = 60,
            max_wait_seconds: int = 60,
            sleep: Callable[[float], None] = time.sleep,
            ) -> None:
            self._client = client
            self._max_attempts = max_attempts
            self._max_total_seconds = max_total_seconds
            self._max_wait_seconds = max_wait_seconds
            self._sleep = sleep
            self._backoff = wait_exponential_jitter(multiplier=0.5, max=max_wait_seconds)

    def order(self, OrderRequest : WMSOrderRequest) -> Confirmation:
        retrying = Retrying(
            retry=retry_if_exception_type(TransientError),
            stop=stop_after_attempt(self._max_attempts) | stop_after_delay(self._max_total_seconds),
            wait=self._wait,
            sleep=self._sleep,
            reraise=True
        )

        return retrying(self._order_once, OrderRequest)

    def _order_once(self, request: WMSOrderRequest)-> Confirmation:
        try:
            log.info("processing order %s, claim=%s", request.order_number, request.reference_id)
            response = self._client.post(
                API_URL + "/api/orders",
                json=request.model_dump(mode="json")
            )
            log.info("calling WMS for %s", request.order_number)
        except httpx.TimeoutException as te:
            raise TransientError(f"network error: {type(te).__name__}") from te

        return self._interpret(response)

    def _wait(self, state: RetryCallState) -> float:
        error = state.outcome.exception() if state.outcome else None
        if isinstance(error, RateLimitedError) and error.retry_after is not None:
            return min(error.retry_after, self._max_wait_seconds)
        return self._backoff  # exponential backoff with jitter

    def _interpret(self, resp: httpx.Response) -> Confirmation:
        status = resp.status_code

        if status in (200, 201):
            try:
                body = WMSOrderRequest.model_validate_json(resp.content)
            except ValidationError as ex:
                # It probably succeeded, but we can't tell what it created. A human must look.
                raise PermanentError(f"{status} with unreadable body: {ex.errors()[0]['msg']}") from ex
            return Confirmation(operator_ref=body.order_number, wms_id=body. replayed=status == 200)

        if status in (401, 403):
            raise AuthError(f"{status} from operator: check the API key")

        if status == 409:
            # Same key, original request still being processed on their side.
            raise TransientError("409: request with this idempotency key still in progress")

        if status == 429:
            raise RateLimitedError(f"429: rate limited for {resp.headers.get("Retry-After")} seconds")

        if status >= 500:
            raise TransientError(f"{status} from operator")

        # 400, 404, 422 ...: the request itself is wrong. Retrying sends the same wrong request.
        raise PermanentError(f"{status} from operator: {problem_summary(resp)}")