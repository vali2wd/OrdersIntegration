from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

class StoreOrderRequest(BaseModel):
    model_config = ConfigDict(frozen=True)
    event_id: str
    order_id: str

class WMSOrderRequest(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
    order_number: str
    reference_id: str

def to_WMSRequest(order: StoreOrderRequest) -> WMSOrderRequest:
    return WMSOrderRequest(
        order_number = order.order_id,
        reference_id = "reference-" + order.order_id, #TODO: e corect sa pasam order_id pentru reference_id?
    )
