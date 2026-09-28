import os
import mysql.connector
from pymongo import MongoClient

# ---------- Parte 1: criar e popular o MySQL ----------
conn = mysql.connector.connect(
    host="localhost", port=3306, user="root",
    password=os.environ["MYSQL_PWD"], database="seguranca"
)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS ativos (
    id INT PRIMARY KEY,
    nome VARCHAR(50),
    ip VARCHAR(20) UNIQUE,
    criticidade ENUM('baixa','media','alta')
)""")
cur.execute("""
CREATE TABLE IF NOT EXISTS alertas (
    id INT PRIMARY KEY,
    ativo_id INT,
    tipo VARCHAR(50),
    severidade VARCHAR(20),
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ativo_id) REFERENCES ativos(id)
)""")

ativos = [(1, "SRV-WEB01", "192.168.1.10", "alta"), (2, "PC-RH03", "192.168.1.45", "baixa")]
alertas = [(1, 1, "BRUTE_FORCE", "critica"), (2, 1, "PORT_SCAN", "alta"), (3, 2, "XSS", "media")]

cur.executemany("INSERT IGNORE INTO ativos (id,nome,ip,criticidade) VALUES (%s,%s,%s,%s)", ativos)
cur.executemany("INSERT IGNORE INTO alertas (id,ativo_id,tipo,severidade) VALUES (%s,%s,%s,%s)", alertas)
conn.commit()

# ---------- Parte 2: ler com JOIN parametrizado ----------
cur = conn.cursor(dictionary=True)
cur.execute("""
    SELECT al.id, al.tipo, al.severidade,
           at.nome AS ativo_nome, at.ip AS ativo_ip, at.criticidade AS ativo_criticidade
    FROM alertas al
    JOIN ativos at ON al.ativo_id = at.id
""")
linhas = cur.fetchall()

# ---------- Parte 3: transformar em documentos aninhados e migrar ----------
documentos = [
    {
        "tipo": linha["tipo"],
        "severidade": linha["severidade"],
        "ativo": {
            "nome": linha["ativo_nome"],
            "ip": linha["ativo_ip"],
            "criticidade": linha["ativo_criticidade"],
        },
    }
    for linha in linhas
]

cliente = MongoClient("mongodb://localhost:27017/")
db = cliente["seguranca"]

# evita duplicar documentos se você rodar o script mais de uma vez
db.alertas.delete_many({})
db.alertas.insert_many(documentos)

# ---------- Verificação: nada pode ter se perdido no caminho ----------
total_mysql = len(linhas)
total_mongo = db.alertas.count_documents({})
status = "MIGRAÇÃO ÍNTEGRA" if total_mysql == total_mongo else "DIVERGÊNCIA!"
print(f"MySQL: {total_mysql} alertas | MongoDB: {total_mongo} documentos -> {status}")

alta_criticidade = db.alertas.count_documents({"ativo.criticidade": "alta"})
print(f"Consulta sem JOIN: db.alertas.find({{'ativo.criticidade':'alta'}}) -> {alta_criticidade} documentos")

# Comentário pedido pelo enunciado:
# Ganha-se: leitura direta, sem JOIN, porque o dado do ativo já mora dentro do alerta.
# Perde-se: duplicação — renomear um ativo exige update_many em todos os alertas dele.

conn.close()
cliente.close()