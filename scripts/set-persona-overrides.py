import redis
import os

redis_url = os.environ.get("REDIS_URL", "redis://redis:6379/1")
r = redis.from_url(redis_url, decode_responses=True)

overrides = {
    "tone": "direct, desi-british, high-energy",
    "initiative_level": "0.95",
    "humor": "0.90",
    "affection": "0.85",
    "verbosity": "0.65",
    "prompt_override": "You are Azim — the real Azim. Copy his exact speech patterns, filler words, and thinking style perfectly. Never be generic or assistant-like.",
}

r.hset("fazle:persona:self", mapping=overrides)
r.expire("fazle:persona:self", 86400 * 365)

stored = r.hgetall("fazle:persona:self")
print("Persona overrides stored in Redis:")
for k, v in stored.items():
    print(f"  {k}: {v}")
print(f"\nTTL: {r.ttl('fazle:persona:self')} seconds")
