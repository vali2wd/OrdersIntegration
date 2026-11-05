import logging

from Clients.wms_client import WMSClient
from MQ.order_dto import StoreOrderRequest, to_WMSRequest
from Errors.errors import TransientError, PermanentError
from Persistence.Claims.order_claims import ClaimResult
from Persistence.order_repo import OrderRepository

log = logging.getLogger("service")

class OrderService:
        def __init__(self, order_repo: OrderRepository, wmsClient: WMSClient) -> None:
            self._order_repo = order_repo
            self._wmsClient = wmsClient

        def handle(self, storeOrderRequest: StoreOrderRequest):
            claim = self._order_repo.try_claim(storeOrderRequest.order_id)

            if claim is ClaimResult.ALREADY_DONE:
                log.info(f"Order {storeOrderRequest.order_id} already done")
                return
            if claim is ClaimResult.IN_PROGRESS:
                raise TransientError(f"ticket {storeOrderRequest.order_id} is being handled by another process")

            try:
                order_response = self._wmsClient.order(storeOrderRequest)
            except PermanentError as pe:
                self._order_repo.mark_failed(storeOrderRequest.order_id, str(pe))
                raise
            except TransientError as te:
                self._order_repo.mark_failed(storeOrderRequest.order_id, str(te))
                raise

            self._order_repo.mark_done(storeOrderRequest.order_id, order_response)
            log.info("order %s processed successfully with WMS Id %s", storeOrderRequest.order_id, order_response)