import os
from datetime import datetime
import mysql.connector
from pymongo import MongoClient

conn = mysql.connector.connect(
    host="localhost", port=3306, user="root",
    password=os.environ["MYSQL_PWD"], database="seguranca",
)
auditoria = MongoClient("mongodb://localhost:27017/")["seguranca"].auditoria

usuarios = [
    (1, "ana", "ana@x.com", 5),
    (2, "bruno", "bruno@x.com", 2),
    (3, "caio", "caio@x.com", 1),
]


def preparar():
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS usuarios")
    cur.execute(
        """
        CREATE TABLE usuarios (
            id INT PRIMARY KEY,
            nome VARCHAR(50),
            email VARCHAR(100),
            nivel_acesso INT
        )
        """
    )
    cur.executemany(
        "INSERT INTO usuarios (id, nome, email, nivel_acesso) VALUES (%s, %s, %s, %s)",
        usuarios,
    )
    conn.commit()
    cur.close()
    auditoria.delete_many({})


def buscar_usuario(cur, uid):
    cur.execute(
        "SELECT id, nome, nivel_acesso FROM usuarios WHERE id = %s FOR UPDATE",
        (uid,),
    )
    return cur.fetchone()


def registrar(quem, alvo, nivel_anterior, nivel_novo, resultado, motivo):
    auditoria.insert_one(
        {
            "quem": quem,
            "alvo": alvo,
            "nivel_anterior": nivel_anterior,
            "nivel_novo": nivel_novo,
            "resultado": resultado,
            "motivo": motivo,
            "timestamp": datetime.now(),
        }
    )


def alterar_nivel(admin_id, alvo_id, novo_nivel):
    cur = conn.cursor(dictionary=True)
    alvo = None
    nivel_anterior = None
    motivo = None
    resultado = "RECUSADO"
    try:
        if not conn.in_transaction:
            conn.start_transaction()
        admin = buscar_usuario(cur, admin_id)
        alvo = buscar_usuario(cur, alvo_id)
        if alvo:
            nivel_anterior = alvo["nivel_acesso"]

        if admin is None or admin["nivel_acesso"] < 5:
            motivo = "admin sem privilégio"
        elif admin_id == alvo_id:
            motivo = "auto-promoção"
        elif alvo is None:
            motivo = "alvo inexistente"
        elif not isinstance(novo_nivel, int) or novo_nivel < 0:
            motivo = "nível inválido"

        if motivo:
            conn.rollback()
        else:
            cur.execute(
                "UPDATE usuarios SET nivel_acesso = %s WHERE id = %s",
                (novo_nivel, alvo_id),
            )
            conn.commit()
            resultado = "ACEITO"
    except mysql.connector.Error:
        conn.rollback()
        resultado = "ERRO"
        motivo = "erro de banco"
    finally:
        cur.close()

    registrar(admin_id, alvo_id, nivel_anterior, novo_nivel, resultado, motivo)

    if resultado == "ACEITO":
        return f"OK. commit. {alvo['nome'].capitalize()}: {nivel_anterior} -> {novo_nivel}"
    detalhe = f" {alvo['nome'].capitalize()}: {nivel_anterior}" if alvo else ""
    return f"RECUSADO ({motivo}). rollback.{detalhe}"


if __name__ == "__main__":
    preparar()
    print("alterar_nivel(1, 2, 4)  ->", alterar_nivel(1, 2, 4))
    print("alterar_nivel(2, 3, 5)  ->", alterar_nivel(2, 3, 5))
    print("alterar_nivel(1, 1, 9)  ->", alterar_nivel(1, 1, 9))
    print("alterar_nivel(1, 99, 3) ->", alterar_nivel(1, 99, 3))
    print()
    total = auditoria.count_documents({})
    recusados = auditoria.count_documents({"resultado": "RECUSADO"})
    print(f"Trilha de auditoria ao final: {total} documentos (1 sucesso, {recusados} recusas)")
    print(f'db.auditoria.count_documents({{"resultado":"RECUSADO"}}) -> {recusados}')
    conn.close()
