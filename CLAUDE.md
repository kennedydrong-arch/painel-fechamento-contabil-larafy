# Painel de Fechamento Contábil (LaraFy)

Painel que mostra o andamento do fechamento contábil do mês, em percentual, para
o time e para a gestão (pedido da Juliane, agosto/2026).

**Fonte de dados: API oficial do Acessórias.** Não há planilha, não há robô de
navegador, não há n8n. Isso é intencional — veja "O que veio antes".

---

## Como funciona

```
api.acessorias.com  ──coletar.py──▶  dados/bruto.json  ──processar.py──▶  data/*.json  ──▶  index.html
```

| Arquivo | Papel |
|---|---|
| `acessorias.py` | Cliente da API: token, ritmo (85 req/min, teto é 100), retry, recuo no 429 |
| `coletar.py` | Baixa empresas ativas + entregas de cada uma. `--rapido` traz só o que mudou |
| `processar.py` | Aplica as regras e gera `data/fechamento.json`, `data/operacional.json`, `data/historico.json` |
| `classificador.py` | Texto do status → semáforo (green/amber/red/red_done/gray) |
| `index.html` | Painel de fechamento contábil |
| `operacional.html` | Painel operacional: todas as obrigações, por área |
| `estilo.css` | Estilo comum das duas páginas |
| `conferir.py` | Reconta os números por um caminho independente e compara |
| `servir.py` | Servidor local (o painel usa `fetch`, não abre por `file://`) |

`dados/bruto.json` é a resposta crua da API. Mudou uma regra? `py processar.py`
recalcula tudo sem baixar de novo. **Nunca apague o bruto para "limpar".**

---

## A API do Acessórias

- Base: `https://api.acessorias.com` · doc: `https://api.acessorias.com/documentation`
- Auth: `Authorization: Bearer <token>`, token gerado no próprio Acessórias
  (engrenagem → API Token). Fica em `.env`, **fora do Git**.
- Limite: 100 req/min. O cliente anda em ~85 e recua sozinho no 429.

Endpoints que este projeto usa:

| Endpoint | Detalhe importante |
|---|---|
| `GET /companies/ListAll?ativa=S&registrationData&Pagina=N` | 20 por página. `registrationData` traz **Regime** e **GrupoDeEmpresas** |
| `GET /deliveries/{cnpj}?DtInitial&DtFinal&config&Pagina=N` | 50 por página. **`ListAll` NÃO funciona aqui** — é sempre por empresa, por isso a coleta completa leva ~50 min (medido: 409 empresas, 1.932 chamadas) |
| `GET /departments/ListAll` | Contábil, Fiscal, Retidos e Simples Nacional, Gerência… |

`DtInitial`/`DtFinal` filtram pelo **prazo**, não pela competência. Por isso a
coleta pede o ano inteiro e o filtro por competência é feito depois, no
`processar.py`.

`DtLastDH` (formato `YYYY-MM-DD HH:MM:SS`) traz só o que mudou — é o que faz o
`--rapido` existir.

### Campos que importam em cada entrega

| Campo | O que é |
|---|---|
| `EntCompetencia` | Mês de referência (`2026-07-01` = jul/26). **É por aqui que o painel agrupa.** |
| `EntDtPrazo` | Prazo técnico — quando o time deveria entregar |
| `EntDtAtraso` | A partir desta data vira atraso de verdade |
| `EntDtEntrega` | Quando entregou (`0000-00-00` = não entregou) |
| `Status` | Texto livre do escritório: "Ent. PzTéc", "Atrasada!", "Dispensada"… |
| `EntLastDH` | Última alteração — base do modo rápido |
| `Config.RespEntrega` / `RespPrazo` | Responsável |
| `Config.DptoNome` | Departamento |

---

## Regras que não são óbvias

**A régua do fechamento.** Uma empresa está fechada quando a tarefa
`FECHAMENTO CONTÁBIL` daquela competência está entregue — no prazo ou em atraso.
Definido com o Kennedy em 26/08/2026: é a última etapa do fluxo, quem chegou nela
já passou pela revisão e pelo balancete.

**Dispensada sai do total.** Não conta a favor nem contra. O painel mostra
quantas foram, para o número não parecer maquiado.

**O nome da tarefa mudou em mai/2026.** Antes: `FECHAMENTO CONTÁBIL SN`,
`… LP`, `… LRA`, `… LRT`. De mai/2026 em diante: só `FECHAMENTO CONTÁBIL`. Por
isso o **regime vem do cadastro da empresa**, e o sufixo do nome é só o plano B.
`FECHAMENTO DRE ANUAL` e `FECHAMENTO BALANÇO ANUAL` **não** entram (são anuais).

**A competência em foco não é o mês corrente.** Em agosto se fecha julho. O
painel abre na competência mais recente que o time **já começou** a trabalhar
(o primeiro prazo técnico já passou). Abrir em ago/26 mostraria 0% sem nenhum
atraso existir.

**A comparação com o mês anterior é no mesmo dia do ciclo.** "58% no mês passado"
não serve de alvo se aquilo foi o resultado do mês inteiro. O eixo do gráfico é
"dias desde a abertura da competência", não data de calendário.

**Departamento é comparado sem acento e em minúsculas.** Comparar com `.title()`
quebra em "Retidos e Simples Nacional" — vira "Retidos **E** Simples Nacional" e
não bate com a chave. Esse departamento sozinho tem 24 mil tarefas: ele sumia do
painel operacional inteiro sem nenhum erro aparecer.

**Competência truncada não entra.** A coleta filtra pelo **prazo**, então de uma
competência antiga chega só o pedaço cujo prazo caiu dentro do período pedido.
O `processar.py` descarta competências com menos de 40% da mediana de volume e
imprime quais foram — senão o gráfico mostra out/25 com 4 tarefas como se fosse
um mês real.

**A linha do gráfico não inclui o mês corrente.** Ele mal começou e entraria com
~1% entregue, dando impressão de despencada.

**Uma empresa = uma linha.** Hoje o Acessórias só deixa uma tarefa de fechamento
ativa por empresa/competência (as outras ficam dispensadas), mas o código está
preparado para duas: nesse caso a empresa só conta como fechada quando as duas
estiverem entregues.

---

## O que veio antes (e por que mudou)

Existia um painel operacional em n8n:
`Google Sheets (planilha "acessorias", colada na mão) → 2 nós de código → commit
de data.json no repo público kennedydrong-arch/painel-operacional-fiscal-larafy`.

Três problemas:

1. **A planilha era manual** — parou de ser alimentada em 12/06/2026 e o painel
   congelou junto.
2. **O repositório era público** — 447 empresas com CNPJ, 43 mil tarefas e nomes
   dos responsáveis abertos na internet. Fechado em 26/08/2026 (`private: true`).
3. Não existia o indicador que a gestão pediu.

O classificador de status (v5.4) e a lógica de dedup foram portados do n8n para
`classificador.py` e `processar.py` — a inteligência foi aproveitada, o
encanamento frágil não.

---

## Cuidados

- **`.env` nunca vai para o Git.** O `.gitignore` cobre, mas confira antes de
  qualquer commit.
- **O repositório é público por decisão do Kennedy (26/08/2026)**, com nomes de
  clientes, CNPJ e desempenho por pessoa acessíveis por link. Eu recomendei
  publicar só os agregados; ele optou por publicar tudo. Mitigação no ar:
  `robots.txt` + `<meta name="robots" content="noindex">`. **Não desfazer isso.**
- Windows/PowerShell 5.1: sem `&&`. Todo script força `utf-8` no stdout — sem
  isso o acento estoura o cp1252 e o script parece ter falhado sem ter falhado.
- A coleta completa demora ~50 min por limite da API, não por lentidão do código.
  Se cair no meio, rodar de novo retoma de onde parou. O `--rapido` existe para
  o dia a dia.
- A pasta `dados/` precisa existir antes do primeiro salvamento de progresso
  (a cada 25 empresas). Já quebrou uma vez em máquina limpa por isso.
