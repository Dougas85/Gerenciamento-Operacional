from flask import Flask, render_template, request, jsonify
from datetime import datetime
import json, os

app = Flask(__name__)

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

data_atual = datetime.now().strftime("%d/%m/%Y")

@app.route("/")
def index():
    lado = request.args.get("lado", "A")
    # Regiões que serão mostradas como CARDS (apenas do lado selecionado)
    regioes_filtradas = {r: regioes[r] for r in regioes if r.endswith(lado)}
    # dias sem entrega (mantive sua lógica)
    dias_sem_entrega = [r for r, s in status_regioes.items() if s == "vermelho"]

    # Renderiza passando:
    # - regioes: SOMENTE as do lado (para os cards)
    # - todas_regioes: TODAS as regioes (para desenhar todos os marcadores no mapa)
    # - status: o dicionário com o status GLOBAL de todas as regioes
    return render_template(
        "index.html",
        regioes=regioes_filtradas,
        todas_regioes=regioes,
        status=status_regioes,
        observacoes=observacoes,
        data=data_atual,
        dias_sem_entrega=dias_sem_entrega,
        lado=lado
    )


@app.route("/", methods=["POST"])
def atualizar():
    lado = request.form.get("lado")
    atendidas = request.form.getlist("atendidas")

    for regiao in [r for r in regioes.keys() if r.endswith(lado)]:
        if regiao in atendidas:
            status_regioes[regiao] = "verde"
        else:
            if status_regioes[regiao] == "verde":
                status_regioes[regiao] = "amarelo"
            elif status_regioes[regiao] == "amarelo":
                status_regioes[regiao] = "vermelho"

    return ("", 204)

@app.route("/salvar_obs", methods=["POST"])
def salvar_observacao():
    data = request.get_json()
    regiao = data.get("regiao")
    texto = data.get("obs", "")
    observacoes[regiao] = texto
    return jsonify({"sucess": True, "regiao": regiao, "observacao": texto})

@app.route("/dados")
def dados():
    return jsonify({
        "status": status_regioes,
        "observacoes": observacoes
    })


if __name__ == "__main__":
    app.run(debug=True)