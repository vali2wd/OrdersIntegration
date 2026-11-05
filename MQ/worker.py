import json
import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from botocore.exceptions import BotoCoreError, ClientError
from pydantic import BaseModel, ValidationError

from Errors.errors import PermanentError, TransientError

log = logging.getLogger("consumer")

class Outcome(StrEnum):
    DONE = "done"
    DEAD_LETTERED = "dead_lettered"
    RETRY_LATER = "retry_later"


@dataclass(frozen=True)
class Envelope:
    """The SQS wrapper around a message: everything except the business data."""

    message_id: str
    receipt_handle: str
    receive_count: int
    group_id: str
    body: str

    @classmethod
    def from_sqs(cls, msg: dict) -> "Envelope":
        attrs = msg.get("Attributes", {})
        return cls(
            message_id=msg["MessageId"],
            receipt_handle=msg["ReceiptHandle"],
            receive_count=int(attrs.get("ApproximateReceiveCount", "1")),
            group_id=attrs.get("MessageGroupId", ""),
            body=msg["Body"],
        )


class QueueConsumer[M: BaseModel]:
    def __init__(
        self,
        sqs,
        queue_url: str,
        dlq_url: str,
        model: type[M],
        handler: Callable[[M], None],
        *,
        wait_seconds: int = 10,
        visibility_timeout: int = 120,
    ) -> None:
        self._sqs = sqs
        self._queue_url = queue_url
        self._dlq_url = dlq_url
        self._model = model
        self._handler = handler
        self._wait_seconds = wait_seconds
        self._visibility_timeout = visibility_timeout
        self._stop = threading.Event()

    def stop(self) -> None:
        log.info("stop requested")
        self._stop.set()

    def run(self) -> None:
        log.info("consuming %s", self._queue_url)
        failures = 0
        while not self._stop.is_set():
            try:
                batch = self._receive()
            except (BotoCoreError, ClientError):
                failures += 1
                delay = min(30, 2**failures)
                log.exception("receive failed, retrying in %s s", delay)
                self._stop.wait(delay)
                continue
            failures = 0
            self._process_batch(batch)
        log.info("consumer stopped")

    def _receive(self) -> list[Envelope]:
        resp = self._sqs.receive_message(
            QueueUrl=self._queue_url,
            MaxNumberOfMessages=10,
            WaitTimeSeconds=self._wait_seconds,
            VisibilityTimeout=self._visibility_timeout,
            MessageSystemAttributeNames=["ApproximateReceiveCount", "MessageGroupId"],
        )
        return [Envelope.from_sqs(m) for m in resp.get("Messages", [])]

    def _process_batch(self, batch: list[Envelope]) -> None:
        failed_groups: set[str] = set()
        for env in batch:
            if env.group_id in failed_groups:
                log.info("skipping %s: an earlier message in group %s failed", env.message_id[:8], env.group_id)
                continue  # left in the queue; comes back after the visibility timeout, still in order
            if self._process_one(env) is Outcome.RETRY_LATER:
                failed_groups.add(env.group_id)

    def _process_one(self, env: Envelope) -> Outcome:
        try:
            item = self._model.model_validate_json(env.body)
        except ValidationError as ex:
            self._dead_letter(env, f"invalid message: {ex.error_count()} error(s): {ex.errors()[0]['msg']}")
            return Outcome.DEAD_LETTERED

        try:
            self._handler(item)
        except PermanentError as ex:
            self._dead_letter(env, str(ex))
            return Outcome.DEAD_LETTERED
        except TransientError as ex:
            log.warning("message %s attempt %d failed, will retry: %s", env.message_id[:8], env.receive_count, ex)
            return Outcome.RETRY_LATER
        except Exception:
            # Unknown failure: don't lose it. Leave it for redelivery; after
            log.exception("unexpected error on message %s", env.message_id[:8])
            return Outcome.RETRY_LATER

        self._ack(env)
        return Outcome.DONE

    def _ack(self, env: Envelope) -> None:
        self._sqs.delete_message(QueueUrl=self._queue_url, ReceiptHandle=env.receipt_handle)

    def _dead_letter(self, env: Envelope, reason: str) -> None:
        log.warning("dead letter requested: %s", reason)