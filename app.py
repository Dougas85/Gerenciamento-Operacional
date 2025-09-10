from flask import Flask, render_template, request, jsonify
from datetime import datetime, date
import psycopg2
import psycopg2.extras

app = Flask(__name__)

# -------------------- Configuração Supabase --------------------
DB_URL = "postgresql://postgres.guyisltwbrcnwpbkoabn:analivia2307@aws-1-sa-east-1.pooler.supabase.com:6543/postgres"

def get_conn():
    return psycopg2.connect(DB_URL)

# -------------------- Dados das regiões --------------------
regioes = {
    "601A": {"coords": [-22.1227, -51.3855]}, "602A": {"coords": [-22.1276, -51.3886]},
    "603A": {"coords": [-22.1367, -51.3886]}, "604A": {"coords": [-22.1302, -51.3962]},
    "605A": {"coords": [-22.1247, -51.3983]}, "606A": {"coords": [-22.1160, -51.3819]},
    "607A": {"coords": [-22.1209, -51.3992]}, "608A": {"coords": [-22.1132, -51.3919]},
    "609A": {"coords": [-22.1159, -51.4008]}, "610A": {"coords": [-22.1045, -51.3926]},
    "611A": {"coords": [-22.0999, -51.4110]}, "612A": {"coords": [-22.0956, -51.4192]},
    "613A": {"coords": [-22.0842, -51.4323]}, "614A": {"coords": [-22.1240, -51.3804]},
    "615A": {"coords": [-22.1306, -51.3772]}, "616A": {"coords": [-22.090, -51.389]},
    "617A": {"coords": [-22.1037, -51.3856]}, "601B": {"coords": [-22.1194, -51.3845]},
    "602B": {"coords": [-22.1335, -51.3922]}, "603B": {"coords": [-22.1451, -51.3945]},
    "604B": {"coords": [-22.1263, -51.3940]}, "605B": {"coords": [-22.1182, -51.3994]},
    "606B": {"coords": [-22.1087, -51.3858]}, "607B": {"coords": [-22.1132, -51.3888]},
    "608B": {"coords": [-22.1081, -51.3912]}, "609B": {"coords": [-22.1100, -51.4007]},
    "610B": {"coords": [-22.0989, -51.4054]}, "611B": {"coords": [-22.1017, -51.4173]},
    "612B": {"coords": [-22.1105, -51.4196]}, "613B": {"coords": [-22.1105, -51.4196]},
    "614B": {"coords": [-22.0804, -51.4156]}, "615B": {"coords": [-22.1191, -51.3757]},
    "616B": {"coords": [-22.0834, -51.3811]}, "617B": {"coords": [-22.0709, -51.3792]}
}

status_regioes = {regiao: "verde" for regiao in regioes.keys()}
observacoes = {regiao: "" for regiao in regioes.keys()}

# -------------------- Carregar dados do banco --------------------
def carregar_dados():
    global observacoes, status_regioes

    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # Observações
    cur.execute("SELECT regiao, observacao FROM regioes_obs ORDER BY data_registro DESC")
    for row in cur.fetchall():
        observacoes[row["regiao"]] = row["observacao"]

    # Não entregas
    cur.execute("SELECT regiao, data_nao_entrega FROM regioes_nao_entrega")
    for row in cur.fetchall():
        status_regioes[row["regiao"]] = "vermelho"

    # Último lado atualizado
    cur.execute("SELECT lado, data_registro FROM lado_atualizacao ORDER BY data_registro DESC LIMIT 1")
    ultimo = cur.fetchone()
    if ultimo:
        app.config["ULTIMO_LADO"] = ultimo["lado"]
        app.config["DATA_LADO"] = ultimo["data_registro"]
    else:
        app.config["ULTIMO_LADO"] = None
        app.config["DATA_LADO"] = None

    cur.close()
    conn.close()

carregar_dados()

# -------------------- Rotas --------------------
@app.route("/")
def index():
    lado = request.args.get("lado", "A")
    regioes_filtradas = {r: regioes[r] for r in regioes if r.endswith(lado)}
    dias_sem_entrega = [r for r, s in status_regioes.items() if s == "vermelho"]

    return render_template(
        "index.html",
        regioes=regioes_filtradas,
        todas_regioes=regioes,
        status=status_regioes,
        observacoes=observacoes,
        data=datetime.now().strftime("%d/%m/%Y"),
        dias_sem_entrega=dias_sem_entrega,
        lado=lado
    )

@app.route("/", methods=["POST"])
def atualizar():
    lado = request.form.get("lado")
    atendidas = request.form.getlist("atendidas")
    hoje = date.today()

    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # 🔹 1. Verifica se já houve atualização no dia (comparando só a DATA)
    cur.execute("""
        SELECT 1 FROM lado_atualizacao 
        WHERE DATE(data_registro) = %s
        LIMIT 1
    """, (hoje,))
    if cur.fetchone():
        cur.close()
        conn.close()
        return jsonify({"erro": "Já houve atualização hoje. Tente novamente amanhã."}), 403

    # 🔹 2. Recupera o último lado registrado (dia útil anterior)
    cur.execute("""
        SELECT lado, DATE(data_registro) as dia 
        FROM lado_atualizacao 
        ORDER BY data_registro DESC 
        LIMIT 1
    """)
    ultimo = cur.fetchone()
    if ultimo:
        ultimo_lado = ultimo["lado"]
        ultimo_dia = ultimo["dia"]

        # Se hoje não é o primeiro dia, precisa ser lado oposto
        if lado == ultimo_lado:
            cur.close()
            conn.close()
            return jsonify({"erro": f"O lado {lado} já foi atendido no último dia útil ({ultimo_dia}). Hoje deve ser o lado oposto."}), 403

    # 🔹 3. Atualiza status das regiões normalmente
    for regiao in [r for r in regioes.keys() if r.endswith(lado)]:
        if regiao in atendidas:
            status_regioes[regiao] = "verde"
        else:
            if status_regioes[regiao] == "verde":
                status_regioes[regiao] = "amarelo"
            elif status_regioes[regiao] == "amarelo":
                status_regioes[regiao] = "vermelho"
                cur.execute(
                    "INSERT INTO regioes_nao_entrega (regiao, data_nao_entrega, motivo) VALUES (%s, %s, %s)",
                    (regiao, hoje, "Sem entrega registrada")
                )

    # 🔹 4. Registra lado atualizado do dia
    cur.execute(
        "INSERT INTO lado_atualizacao (lado, data_registro) VALUES (%s, NOW())",
        (lado,)
    )

    conn.commit()
    cur.close()
    conn.close()

    return ("", 204)



@app.route("/salvar_obs", methods=["POST"])
def salvar_observacao():
    data = request.get_json()
    regiao = data.get("regiao")
    texto = data.get("obs", "")

    observacoes[regiao] = texto

    # Salvar no banco
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO regioes_obs (regiao, observacao) VALUES (%s, %s)",
        (regiao, texto)
    )
    conn.commit()
    cur.close()
    conn.close()

    return jsonify({"sucess": True, "regiao": regiao, "observacao": texto})

@app.route("/dados")
def dados():
    return jsonify({
        "status": status_regioes,
        "observacoes": observacoes
    })

# -------------------- Main --------------------
if __name__ == "__main__":
    app.run(debug=True)


