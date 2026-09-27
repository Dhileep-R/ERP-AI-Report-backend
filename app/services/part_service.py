import json

from app.database.connection import get_connection
from app.database.redis_connection import redis_client


# ============================================================
# REDIS CACHE KEYS
# ============================================================

def part_cache_key(part_id):
    return f"part:{part_id}"


def part_search_cache_key(part_number="", part_name=""):
    return (
        f"parts:search:"
        f"{part_number.strip().lower()}:"
        f"{part_name.strip().lower()}"
    )


# ============================================================
# INVALIDATE PART SEARCH CACHE
# ============================================================

def invalidate_part_search_cache():
    cursor = 0

    while True:
        cursor, keys = redis_client.scan(
            cursor=cursor,
            match="parts:search:*",
            count=100
        )

        if keys:
            redis_client.delete(*keys)

        if cursor == 0:
            break


# ============================================================
# SEARCH PARTS
# ============================================================

def search_parts(part_number="", part_name=""):

    search_part_number = part_number.strip()
    search_part_name = part_name.strip()

    cache_key = part_search_cache_key(
        search_part_number,
        search_part_name
    )

    # --------------------------------------------------------
    # CHECK REDIS FIRST
    # --------------------------------------------------------

    cached_data = redis_client.get(cache_key)

    if cached_data:
        return json.loads(cached_data)

    connection = None
    cursor = None

    try:

        query = """
            SELECT
                id,
                partNumber,
                partName,
                partPrice
            FROM part
        """

        conditions = []
        params = []

        # ----------------------------------------------------
        # SEARCH BY PART NUMBER
        # ----------------------------------------------------

        if search_part_number:
            conditions.append("partNumber LIKE %s")
            params.append(f"%{search_part_number}%")

        # ----------------------------------------------------
        # SEARCH BY PART NAME
        # ----------------------------------------------------

        if search_part_name:
            conditions.append("partName LIKE %s")
            params.append(f"%{search_part_name}%")

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY id"

        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(query, params)

        parts = cursor.fetchall()

        # ----------------------------------------------------
        # SAVE RESULT TO REDIS
        # ----------------------------------------------------

        redis_client.setex(
            cache_key,
            300,
            json.dumps(parts, default=str)
        )

        return parts

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ============================================================
# GET PART BY ID
# ============================================================

def get_part_by_id(part_id):

    cache_key = part_cache_key(part_id)

    # --------------------------------------------------------
    # CHECK REDIS FIRST
    # --------------------------------------------------------

    cached_data = redis_client.get(cache_key)

    if cached_data:
        return json.loads(cached_data)

    connection = None
    cursor = None

    try:

        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT
                id,
                partNumber,
                partName,
                partPrice
            FROM part
            WHERE id = %s
            """,
            (part_id,)
        )

        part = cursor.fetchone()

        # ----------------------------------------------------
        # SAVE TO REDIS
        # ----------------------------------------------------

        if part:
            redis_client.setex(
                cache_key,
                300,
                json.dumps(part, default=str)
            )

        return part

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ============================================================
# CREATE PART
# ============================================================

def create_part(part_name, part_price):

    connection = None
    cursor = None

    try:

        name = part_name.strip()
        price = float(part_price)

        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        # ----------------------------------------------------
        # CHECK DUPLICATE
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT id
            FROM part
            WHERE partName = %s
            LIMIT 1
            """,
            (name,)
        )

        existing_part = cursor.fetchone()

        if existing_part:
            return {
                "status": 409,
                "error": "Part already exists"
            }

        # ----------------------------------------------------
        # INSERT PART
        # ----------------------------------------------------

        cursor.execute(
            """
            INSERT INTO part (
                partNumber,
                partName,
                partPrice
            )
            VALUES (
                0,
                %s,
                %s
            )
            """,
            (
                name,
                price
            )
        )

        part_id = cursor.lastrowid

        # ----------------------------------------------------
        # GENERATE PART NUMBER
        # ----------------------------------------------------

        part_number = f"P{part_id:03d}"

        # ----------------------------------------------------
        # UPDATE PART NUMBER
        # ----------------------------------------------------

        cursor.execute(
            """
            UPDATE part
            SET partNumber = %s
            WHERE id = %s
            """,
            (
                part_number,
                part_id
            )
        )

        # ----------------------------------------------------
        # COMMIT MYSQL
        # ----------------------------------------------------

        connection.commit()

        # ----------------------------------------------------
        # CREATE OBJECT FOR CACHE
        # ----------------------------------------------------

        part = {
            "id": part_id,
            "partNumber": part_number,
            "partName": name,
            "partPrice": price
        }

        # ----------------------------------------------------
        # SAVE NEW PART TO REDIS
        # ----------------------------------------------------

        redis_client.setex(
            part_cache_key(part_id),
            300,
            json.dumps(part, default=str)
        )

        # ----------------------------------------------------
        # INVALIDATE SEARCH CACHE
        # ----------------------------------------------------

        invalidate_part_search_cache()

        return part

    except Exception:

        if connection:
            connection.rollback()

        raise

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ============================================================
# UPDATE PART
# ============================================================

def update_part(part_id, part_name, part_price):

    connection = None
    cursor = None

    try:

        name = part_name.strip()
        price = float(part_price)

        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        # ----------------------------------------------------
        # CHECK PART EXISTS
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT
                id,
                partNumber
            FROM part
            WHERE id = %s
            """,
            (part_id,)
        )

        existing_part = cursor.fetchone()

        if not existing_part:
            return {
                "status": 404,
                "error": "Part not found"
            }

        # ----------------------------------------------------
        # CHECK DUPLICATE PART NAME
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT id
            FROM part
            WHERE partName = %s
              AND id <> %s
            LIMIT 1
            """,
            (
                name,
                part_id
            )
        )

        duplicate_part = cursor.fetchone()

        if duplicate_part:
            return {
                "status": 409,
                "error": "Another part with this name already exists"
            }

        # ----------------------------------------------------
        # UPDATE MYSQL
        # ----------------------------------------------------

        cursor.execute(
            """
            UPDATE part
            SET
                partName = %s,
                partPrice = %s
            WHERE id = %s
            """,
            (
                name,
                price,
                part_id
            )
        )

        connection.commit()

        # ----------------------------------------------------
        # CREATE UPDATED PART OBJECT
        # ----------------------------------------------------

        part = {
            "id": int(part_id),
            "partNumber": existing_part["partNumber"],
            "partName": name,
            "partPrice": price
        }

        # ----------------------------------------------------
        # UPDATE REDIS CACHE
        # ----------------------------------------------------

        redis_client.setex(
            part_cache_key(part_id),
            300,
            json.dumps(part, default=str)
        )

        # ----------------------------------------------------
        # INVALIDATE SEARCH CACHE
        # ----------------------------------------------------

        invalidate_part_search_cache()

        return part

    except Exception:

        if connection:
            connection.rollback()

        raise

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()