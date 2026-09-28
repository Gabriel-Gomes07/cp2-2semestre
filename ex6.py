import os
from functools import wraps
from flask import Flask, request, jsonify, g
import mysql.connector

app = Flask(__name__)

analistas = [(1, "ana", "key-ana-001", 5), (2, "bruno", "key-bruno-002", 2)]
incidentes = [
    (1, 1, "Brute force SSH", "critica"),
    (2, 2, "Phishing no RH", "media"),
]


def conectar():
    return mysql.connector.connect(
        host="localhost", port=3306, user="root",
        password=os.environ["MYSQL_PWD"], database="seguranca",
    )


def preparar():
    con = conectar()
    cur = con.cursor()
    cur.execute("DROP TABLE IF EXISTS incidentes")
    cur.execute("DROP TABLE IF EXISTS analistas")
    cur.execute(
        """
        CREATE TABLE analistas (
            id INT PRIMARY KEY,
            nome VARCHAR(50),
            api_key VARCHAR(100) UNIQUE,
            nivel INT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE incidentes (
            id INT PRIMARY KEY,
            dono_id INT,
            titulo VARCHAR(100),
            severidade VARCHAR(20),
            status VARCHAR(20) DEFAULT 'aberto',
            FOREIGN KEY (dono_id) REFERENCES analistas(id)
        )
        """
    )
    cur.executemany(
        "INSERT INTO analistas (id, nome, api_key, nivel) VALUES (%s, %s, %s, %s)",
        analistas,
    )
    cur.executemany(
        "INSERT INTO incidentes (id, dono_id, titulo, severidade) VALUES (%s, %s, %s, %s)",
        incidentes,
    )
    con.commit()
    cur.close()
    con.close()


def consultar(sql, params, um=False, escrita=False):
    con = conectar()
    try:
        cur = con.cursor(dictionary=True)
        cur.execute(sql, params)
        if escrita:
            con.commit()
            resultado = cur.rowcount
        else:
            resultado = cur.fetchone() if um else cur.fetchall()
        cur.close()
        return resultado
    finally:
        con.close()


def autenticado(funcao):
    @wraps(funcao)
    def envoltorio(*args, **kwargs):
        chave = request.headers.get("X-API-Key", "")
        if not chave:
            return jsonify({"erro": "não autenticado"}), 401
        analista = consultar(
            "SELECT id, nome, nivel FROM analistas WHERE api_key = %s",
            (chave,),
            um=True,
        )
        if analista is None:
            return jsonify({"erro": "não autenticado"}), 401
        g.analista = analista
        return funcao(*args, **kwargs)

    return envoltorio


@app.errorhandler(mysql.connector.Error)
def erro_banco(_):
    return jsonify({"erro": "erro interno"}), 500


@app.route("/api/incidentes", methods=["GET"])
@autenticado
def listar():
    linhas = consultar(
        "SELECT id, dono_id, titulo, severidade, status FROM incidentes WHERE dono_id = %s",
        (g.analista["id"],),
    )
    return jsonify(linhas), 200


@app.route("/api/incidentes/<int:incidente_id>", methods=["GET"])
@autenticado
def obter(incidente_id):
    incidente = consultar(
        "SELECT id, dono_id, titulo, severidade, status FROM incidentes WHERE id = %s",
        (incidente_id,),
        um=True,
    )
    if incidente is None:
        return jsonify({"erro": "não encontrado"}), 404
    if incidente["dono_id"] != g.analista["id"]:
        return jsonify({"erro": "acesso negado"}), 403
    return jsonify(incidente), 200


@app.route("/api/incidentes/<int:incidente_id>", methods=["DELETE"])
@autenticado
def apagar(incidente_id):
    if g.analista["nivel"] < 5:
        return jsonify({"erro": "acesso negado"}), 403
    removidos = consultar(
        "DELETE FROM incidentes WHERE id = %s", (incidente_id,), escrita=True
    )
    if removidos == 0:
        return jsonify({"erro": "não encontrado"}), 404
    return jsonify({"removido": incidente_id}), 200


if __name__ == "__main__":
    preparar()
    app.run(host="127.0.0.1", port=5000)
