from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

class StoreOrderRequest(BaseModel):
    model_config = ConfigDict(frozen=True)
    event_id: str
    order_id: str

class WMSOrderRequest(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
    reference_id: str
    order_number: str

def to_WMSRequest(order: StoreOrderRequest) -> WMSOrderRequest:
    return WMSOrderRequest(
        reference_id = order.order_id,
        order_number = order.order_id,
    )
