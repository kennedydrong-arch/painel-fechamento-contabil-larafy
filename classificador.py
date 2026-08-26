# -*- coding: utf-8 -*-
"""Traduz o texto de status do Acessorias em semaforo.

O Acessorias deixa cada escritorio escrever o proprio texto de status
("Ent. PzTec", "Atrasada!", "Prazo tecnico"...). Por isso a classificacao
e por padrao de texto, e nao por lista fechada: status novo que aparecer
cai numa regra generica em vez de sumir do painel.

Herdado do classificador v5.4 que rodava no n8n.
"""
import re
import unicodedata

# quanto maior, mais "resolvido" o status. Usado para desempatar duplicidade.
RANK = {"green": 5, "red_done": 3, "red": 2, "amber": 1, "gray": 0}

ENTREGUE = ("green", "red_done")        # entregue no prazo OU entregue atrasado


def normalizar(s):
    s = str(s or "").lower()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[.!?,;:]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def classificar(status_original):
    """Devolve (semaforo, justificado)."""
    s = normalizar(status_original)
    if not s:
        return "amber", False
    justif = bool(re.search(r"justific", s))

    # entregue, porem fora do prazo
    if (re.search(r"\bent\b.*atra[sz]", s)
            or re.search(r"\bentregue\b.*atra[sz]", s)
            or re.search(r"\bentrega\b.*atra[sz]", s)
            or re.search(r"\bfora\s+(do\s+)?prazo", s)
            or re.search(r"atra[sz]o?\s*justific", s)
            or re.search(r"justific.*atra[sz]", s)):
        return "red_done", justif

    # entregue
    if (re.search(r"\bent\b\s+(?!atra[sz])", s)
            or re.search(r"\bentregue\b(?!.*atra[sz])", s)
            or re.search(r"\bantecipad", s)
            or re.search(r"\bentrega\b.*(pz|prazo|tec|legal|antecip|no\s*prazo|justif)", s)
            or re.search(r"\brealizad", s)
            or re.search(r"\bconcluid", s)
            or re.search(r"\bfinaliza", s)
            or re.search(r"\bok\b", s)):
        return "green", justif

    # atrasada e ainda nao entregue
    if (re.search(r"\batra[sz]", s)
            or re.search(r"\bvencid", s)
            or re.search(r"\bnao\s*entreg", s)):
        return "red", False

    # fora do jogo: nao entra na conta
    if (re.search(r"\bdispens", s)
            or re.search(r"\bcancel", s)
            or re.search(r"\binexig", s)
            or re.search(r"\binativ", s)
            or re.search(r"\bnao\s*se?\s*aplic", s)
            or re.search(r"\bn/?a\b", s)
            or re.search(r"\bsem\s*movimento", s)):
        return "gray", False

    # em aberto, ainda dentro do prazo
    if (re.search(r"\bpend", s)
            or re.search(r"\bandament", s)
            or re.search(r"\babert", s)
            or re.search(r"\baguard", s)
            or re.search(r"\bprazo\s+(tec|legal)", s)
            or re.search(r"\bpz\s*(tec|legal)", s)
            or re.search(r"\bno\s*prazo", s)):
        return "amber", justif

    return "amber", justif        # desconhecido entra como pendente, nunca some
