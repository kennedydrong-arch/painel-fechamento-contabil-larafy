# -*- coding: utf-8 -*-
"""Le dados/bruto.json (o que veio da API) e gera os arquivos do painel.

Saidas:
    data/fechamento.json   - painel de fechamento contabil (o pedido da Juliane)
    data/operacional.json  - painel operacional: todas as obrigacoes, por area
    data/historico.json    - uma linha por rodada, para auditar o avanco

Regra do fechamento (definida com o Kennedy em 26/08/2026):
    uma empresa esta FECHADA quando a tarefa "FECHAMENTO CONTABIL" dela
    naquela competencia esta entregue - no prazo ou atrasada, tanto faz.
    Tarefa dispensada/inativa sai do total (nao conta contra nem a favor).
"""
import datetime as dt
import json
import os
import re
import sys
import unicodedata
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from classificador import ENTREGUE, RANK, classificar    # noqa: E402

AQUI = os.path.dirname(os.path.abspath(__file__))
BRUTO = os.path.join(AQUI, "dados", "bruto.json")
DIR_DATA = os.path.join(AQUI, "data")

MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]

# a tarefa que define o fechamento; o resto do nome e o regime (LP, SN, LRA...)
RE_FECHAMENTO = re.compile(r"^fechamento contabil\b")
APOIO = {"BALANCETE MENSAL": "balancete", "CHECKLIST CONTABIL SR": "checklist"}


def sem_acento(s):
    s = unicodedata.normalize("NFD", str(s or ""))
    return "".join(c for c in s if unicodedata.category(c) != "Mn").lower().strip()


def data_iso(v):
    """'2026-07-01' -> date. Trata o '0000-00-00' que a API usa como vazio."""
    s = str(v or "").strip()
    if not s or s.startswith("0000"):
        return None
    try:
        return dt.date.fromisoformat(s[:10])
    except ValueError:
        pass
    m = re.match(r"^(\d{2})/(\d{2})/(\d{4})", s)
    if m:
        return dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    return None


def competencia_label(d):
    return "%s/%s" % (MESES[d.month - 1], str(d.year)[-2:]) if d else ""


def ordem_comp(label):
    m = re.match(r"([a-z]{3})/(\d{2})", str(label or ""))
    return int(m.group(2)) * 100 + MESES.index(m.group(1)) + 1 if m else 0


def so_digitos(s):
    return re.sub(r"\D", "", str(s or ""))


def pct(parte, total):
    return round(parte * 100.0 / total, 1) if total else 0.0


# ---------------------------------------------------------------- normalizacao

def achatar(bruto):
    """Transforma o JSON da API numa lista plana de entregas, ja classificadas."""
    hoje = dt.date.today()
    linhas = []
    for emp in bruto.get("empresas", []):
        cnpj = so_digitos(emp.get("Identificador"))
        razao = (emp.get("Razao") or "").strip()
        cad = emp.get("_cadastro") or {}
        uf = (cad.get("UF") or emp.get("UF") or "").strip()
        regime_cad = (cad.get("Regime") or emp.get("Regime") or "").strip()
        grupo = (cad.get("GrupoDeEmpresas") or emp.get("GrupoDeEmpresas") or "").strip()
        for e in emp.get("Entregas") or []:
            status = (e.get("Status") or "").strip()
            semaforo, justificado = classificar(status)
            comp = data_iso(e.get("EntCompetencia"))
            d_prazo = data_iso(e.get("EntDtPrazo"))       # prazo tecnico (interno)
            d_legal = data_iso(e.get("EntDtAtraso"))      # a partir daqui e atraso
            d_entrega = data_iso(e.get("EntDtEntrega"))
            ref = d_legal or d_prazo

            if d_entrega and ref:
                atraso = max(0, (d_entrega - ref).days)
            elif not d_entrega and ref and semaforo in ("red", "amber"):
                atraso = max(0, (hoje - ref).days)        # atraso que ainda corre
            else:
                atraso = 0

            cfg = e.get("Config") or {}
            linhas.append({
                "cnpj": cnpj,
                "empresa": razao,
                "uf": uf,
                "regime": regime_cad,
                "grupo": grupo,
                "obrigacao": (e.get("Nome") or "").strip(),
                "competencia": competencia_label(comp),
                "competencia_iso": comp.isoformat() if comp else "",
                "prazo_tecnico": d_prazo.isoformat() if d_prazo else "",
                "prazo_legal": d_legal.isoformat() if d_legal else "",
                "data_entrega": d_entrega.isoformat() if d_entrega else "",
                "status_original": status,
                "status_semaforo": semaforo,
                "justificado": justificado,
                "dias_atraso": atraso,
                "entregue": semaforo in ENTREGUE,
                "departamento": (cfg.get("DptoNome") or "").strip(),
                "responsavel": ((e.get("RespEntrega") or cfg.get("RespEntrega")
                                 or cfg.get("RespPrazo") or "").strip()),
                "multa": e.get("EntMulta") == "S",
                "ent_id": cfg.get("EntID") or "",
                "atualizado_em": e.get("EntLastDH") or "",
            })
    return linhas


def deduplicar(linhas):
    """Mesma empresa + obrigacao + competencia so pode aparecer uma vez.

    Fica a mais resolvida; empatou, fica a de entrega mais recente.
    """
    mapa = {}
    for a in linhas:
        chave = (a["cnpj"], a["obrigacao"], a["competencia"])
        atual = mapa.get(chave)
        if atual is None:
            mapa[chave] = a
            continue
        if RANK.get(a["status_semaforo"], 0) > RANK.get(atual["status_semaforo"], 0):
            mapa[chave] = a
        elif RANK.get(a["status_semaforo"], 0) == RANK.get(atual["status_semaforo"], 0):
            if (a["data_entrega"] or "") > (atual["data_entrega"] or ""):
                mapa[chave] = a
    return list(mapa.values())


# ---------------------------------------------------------------- fechamento

SIGLA_REGIME = {
    "simples nacional": "Simples Nacional", "mei": "MEI",
    "lucro presumido": "Lucro Presumido", "lucro real": "Lucro Real",
    "lucro real anual": "Lucro Real", "lucro real trimestral": "Lucro Real",
    "lucro arbitrado": "Lucro Arbitrado", "imune": "Imune/Isenta",
    "isenta": "Imune/Isenta", "terceiro setor": "Terceiro Setor",
    # como vinha no NOME da tarefa ate abr/2026, quando o cadastro nao responde
    "sn": "Simples Nacional", "lp": "Lucro Presumido",
    "lra": "Lucro Real", "lrt": "Lucro Real",
}


def regime_de(linha):
    """O regime vem do CADASTRO da empresa.

    Ate abr/2026 a tarefa se chamava "FECHAMENTO CONTABIL SN/LP/LRA"; de
    mai/2026 em diante virou so "FECHAMENTO CONTABIL". Por isso o nome da
    tarefa e apenas o plano B.
    """
    cad = sem_acento(linha.get("regime"))
    if cad in SIGLA_REGIME:
        return SIGLA_REGIME[cad]
    if cad:
        return str(linha.get("regime")).title()
    resto = sem_acento(linha.get("obrigacao")).replace("fechamento contabil", "")
    resto = resto.replace("prioritarias", "").strip()
    resto = re.sub(r"\bdia\s*\d+\b", "", resto).strip()
    return SIGLA_REGIME.get(resto, resto.upper() or "Sem regime")


def bloco_fechamento(linhas, competencias, empresas_ativas=None):
    fech = [a for a in linhas if RE_FECHAMENTO.match(sem_acento(a["obrigacao"]))]
    apoio = [a for a in linhas if sem_acento(a["obrigacao"]).upper() in APOIO]
    empresas_ativas = empresas_ativas or {}
    por_comp = {}

    for comp in competencias:
        ativas = [a for a in fech if a["competencia"] == comp and a["status_semaforo"] != "gray"]
        if not ativas:
            continue
        dispensadas = len({a["cnpj"] for a in fech
                           if a["competencia"] == comp and a["status_semaforo"] == "gray"}
                          - {a["cnpj"] for a in ativas})

        # o indicador e "% de EMPRESAS fechadas", nao "% de tarefas".
        # Hoje o Acessorias so deixa uma tarefa de fechamento ativa por empresa,
        # mas se um dia deixar duas, a empresa so conta como fechada quando as
        # duas estiverem entregues - por isso fica a pior das tarefas dela.
        por_cnpj = {}
        for a in ativas:
            atual = por_cnpj.get(a["cnpj"])
            if atual is None:
                por_cnpj[a["cnpj"]] = a
                continue
            if atual["entregue"] and not a["entregue"]:
                por_cnpj[a["cnpj"]] = a                       # falta uma: nao fechou
            elif atual["entregue"] == a["entregue"]:
                if a["dias_atraso"] > atual["dias_atraso"] or \
                        (a["data_entrega"] or "") > (atual["data_entrega"] or ""):
                    por_cnpj[a["cnpj"]] = a
        alvo = list(por_cnpj.values())
        total = len(alvo)
        concluidas = [a for a in alvo if a["entregue"]]
        atrasadas = [a for a in alvo if a["status_semaforo"] == "red"]
        pendentes = [a for a in alvo if a["status_semaforo"] == "amber"]
        no_prazo = [a for a in concluidas if a["status_semaforo"] == "green"]

        # evolucao: quantas empresas fecharam a cada dia (acumulado)
        entregas = sorted(a["data_entrega"] for a in concluidas if a["data_entrega"])
        curva, acc = [], 0
        for dia in sorted(set(entregas)):
            no_dia = entregas.count(dia)
            acc += no_dia
            curva.append({"dia": dia, "no_dia": no_dia,
                          "acumulado": acc, "percentual": pct(acc, total)})

        # ritmo por pessoa
        resp = defaultdict(lambda: {"total": 0, "concluidas": 0, "atrasadas": 0, "pendentes": 0})
        for a in alvo:
            r = resp[a["responsavel"] or "Sem responsavel"]
            r["total"] += 1
            if a["entregue"]:
                r["concluidas"] += 1
            elif a["status_semaforo"] == "red":
                r["atrasadas"] += 1
            else:
                r["pendentes"] += 1
        # quem tem mais coisa em aberto aparece primeiro: o painel serve para
        # saber onde o fechamento esta parado, nao para premiar quem terminou.
        ranking = sorted(
            [dict(nome=k, percentual=pct(v["concluidas"], v["total"]), **v)
             for k, v in resp.items()],
            key=lambda x: (-(x["pendentes"] + x["atrasadas"]), -x["total"], x["nome"]))

        # por regime tributario
        reg = defaultdict(lambda: {"total": 0, "concluidas": 0})
        for a in alvo:
            g = reg[regime_de(a)]
            g["total"] += 1
            if a["entregue"]:
                g["concluidas"] += 1
        regimes = sorted([dict(regime=k, percentual=pct(v["concluidas"], v["total"]), **v)
                          for k, v in reg.items()], key=lambda x: -x["total"])

        # apoio: balancete e checklist da mesma competencia
        ap = {}
        for nome, chave in APOIO.items():
            c = [a for a in apoio if sem_acento(a["obrigacao"]).upper() == nome
                 and a["competencia"] == comp and a["status_semaforo"] != "gray"]
            if c:
                ok = len([a for a in c if a["entregue"]])
                ap[chave] = {"nome": nome, "total": len(c), "concluidas": ok,
                             "percentual": pct(ok, len(c))}

        # Empresa ativa que nao tem NENHUMA tarefa de fechamento na competencia -
        # nem dispensada. Ela nao entra no total, entao o painel nao a enxerga:
        # se deveria ter fechamento, o indicador esta medindo menos do que deveria.
        com_tarefa = {a["cnpj"] for a in fech if a["competencia"] == comp}
        sem_tarefa = sorted(
            ({"cnpj": c, "empresa": d.get("empresa", ""), "regime": d.get("regime", ""),
              "uf": d.get("uf", "")}
             for c, d in empresas_ativas.items() if c not in com_tarefa),
            key=lambda x: x["empresa"])

        prazos = [a["prazo_legal"] for a in alvo if a["prazo_legal"]]
        tecnicos = [a["prazo_tecnico"] for a in alvo if a["prazo_tecnico"]]
        por_comp[comp] = {
            # quando o time comeca a trabalhar essa competencia (o 1o prazo tecnico)
            "abre_em": min(tecnicos) if tecnicos else "",
            "total": total,
            "concluidas": len(concluidas),
            "concluidas_no_prazo": len(no_prazo),
            "concluidas_atrasadas": len(concluidas) - len(no_prazo),
            "pendentes": len(pendentes),
            "atrasadas": len(atrasadas),
            "dispensadas": dispensadas,
            "sem_tarefa": len(sem_tarefa),
            "sem_tarefa_lista": sem_tarefa,
            "percentual": pct(len(concluidas), total),
            "percentual_pendentes": pct(len(pendentes), total),
            "percentual_atrasadas": pct(len(atrasadas), total),
            "prazo_legal": max(prazos) if prazos else "",
            "curva": curva,
            "por_responsavel": ranking,
            "por_regime": regimes,
            "apoio": ap,
            "empresas": sorted([{
                "cnpj": a["cnpj"], "empresa": a["empresa"], "uf": a["uf"],
                "grupo": a.get("grupo", ""),
                "regime": regime_de(a), "obrigacao": a["obrigacao"],
                "status": a["status_original"], "semaforo": a["status_semaforo"],
                "entregue": a["entregue"], "responsavel": a["responsavel"],
                "prazo": a["prazo_legal"] or a["prazo_tecnico"],
                "entrega": a["data_entrega"], "dias_atraso": a["dias_atraso"],
            } for a in alvo], key=lambda x: (x["entregue"], -x["dias_atraso"], x["empresa"])),
        }
    return por_comp


# ---------------------------------------------------------------- painel geral

# Chaves ja normalizadas (sem acento, minusculas). Comparar com .title() quebra
# em "Retidos e Simples Nacional", que vira "Retidos E Simples Nacional" e nao
# bate - o departamento inteiro caia fora do painel sem ninguem perceber.
TIME = {
    "contabil": "Contabil",
    "compartilhadas contabil fiscal": "Contabil",
    "fiscal": "Fiscal",
    "retidos e simples nacional": "Fiscal",
}
NOME_TIME = {"Fiscal": "Fiscal", "Contabil": "Contábil", "Outras": "Outras áreas"}


def time_de(departamento):
    return TIME.get(sem_acento(departamento), "Outras")


def kpi(conj):
    total = len(conj)
    g = len([a for a in conj if a["status_semaforo"] == "green"])
    rd = len([a for a in conj if a["status_semaforo"] == "red_done"])
    r = len([a for a in conj if a["status_semaforo"] == "red"])
    am = len([a for a in conj if a["status_semaforo"] == "amber"])
    return {"total": total, "entregues": g, "entregues_atrasados": rd,
            "atrasadas": r, "pendentes": am,
            "percentual_entregues": pct(g + rd, total),
            "percentual_no_prazo": pct(g, total),
            "percentual_atrasadas": pct(r, total),
            "percentual_pendentes": pct(am, total)}


def bloco_operacional(linhas, comps, foco):
    """Painel do dia a dia: como estao TODAS as obrigacoes, nao so o fechamento.

    Aqui o recorte e por time (Fiscal / Contabil / Outras areas), e o que
    interessa e o que esta em aberto - inclusive o passivo de meses ja
    vencidos, que some quando se olha so a competencia do mes.
    """
    vivas = [a for a in linhas if a["status_semaforo"] != "gray"]
    times = ["Fiscal", "Contabil", "Outras"]
    for a in vivas:
        a["time"] = time_de(a["departamento"])

    por_competencia = {}
    for comp in comps:
        do_mes = [a for a in vivas if a["competencia"] == comp]
        if not do_mes:
            continue

        # obrigacoes que mais seguram o mes
        obrig = defaultdict(lambda: {"total": 0, "entregues": 0,
                                     "pendentes": 0, "atrasadas": 0, "time": ""})
        for a in do_mes:
            o = obrig[a["obrigacao"]]
            o["total"] += 1
            o["time"] = o["time"] or NOME_TIME.get(a["time"], a["time"])
            if a["entregue"]:
                o["entregues"] += 1
            elif a["status_semaforo"] == "red":
                o["atrasadas"] += 1
            else:
                o["pendentes"] += 1

        por_competencia[comp] = {
            "geral": kpi(do_mes),
            "times": {t: kpi([a for a in do_mes if a["time"] == t]) for t in times},
            "ranking": {t: ranking_de([a for a in do_mes if a["time"] == t]) for t in times},
            "obrigacoes": sorted(
                [dict(obrigacao=k, percentual=pct(v["entregues"], v["total"]), **v)
                 for k, v in obrig.items()],
                key=lambda x: (-x["atrasadas"], -x["pendentes"], -x["total"]))[:40],
        }

    # A linha vai so ate a competencia em foco: o mes corrente ainda esta sendo
    # trabalhado e entraria com ~1% entregue, dando impressao de despencada.
    tendencia = []
    for comp in sorted(por_competencia, key=ordem_comp):
        if ordem_comp(comp) > ordem_comp(foco):
            continue
        b = por_competencia[comp]
        tendencia.append({
            "competencia": comp,
            "total": b["geral"]["total"],
            "geral": b["geral"]["percentual_entregues"],
            "fiscal": b["times"]["Fiscal"]["percentual_entregues"],
            "contabil": b["times"]["Contabil"]["percentual_entregues"],
        })

    # Passivo: atrasada e ainda NAO entregue, de qualquer competencia. E o que
    # nao aparece quando se olha so o mes corrente - e o que mais cobra multa.
    atrasadas = [a for a in vivas if a["status_semaforo"] == "red"]
    passivo_comp = defaultdict(int)
    passivo_time = defaultdict(int)
    for a in atrasadas:
        passivo_comp[a["competencia"]] += 1
        passivo_time[NOME_TIME.get(a["time"], a["time"])] += 1

    def enxuto(a):
        return {"empresa": a["empresa"], "cnpj": a["cnpj"], "uf": a["uf"],
                "obrigacao": a["obrigacao"], "competencia": a["competencia"],
                "time": NOME_TIME.get(a["time"], a["time"]),
                "departamento": a["departamento"], "responsavel": a["responsavel"],
                "status": a["status_original"], "semaforo": a["status_semaforo"],
                "prazo": a["prazo_legal"] or a["prazo_tecnico"],
                "dias_atraso": a["dias_atraso"], "multa": a["multa"]}

    # detalhe do que esta em aberto: tudo que nao foi entregue ate a competencia
    # em foco. O mes corrente fica de fora da lista (ainda nem comecou) mas
    # continua nos indicadores.
    limite = ordem_comp(foco)
    aberto = [enxuto(a) for a in vivas
              if not a["entregue"] and ordem_comp(a["competencia"]) <= limite]
    aberto.sort(key=lambda x: (-x["dias_atraso"], x["empresa"]))

    return {
        "competencias": comps,
        "competencia_foco": foco,
        "times": times,
        "nome_time": NOME_TIME,
        "por_competencia": por_competencia,
        "tendencia": tendencia,
        "passivo": {
            "total": len(atrasadas),
            "com_multa": len([a for a in atrasadas if a["multa"]]),
            "por_time": dict(passivo_time),
            "por_competencia": sorted(
                [{"competencia": c, "total": n} for c, n in passivo_comp.items()],
                key=lambda x: ordem_comp(x["competencia"]), reverse=True),
            "mais_antigos": [enxuto(a) for a in
                             sorted(atrasadas, key=lambda a: -a["dias_atraso"])[:60]],
        },
        "aberto": aberto,
    }


def ranking_de(conj):
    d = defaultdict(lambda: {"total": 0, "entregues": 0, "atrasadas": 0,
                             "pendentes": 0, "entregues_atrasados": 0})
    for a in conj:
        x = d[a["responsavel"] or "Sem responsavel"]
        x["total"] += 1
        if a["status_semaforo"] == "green":
            x["entregues"] += 1
        elif a["status_semaforo"] == "red_done":
            x["entregues_atrasados"] += 1
        elif a["status_semaforo"] == "red":
            x["atrasadas"] += 1
        elif a["status_semaforo"] == "amber":
            x["pendentes"] += 1
    return sorted([dict(nome=k,
                        percentual=pct(v["entregues"] + v["entregues_atrasados"], v["total"]),
                        **v) for k, v in d.items()],
                  key=lambda x: (-x["percentual"], -x["total"]))


def main():
    if not os.path.exists(BRUTO):
        print("Nao achei %s. Rode 'py coletar.py' antes." % BRUTO)
        return 1
    with open(BRUTO, encoding="utf-8") as f:
        bruto = json.load(f)

    linhas = deduplicar(achatar(bruto))
    linhas = [a for a in linhas if a["competencia"]]

    hoje = dt.date.today()
    limite = competencia_label(hoje)                       # nao mostra competencia futura
    comps = sorted({a["competencia"] for a in linhas}, key=ordem_comp, reverse=True)
    comps = [c for c in comps if ordem_comp(c) <= ordem_comp(limite)]

    # Competencia truncada nao entra. A coleta filtra pelo PRAZO, entao de uma
    # competencia velha so chega o pedaco cujo prazo caiu dentro do periodo -
    # ela apareceria com 40 tarefas em vez de 6.000 e distorceria o grafico.
    volume = {c: len([a for a in linhas if a["competencia"] == c]) for c in comps}
    ordenados = sorted(volume.values())
    mediana = ordenados[len(ordenados) // 2] if ordenados else 0
    parciais = [c for c in comps if volume[c] < mediana * 0.4]
    if parciais:
        print("Competencias incompletas, fora do painel: %s"
              % ", ".join("%s (%d tarefas)" % (c, volume[c]) for c in parciais))
    comps = [c for c in comps if c not in parciais]
    linhas = [a for a in linhas if a["competencia"] in comps]

    # cadastro das empresas ativas, para saber quem ficou de fora do painel
    empresas_ativas = {}
    for emp in bruto.get("empresas", []):
        cad = emp.get("_cadastro") or {}
        if (cad.get("Status") or emp.get("Status") or "Ativa") != "Ativa":
            continue
        cnpj = so_digitos(emp.get("Identificador"))
        if cnpj:
            empresas_ativas[cnpj] = {
                "empresa": (emp.get("Razao") or "").strip(),
                "regime": (cad.get("Regime") or "").strip(),
                "uf": (cad.get("UF") or "").strip(),
            }

    fechamento = bloco_fechamento(linhas, comps, empresas_ativas)
    comps_fech = [c for c in comps if c in fechamento]

    # Competencia em foco = a mais recente que o time JA comecou a trabalhar.
    # A competencia do mes corrente ja existe no Acessorias, mas so comeca a
    # ser fechada no mes seguinte - abrir o painel nela mostraria 0% e
    # assustaria a gestao sem motivo.
    hoje_iso = hoje.isoformat()
    em_trabalho = [c for c in comps_fech
                   if fechamento[c]["abre_em"] and fechamento[c]["abre_em"] <= hoje_iso]
    foco = em_trabalho[0] if em_trabalho else (comps_fech[0] if comps_fech else
                                               (comps[0] if comps else ""))

    agora = dt.datetime.now().astimezone()
    meta = {
        "atualizado_em": agora.isoformat(timespec="seconds"),
        "coletado_em": bruto.get("coletado_em"),
        "fonte": "api.acessorias.com",
        "periodo": {"de": bruto.get("dt_inicial"), "ate": bruto.get("dt_final")},
        "total_empresas": len({a["cnpj"] for a in linhas}),
        "total_entregas": len(linhas),
        "falhas_na_coleta": len(bruto.get("falhas") or []),
    }

    os.makedirs(DIR_DATA, exist_ok=True)

    with open(os.path.join(DIR_DATA, "fechamento.json"), "w", encoding="utf-8") as f:
        json.dump({"meta": meta, "competencia_foco": foco,
                   "competencias": comps_fech, "fechamento": fechamento},
                  f, ensure_ascii=False)

    operacional = bloco_operacional(linhas, comps, foco)
    operacional["meta"] = meta
    with open(os.path.join(DIR_DATA, "operacional.json"), "w", encoding="utf-8") as f:
        json.dump(operacional, f, ensure_ascii=False)

    # historico: uma linha por rodada, para conferir se o painel avanca
    hist_path = os.path.join(DIR_DATA, "historico.json")
    hist = []
    if os.path.exists(hist_path):
        try:
            with open(hist_path, encoding="utf-8") as f:
                hist = json.load(f)
        except json.JSONDecodeError:
            hist = []
    hist = [h for h in hist if h.get("dia") != hoje.isoformat()]      # 1 registro por dia
    hist.append({"dia": hoje.isoformat(), "em": meta["atualizado_em"],
                 "competencias": {c: {"total": fechamento[c]["total"],
                                      "concluidas": fechamento[c]["concluidas"],
                                      "percentual": fechamento[c]["percentual"]}
                                  for c in comps_fech[:4]}})
    hist.sort(key=lambda h: h["dia"])
    with open(hist_path, "w", encoding="utf-8") as f:
        json.dump(hist, f, ensure_ascii=False, indent=1)

    print("Empresas: %d | entregas: %d" % (meta["total_empresas"], meta["total_entregas"]))
    print("Competencias: %s" % ", ".join(comps))
    print()
    print("FECHAMENTO CONTABIL")
    for c in comps_fech:
        b = fechamento[c]
        print("  %-7s %3d/%3d concluidas (%5.1f%%) | pendentes %3d | atrasadas %3d | dispensadas %3d"
              % (c, b["concluidas"], b["total"], b["percentual"],
                 b["pendentes"], b["atrasadas"], b["dispensadas"]))
    print()
    for nome, arq in (("fechamento", "fechamento.json"), ("operacional", "operacional.json")):
        p = os.path.join(DIR_DATA, arq)
        print("  %-12s -> %s (%.1f MB)" % (nome, arq, os.path.getsize(p) / 1024 / 1024))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
