const express = require("express");

const pool = require("../db");

const {
    redisClient
} = require("../redis");


const router = express.Router();


const CACHE_KEY = "names:all";

const CACHE_TTL = 300;


// GET /api/names

router.get("/", async (req, res) => {

    try {

        const search =
            typeof req.query.search === "string"
                ? req.query.search.trim()
                : "";


        // -----------------------------
        // Get all names
        // -----------------------------

        if (!search) {

            const cached =
                await redisClient.get(
                    CACHE_KEY
                );


            if (cached) {

                console.log(
                    "Redis cache HIT"
                );

                return res.json(
                    JSON.parse(cached)
                );
            }


            console.log(
                "Redis cache MISS"
            );


            const [rows] =
                await pool.query(`
                    SELECT id, name
                    FROM names
                    ORDER BY name ASC
                `);


            await redisClient.set(
                CACHE_KEY,
                JSON.stringify(rows),
                {
                    EX: CACHE_TTL
                }
            );


            return res.json(rows);
        }


        // -----------------------------
        // Search
        // -----------------------------

        const [rows] =
            await pool.query(
                `
                SELECT id, name
                FROM names
                WHERE name LIKE ?
                ORDER BY name ASC
                `,
                [`%${search}%`]
            );


        return res.json(rows);

    } catch (error) {

        console.error(error);

        return res.status(500).json({
            message: "Failed to fetch names"
        });
    }
});


// POST /api/names

router.post("/", async (req, res) => {

    try {

        const name =
            typeof req.body.name === "string"
                ? req.body.name.trim()
                : "";


        if (!name) {

            return res.status(400).json({
                message: "Name is required"
            });
        }


        // Insert into MySQL

        const [result] =
            await pool.execute(
                `
                INSERT INTO names (name)
                VALUES (?)
                `,
                [name]
            );


        // Remove old cache

        await redisClient.del(
            CACHE_KEY
        );


        return res.status(201).json({

            id: result.insertId,

            name
        });

    } catch (error) {

        console.error(error);

        return res.status(500).json({
            message: "Failed to add name"
        });
    }
});


module.exports = router;