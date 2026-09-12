const { createClient } = require("redis");

const redisClient = createClient({
    url: process.env.REDIS_URL
});

redisClient.on("error", (error) => {
    console.error("Redis error:", error);
});

async function connectRedis() {
    await redisClient.connect();

    console.log("Redis connected");
}

module.exports = {
    redisClient,
    connectRedis
};