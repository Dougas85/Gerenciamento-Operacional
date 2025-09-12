from flask import Flask, render_template, request, jsonify
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import date, datetime

app = Flask(__name__)

# Configuração do banco
DB_CONFIG = {
    "dbname": "flaskdb_local",
    "user": "postgres",
    "password": "lara1503",
    "host": "localhost",
    "port": "5432"
}

def get_db_conn():
    return psycopg2.connect(**DB_CONFIG)


# ------------------ Funções auxiliares ------------------
def criar_tabelas():
    """Cria tabelas necessárias caso não existam"""
    conn = get_db_conn()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS lado_atualizacao (
            data DATE PRIMARY KEY,
            lado VARCHAR(1) NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS regioes_status (
            data DATE NOT NULL,
            regiao VARCHAR(20) NOT NULL,
            status VARCHAR(10) NOT NULL,
            PRIMARY KEY (data, regiao)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS regioes_obs (
            regiao VARCHAR(20) PRIMARY KEY,
            observacao TEXT
        )
    """)
    conn.commit()
    cur.close()
    conn.close()


def carregar_status_do_dia(data_hoje):
    """Carrega status de todas as regiões para a data do dia"""
    conn = get_db_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("SELECT regiao, status FROM regioes_status WHERE data = %s", (data_hoje,))
    rows = cur.fetchall()
    cur.close()
    conn.close()

    status = {}
    for r in rows:
        status[r["regiao"]] = r["status"]
    return status


def salvar_status_do_dia(data_hoje, status_dict):
    """Apaga status do dia e salva os novos"""
    conn = get_db_conn()
    cur = conn.cursor()

    cur.execute("DELETE FROM regioes_status WHERE data = %s", (data_hoje,))
    for regiao, status in status_dict.items():
        cur.execute(
            "INSERT INTO regioes_status (data, regiao, status) VALUES (%s, %s, %s)",
            (data_hoje, regiao, status)
        )

    conn.commit()
    cur.close()
    conn.close()


def carregar_observacoes():
    conn = get_db_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT regiao, observacao FROM regioes_obs")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    obs = {}
    for r in rows:
        obs[r["regiao"]] = r["observacao"] or ""
    return obs


def salvar_observacao(regiao, texto):
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO regioes_obs (regiao, observacao)
        VALUES (%s, %s)
        ON CONFLICT (regiao) DO UPDATE SET observacao = EXCLUDED.observacao
    """, (regiao, texto))
    conn.commit()
    cur.close()
    conn.close()


# ------------------ Rotas ------------------
@app.route("/", methods=["GET", "POST"])
def index():
    data_hoje = date.today()

    # exemplo fixo de regiões (substitua pelo seu dicionário real)
    todas_regioes = {
        "601 A": {"coords": [-22.121, -51.389]},
        "601 B": {"coords": [-22.131, -51.401]},
        "602 A": {"coords": [-22.141, -51.392]},
        "602 B": {"coords": [-22.151, -51.402]},
    }

    criar_tabelas()

    conn = get_db_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Qual lado já foi atualizado hoje?
    cur.execute("SELECT lado FROM lado_atualizacao WHERE data = %s", (data_hoje,))
    row = cur.fetchone()
    lado_bloqueado = bool(row)
    lado_sugerido = "A" if (not row or row["lado"] == "B") else "B"

    if request.method == "POST":
        if lado_bloqueado:
            return jsonify({"erro": "Distribuição já registrada hoje."}), 400

        lado = request.form.get("lado")
        atendidas = request.form.getlist("atendidas")

        # carregamos status do dia (antes de alterar)
        status_atual = carregar_status_do_dia(data_hoje)

        # atualiza apenas regiões do lado escolhido
        for regiao in todas_regioes.keys():
            if not regiao.endswith(lado):
                continue
            if regiao in atendidas:
                status_atual[regiao] = "verde"
            else:
                # progressão amarelo → vermelho
                if status_atual.get(regiao) == "verde":
                    status_atual[regiao] = "amarelo"
                elif status_atual.get(regiao) == "amarelo":
                    status_atual[regiao] = "vermelho"
                else:
                    status_atual[regiao] = "amarelo"  # primeira ausência

        salvar_status_do_dia(data_hoje, status_atual)

        # grava lado atualizado
        cur.execute(
            "INSERT INTO lado_atualizacao (data, lado) VALUES (%s, %s) "
            "ON CONFLICT (data) DO UPDATE SET lado = EXCLUDED.lado",
            (data_hoje, lado)
        )
        conn.commit()

        cur.close()
        conn.close()
        return jsonify({"mensagem": f"Distribuição registrada para lado {lado} em {data_hoje}."})

    # GET → carregar dados atuais
    status = carregar_status_do_dia(data_hoje)
    observacoes = carregar_observacoes()

    cur.close()
    conn.close()

    return render_template(
        "index.html",
        todas_regioes=todas_regioes,
        status=status,
        observacoes=observacoes,
        data=data_hoje.strftime("%d/%m/%Y"),
        lado_bloqueado=lado_bloqueado,
        lado_sugerido=lado_sugerido
    )


@app.route("/salvar_obs", methods=["POST"])
def salvar_obs():
    data = request.get_json()
    regiao = data.get("regiao")
    obs = data.get("obs", "")
    salvar_observacao(regiao, obs)
    return jsonify({"mensagem": "Observação salva."})


if __name__ == "__main__":
    app.run(debug=True)
