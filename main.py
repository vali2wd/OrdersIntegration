import logging
import signal

import boto3

from MQ.order_dto import StoreOrderRequest
from MQ.worker import QueueConsumer


log = logging.getLogger("orders")

def test_if_consuming_works(store_order: StoreOrderRequest) -> None:
    print("Consuming SQS works.", store_order)

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

    consumer = QueueConsumer(sqs, queue_url, dlq_url, model=StoreOrderRequest, handler=test_if_consuming_works)
    signal.signal(signal.SIGINT, lambda signum, frame: consumer.stop())
    signal.signal(signal.SIGTERM, lambda signum, frame: consumer.stop())
    consumer.run()


if __name__ == "__main__":
    main()