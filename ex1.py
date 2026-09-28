REGRAS = [
    {
        "nome": "credenciais_do_SOC",
        "condicao": lambda p: p["schema_fixo"] and p["precisa_acid"] and p["dado_sensivel"],
        "banco": "MySQL",
        "cap": "CP",
        "justificativa": "autenticar errado é pior que ficar fora do ar",
        "risco_owasp": "A07",
    },
    {
        "nome": "telemetria",
        "condicao": lambda p: p["escala_horizontal"] and p["tolera_atraso_de_consistencia"] and not p["dado_sensivel"],
        "banco": "MongoDB",
        "cap": "AP",
        "justificativa": "perder 1s de log < parar de aceitar log",
        "risco_owasp": "A09",
    },
    {
        "nome": "trilha_de_auditoria",
        "condicao": lambda p: p["escala_horizontal"] and p["dado_sensivel"] and not p["tolera_atraso_de_consistencia"],
        "banco": "MongoDB",
        "cap": "CP",
        "justificativa": "parar o serviço é melhor do que guardar dados errados",
        "risco_owasp": "A08",
    },
    {
        "nome": "carrinho_de_licencas",
        "condicao": lambda p: p["schema_fixo"] and p["precisa_acid"] and not p["dado_sensivel"],
        "banco": "MySQL",
        "cap": "CP",
        "justificativa": "parar o serviço é melhor do que usar a licença errada",
        "risco_owasp": "A04",
    },
    {
    "nome": "cache_de_sessoes",
    "condicao": lambda p: p["schema_fixo"] and p["escala_horizontal"] and p["tolera_atraso_de_consistencia"] and p["dado_sensivel"] and not p["precisa_acid"],
    "banco": "MongoDB",
    "cap": "AP",
    "justificativa": "forçar relogin é aceitável; servir sessão de um usuário para outro não",
    "risco_owasp": "A07",
    },
]

def recomendar(perfil):
    for regra in REGRAS:
        if regra["condicao"](perfil):
            return {
                "banco": regra["banco"],
                "cap": regra["cap"],
                "justificativa": regra["justificativa"],
                "risco_owasp": regra["risco_owasp"],
            }
    raise ValueError("nenhuma regra cobre esse perfil")