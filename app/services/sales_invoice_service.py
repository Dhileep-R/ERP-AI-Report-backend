import json

from app.database.connection import get_connection
from app.database.redis_connection import redis_client

from datetime import datetime, timedelta, timezone


# ============================================================
# INDIA DATE
# ============================================================

def get_india_date():
    india_timezone = timezone(
        timedelta(hours=5, minutes=30)
    )

    return datetime.now(
        india_timezone
    ).strftime("%Y-%m-%d")


# ============================================================
# REDIS CACHE KEYS
# ============================================================

def sales_invoice_cache_key(sales_invoice_id):
    return f"sales-invoice:{sales_invoice_id}"


def sales_invoice_search_cache_key(
    sales_invoice_number="",
    customer_id="",
    from_date="",
    to_date=""
):
    return (
        f"sales-invoices:search:"
        f"{sales_invoice_number.strip().lower()}:"
        f"{str(customer_id).strip().lower()}:"
        f"{from_date.strip().lower()}:"
        f"{to_date.strip().lower()}"
    )


# ============================================================
# INVALIDATE SALES INVOICE SEARCH CACHE
# ============================================================

def invalidate_sales_invoice_search_cache():

    cursor = 0

    while True:

        cursor, keys = redis_client.scan(
            cursor=cursor,
            match="sales-invoices:search:*",
            count=100
        )

        if keys:
            redis_client.delete(*keys)

        if cursor == 0:
            break


# ============================================================
# SEARCH SALES INVOICES
# ============================================================

def search_sales_invoices(
    sales_invoice_number="",
    customer_id="",
    from_date="",
    to_date=""
):

    search_invoice_number = sales_invoice_number.strip()
    search_customer_id = str(customer_id).strip()
    search_from_date = from_date.strip()
    search_to_date = to_date.strip()

    cache_key = sales_invoice_search_cache_key(
        search_invoice_number,
        search_customer_id,
        search_from_date,
        search_to_date
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
                si.id,
                si.salesInvoiceNumber,
                si.salesInvoiceDate,
                si.customerId,
                c.name AS customerName,

                COALESCE(
                    SUM(
                        sil.price * sil.quantity
                    ),
                    0
                ) AS totalAmount

            FROM salesinvoice si

            INNER JOIN customer c
                ON c.id = si.customerId

            LEFT JOIN salesinvoicelineitem sil
                ON sil.salesInvoiceId = si.id
        """

        conditions = []
        params = []

        # ----------------------------------------------------
        # SALES INVOICE NUMBER
        # ----------------------------------------------------

        if search_invoice_number:

            conditions.append(
                "si.salesInvoiceNumber LIKE %s"
            )

            params.append(
                f"%{search_invoice_number}%"
            )

        # ----------------------------------------------------
        # CUSTOMER
        # ----------------------------------------------------

        if search_customer_id:

            conditions.append(
                "si.customerId = %s"
            )

            params.append(
                search_customer_id
            )

        # ----------------------------------------------------
        # FROM DATE
        # ----------------------------------------------------

        if search_from_date:

            conditions.append(
                "si.salesInvoiceDate >= %s"
            )

            params.append(
                search_from_date
            )

        # ----------------------------------------------------
        # TO DATE
        # ----------------------------------------------------

        if search_to_date:

            conditions.append(
                "si.salesInvoiceDate <= %s"
            )

            params.append(
                search_to_date
            )

        # ----------------------------------------------------
        # WHERE
        # ----------------------------------------------------

        if conditions:

            query += " WHERE " + " AND ".join(conditions)

        # ----------------------------------------------------
        # GROUP BY / ORDER BY
        # ----------------------------------------------------

        query += """

            GROUP BY
                si.id,
                si.salesInvoiceNumber,
                si.salesInvoiceDate,
                si.customerId,
                c.name

            ORDER BY
                si.id DESC
        """

        connection = get_connection()

        cursor = connection.cursor(
            dictionary=True
        )

        cursor.execute(
            query,
            params
        )

        invoices = cursor.fetchall()

        # ----------------------------------------------------
        # SAVE TO REDIS
        # ----------------------------------------------------

        redis_client.setex(
            cache_key,
            300,
            json.dumps(
                invoices,
                default=str
            )
        )

        return invoices

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ============================================================
# GET SALES INVOICE BY ID
# ============================================================

def get_sales_invoice_by_id(sales_invoice_id):

    cache_key = sales_invoice_cache_key(
        sales_invoice_id
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

        connection = get_connection()

        cursor = connection.cursor(
            dictionary=True
        )

        # ----------------------------------------------------
        # HEADER
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT
                si.id,
                si.salesInvoiceNumber,
                si.salesInvoiceDate,
                si.customerId,
                c.name AS customerName

            FROM salesinvoice si

            INNER JOIN customer c
                ON c.id = si.customerId

            WHERE si.id = %s
            """,
            (sales_invoice_id,)
        )

        invoice = cursor.fetchone()

        if not invoice:
            return None

        # ----------------------------------------------------
        # LINE ITEMS
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT
                sil.id,
                sil.salesInvoiceId,
                sil.partId,
                p.PartNumber AS partNumber,
                p.PartName AS partName,
                sil.price,
                sil.quantity

            FROM salesinvoicelineitem sil

            INNER JOIN part p
                ON p.id = sil.partId

            WHERE sil.salesInvoiceId = %s

            ORDER BY sil.id
            """,
            (sales_invoice_id,)
        )

        line_items = cursor.fetchall()

        invoice["lineItems"] = line_items

        # ----------------------------------------------------
        # SAVE COMPLETE INVOICE TO REDIS
        # ----------------------------------------------------

        redis_client.setex(
            cache_key,
            300,
            json.dumps(
                invoice,
                default=str
            )
        )

        return invoice

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ============================================================
# CREATE SALES INVOICE
# ============================================================

def create_sales_invoice(
    customer_id,
    line_items
):

    connection = None
    cursor = None

    try:

        connection = get_connection()

        cursor = connection.cursor(
            dictionary=True
        )

        # ----------------------------------------------------
        # CURRENT DATE
        # ----------------------------------------------------

        today = get_india_date()

        # ----------------------------------------------------
        # INSERT HEADER
        # ----------------------------------------------------

        cursor.execute(
            """
            INSERT INTO salesinvoice (
                salesInvoiceNumber,
                salesInvoiceDate,
                customerId
            )
            VALUES (
                0,
                %s,
                %s
            )
            """,
            (
                today,
                customer_id
            )
        )

        sales_invoice_id = cursor.lastrowid

        # ----------------------------------------------------
        # GENERATE SALES INVOICE NUMBER
        # ----------------------------------------------------

        sales_invoice_number = (
            f"SO{sales_invoice_id:03d}"
        )

        # ----------------------------------------------------
        # UPDATE INVOICE NUMBER
        # ----------------------------------------------------

        cursor.execute(
            """
            UPDATE salesinvoice
            SET salesInvoiceNumber = %s
            WHERE id = %s
            """,
            (
                sales_invoice_number,
                sales_invoice_id
            )
        )

        # ----------------------------------------------------
        # INSERT LINE ITEMS
        # ----------------------------------------------------

        for item in line_items:

            cursor.execute(
                """
                INSERT INTO salesinvoicelineitem (
                    salesInvoiceId,
                    partId,
                    price,
                    quantity
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s
                )
                """,
                (
                    sales_invoice_id,
                    item["partId"],
                    float(item["price"]),
                    int(item["quantity"])
                )
            )

        # ----------------------------------------------------
        # COMMIT MYSQL
        # ----------------------------------------------------

        connection.commit()

        invoice = {
            "id": sales_invoice_id,
            "salesInvoiceNumber": sales_invoice_number,
            "salesInvoiceDate": today,
            "customerId": customer_id,
            "lineItems": line_items
        }

        # ----------------------------------------------------
        # SAVE NEW INVOICE TO REDIS
        # ----------------------------------------------------

        redis_client.setex(
            sales_invoice_cache_key(
                sales_invoice_id
            ),
            300,
            json.dumps(
                invoice,
                default=str
            )
        )

        # ----------------------------------------------------
        # INVALIDATE SEARCH CACHE
        # ----------------------------------------------------

        invalidate_sales_invoice_search_cache()

        return invoice

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
# UPDATE SALES INVOICE
# ============================================================

def update_sales_invoice(
    sales_invoice_id,
    customer_id,
    line_items
):

    connection = None
    cursor = None

    try:

        connection = get_connection()

        cursor = connection.cursor(
            dictionary=True
        )

        # ----------------------------------------------------
        # CHECK INVOICE
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT
                id,
                salesInvoiceNumber
            FROM salesinvoice
            WHERE id = %s
            """,
            (sales_invoice_id,)
        )

        invoice = cursor.fetchone()

        if not invoice:

            return {
                "status": 404,
                "error": "Sales Invoice not found"
            }

        # ----------------------------------------------------
        # CURRENT DATE
        # ----------------------------------------------------

        today = get_india_date()

        # ----------------------------------------------------
        # UPDATE HEADER
        # ----------------------------------------------------

        cursor.execute(
            """
            UPDATE salesinvoice
            SET
                salesInvoiceDate = %s,
                customerId = %s
            WHERE id = %s
            """,
            (
                today,
                customer_id,
                sales_invoice_id
            )
        )

        # ----------------------------------------------------
        # DELETE OLD LINE ITEMS
        # ----------------------------------------------------

        cursor.execute(
            """
            DELETE FROM salesinvoicelineitem
            WHERE salesInvoiceId = %s
            """,
            (sales_invoice_id,)
        )

        # ----------------------------------------------------
        # INSERT UPDATED LINE ITEMS
        # ----------------------------------------------------

        for item in line_items:

            cursor.execute(
                """
                INSERT INTO salesinvoicelineitem (
                    salesInvoiceId,
                    partId,
                    price,
                    quantity
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s
                )
                """,
                (
                    sales_invoice_id,
                    item["partId"],
                    float(item["price"]),
                    int(item["quantity"])
                )
            )

        # ----------------------------------------------------
        # COMMIT MYSQL
        # ----------------------------------------------------

        connection.commit()

        updated_invoice = {
            "id": int(sales_invoice_id),
            "salesInvoiceNumber": invoice["salesInvoiceNumber"],
            "salesInvoiceDate": today,
            "customerId": customer_id,
            "lineItems": line_items
        }

        # ----------------------------------------------------
        # UPDATE REDIS
        # ----------------------------------------------------

        redis_client.setex(
            sales_invoice_cache_key(
                sales_invoice_id
            ),
            300,
            json.dumps(
                updated_invoice,
                default=str
            )
        )

        # ----------------------------------------------------
        # INVALIDATE SEARCH CACHE
        # ----------------------------------------------------

        invalidate_sales_invoice_search_cache()

        return updated_invoice

    except Exception:

        if connection:
            connection.rollback()

        raise

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()