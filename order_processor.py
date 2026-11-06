from Clients.wms_client import WMSClient
from Errors.errors import TransientError
from MQ.order_dto import StoreOrderRequest, to_wms_request
from Persistence.Claims.order_claims import ClaimResult
from Persistence.order_repo import OrderRepository
import logging

log = logging.getLogger("order_processors")

class OrderProcessor():
    def __init__(self, order_repo : OrderRepository, wms : WMSClient):
        self._order_repo = order_repo
        self._wms = wms

    def process_order(self, order: StoreOrderRequest) -> None:
        claim = self._order_repo.try_claim(order.order_id)

        if claim is ClaimResult.ALREADY_DONE:
            log.info("order %s already sent, acknowledging duplicate", order.order_id)
            return  # normal return → the consumer acknowledges
        if claim is ClaimResult.IN_PROGRESS:
            raise TransientError(f"order {order.order_id} is being processed by another worker")

        # CLAIMED: this order is ours now
        try:
            wms_request = to_wms_request(order)
            wms_ref = self._wms.order(
                wms_request
            )
        except Exception as ex:
            self._order_repo.mark_failed(order.order_id, str(ex))  # 'failed' rows can be claimed again later
            raise

        self._order_repo.mark_done(order.order_id, wms_ref.wms_id)
        log.info("order %s sent to WMS as %s", order.order_id, wms_ref)
