import math
from datetime import datetime
import numpy as np
from flask import Flask, request, jsonify
from pymongo import MongoClient
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix, f1_score, precision_score, recall_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

app = Flask(__name__)
db = MongoClient("mongodb://localhost:27017/")["seguranca"]

NUM_FEATURES = 4


def gerar_dados():
    rng = np.random.default_rng(42)
    n_baixo, n_alto = 850, 150
    baixo = np.column_stack(
        [
            rng.integers(0, 4, n_baixo),
            rng.integers(1, 4, n_baixo),
            rng.integers(500, 20000, n_baixo),
            rng.integers(7, 21, n_baixo),
        ]
    )
    alto = np.column_stack(
        [
            rng.integers(8, 31, n_alto),
            rng.integers(5, 41, n_alto),
            rng.integers(50000, 500000, n_alto),
            rng.integers(0, 7, n_alto),
        ]
    )
    X = np.vstack([baixo, alto]).astype(float)
    y = np.array([0] * n_baixo + [1] * n_alto)
    return X, y


def treinar():
    X, y = gerar_dados()
    X_treino, X_teste, y_treino, y_teste = train_test_split(
        X, y, test_size=0.3, random_state=42, stratify=y
    )
    modelo = make_pipeline(StandardScaler(), LogisticRegression(C=100, max_iter=1000))
    modelo.fit(X_treino, y_treino)
    previsto = modelo.predict(X_teste)
    metricas = {
        "precisao": round(float(precision_score(y_teste, previsto)), 4),
        "recall": round(float(recall_score(y_teste, previsto)), 4),
        "f1": round(float(f1_score(y_teste, previsto)), 4),
        "matriz": confusion_matrix(y_teste, previsto).tolist(),
    }
    return modelo, metricas


modelo, METRICAS = treinar()


def validar(corpo):
    if not isinstance(corpo, dict) or "features" not in corpo:
        return None, "corpo JSON com o campo 'features' é obrigatório"
    features = corpo["features"]
    if not isinstance(features, list):
        return None, "features deve ser uma lista"
    if len(features) != NUM_FEATURES:
        return None, f"esperadas {NUM_FEATURES} features, recebidas {len(features)}"
    for valor in features:
        if isinstance(valor, bool) or not isinstance(valor, (int, float)):
            return None, "features devem ser numéricas"
        if not math.isfinite(valor):
            return None, "features devem ser numéricas"
    if not 0 <= features[3] <= 23:
        return None, "hora_do_dia deve estar entre 0 e 23"
    return [float(v) for v in features], None


@app.route("/api/triagem", methods=["POST"])
def triagem():
    corpo = request.get_json(silent=True)
    features, erro = validar(corpo)
    if erro:
        return jsonify({"erro": erro}), 400

    probabilidades = modelo.predict_proba([features])[0]
    classe = int(np.argmax(probabilidades))
    resultado = {
        "risco": "alto" if classe == 1 else "baixo",
        "confianca": round(float(probabilidades[classe]), 2),
    }
    try:
        db.previsoes.insert_one(
            {
                "entrada": features,
                "saida": resultado["risco"],
                "confianca": resultado["confianca"],
                "timestamp": datetime.now(),
            }
        )
    except Exception:
        return jsonify({"erro": "erro interno"}), 500
    return jsonify(resultado), 200


@app.route("/api/modelo/metricas", methods=["GET"])
def metricas():
    resposta = dict(METRICAS)
    resposta["aviso"] = (
        "acurácia omitida de propósito: com poucos casos de risco alto, um modelo que "
        "sempre respondesse 'baixo' teria acurácia alta e esconderia os ataques que ele "
        "deixa passar; precisão, recall e F1 mostram esse erro."
    )
    return jsonify(resposta), 200


if __name__ == "__main__":
    db.previsoes.drop()
    app.run(host="127.0.0.1", port=5000)
