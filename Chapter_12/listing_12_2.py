"""
Listing 12.2 - Productor continuo con corrutinas get y put
Demuestra: productor que genera clientes cada segundo, workers infinitos,
cola con límite máximo. Usa await queue.put() y await queue.get().
"""
import asyncio
from asyncio import Queue
from random import randrange
from typing import List


class Product:
    def __init__(self, name: str, checkout_time: float):
        self.name = name
        self.checkout_time = checkout_time


class Customer:
    def __init__(self, customer_id: int, products: List[Product]):
        self.customer_id = customer_id
        self.products = products


def generate_customer(customer_id: int) -> Customer:
    all_products = [Product('cerveza', 2),
                    Product('plátanos', .5),
                    Product('salchicha', .2),
                    Product('pañales', .2)]
    products = [all_products[randrange(len(all_products))]
                for _ in range(randrange(1, 5))]
    return Customer(customer_id, products)


async def checkout_customer(queue: Queue, cashier_number: int):
    while True:
        customer: Customer = await queue.get()
        print(f'Cajero {cashier_number} atendiendo al cliente {customer.customer_id}')
        for product in customer.products:
            print(f"Cajero {cashier_number} escaneando "
                  f"{product.name} del cliente {customer.customer_id}")
            await asyncio.sleep(product.checkout_time)
        print(f'Cajero {cashier_number} terminó con el cliente {customer.customer_id}')
        queue.task_done()


async def customer_generator(queue: Queue):
    customer_count = 0

    while True:
        new_customers = [generate_customer(i)
                         for i in range(customer_count,
                                        customer_count + randrange(1, 4))]
        for customer in new_customers:
            print('Esperando para poner cliente en la cola...')
            await queue.put(customer)
            print(f'¡Cliente {customer.customer_id} en la cola!')
        customer_count += len(new_customers)
        await asyncio.sleep(1)


async def main():
    customer_queue = Queue(maxsize=5)

    customer_producer = asyncio.create_task(customer_generator(customer_queue))

    cashiers = [asyncio.create_task(checkout_customer(customer_queue, i))
                for i in range(3)]

    try:
        await asyncio.gather(customer_producer, *cashiers)
    except asyncio.CancelledError:
        pass


asyncio.run(main())
