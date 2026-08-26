# -*- coding: utf-8 -*-
"""Baixa do Acessorias todas as empresas ativas e as entregas de cada uma.

Grava dados/bruto.json. Nao interpreta nada: so guarda o que a API devolveu,
para que o processamento possa ser refeito sem baixar tudo de novo.

Uso:
    py coletar.py                       # 01/jan do ano corrente ate hoje+120d
    py coletar.py 2026-01-01 2026-12-31 # periodo explicito (filtra pelo PRAZO)
    py coletar.py --rapido              # so o que mudou desde a ultima coleta

O --rapido leva ~5 min em vez de ~25, e e o modo do dia a dia. Ele NUNCA apaga
nada: mescla por cima do que ja existe. Uma coleta completa por semana continua
valendo, para pegar uma empresa nova ou uma tarefa recriada.
"""
import datetime as dt
import json
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")        # Windows: evita quebrar no cp1252
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from acessorias import Acessorias                                       # noqa: E402

AQUI = os.path.dirname(os.path.abspath(__file__))
SAIDA = os.path.join(AQUI, "dados", "bruto.json")
PARCIAL = os.path.join(AQUI, "dados", "bruto.parcial.json")


def periodo_padrao():
    hoje = dt.date.today()
    return (dt.date(hoje.year, 1, 1).isoformat(),
            (hoje + dt.timedelta(days=120)).isoformat())


def chave_entrega(e):
    """Identidade de uma entrega, para mesclar sem duplicar."""
    cfg = e.get("Config") or {}
    return (cfg.get("EntID") or "") or (e.get("Nome", ""), e.get("EntCompetencia", ""))


def carregar_anterior():
    if not os.path.exists(SAIDA):
        return None
    try:
        with open(SAIDA, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    rapido = "--rapido" in sys.argv

    anterior = carregar_anterior() if rapido else None
    if rapido and not anterior:
        print("Nao ha coleta anterior para completar - fazendo a coleta completa.")
        rapido = False

    if len(args) >= 2:
        dt_ini, dt_fim = args[0], args[1]
    elif rapido:
        dt_ini, dt_fim = anterior["dt_inicial"], anterior["dt_final"]
    else:
        dt_ini, dt_fim = periodo_padrao()

    dt_last = None
    if rapido:
        # 2 dias de folga: se a rodada anterior parou no meio, nada escapa
        base = dt.datetime.fromisoformat(anterior["coletado_em"]) - dt.timedelta(days=2)
        dt_last = base.strftime("%Y-%m-%d %H:%M:%S")

    # a pasta precisa existir ANTES do primeiro salvamento de progresso,
    # que acontece a cada 25 empresas - nao so no fim
    os.makedirs(os.path.dirname(SAIDA), exist_ok=True)

    t0 = time.time()
    api = Acessorias()
    print(f"Coletando entregas com prazo entre {dt_ini} e {dt_fim}")
    if dt_last:
        print(f"Modo rapido: so o que mudou desde {dt_last}")

    print("Departamentos...")
    departamentos = api.departamentos()
    print(f"  {len(departamentos)} departamentos")

    print("Empresas ativas...")
    empresas = api.empresas(somente_ativas=True)
    print(f"  {len(empresas)} empresas ativas")

    # no modo rapido, parte do que ja foi coletado e vai mesclando por cima
    coletado = {}
    base_rapido = {}
    if rapido:
        base_rapido = {e["ID"]: e for e in anterior.get("empresas", [])}
        print(f"  base anterior: {len(base_rapido)} empresas, "
              f"{sum(len(e.get('Entregas') or []) for e in base_rapido.values())} entregas")

    if os.path.exists(PARCIAL) and not rapido:
        try:
            with open(PARCIAL, encoding="utf-8") as f:
                anterior = json.load(f)
            if anterior.get("dt_inicial") == dt_ini and anterior.get("dt_final") == dt_fim:
                coletado = {e["ID"]: e for e in anterior.get("empresas", [])}
                print(f"  retomando: {len(coletado)} empresas ja baixadas")
        except (json.JSONDecodeError, KeyError, OSError):
            coletado = {}

    total, falhas, sem_entrega = len(empresas), [], 0
    for i, emp in enumerate(empresas, 1):
        eid = emp["ID"]
        if eid in coletado:
            continue
        ident = (emp.get("Identificador") or "").replace(".", "").replace("/", "").replace("-", "")
        try:
            reg = api.entregas_da_empresa(ident or eid, dt_ini, dt_fim, dt_last)
        except Exception as e:                                  # noqa: BLE001
            falhas.append({"ID": eid, "empresa": emp.get("Razao"), "erro": str(e)})
            print(f"  [{i}/{total}] FALHOU {emp.get('Razao')}: {e}")
            if eid in base_rapido:
                coletado[eid] = base_rapido[eid]                # mantem o que ja tinha
            continue

        if reg is None:
            sem_entrega += 1
            reg = {k: v for k, v in emp.items()}
            reg["Entregas"] = []

        if rapido and eid in base_rapido:
            # mescla: a versao nova de cada entrega manda, o resto permanece
            antigas = {chave_entrega(e): e for e in base_rapido[eid].get("Entregas") or []}
            for nova in reg.get("Entregas") or []:
                antigas[chave_entrega(nova)] = nova
            reg["Entregas"] = list(antigas.values())

        reg["_cadastro"] = emp
        coletado[eid] = reg

        if i % 25 == 0 or i == total:
            n = sum(len(r.get("Entregas") or []) for r in coletado.values())
            print(f"  [{i}/{total}] {len(coletado)} empresas, {n} entregas "
                  f"({time.time()-t0:.0f}s, {api.chamadas} chamadas)")
            with open(PARCIAL, "w", encoding="utf-8") as f:
                json.dump({"dt_inicial": dt_ini, "dt_final": dt_fim,
                           "empresas": list(coletado.values())}, f, ensure_ascii=False)

    empresas_out = list(coletado.values())
    n_entregas = sum(len(r.get("Entregas") or []) for r in empresas_out)

    saida = {
        "coletado_em": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "dt_inicial": dt_ini,
        "dt_final": dt_fim,
        "fonte": "api.acessorias.com",
        "departamentos": departamentos,
        "empresas": empresas_out,
        "falhas": falhas,
    }
    os.makedirs(os.path.dirname(SAIDA), exist_ok=True)
    with open(SAIDA, "w", encoding="utf-8") as f:
        json.dump(saida, f, ensure_ascii=False)
    if os.path.exists(PARCIAL):
        os.remove(PARCIAL)

    print()
    print(f"OK: {len(empresas_out)} empresas / {n_entregas} entregas -> {SAIDA}")
    print(f"    {sem_entrega} empresas sem nenhuma entrega no periodo")
    print(f"    {len(falhas)} falhas | {api.chamadas} chamadas | {time.time()-t0:.0f}s")
    if falhas:
        print("    ATENCAO: houve falha. Rode de novo para completar.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
