# -*- coding: utf-8 -*-
"""Cliente da API do Acessorias (api.acessorias.com).

Autenticacao: Bearer token gerado no proprio Acessorias
(engrenagem > API Token). Fica no .env, nunca no codigo.

Limite oficial: 100 requisicoes/minuto (janela deslizante).
Aqui o passo e mais lento de proposito, com margem.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://api.acessorias.com"
PAUSA = 0.70          # ~85 req/min, abaixo do teto de 100
TENTATIVAS = 4


def carregar_token(caminho=None):
    tok = os.environ.get("ACESSORIAS_TOKEN")
    if tok:
        return tok.strip()
    caminho = caminho or os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(caminho):
        with open(caminho, encoding="utf-8") as f:
            for linha in f:
                if linha.startswith("ACESSORIAS_TOKEN="):
                    return linha.split("=", 1)[1].strip()
    raise RuntimeError(
        "Token do Acessorias nao encontrado. Defina ACESSORIAS_TOKEN "
        "no ambiente ou no arquivo .env ao lado deste script."
    )


class Acessorias:
    def __init__(self, token=None, verbose=True):
        self.token = token or carregar_token()
        self.verbose = verbose
        self.chamadas = 0
        self._ultimo = 0.0

    def _log(self, msg):
        if self.verbose:
            print(msg, flush=True)

    def get(self, caminho, params=None):
        """GET no endpoint. Devolve o JSON, ou None quando 204 (sem resultado)."""
        url = BASE + "/" + caminho.lstrip("/")
        if params:
            partes = []
            for k, v in params.items():
                if v is None:
                    partes.append(urllib.parse.quote(str(k)))       # flag sem valor: ?config
                else:
                    partes.append(urllib.parse.urlencode({k: v}))
            url += "?" + "&".join(partes)

        for tentativa in range(1, TENTATIVAS + 1):
            espera = PAUSA - (time.time() - self._ultimo)
            if espera > 0:
                time.sleep(espera)
            req = urllib.request.Request(url, headers={
                "Authorization": "Bearer " + self.token,
                "Accept": "application/json",
                "User-Agent": "LaraFy-PainelContabil/1.0",
            })
            try:
                with urllib.request.urlopen(req, timeout=90) as r:
                    self._ultimo = time.time()
                    self.chamadas += 1
                    if r.status == 204:
                        return None
                    corpo = r.read()
                    if not corpo:
                        return None
                    return json.loads(corpo.decode("utf-8"))
            except urllib.error.HTTPError as e:
                self._ultimo = time.time()
                if e.code == 204:
                    return None
                if e.code == 429:                       # estourou o limite: recua e volta
                    pausa = 20 * tentativa
                    self._log(f"  [429] limite atingido, aguardando {pausa}s")
                    time.sleep(pausa)
                    continue
                if e.code == 401:
                    raise RuntimeError("Token do Acessorias recusado (401). Gere outro no sistema.")
                if e.code == 404:
                    return None
                if tentativa == TENTATIVAS:
                    raise
                time.sleep(3 * tentativa)
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
                self._ultimo = time.time()
                if tentativa == TENTATIVAS:
                    raise
                self._log(f"  [retry {tentativa}] {caminho}: {e}")
                time.sleep(3 * tentativa)
        raise RuntimeError("Falhou depois de %d tentativas: %s" % (TENTATIVAS, caminho))

    # ---------- recursos ----------

    def departamentos(self):
        return self.get("departments/ListAll") or []

    def empresas(self, somente_ativas=True):
        """Percorre todas as paginas de /companies (20 por pagina).

        Com registrationData vem tambem Regime e GrupoDeEmpresas - o regime
        precisa vir daqui porque a tarefa de fechamento deixou de trazer o
        regime no nome a partir de mai/2026.
        """
        todas, pagina = [], 1
        while True:
            params = {"Pagina": pagina, "registrationData": None}
            if somente_ativas:
                params["ativa"] = "S"
            lote = self.get("companies/ListAll", params)
            if not lote:
                break
            todas.extend(lote)
            self._log(f"  empresas: pagina {pagina} (+{len(lote)}, total {len(todas)})")
            if len(lote) < 20:
                break
            pagina += 1
            if pagina > 200:                            # trava contra loop infinito
                self._log("  [aviso] parei em 200 paginas de empresas")
                break
        return todas

    def entregas_da_empresa(self, identificador, dt_inicial, dt_final, dt_last=None):
        """Entregas de UMA empresa. /deliveries nao aceita ListAll: e sempre por empresa.

        dt_inicial/dt_final filtram pelo PRAZO da entrega (nao pela competencia).
        dt_last ('YYYY-MM-DD HH:MM:SS') traz so o que mudou depois daquele momento -
        e o que faz a atualizacao diaria levar 5 minutos em vez de 25.
        Pagina de 50 em 50.
        """
        entregas, pagina, empresa = [], 1, None
        while True:
            params = {
                "DtInitial": dt_inicial,
                "DtFinal": dt_final,
                "config": None,
                "Pagina": pagina,
            }
            if dt_last:
                params["DtLastDH"] = dt_last
            resp = self.get("deliveries/" + str(identificador), params)
            if not resp:
                break
            if empresa is None:
                empresa = {k: v for k, v in resp.items() if k != "Entregas"}
            lote = resp.get("Entregas") or []
            entregas.extend(lote)
            if len(lote) < 50:
                break
            pagina += 1
            if pagina > 100:
                self._log(f"  [aviso] parei em 100 paginas de entregas de {identificador}")
                break
        if empresa is None:
            return None
        empresa["Entregas"] = entregas
        return empresa
