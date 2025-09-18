from flask import Flask, render_template, request, jsonify
from datetime import datetime, date
import psycopg2
import psycopg2.extras

app = Flask(__name__)

# -------------------- Configuração Banco --------------------
DB_URL = "postgresql://postgres.guyisltwbrcnwpbkoabn:analivia2307@aws-1-sa-east-1.pooler.supabase.com:6543/postgres"

def get_conn():
    return psycopg2.connect(DB_URL)

# -------------------- Dados fixos das regiões --------------------
regioes = {
    "601A": {"coords": [-22.1227, -51.3855]},
    "602A": {"coords": [-22.1276, -51.3886]},
    "603A": {"coords": [-22.1367, -51.3886]},
    "604A": {"coords": [-22.1302, -51.3962]},
    "605A": {"coords": [-22.1247, -51.3983]},
    "606A": {"coords": [-22.1160, -51.3819]},
    "607A": {"coords": [-22.1209, -51.3992]},
    "608A": {"coords": [-22.1132, -51.3919]},
    "609A": {"coords": [-22.1159, -51.4008]},
    "610A": {"coords": [-22.1045, -51.3926]},
    "611A": {"coords": [-22.0999, -51.4110]},
    "612A": {"coords": [-22.0956, -51.4192]},
    "613A": {"coords": [-22.0842, -51.4323]},
    "614A": {"coords": [-22.1240, -51.3804]},
    "615A": {"coords": [-22.1306, -51.3772]},
    "616A": {"coords": [-22.090, -51.389]},
    "617A": {"coords": [-22.1037, -51.3856]},
    "601B": {"coords": [-22.1194, -51.3845]},
    "602B": {"coords": [-22.1335, -51.3922]},
    "603B": {"coords": [-22.1451, -51.3945]},
    "604B": {"coords": [-22.1263, -51.3940]},
    "605B": {"coords": [-22.1182, -51.3994]},
    "606B": {"coords": [-22.1087, -51.3858]},
    "607B": {"coords": [-22.1132, -51.3888]},
    "608B": {"coords": [-22.1081, -51.3912]},
    "609B": {"coords": [-22.1100, -51.4007]},
    "610B": {"coords": [-22.0989, -51.4054]},
    "611B": {"coords": [-22.1017, -51.4173]},
    "612B": {"coords": [-22.1105, -51.4196]},
    "613B": {"coords": [-22.1105, -51.4196]},
    "614B": {"coords": [-22.0804, -51.4156]},
    "615B": {"coords": [-22.1191, -51.3757]},
    "616B": {"coords": [-22.0834, -51.3811]},
    "617B": {"coords": [-22.0709, -51.3792]}
}

status_regioes = {regiao: "verde" for regiao in regioes.keys()}
observacoes = {regiao: "" for regiao in regioes.keys()}

# -------------------- Carregar dados do banco --------------------
def carregar_dados():
    global observacoes, status_regioes
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # Observações
    cur.execute("""
        SELECT DISTINCT ON (regiao) regiao, observacao
        FROM regioes_obs
        ORDER BY regiao,  data_registro DESC
    """)
    for row in cur.fetchall():
        observacoes[row["regiao"]] = row["observacao"]

    # Status das regiões (último registro por região)
    cur.execute("""
    SELECT DISTINCT ON (regiao) regiao, status
    FROM regioes_status
    ORDER BY regiao, data_registro DESC
    """)
    for row in cur.fetchall():
        status_regioes[row["regiao"]] = row["status"]

    # Último lado atualizado
    cur.execute("SELECT lado, DATE(data_registro) as dia FROM lado_atualizacao ORDER BY data_registro DESC LIMIT 1")
    ultimo = cur.fetchone()
    if ultimo:
        app.config["ULTIMO_LADO"] = ultimo["lado"]
        app.config["DATA_LADO"] = ultimo["dia"]
    else:
        app.config["ULTIMO_LADO"] = None
        app.config["DATA_LADO"] = None

    cur.close()
    conn.close()

# Carregar logo ao iniciar
carregar_dados()

@app.route("/", methods=["GET", "POST"])
def index():
    hoje = date.today()
    mensagem = None
    lado_bloqueado = False
    lado = None  # 🔹 inicializa a variável

    carregar_dados()

    # Variáveis do cálculo do EPTC
    eptc_estimado = 0.0
    primeira_tentativa = 0.0
    limite_maximo = 0.0
    ausentes_ajustados = 0.0
    limite_ausentes = 0.0

    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # Última atualização
    cur.execute("""
        SELECT lado, DATE(data_registro) as dia 
        FROM lado_atualizacao 
        ORDER BY data_registro DESC 
        LIMIT 1
    """)
    ultimo = cur.fetchone()

    # Determina o lado sugerido
    if ultimo and ultimo["dia"] < hoje:
        lado_sugerido = "B" if ultimo["lado"] == "A" else "A"
    else:
        lado_sugerido = ultimo["lado"] if ultimo else "A"

    # Verifica se o lado sugerido já foi atualizado hoje
    if ultimo and ultimo["dia"] == hoje and ultimo["lado"] == lado_sugerido:
        lado_bloqueado = True

    if request.method == "POST":
        # 🔹 Caso 1: Cálculo do EPTC
        if "calcular_eptc" in request.form:
            try:
                total_objetos = int(request.form.get("total_objetos", 0))
                ausentes = int(request.form.get("ausentes", 0))

                # 1ª tentativa
                primeira_tentativa = total_objetos * 0.82

                # limite de ausentes
                limite_ausentes = primeira_tentativa * 0.065
                limite_maximo = limite_ausentes
               

                # cálculo previsto do EPTC
                ausentes_ajustados = ausentes * 0.587
                eptc_estimado = 100 - (ausentes_ajustados / primeira_tentativa * 100)

            except ValueError:
                mensagem = "Por favor, insira números válidos."

        # 🔹 Caso 2: Atualização de lado A/B
        else:
            lado = request.form.get("lado")
            atendidas = request.form.getlist("atendidas")

            if lado_bloqueado:
                mensagem = f"O lado {lado_sugerido} já foi atualizado em {hoje.strftime('%d/%m/%Y')}."
            else:
                for regiao in [r for r in regioes if r.endswith(lado)]:
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

                    cur.execute(
                        "INSERT INTO regioes_status (regiao, status, data_registro) VALUES (%s, %s, NOW())",
                        (regiao, status_regioes[regiao])
                    )

                cur.execute(
                    "INSERT INTO lado_atualizacao (lado, data_registro) VALUES (%s, NOW())",
                    (lado,)
                )
                conn.commit()
                mensagem = f"Distribuição registrada para lado {lado} em {hoje.strftime('%d/%m/%Y')}."

    cur.close()
    conn.close()

    regioes_filtradas = {r: regioes[r] for r in regioes if r.endswith(lado_sugerido)}

    return render_template(
        "index.html",
        regioes=regioes_filtradas,
        todas_regioes=regioes,
        status=status_regioes,
        observacoes=observacoes,
        data=datetime.now().strftime("%d/%m/%Y"),
        lado=lado,  # pode ser None se for GET
        lado_bloqueado=lado_bloqueado,
        mensagem=mensagem,
        lado_sugerido=lado_sugerido,
        # 🔹 Variáveis do EPTC
        eptc_estimado=eptc_estimado,
        primeira_tentativa=primeira_tentativa,
        ausentes_ajustados=ausentes_ajustados,
        limite_maximo=limite_maximo
    )

# -------------------- Salvar observação --------------------
@app.route("/salvar_obs", methods=["POST"])
def salvar_observacao():
    data = request.get_json()
    regiao = data.get("regiao")
    texto = data.get("obs", "")
    observacoes[regiao] = texto

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO regioes_obs (regiao, observacao, data_registro) VALUES (%s, %s, NOW())", (regiao, texto))
    conn.commit()
    cur.close()
    conn.close()

    return jsonify({"sucesso": True, "regiao": regiao, "observacao": texto})

# -------------------- Endpoint dados --------------------
@app.route("/dados")
def dados():
    return jsonify({"status": status_regioes, "observacoes": observacoes})

# -------------------- Main --------------------
if __name__ == "__main__":
    app.run(debug=True)
















