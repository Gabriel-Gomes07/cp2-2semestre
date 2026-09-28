import random
from datetime import datetime, timedelta
from pymongo import MongoClient

db = MongoClient("mongodb://localhost:27017/")["seguranca"]
db.eventos.drop()

agora = datetime.now()
tipos = ["LOGIN_FALHO", "PORT_SCAN", "BRUTE_FORCE"]
eventos = [
    {
        "timestamp": agora - timedelta(minutes=random.randint(0, 24 * 60 - 1)),
        "tipo": random.choice(tipos),
    }
    for _ in range(200)
]
db.eventos.insert_many(eventos)
db.eventos.create_index("timestamp", expireAfterSeconds=604800)

pipeline = [
    {"$match": {"timestamp": {"$gte": agora - timedelta(hours=24)}}},
    {"$group": {"_id": {"$hour": "$timestamp"}, "total": {"$sum": 1}}},
    {"$sort": {"_id": 1}},
]
resultado = list(db.eventos.aggregate(pipeline))
pico = max(resultado, key=lambda r: r["total"])

print("=== Falhas por hora (últimas 24h) ===")
for r in resultado:
    marca = "   <- pico" if r["_id"] == pico["_id"] else ""
    print(f"{r['_id']:02d}h | {'█' * r['total']} {r['total']}{marca}")
print(f"Hora de pico: {pico['_id']:02d}h ({pico['total']} falhas)")
print("Índice TTL ativo: eventos com mais de 7 dias serão removidos automaticamente.")
