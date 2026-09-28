from flask import Flask, render_template_string
from pymongo import MongoClient

app = Flask(__name__)
db = MongoClient("mongodb://localhost:27017/")["seguranca"]

p1 = "<script>alert('xss1')</script>"
p2 = 'x" onerror="alert(\'xss2\')'

CABECALHO = """<!doctype html>
<html lang="pt-br">
<head><meta charset="utf-8"><title>Dashboard de incidentes</title></head>
<body>
"""

TEMPLATE_SEGURO = CABECALHO + """
<h1>Dashboard de incidentes</h1>
<table border="1">
<tr><th>Título</th><th>Ativo</th></tr>
{% for i in incidentes %}
<tr>
<td>{{ i.titulo }}</td>
<td><img src="/icone.png" alt="{{ i.ativo }}"></td>
</tr>
{% endfor %}
</table>
</body>
</html>
"""

TEMPLATE_INSEGURO = CABECALHO + """
<h1>DASHBOARD INSEGURO (somente para comparação)</h1>
<table border="1">
<tr><th>Título</th><th>Ativo</th></tr>
{% for i in incidentes %}
<tr>
<td>{{ i.titulo|safe }}</td>
<td><img src="/icone.png" alt="{{ i.ativo|safe }}"></td>
</tr>
{% endfor %}
</table>
</body>
</html>
"""


def preparar():
    db.incidentes.drop()
    db.incidentes.insert_many(
        [
            {"titulo": p1, "ativo": p1},
            {"titulo": p2, "ativo": p2},
        ]
    )


def carregar():
    return list(db.incidentes.find({}, {"_id": 0}))


@app.after_request
def cabecalhos(resposta):
    resposta.headers["Content-Security-Policy"] = "default-src 'self'"
    resposta.headers["X-Content-Type-Options"] = "nosniff"
    return resposta


@app.route("/dashboard")
def dashboard():
    return render_template_string(TEMPLATE_SEGURO, incidentes=carregar())


@app.route("/dashboard-inseguro")
def dashboard_inseguro():
    return render_template_string(TEMPLATE_INSEGURO, incidentes=carregar())


if __name__ == "__main__":
    preparar()
    app.run(host="127.0.0.1", port=5000)
