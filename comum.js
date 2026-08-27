/* ============================================================
   Peças usadas pelas três telas.

   A queda do GitHub em 26/08/2026 mostrou o buraco: se a rodada
   automática não acontece, o painel continua no ar mostrando os
   números da última vez que deu certo — e ninguém percebe. Quem
   olha às 8h da manhã acredita que aquele número é de hoje.

   Nenhuma tela pode ficar velha em silêncio.
   ============================================================ */

// A rodada é de manhã, em dia útil. 36h cobrem o fim de semana normal
// (sexta de manhã → segunda de manhã são 72h, e aí o aviso é correto:
// os números são realmente de sexta).
const HORAS_ATE_ENVELHECER = 36;

/* Recebe o meta do JSON e, se houver, o pulso (data/pulso.json). O pulso
   separa duas coisas que não são a mesma: quando o robô verificou pela
   última vez, e quando os números realmente mudaram. Rodando de hora em
   hora, quase toda verificação não traz novidade — e isso não é falha. */
function idadeDosDados(meta, pulso) {
  const ref = (pulso && pulso.verificado_em) || (meta && meta.atualizado_em);
  const t = ref ? new Date(ref) : null;
  if (!t || isNaN(t)) return { horas: null, velho: false, texto: 'data desconhecida' };
  const horas = (Date.now() - t.getTime()) / 3600000;
  const dias = Math.floor(horas / 24);
  const tDados = pulso && pulso.dados_de ? new Date(pulso.dados_de) : t;
  const hDados = tDados ? (Date.now() - tDados.getTime()) / 3600000 : horas;
  return {
    horas,
    horasDados: hDados,
    dadosDe: tDados ? tDados.toLocaleString('pt-BR', { day:'2-digit', month:'2-digit',
                                                      hour:'2-digit', minute:'2-digit' }) : '—',
    velho: horas > HORAS_ATE_ENVELHECER,
    quando: t.toLocaleString('pt-BR', { day: '2-digit', month: '2-digit',
                                        hour: '2-digit', minute: '2-digit' }),
    texto: horas < 1 ? 'agora há pouco'
         : horas < 24 ? `há ${Math.floor(horas)} hora${Math.floor(horas) === 1 ? '' : 's'}`
         : `há ${dias} dia${dias === 1 ? '' : 's'}`,
  };
}

/* Frase única, para caber tanto numa faixa quanto numa barra de topo. */
function frateDadosVelhos(meta) {
  const i = idadeDosDados(meta);
  if (!i.velho) return '';
  return `Estes números são de ${i.quando} (${i.texto}). A atualização automática `
       + `não rodou desde então — o Acessórias pode já estar diferente.`;
}
