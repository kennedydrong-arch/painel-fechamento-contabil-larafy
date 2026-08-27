# Painel de Fechamento Contábil · LaraFy

Painel que mostra, em percentual, quanto do fechamento contábil do mês já está
concluído — para acompanhar o time e apresentar à gestão.

Os dados vêm **direto do Acessórias**, pela API oficial. Ninguém exporta planilha,
ninguém digita nada.

---

## Como rodar (o dia a dia)

Duplo clique em **`ATUALIZAR E ABRIR.bat`**.

Ele faz três coisas, nesta ordem:

1. baixa do Acessórias tudo que mudou (leva ~15 minutos, é a parte lenta);
2. calcula os indicadores;
3. abre o painel no navegador.

Se quiser só **abrir o painel** com os dados da última vez, duplo clique em
`ABRIR PAINEL.bat` — abre na hora.

---

## As três telas

| Tela | Para quê |
|---|---|
| **`painel.html`** | **Tudo numa tela só.** Ocupa a tela inteira, não rola, tem relógio e troca claro/escuro. É a que se projeta numa reunião ou deixa numa TV. **É esta que você manda para a Juliane.** |
| `index.html` | Fechamento empresa a empresa: tabela, busca, filtro, Excel |
| `operacional.html` | Todas as obrigações do escritório, por área, com o passivo em aberto |

As três têm as mesmas abas no topo para trocar entre elas.

### Deixar numa TV

O `painel.html` é sempre escuro — é onde ele vai ficar: numa TV, ligado o dia
todo. Não tem botão de tema, e o escuro é fixo: ele não vira claro na máquina
de quem abrir com o sistema no modo claro.

As duas telas de trabalho seguem o tema do computador de quem abre.

O botão **Tela cheia** (ou a tecla **F**) tira a barra do
navegador e o painel ocupa a tela inteira. `Esc` volta. Depois de 3 segundos
parado, o ponteiro do mouse some sozinho — ele ficava na frente do número o dia
inteiro. As setas **←** e **→** trocam a competência sem precisar do mouse.

Os dados se atualizam sozinhos a cada 5 minutos, então a tela pode ficar ligada
sem ninguém mexer.

---

## A atualização automática

O robô do GitHub busca os dados novos **duas vezes por dia útil**: 07:17 e
13:17. São dois horários de propósito — se o da manhã falhar, o da tarde
atualiza mesmo assim.

O painel aberto relê o arquivo a cada 5 minutos, então a TV pega a atualização
sozinha, sem precisar dar F5.

**Se os dados ficarem mais de 36 horas sem atualizar**, as três telas avisam:
no painel, a barra do topo fica vermelha com a data real dos números. Nenhuma
tela fica velha em silêncio.

Para forçar na hora: GitHub → aba **Actions** → **Atualizar painel** → **Run
workflow**. Leva uns 8 minutos.

### O que cabe na tela do `painel.html`

| Bloco | Responde |
|---|---|
| % do fechamento | quanto do mês está fechado, com concluídas / pendentes / atrasadas / dispensadas |
| Onde cada mês terminou | as últimas 6 competências em barras — a régua de quanto é "normal" |
| **Ritmo** | quantas empresas por dia útil o time está fechando, quantas **precisaria** fechar para bater o prazo, e onde o mês termina se o ritmo não mudar |
| Curva do ciclo | o mês atual contra o anterior, dia a dia, com "hoje" marcado |
| O escritório | % entregue de Fiscal, Contábil e Outras áreas, o que mais segura o mês e o passivo acumulado |
| Por pessoa | quem está com fechamento em aberto |
| **Arrastando** | empresas com o fechamento em aberto em 2 ou mais meses já vencidos — o problema que não aparece olhando só o mês |

---

## O que o painel mostra

| Bloco | O que responde |
|---|---|
| Anel grande | **% de empresas com o fechamento concluído** na competência |
| Cartões | Concluídas (no prazo / em atraso), pendentes, atrasadas, quanto falta |
| Evolução do fechamento | Como o mês foi andando, dia a dia — com o mês anterior no fundo, para comparar ritmo |
| Por responsável | Quanto cada pessoa já fechou; clicar filtra a tabela |
| Por regime | % concluído em Lucro Presumido, Simples, Lucro Real… |
| Etapas de apoio | Balancete mensal e checklist contábil da mesma competência |
| Tabela | Empresa por empresa, com busca, filtro e botão de baixar Excel |

O botão **Imprimir / PDF** gera a versão de apresentação, sem os filtros.

---

## A segunda página: Painel Operacional

No topo há duas abas: **Fechamento contábil** e **Operacional**.

O operacional mostra **todas as obrigações**, não só o fechamento — é o painel do
dia a dia do time:

| Bloco | O que responde |
|---|---|
| Três cartões no topo | % entregue de **Fiscal**, **Contábil** e **Outras áreas** no mês |
| **Passivo em aberto** | quanta coisa já venceu e **ainda não foi entregue**, somando todos os meses. Este número some quando se olha só a competência do mês — e é o que gera multa |
| Entregas mês a mês | a linha de cada área ao longo do ano, para ver se está melhorando ou piorando |
| O que está segurando o mês | quais obrigações têm mais coisa em aberto; clicar filtra a tabela |
| Por responsável | por área, quem tem mais coisa em aberto primeiro |
| Tabela | tudo que não foi entregue, com filtro por área, por mês, só com multa, busca e Excel |

Clicar num mês do **Passivo** filtra a tabela por aquele mês.

---

## A regra do que conta como "fechado"

Uma empresa entra como **concluída** quando a tarefa `FECHAMENTO CONTÁBIL`
daquela competência está entregue no Acessórias — no prazo ou em atraso, tanto faz
(o painel separa as duas coisas nos cartões, mas as duas contam como fechada).

Tarefa **dispensada** sai da conta: não conta a favor nem contra, e o painel mostra
quantas foram, para o número não parecer maquiado.

Quem muda essa régua é o Acessórias, não o painel: se a tarefa for marcada lá,
aparece aqui na próxima atualização.

---

## Os arquivos

| Arquivo | Para que serve |
|---|---|
| `coletar.py` | Fala com a API do Acessórias e grava `dados/bruto.json` |
| `processar.py` | Lê o bruto, aplica as regras e gera `data/fechamento.json` |
| `classificador.py` | Traduz o texto do status ("Ent. PzTéc", "Atrasada!") em concluído/pendente/atrasado |
| `acessorias.py` | O cliente da API: token, ritmo de chamadas, tentativas |
| `index.html` | O painel |
| `servir.py` | Sobe o painel no navegador |
| `.env` | **O token do Acessórias. Não vai para o Git, não vai para lugar nenhum.** |

`dados/bruto.json` é o que a API respondeu, sem interpretação. Se a regra mudar,
dá para recalcular tudo sem baixar de novo: `py processar.py`.

---

## Se der problema

**"Não consegui ler os dados" no navegador**
O painel precisa ser aberto pelo `.bat` (ou por `py servir.py`). Abrir o
`index.html` com duplo clique não funciona — o navegador bloqueia a leitura do
arquivo de dados.

**"Token do Acessorias recusado (401)"**
O token foi apagado ou trocado no Acessórias. Gere outro em
**engrenagem (canto superior direito) → API Token** e cole no arquivo `.env`,
na linha `ACESSORIAS_TOKEN=`.

**A coleta parou no meio**
Rode de novo. Ela retoma de onde parou — não recomeça do zero.

**O número não bate com o Acessórias**
Confira a competência selecionada no topo. O painel usa a **competência** da
tarefa (o mês de referência), não o mês do prazo — julho fecha em agosto.

---

## Limite da API

O Acessórias permite 100 chamadas por minuto. O coletor anda de propósito abaixo
disso (~85/min) e recua sozinho se levar bloqueio. Por isso a coleta completa leva
uns 15 minutos: são 409 empresas, e a API não deixa pedir todas de uma vez.
