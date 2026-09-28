from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.customers import router as customers_router
from app.api.parts import router as parts_router
from app.api.sales_invoices import router as sales_invoices_router
from app.api.ai import router as ai_router
from app.database.connection import get_connection


app = FastAPI(
    title="ERP AI Assistant",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(customers_router)
app.include_router(parts_router)
app.include_router(sales_invoices_router)
app.include_router(ai_router)


@app.get("/")
async def root():
    return {
        "success": True,
        "message": "ERP AI Assistant Python Backend is running"
    }


@app.get("/healthCheck")
async def health():
    return {
        "success": True,
        "status": "healthy"
    }


@app.get("/db-test")
async def db_test():
    connection = None

    try:
        connection = get_connection()

        cursor = connection.cursor()

        cursor.execute("SELECT 1")

        result = cursor.fetchone()

        cursor.close()

        return {
            "success": True,
            "database": "connected",
            "result": result[0]
        }

    except Exception as error:
        return {
            "success": False,
            "database": "connection failed",
            "error": str(error)
        }

    finally:
        if connection:
            connection.close()