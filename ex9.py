import os
import time
from datetime import datetime
import numpy as np
from flask import Flask, g, jsonify, request
from pymongo import MongoClient
from sklearn.ensemble import IsolationForest

app = Flask(__name__)
db = MongoClient("mongodb://localhost:27017/")["seguranca"]

SIMULAR_IP = os.environ.get("LAB_SIMULAR_IP") == "1"
JANELA_MINIMA_SEGUNDOS = 10
DURACAO_BLOQUEIO = 60
bloqueados = {}


def ip_cliente():
    if SIMULAR_IP and request.headers.get("X-Forwarded-For"):
        return request.headers["X-Forwarded-For"].split(",")[0].strip()
    return request.remote_addr


def agregar():
    pipeline = [
        {"$match": {"status": {"$exists": True}}},
        {
            "$group": {
                "_id": "$ip",
                "total": {"$sum": 1},
                "primeiro": {"$min": "$timestamp"},
                "ultimo": {"$max": "$timestamp"},
                "erros": {"$sum": {"$cond": [{"$gte": ["$status", 400]}, 1, 0]}},
                "rotas": {"$addToSet": "$rota"},
            }
        },
    ]
    return list(db.acessos.aggregate(pipeline))


def analisar():
    grupos = agregar()
    if len(grupos) < 2:
        return []
    linhas = []
    for grupo in grupos:
        segundos = (grupo["ultimo"] - grupo["primeiro"]).total_seconds()
        minutos = max(segundos, JANELA_MINIMA_SEGUNDOS) / 60
        linhas.append(
            {
                "ip": grupo["_id"],
                "req_por_minuto": round(grupo["total"] / minutos, 2),
                "taxa_4xx": round(grupo["erros"] / grupo["total"], 2),
                "rotas_distintas": len(grupo["rotas"]),
            }
        )
    X = np.array(
        [[l["req_por_minuto"], l["taxa_4xx"], l["rotas_distintas"]] for l in linhas]
    )
    modelo = IsolationForest(contamination=0.2, random_state=42).fit(X)
    previsoes = modelo.predict(X)
    for linha, previsao in zip(linhas, previsoes):
        linha["anomalia"] = bool(previsao == -1)
        if linha["anomalia"]:
            bloqueados[linha["ip"]] = time.time() + DURACAO_BLOQUEIO
    return linhas


@app.before_request
def controlar():
    if request.path == "/api/analise":
        return None
    ip = ip_cliente()
    registro = db.acessos.insert_one(
        {
            "ip": ip,
            "rota": request.path,
            "metodo": request.method,
            "timestamp": datetime.now(),
        }
    )
    g.registro = registro.inserted_id
    ate = bloqueados.get(ip)
    if ate and ate > time.time():
        resposta = jsonify({"erro": "muitas requisições"})
        resposta.status_code = 429
        resposta.headers["Retry-After"] = str(DURACAO_BLOQUEIO)
        return resposta
    return None


@app.after_request
def completar(resposta):
    registro = g.get("registro")
    if registro is not None:
        db.acessos.update_one(
            {"_id": registro}, {"$set": {"status": resposta.status_code}}
        )
    return resposta


@app.route("/api/status")
def status():
    return jsonify({"status": "ok"}), 200


@app.route("/api/saude")
def saude():
    return jsonify({"saude": "ok"}), 200


@app.route("/api/analise")
def analise():
    return jsonify(analisar()), 200


if __name__ == "__main__":
    db.acessos.drop()
    app.run(host="127.0.0.1", port=5000)
