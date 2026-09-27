import json

from app.database.connection import get_connection
from app.database.redis_connection import redis_client


# ============================================================
# REDIS KEYS
# ============================================================

def customer_cache_key(customer_id):
    return f"customer:{customer_id}"


def customer_search_cache_key(name):
    return f"customers:search:{name.strip().lower()}"


# ============================================================
# SEARCH CUSTOMERS
# ============================================================

def search_customers(name=""):

    search_value = name.strip()

    cache_key = customer_search_cache_key(search_value)

    # ========================================================
    # CHECK REDIS FIRST
    # ========================================================

    cached_data = redis_client.get(cache_key)

    if cached_data:

        return json.loads(cached_data)

    connection = None
    cursor = None

    try:

        query = """
            SELECT
                id,
                name
            FROM customer
        """

        params = []

        if search_value:

            query += """
                WHERE name LIKE %s
            """

            params.append(f"%{search_value}%")

        query += """
            ORDER BY name
        """

        connection = get_connection()

        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            query,
            params
        )

        rows = cursor.fetchall()

        # ====================================================
        # SAVE DB RESULT INTO REDIS
        # ====================================================

        redis_client.setex(
            cache_key,
            300,  # 5 minutes
            json.dumps(rows)
        )

        return rows

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ============================================================
# CREATE CUSTOMER
# ============================================================

def create_customer(name):

    customer_name = name.strip()

    connection = None
    cursor = None

    try:

        connection = get_connection()

        cursor = connection.cursor(dictionary=True)

        # ====================================================
        # CHECK DUPLICATE
        # ====================================================

        cursor.execute(
            """
            SELECT id
            FROM customer
            WHERE name = %s
            LIMIT 1
            """,
            (customer_name,)
        )

        existing_customer = cursor.fetchone()

        if existing_customer:

            return {
                "error": "Customer already exists",
                "status": 409
            }

        # ====================================================
        # INSERT CUSTOMER
        # ====================================================

        cursor.execute(
            """
            INSERT INTO customer (name)
            VALUES (%s)
            """,
            (customer_name,)
        )

        customer_id = cursor.lastrowid

        connection.commit()

        customer = {
            "id": customer_id,
            "name": customer_name
        }

        # ====================================================
        # SAVE INTO REDIS
        # ====================================================

        redis_client.setex(
            customer_cache_key(customer_id),
            300,
            json.dumps(customer)
        )

        # ====================================================
        # INVALIDATE CUSTOMER SEARCH CACHE
        # ====================================================

        invalidate_customer_search_cache()

        return customer

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ============================================================
# UPDATE CUSTOMER
# ============================================================

def update_customer(customer_id, name):

    customer_name = name.strip()

    connection = None
    cursor = None

    try:

        connection = get_connection()

        cursor = connection.cursor(dictionary=True)

        # ====================================================
        # CHECK CUSTOMER EXISTS
        # ====================================================

        cursor.execute(
            """
            SELECT id
            FROM customer
            WHERE id = %s
            """,
            (customer_id,)
        )

        existing_customer = cursor.fetchone()

        if not existing_customer:

            return {
                "error": "Customer not found",
                "status": 404
            }

        # ====================================================
        # CHECK DUPLICATE NAME
        # ====================================================

        cursor.execute(
            """
            SELECT id
            FROM customer
            WHERE name = %s
              AND id <> %s
            """,
            (
                customer_name,
                customer_id
            )
        )

        duplicate_customer = cursor.fetchone()

        if duplicate_customer:

            return {
                "error":
                    "Another customer with this name already exists",
                "status": 409
            }

        # ====================================================
        # UPDATE CUSTOMER
        # ====================================================

        cursor.execute(
            """
            UPDATE customer
            SET name = %s
            WHERE id = %s
            """,
            (
                customer_name,
                customer_id
            )
        )

        connection.commit()

        customer = {
            "id": int(customer_id),
            "name": customer_name
        }

        # ====================================================
        # UPDATE REDIS
        # ====================================================

        redis_client.setex(
            customer_cache_key(customer_id),
            300,
            json.dumps(customer)
        )

        # ====================================================
        # INVALIDATE SEARCH CACHE
        # ====================================================

        invalidate_customer_search_cache()

        return customer

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ============================================================
# GET CUSTOMER BY ID
# ============================================================

def get_customer_by_id(customer_id):

    cache_key = customer_cache_key(customer_id)

    # ========================================================
    # CHECK REDIS FIRST
    # ========================================================

    cached_data = redis_client.get(cache_key)

    if cached_data:

        return json.loads(cached_data)

    # ========================================================
    # REDIS MISS → MYSQL
    # ========================================================

    connection = None
    cursor = None

    try:

        connection = get_connection()

        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT
                id,
                name
            FROM customer
            WHERE id = %s
            """,
            (customer_id,)
        )

        customer = cursor.fetchone()

        # ====================================================
        # SAVE MYSQL RESULT INTO REDIS
        # ====================================================

        if customer:

            redis_client.setex(
                cache_key,
                300,
                json.dumps(customer)
            )

        return customer

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ============================================================
# INVALIDATE CUSTOMER SEARCH CACHE
# ============================================================

def invalidate_customer_search_cache():

    # Delete all customer search cache keys
    keys = redis_client.keys("customers:search:*")

    if keys:

        redis_client.delete(*keys)