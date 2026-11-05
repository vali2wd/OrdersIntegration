import logging
import signal

import boto3
import httpx

from Clients.wms_client import WMSClient
from MQ.order_dto import StoreOrderRequest
from MQ.worker import QueueConsumer
from Persistence import order_repo
from order_processor import OrderProcessor

log = logging.getLogger("orders")

CONN_STR = (
    "Driver={ODBC Driver 18 for SQL Server};"
    "Server=DESKTOP-9ICFBLJ\\V17;"                 # the same name you use in SSMS
    "Database=OrdersProcessing;"
    "Trusted_Connection=yes;"           # your Windows login, so no password needed locally
    "TrustServerCertificate=yes;"       # Driver 18 encrypts by default; local dev only
)

def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s: %(message)s")

    sqs = boto3.client(
        "sqs",
        endpoint_url="http://localhost:9324",
        region_name="elasticmq",
        aws_access_key_id="x",
        aws_secret_access_key="x",
    )
    queue_url = sqs.get_queue_url(QueueName="orders.fifo")["QueueUrl"]
    dlq_url = sqs.get_queue_url(QueueName="orders-dlq.fifo")["QueueUrl"]

    signal.signal(signal.SIGTERM, lambda signum, frame: consumer.stop())

    with httpx.Client(
            timeout=httpx.Timeout(10.0, connect=3.0),
    ) as http:
        processor = OrderProcessor(
            order_repo=order_repo.OrderRepository(CONN_STR),
            wms=WMSClient(http),
        )
        consumer = QueueConsumer(
            sqs, queue_url, dlq_url,
            model=StoreOrderRequest,
            handler=processor.process_order,  # the bound method: takes just the order
        )

        signal.signal(signal.SIGINT, lambda signum, frame: consumer.stop())
        signal.signal(signal.SIGTERM, lambda signum, frame: consumer.stop())

        consumer.run()  # blocks here until Ctrl+C or SIGTERM



if __name__ == "__main__":
    main()
