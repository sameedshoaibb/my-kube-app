import pika
import time

RABBITMQ_URL = "amqp://guest:guest@rabbitmq:5672/"

# Retry loop
for i in range(10):
    try:
        print("🔌 Attempting RabbitMQ connection...")
        connection = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
        channel = connection.channel()
        break
    except pika.exceptions.AMQPConnectionError as e:
        print(f"⏳ RabbitMQ not ready, retrying in 3s... ({i+1}/10)")
        time.sleep(3)
else:
    raise RuntimeError("❌ Could not connect to RabbitMQ after 10 attempts.")

# Continue with normal logic
channel.queue_declare(queue='default')

def callback(ch, method, properties, body):
    print(f"✅ Received message: {body.decode()}")
    print("🛠️  Processing...")
    time.sleep(2)
    print("✅ Done processing")

channel.basic_consume(queue='default', on_message_callback=callback, auto_ack=True)
print("👷 Consumer waiting for messages...")
channel.start_consuming()
 