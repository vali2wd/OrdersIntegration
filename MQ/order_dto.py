from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

class StoreOrderRequest(BaseModel):
    model_config = ConfigDict(frozen=True)
    event_id: str
    order_id: str

class WMSOrderRequest(BaseModel):
    model_config = ConfigDict()#(alias_generator=to_camel, populate_by_name=True)
    order_number: str
    reference_id: str

def to_wms_request(order: StoreOrderRequest) -> WMSOrderRequest:
    return WMSOrderRequest(
        order_number = order.order_id,
        reference_id = order.order_id,
    )

class WMSOrderResponse(BaseModel):
    wms_id: int = Field(validation_alias="id")
    reference_id: str
    order_number: str
