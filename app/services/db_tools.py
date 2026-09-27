from app.database.connection import get_connection


# ============================================================
# GET CUSTOMERS
# ============================================================

def get_customers():

    connection = None
    cursor = None

    try:

        connection = get_connection()

        cursor = connection.cursor(
            dictionary=True
        )

        cursor.execute(
            """
            SELECT
                name
            FROM Customer
            ORDER BY name
            """
        )

        rows = cursor.fetchall()

        return rows

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ============================================================
# GET PARTS
# ============================================================

def get_parts():

    connection = None
    cursor = None

    try:

        connection = get_connection()

        cursor = connection.cursor(
            dictionary=True
        )

        cursor.execute(
            """
            SELECT
                id,
                PartNumber,
                PartName
            FROM Part
            ORDER BY PartName
            """
        )

        rows = cursor.fetchall()

        return rows

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ============================================================
# GET SALES ORDERS
# ============================================================

def get_sales_invoices(
    sales_invoice_number=None,
    customer_name=None,
    part_number=None,
    from_date=None,
    to_date=None,
    include_customer_summary=False,
    include_part_summary=False,
    include_unused_customers=False,
    include_unused_parts=False
):

    connection = None
    cursor = None

    try:

        connection = get_connection()

        cursor = connection.cursor(
            dictionary=True
        )

        # ====================================================
        # 1. UNUSED CUSTOMERS
        # ====================================================

        if include_unused_customers:

            cursor.execute(
                """
                SELECT
                    c.id,
                    c.name AS CustomerName

                FROM Customer c

                LEFT JOIN SalesInvoice si
                    ON si.CustomerId = c.id

                WHERE si.id IS NULL

                ORDER BY c.name
                """
            )

            rows = cursor.fetchall()

            return {
                "type": "unused_customers",
                "count": len(rows),
                "data": rows
            }

        # ====================================================
        # 2. UNUSED PARTS
        # ====================================================

        if include_unused_parts:

            cursor.execute(
                """
                SELECT
                    p.id,
                    p.PartNumber,
                    p.PartName

                FROM Part p

                LEFT JOIN salesinvoicelineitem sil
                    ON sil.PartId = p.id

                WHERE sil.PartId IS NULL

                ORDER BY p.PartName
                """
            )

            rows = cursor.fetchall()

            return {
                "type": "unused_parts",
                "count": len(rows),
                "data": rows
            }

        # ====================================================
        # 3. CUSTOMER SALES SUMMARY
        # ====================================================

        if include_customer_summary:

            where = []
            params = []

            # ------------------------------------------------
            # FROM DATE
            # ------------------------------------------------

            if from_date:

                where.append(
                    "si.SalesInvoiceDate >= %s"
                )

                params.append(from_date)

            # ------------------------------------------------
            # TO DATE
            # ------------------------------------------------

            if to_date:

                where.append(
                    """
                    si.SalesInvoiceDate
                    < DATE_ADD(%s, INTERVAL 1 DAY)
                    """
                )

                params.append(to_date)

            # ------------------------------------------------
            # CUSTOMER
            # ------------------------------------------------

            if customer_name:

                where.append(
                    "c.name LIKE %s"
                )

                params.append(
                    f"%{customer_name}%"
                )

            # ------------------------------------------------
            # WHERE CLAUSE
            # ------------------------------------------------

            where_clause = ""

            if where:

                where_clause = (
                    "WHERE "
                    + " AND ".join(where)
                )

            query = f"""
                SELECT
                    c.id AS CustomerId,
                    c.name AS CustomerName,

                    COUNT(DISTINCT si.id)
                        AS SalesInvoiceCount,

                    COALESCE(
                        SUM(
                            sil.price * sil.quantity
                        ),
                        0
                    ) AS TotalSales

                FROM Customer c

                INNER JOIN SalesInvoice si
                    ON si.CustomerId = c.id

                INNER JOIN salesinvoicelineitem sil
                    ON sil.SalesOrderId = si.id

                {where_clause}

                GROUP BY
                    c.id,
                    c.name

                ORDER BY
                    TotalSales DESC
            """

            cursor.execute(
                query,
                params
            )

            rows = cursor.fetchall()

            return {
                "type": "customer_sales_summary",
                "count": len(rows),
                "data": rows
            }

        # ====================================================
        # 4. PART SALES SUMMARY
        # ====================================================

        if include_part_summary:

            where = []
            params = []

            # ------------------------------------------------
            # FROM DATE
            # ------------------------------------------------

            if from_date:

                where.append(
                    "si.SalesInvoiceDate >= %s"
                )

                params.append(from_date)

            # ------------------------------------------------
            # TO DATE
            # ------------------------------------------------

            if to_date:

                where.append(
                    """
                    si.SalesInvoiceDate
                    < DATE_ADD(%s, INTERVAL 1 DAY)
                    """
                )

                params.append(to_date)

            # ------------------------------------------------
            # PART NUMBER
            # ------------------------------------------------

            if part_number:

                where.append(
                    "p.PartNumber LIKE %s"
                )

                params.append(
                    f"%{part_number}%"
                )

            # ------------------------------------------------
            # WHERE CLAUSE
            # ------------------------------------------------

            where_clause = ""

            if where:

                where_clause = (
                    "WHERE "
                    + " AND ".join(where)
                )

            query = f"""
                SELECT
                    p.id AS PartId,
                    p.PartNumber,
                    p.PartName,

                    COUNT(DISTINCT si.id)
                        AS SalesInvoiceCount,

                    COALESCE(
                        SUM(
                            sil.price * sil.quantity
                        ),
                        0
                    ) AS TotalSales

                FROM Part p

                INNER JOIN salesinvoicelineitem sil
                    ON sil.PartId = p.id

                INNER JOIN SalesInvoice si
                    ON si.id = sil.SalesInvoiceId

                {where_clause}

                GROUP BY
                    p.id,
                    p.PartNumber,
                    p.PartName

                ORDER BY
                    TotalSales DESC
            """

            cursor.execute(
                query,
                params
            )

            rows = cursor.fetchall()

            return {
                "type": "part_sales_summary",
                "count": len(rows),
                "data": rows
            }

        # ====================================================
        # 5. NORMAL SALES ORDER SEARCH
        # ====================================================

        where = []
        params = []

        # ----------------------------------------------------
        # SALES ORDER NUMBER
        # ----------------------------------------------------

        if sales_invoice_number:

            where.append(
                "so.SalesInvoiceNumber LIKE %s"
            )

            params.append(
                f"%{sales_invoice_number}%"
            )

        # ----------------------------------------------------
        # CUSTOMER NAME
        # ----------------------------------------------------

        if customer_name:

            where.append(
                "c.name LIKE %s"
            )

            params.append(
                f"%{customer_name}%"
            )

        # ----------------------------------------------------
        # PART NUMBER
        # ----------------------------------------------------

        if part_number:

            where.append(
                """
                EXISTS (
                    SELECT 1

                    FROM salesinvoicelineitem sil_filter

                    INNER JOIN Part p_filter
                        ON p_filter.id = sil_filter.PartId

                    WHERE
                        sil_filter.SalesInvoiceId = si.id

                        AND p_filter.PartNumber LIKE %s
                )
                """
            )

            params.append(
                f"%{part_number}%"
            )

        # ----------------------------------------------------
        # FROM DATE
        # ----------------------------------------------------

        if from_date:

            where.append(
                "si.SalesInvoiceDate >= %s"
            )

            params.append(from_date)

        # ----------------------------------------------------
        # TO DATE
        # ----------------------------------------------------

        if to_date:

            where.append(
                """
                si.SalesInvoiceDate
                < DATE_ADD(%s, INTERVAL 1 DAY)
                """
            )

            params.append(to_date)

        # ====================================================
        # WHERE CLAUSE
        # ====================================================

        where_clause = ""

        if where:

            where_clause = (
                "WHERE "
                + " AND ".join(where)
            )

        # ====================================================
        # GET SALES ORDERS
        # ====================================================

        query = f"""
            SELECT
                si.id,
                si.SalesInvoiceNumber,
                si.SalesInvoiceDate,
                c.name AS CustomerName

            FROM SalesInvoice si

            LEFT JOIN Customer c
                ON c.id = si.CustomerId

            {where_clause}

            ORDER BY
                si.SalesInvoiceDate DESC,
                si.id DESC
        """

        cursor.execute(
            query,
            params
        )

        orders = cursor.fetchall()

        # ====================================================
        # NO ORDERS
        # ====================================================

        if not orders:

            return {
                "type": "sales_invoices",
                "count": 0,
                "data": []
            }

        # ====================================================
        # GET ALL LINE ITEMS
        # ====================================================

        order_ids = [
            order["id"]
            for order in orders
        ]

        placeholders = ",".join(
            ["%s"] * len(order_ids)
        )

        items_query = f"""
            SELECT
                sil.SalesInvoiceId,
                sil.PartId,
                p.PartNumber,
                p.PartName,
                sil.price,
                sil.quantity

            FROM salesinvoicelineitem sil

            LEFT JOIN Part p
                ON p.id = sil.PartId

            WHERE
                sil.SalesInvoiceId IN ({placeholders})

            ORDER BY
                sil.SalesInvoiceId
        """

        cursor.execute(
            items_query,
            order_ids
        )

        items = cursor.fetchall()

        # ====================================================
        # GROUP ITEMS BY SALES ORDER
        # ====================================================

        items_by_order = {}

        for item in items:

            order_id = item["SalesInvoiceId"]

            if order_id not in items_by_order:

                items_by_order[order_id] = []

            price = float(item["price"])
            quantity = int(item["quantity"])

            items_by_order[order_id].append(
                {
                    "PartId": item["PartId"],

                    "PartNumber":
                        item["PartNumber"],

                    "PartName":
                        item["PartName"],

                    "price": price,

                    "quantity": quantity,

                    "amount":
                        price * quantity
                }
            )

        # ====================================================
        # ATTACH ITEMS TO ORDERS
        # ====================================================

        for order in orders:

            order["items"] = (
                items_by_order.get(
                    order["id"],
                    []
                )
            )

        # ====================================================
        # RETURN
        # ====================================================

        return {
            "type": "sales_invoices",
            "count": len(orders),
            "data": orders
        }

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()