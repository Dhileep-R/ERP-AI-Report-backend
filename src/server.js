require("dotenv").config();

const express = require("express");
const cors = require("cors");

const pool = require("./db");

const {
    connectRedis
} = require("./redis");

const namesRouter = require("./routes/names");


const app = express();


// Middleware

app.use(cors());
app.use(express.json());


// Health check

app.get("/api/health", async (req, res) => {

    try {

        await pool.query("SELECT 1");

        res.json({
            status: "OK"
        });

    } catch (error) {

        console.error(
            "Database health check failed:",
            error
        );

        res.status(500).json({
            status: "ERROR"
        });
    }
});


// Names API

app.use(
    "/api/names",
    namesRouter
);


const PORT =
    Number(process.env.PORT) || 5000;


// Start server

async function startServer() {

    try {

        // Verify MySQL connection

        await pool.query("SELECT 1");

        console.log("MySQL connected");


        // Connect Redis

        await connectRedis();


        // Start Express

        app.listen(
            PORT,
            () => {

                console.log(
                    `Backend running on http://localhost:${PORT}`
                );
            }
        );

    } catch (error) {

        console.error(
            "Failed to start server:",
            error
        );

        process.exit(1);
    }
}


startServer();