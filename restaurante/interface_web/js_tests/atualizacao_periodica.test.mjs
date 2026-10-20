import assert from "node:assert/strict";
import test from "node:test";

import {
  INTERVALO_ATUALIZACAO_MS,
  iniciarAtualizacaoPeriodica,
} from "../static/interface_web/js/atualizacao_periodica.mjs";


test("inicia a consulta periódica a cada dois segundos", () => {
  const raiz = { dataset: { revisaoAtualizacao: "estado-a" } };
  const documento = {
    querySelector: (seletor) =>
      seletor === "[data-atualizacao-periodica]" ? raiz : null,
  };
  const janela = {
    addEventListener() {},
    removeEventListener() {},
  };
  let intervaloRegistrado = null;

  const ciclo = iniciarAtualizacaoPeriodica({
    documento,
    janela,
    agendar: (_callback, intervalo) => {
      intervaloRegistrado = intervalo;
      return 1;
    },
    cancelarAgendamento() {},
    buscar: async () => {
      throw new Error("o primeiro ciclo não deve ser imediato");
    },
  });

  assert.equal(INTERVALO_ATUALIZACAO_MS, 2000);
  assert.equal(intervaloRegistrado, 2000);
  ciclo.parar();
});


test("uma mudança externa substitui a visualização por uma consulta GET", async () => {
  const novaRaiz = { dataset: { revisaoAtualizacao: "estado-b" } };
  let raizExibida = {
    dataset: { revisaoAtualizacao: "estado-a" },
    replaceWith(nova) {
      raizExibida = nova;
    },
  };
  const documento = {
    querySelector: () => raizExibida,
  };
  const janela = {
    location: { href: "http://restaurante/comandas/consultar/?identificador=001" },
    addEventListener() {},
    removeEventListener() {},
  };
  let executarCiclo;
  let requisicao;

  iniciarAtualizacaoPeriodica({
    documento,
    janela,
    agendar: (callback) => {
      executarCiclo = callback;
      return 1;
    },
    cancelarAgendamento() {},
    buscar: async (url, opcoes) => {
      requisicao = { url, opcoes };
      return {
        ok: true,
        redirected: false,
        text: async () => "<html>estado-b</html>",
      };
    },
    analisarHtml: () => ({
      querySelector: () => novaRaiz,
    }),
    criarControlador: () => ({ signal: "sinal", abort() {} }),
  });

  await executarCiclo();

  assert.equal(requisicao.url, janela.location.href);
  assert.equal(requisicao.opcoes.method, "GET");
  assert.equal(requisicao.opcoes.signal, "sinal");
  assert.equal(raizExibida, novaRaiz);
});


test("a mesma revisão mantém a visualização estável", async () => {
  let substituicoes = 0;
  const raiz = {
    dataset: { revisaoAtualizacao: "sem-mudanca" },
    replaceWith() {
      substituicoes += 1;
    },
  };
  let executarCiclo;
  iniciarAtualizacaoPeriodica({
    documento: { querySelector: () => raiz },
    janela: {
      location: { href: "http://restaurante/consulta" },
      addEventListener() {},
      removeEventListener() {},
    },
    agendar: (callback) => {
      executarCiclo = callback;
      return 1;
    },
    cancelarAgendamento() {},
    buscar: async () => ({
      ok: true,
      redirected: false,
      text: async () => "<html>sem-mudanca</html>",
    }),
    analisarHtml: () => ({
      querySelector: () => ({
        dataset: { revisaoAtualizacao: "sem-mudanca" },
      }),
    }),
    criarControlador: () => ({ signal: "sinal", abort() {} }),
  });

  await executarCiclo();

  assert.equal(substituicoes, 0);
});


test("não inicia outra consulta enquanto a anterior está em andamento", async () => {
  const raiz = { dataset: { revisaoAtualizacao: "estado-a" } };
  let executarCiclo;
  let concluirConsulta;
  let consultas = 0;
  iniciarAtualizacaoPeriodica({
    documento: { querySelector: () => raiz },
    janela: {
      location: { href: "http://restaurante/consulta" },
      addEventListener() {},
      removeEventListener() {},
    },
    agendar: (callback) => {
      executarCiclo = callback;
      return 1;
    },
    cancelarAgendamento() {},
    buscar: () => {
      consultas += 1;
      return new Promise((resolver) => {
        concluirConsulta = resolver;
      });
    },
    criarControlador: () => ({ signal: "sinal", abort() {} }),
  });

  const primeira = executarCiclo();
  await executarCiclo();
  assert.equal(consultas, 1);
  concluirConsulta({ ok: false, redirected: false });
  await primeira;
});


test("sair da página encerra o intervalo e aborta a consulta", async () => {
  const raiz = { dataset: { revisaoAtualizacao: "estado-a" } };
  let executarCiclo;
  let aoSair;
  let intervaloCancelado;
  let consultaAbortada = false;
  let rejeitarConsulta;
  iniciarAtualizacaoPeriodica({
    documento: { querySelector: () => raiz },
    janela: {
      location: { href: "http://restaurante/consulta" },
      addEventListener: (evento, callback) => {
        if (evento === "pagehide") aoSair = callback;
      },
      removeEventListener() {},
    },
    agendar: (callback) => {
      executarCiclo = callback;
      return 27;
    },
    cancelarAgendamento: (identificador) => {
      intervaloCancelado = identificador;
    },
    buscar: () =>
      new Promise((_resolver, rejeitar) => {
        rejeitarConsulta = rejeitar;
      }),
    criarControlador: () => ({
      signal: "sinal",
      abort() {
        consultaAbortada = true;
        const erro = new Error("abortada");
        erro.name = "AbortError";
        rejeitarConsulta(erro);
      },
    }),
  });

  const consulta = executarCiclo();
  aoSair();
  await consulta;

  assert.equal(intervaloCancelado, 27);
  assert.equal(consultaAbortada, true);
});


test("um redirecionamento do backend leva a tela ao novo estado", async () => {
  const raiz = { dataset: { revisaoAtualizacao: "estado-a" } };
  let executarCiclo;
  let destino;
  iniciarAtualizacaoPeriodica({
    documento: { querySelector: () => raiz },
    janela: {
      location: {
        href: "http://restaurante/caixa/atendimentos/1/fechar/",
        assign(url) {
          destino = url;
        },
      },
      addEventListener() {},
      removeEventListener() {},
    },
    agendar: (callback) => {
      executarCiclo = callback;
      return 1;
    },
    cancelarAgendamento() {},
    buscar: async () => ({
      ok: true,
      redirected: true,
      url: "http://restaurante/caixa/atendimentos/1/resumo-final/",
    }),
    criarControlador: () => ({ signal: "sinal", abort() {} }),
  });

  await executarCiclo();

  assert.equal(
    destino,
    "http://restaurante/caixa/atendimentos/1/resumo-final/",
  );
});
