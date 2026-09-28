import os
import random
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
import mysql.connector

app = Flask(__name__)

COLUNAS = {"data": "criado_em", "sev": "severidade", "ip": "ip_origem"}
ORDEM = {"asc": "ASC", "desc": "DESC"}
TAMANHO_PADRAO = 10
TAMANHO_MAXIMO = 100


def conectar():
    return mysql.connector.connect(
        host="localhost", port=3306, user="root",
        password=os.environ["MYSQL_PWD"], database="seguranca",
    )


def preparar():
    con = conectar()
    cur = con.cursor()
    cur.execute("DROP TABLE IF EXISTS eventos")
    cur.execute(
        """
        CREATE TABLE eventos (
            id INT AUTO_INCREMENT PRIMARY KEY,
            criado_em DATETIME,
            severidade ENUM('baixa','media','alta','critica'),
            ip_origem VARCHAR(20)
        )
        """
    )
    agora = datetime.now()
    dados = [
        (
            agora - timedelta(minutes=random.randint(0, 1440)),
            random.choice(["baixa", "media", "alta", "critica"]),
            f"192.168.1.{random.randint(1, 50)}",
        )
        for _ in range(30)
    ]
    cur.executemany(
        "INSERT INTO eventos (criado_em, severidade, ip_origem) VALUES (%s, %s, %s)",
        dados,
    )
    con.commit()
    cur.close()
    con.close()


@app.route("/api/eventos")
def listar_eventos():
    chave = request.args.get("ordenar_por", "data")
    ordem = request.args.get("ordem", "desc").lower()
    tamanho_bruto = request.args.get("tamanho", str(TAMANHO_PADRAO))

    if chave not in COLUNAS:
        return jsonify({"erro": "campo de ordenação inválido"}), 400
    if ordem not in ORDEM:
        return jsonify({"erro": "ordem inválida"}), 400
    try:
        tamanho = int(tamanho_bruto)
    except ValueError:
        return jsonify({"erro": "tamanho deve ser inteiro"}), 400
    if tamanho < 1:
        return jsonify({"erro": "tamanho deve ser maior que zero"}), 400
    tamanho = min(tamanho, TAMANHO_MAXIMO)

    sql = (
        "SELECT id, criado_em, severidade, ip_origem FROM eventos "
        f"ORDER BY {COLUNAS[chave]} {ORDEM[ordem]}, id ASC LIMIT %s"
    )
    con = None
    try:
        con = conectar()
        cur = con.cursor(dictionary=True)
        cur.execute(sql, (tamanho,))
        linhas = cur.fetchall()
        cur.close()
    except mysql.connector.Error:
        return jsonify({"erro": "erro interno"}), 500
    finally:
        if con is not None and con.is_connected():
            con.close()
    return jsonify(linhas), 200


if __name__ == "__main__":
    preparar()
    app.run(host="127.0.0.1", port=5000)
