# -*- coding: utf-8 -*-
"""Reconta os numeros do painel por um caminho independente e compara.

Nao importa nada de processar.py de proposito: le o bruto da API e conta na
mao, com listas fixas de status em vez de expressao regular. Se os dois
caminhos chegarem no mesmo numero, o numero e confiavel; se divergirem, o
painel esta errado em algum lugar e o script diz onde.

    py conferir.py
"""
import datetime as dt
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

AQUI = os.path.dirname(os.path.abspath(__file__))
BRUTO = os.path.join(AQUI, "dados", "bruto.json")
PAINEL = os.path.join(AQUI, "data", "fechamento.json")

MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]

# listas fixas, escritas na mao a partir do que o Acessorias devolve.
# Se aparecer um status fora destas listas, o script avisa em vez de chutar.
ENTREGUE = {"entregue", "ent. pztéc", "ent. pztec", "ent. atrasada", "antecipada",
            "ent. antecipada", "ent. justificada", "entregue no prazo",
            "ent. prazo legal", "ent. pzlegal"}
ABERTO = {"pendente", "atrasada!", "atrasada", "prazo técnico", "prazo tecnico",
          "prazo legal", "aguardando", "em andamento"}
FORA = {"dispensada", "inativa", "cancelada", "não se aplica", "nao se aplica"}


def competencia(iso):
    if not iso or str(iso).startswith("0000"):
        return ""
    d = dt.date.fromisoformat(str(iso)[:10])
    return "%s/%s" % (MESES[d.month - 1], str(d.year)[-2:])


def main():
    for caminho in (BRUTO, PAINEL):
        if not os.path.exists(caminho):
            print("Falta %s - rode coletar.py e processar.py antes." % caminho)
            return 1

    with open(BRUTO, encoding="utf-8") as f:
        bruto = json.load(f)
    with open(PAINEL, encoding="utf-8") as f:
        painel = json.load(f)

    # conta na mao: para cada empresa, a tarefa de fechamento de cada competencia
    contagem = {}          # competencia -> {"fechadas": set(cnpj), "abertas": set(cnpj)}
    desconhecidos = {}

    for emp in bruto.get("empresas", []):
        cnpj = "".join(c for c in str(emp.get("Identificador") or "") if c.isdigit())
        for e in emp.get("Entregas") or []:
            nome = (e.get("Nome") or "").strip().upper()
            if not nome.startswith("FECHAMENTO CONT"):
                continue
            if "ANUAL" in nome or "BALAN" in nome and "CONTÁBIL" not in nome:
                continue
            comp = competencia(e.get("EntCompetencia"))
            if not comp:
                continue
            st = (e.get("Status") or "").strip().lower()
            if st in FORA:
                continue
            reg = contagem.setdefault(comp, {"fechadas": set(), "abertas": set()})
            if st in ENTREGUE:
                reg["fechadas"].add(cnpj)
            elif st in ABERTO:
                reg["abertas"].add(cnpj)
            else:
                desconhecidos[st] = desconhecidos.get(st, 0) + 1
                reg["abertas"].add(cnpj)      # na duvida, conta como nao fechada

    if desconhecidos:
        print("ATENCAO: status que eu nao conhecia (contados como NAO fechados):")
        for st, n in sorted(desconhecidos.items(), key=lambda x: -x[1]):
            print("   %4dx  %r" % (n, st))
        print()

    print("%-9s %-22s %-22s %s" % ("comp", "conferencia", "painel", "bate?"))
    print("-" * 70)
    divergencias = 0
    for comp in sorted(painel.get("competencias", []),
                       key=lambda c: (int(c[-2:]), MESES.index(c[:3])), reverse=True):
        p = painel["fechamento"][comp]
        c = contagem.get(comp, {"fechadas": set(), "abertas": set()})
        # a empresa so entra uma vez: se tem tarefa fechada e outra aberta, vale a aberta
        fechadas = c["fechadas"] - c["abertas"]
        total = len(c["fechadas"] | c["abertas"])
        pc_meu = round(len(fechadas) * 100.0 / total, 1) if total else 0.0
        ok = (total == p["total"] and len(fechadas) == p["concluidas"])
        divergencias += 0 if ok else 1
        print("%-9s %3d/%-3d = %5.1f%%      %3d/%-3d = %5.1f%%      %s"
              % (comp, len(fechadas), total, pc_meu,
                 p["concluidas"], p["total"], p["percentual"],
                 "sim" if ok else "NAO <<<"))

    print()
    if divergencias:
        print("%d competencia(s) divergiram. O painel NAO esta confiavel." % divergencias)
        return 1
    print("Os dois caminhos chegaram no mesmo numero em todas as competencias.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
