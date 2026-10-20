import assert from "node:assert/strict";
import test from "node:test";

import {
  INTERVALO_ATUALIZACAO_MS,
  TEMPO_LIMITE_REQUISICAO_MS,
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


test("perda no polling preserva os dados e bloqueia as mutacoes", async () => {
  const botao = { disabled: false };
  const formulario = { querySelectorAll: () => [botao] };
  const aviso = { hidden: true };
  const raiz = {
    dataset: { revisaoAtualizacao: "estado-confirmado" },
    setAttribute(nome, valor) {
      this[nome] = valor;
    },
    removeAttribute(nome) {
      delete this[nome];
    },
    replaceWith() {
      assert.fail("os ultimos dados nao devem ser substituidos na falha");
    },
  };
  let executarCiclo;
  iniciarAtualizacaoPeriodica({
    documento: {
      querySelector(seletor) {
        if (seletor === "[data-atualizacao-periodica]") return raiz;
        if (seletor === "[data-aviso-comunicacao]") return aviso;
        return null;
      },
      querySelectorAll: (seletor) =>
        seletor === "form[data-acao-mutavel]" ? [formulario] : [],
      addEventListener() {},
    },
    janela: {
      location: { href: "http://restaurante/comandas/consultar/" },
      addEventListener() {},
      removeEventListener() {},
    },
    agendar: (callback) => {
      executarCiclo = callback;
      return 1;
    },
    cancelarAgendamento() {},
    buscar: async () => {
      throw new TypeError("Failed to fetch");
    },
    criarControlador: () => ({ signal: "sinal", abort() {} }),
  });

  await executarCiclo();

  assert.equal(aviso.hidden, false);
  assert.equal(raiz.dataset.possivelmenteDesatualizados, "true");
  assert.equal(botao.disabled, true);
});


test("recuperacao consulta o estado antes de remover o aviso e reabilitar acoes", async () => {
  const botao = { disabled: false };
  const formulario = {
    querySelectorAll: () => [botao],
  };
  const aviso = { hidden: true };
  const raiz = {
    dataset: { revisaoAtualizacao: "estado-confirmado" },
    replaceWith() {},
  };
  let executarCiclo;
  let tentativa = 0;
  iniciarAtualizacaoPeriodica({
    documento: {
      querySelector(seletor) {
        if (seletor === "[data-atualizacao-periodica]") return raiz;
        if (seletor === "[data-aviso-comunicacao]") return aviso;
        return null;
      },
      querySelectorAll: () => [formulario],
      addEventListener() {},
    },
    janela: {
      location: { href: "http://restaurante/comandas/consultar/" },
      addEventListener() {},
      removeEventListener() {},
    },
    agendar: (callback) => {
      executarCiclo = callback;
      return 1;
    },
    cancelarAgendamento() {},
    buscar: async () => {
      tentativa += 1;
      if (tentativa === 1) throw new TypeError("Failed to fetch");
      assert.equal(aviso.hidden, false);
      assert.equal(botao.disabled, true);
      return {
        ok: true,
        redirected: false,
        status: 200,
        text: async () => "<html>estado-confirmado</html>",
      };
    },
    analisarHtml: () => ({
      querySelector: () => ({
        dataset: { revisaoAtualizacao: "estado-confirmado" },
      }),
    }),
    criarControlador: () => ({ signal: "sinal", abort() {} }),
  });

  await executarCiclo();
  await executarCiclo();

  assert.equal(tentativa, 2);
  assert.equal(aviso.hidden, true);
  assert.equal(raiz.dataset.possivelmenteDesatualizados, undefined);
  assert.equal(botao.disabled, false);
});


test("falha conhecida impede a mutacao antes do envio", async () => {
  const botao = { disabled: false };
  const formulario = {
    matches: (seletor) => seletor === "form[data-acao-mutavel]",
    querySelectorAll: () => [botao],
  };
  const raiz = { dataset: { revisaoAtualizacao: "estado-a" } };
  let executarCiclo;
  let aoEnviar;
  let requisicoes = 0;
  iniciarAtualizacaoPeriodica({
    documento: {
      querySelector: (seletor) =>
        seletor === "[data-atualizacao-periodica]" ? raiz : { hidden: true },
      querySelectorAll: () => [formulario],
      addEventListener(evento, callback) {
        if (evento === "submit") aoEnviar = callback;
      },
      removeEventListener() {},
    },
    janela: {
      location: { href: "http://restaurante/comandas/consultar/" },
      addEventListener() {},
      removeEventListener() {},
    },
    agendar: (callback) => {
      executarCiclo = callback;
      return 1;
    },
    cancelarAgendamento() {},
    buscar: async () => {
      requisicoes += 1;
      throw new TypeError("Failed to fetch");
    },
    criarControlador: () => ({ signal: "sinal", abort() {} }),
  });
  await executarCiclo();
  let envioImpedido = false;

  await aoEnviar({
    target: formulario,
    preventDefault() {
      envioImpedido = true;
    },
  });

  assert.equal(envioImpedido, true);
  assert.equal(requisicoes, 1);
});


test("envio sem resposta fica incerto, nao repete a mutacao e consulta o estado", async () => {
  const botao = { disabled: false };
  const formulario = {
    action: "http://restaurante/lancamentos/adicional/",
    method: "post",
    matches: (seletor) => seletor === "form[data-acao-mutavel]",
    checkValidity: () => true,
    querySelectorAll: () => [botao],
  };
  const avisoComunicacao = { hidden: true };
  const avisoResultadoIncerto = { hidden: true };
  const raiz = { dataset: { revisaoAtualizacao: "estado-a" } };
  let executarCiclo;
  let aoEnviar;
  const requisicoes = [];
  iniciarAtualizacaoPeriodica({
    documento: {
      querySelector(seletor) {
        if (seletor === "[data-atualizacao-periodica]") return raiz;
        if (seletor === "[data-aviso-comunicacao]") return avisoComunicacao;
        if (seletor === "[data-aviso-resultado-incerto]") {
          return avisoResultadoIncerto;
        }
        return null;
      },
      querySelectorAll: () => [formulario],
      addEventListener(evento, callback) {
        if (evento === "submit") aoEnviar = callback;
      },
      removeEventListener() {},
    },
    janela: {
      location: { href: "http://restaurante/comandas/consultar/" },
      addEventListener() {},
      removeEventListener() {},
    },
    agendar: (callback) => {
      executarCiclo = callback;
      return 1;
    },
    cancelarAgendamento() {},
    buscar: async (url, opcoes) => {
      requisicoes.push({ url, metodo: opcoes.method });
      if (opcoes.method === "POST") throw new TypeError("Failed to fetch");
      return {
        ok: false,
        redirected: false,
        status: 503,
      };
    },
    criarDadosFormulario: () => "dados-do-formulario",
    criarControlador: () => ({ signal: "sinal", abort() {} }),
  });
  let envioImpedido = false;

  await aoEnviar({
    target: formulario,
    preventDefault() {
      envioImpedido = true;
    },
  });
  await executarCiclo();

  assert.equal(envioImpedido, true);
  assert.equal(avisoComunicacao.hidden, false);
  assert.equal(avisoResultadoIncerto.hidden, false);
  assert.deepEqual(requisicoes, [
    {
      url: "http://restaurante/lancamentos/adicional/",
      metodo: "POST",
    },
    {
      url: "http://restaurante/comandas/consultar/",
      metodo: "GET",
    },
  ]);
});


test("tela sem estado usa a saude no mesmo ciclo de comunicacao", async () => {
  const gerenciador = { dataset: { urlSaude: "http://restaurante/saude/" } };
  let executarCiclo;
  let requisicao;
  const ciclo = iniciarAtualizacaoPeriodica({
    documento: {
      querySelector(seletor) {
        if (seletor === "[data-gerenciador-comunicacao]") return gerenciador;
        return null;
      },
      querySelectorAll: () => [],
      addEventListener() {},
      removeEventListener() {},
    },
    janela: {
      location: { href: "http://restaurante/garcom/" },
      addEventListener() {},
      removeEventListener() {},
    },
    agendar: (callback) => {
      executarCiclo = callback;
      return 1;
    },
    cancelarAgendamento() {},
    buscar: async (url, opcoes) => {
      requisicao = { url, opcoes };
      return { ok: true, redirected: false, status: 200 };
    },
    criarControlador: () => ({ signal: "sinal", abort() {} }),
  });

  await executarCiclo();

  assert.ok(ciclo);
  assert.equal(requisicao.url, "http://restaurante/saude/");
  assert.equal(requisicao.opcoes.method, "GET");
});


test("primeiro lancamento incerto consulta a comanda quando a saude volta", async () => {
  const botao = { disabled: false };
  const formulario = {
    action: "http://restaurante/lancamentos/primeiro/",
    method: "post",
    dataset: { urlVerificacao: "/comandas/consultar/" },
    elements: {
      namedItem: (nome) =>
        nome === "identificador_comanda" ? { value: "001" } : null,
    },
    matches: (seletor) => seletor === "form[data-acao-mutavel]",
    checkValidity: () => true,
    querySelectorAll: () => [botao],
  };
  const aviso = { hidden: true };
  const avisoIncerto = { hidden: true };
  let aoEnviar;
  let executarCiclo;
  let destino;
  iniciarAtualizacaoPeriodica({
    documento: {
      querySelector(seletor) {
        if (seletor === "[data-gerenciador-comunicacao]") {
          return { dataset: { urlSaude: "/saude/" } };
        }
        if (seletor === "[data-aviso-comunicacao]") return aviso;
        if (seletor === "[data-aviso-resultado-incerto]") return avisoIncerto;
        return null;
      },
      querySelectorAll: () => [formulario],
      addEventListener(evento, callback) {
        if (evento === "submit") aoEnviar = callback;
      },
      removeEventListener() {},
    },
    janela: {
      location: {
        href: "http://restaurante/garcom/",
        assign(url) {
          assert.equal(aviso.hidden, false);
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
    buscar: async (_url, opcoes) => {
      if (opcoes.method === "POST") throw new TypeError("Failed to fetch");
      return { ok: true, redirected: false, status: 200 };
    },
    criarDadosFormulario: () => "dados",
    criarControlador: () => ({ signal: "sinal", abort() {} }),
  });

  await aoEnviar({ target: formulario, preventDefault() {} });
  await executarCiclo();

  assert.equal(
    destino,
    "http://restaurante/comandas/consultar/?identificador=001",
  );
});


test("erros de dominio nao sao tratados como perda de comunicacao", async () => {
  for (const status of [400, 403, 409]) {
    const formulario = {
      action: "http://restaurante/operacao/",
      method: "post",
      matches: () => true,
      checkValidity: () => true,
      querySelectorAll: () => [],
    };
    const aviso = { hidden: true };
    let aoEnviar;
    let paginaExibida;
    iniciarAtualizacaoPeriodica({
      documento: {
        querySelector(seletor) {
          if (seletor === "[data-atualizacao-periodica]") {
            return { dataset: { revisaoAtualizacao: "estado-a" } };
          }
          if (seletor === "[data-aviso-comunicacao]") return aviso;
          return null;
        },
        querySelectorAll: () => [formulario],
        addEventListener(evento, callback) {
          if (evento === "submit") aoEnviar = callback;
        },
        removeEventListener() {},
      },
      janela: {
        location: { href: "http://restaurante/consulta/" },
        addEventListener() {},
        removeEventListener() {},
      },
      agendar: () => 1,
      cancelarAgendamento() {},
      buscar: async () => ({
        ok: false,
        redirected: false,
        status,
        text: async () => `erro-${status}`,
      }),
      criarDadosFormulario: () => "dados",
      substituirPagina: (html) => {
        paginaExibida = html;
      },
    });

    await aoEnviar({ target: formulario, preventDefault() {} });

    assert.equal(aviso.hidden, true);
    assert.equal(paginaExibida, `erro-${status}`);
  }
});


test("polling nao concorre com uma mutacao em andamento", async () => {
  const formulario = {
    action: "http://restaurante/operacao/",
    method: "post",
    matches: () => true,
    checkValidity: () => true,
    querySelectorAll: () => [],
  };
  let aoEnviar;
  let executarCiclo;
  let concluirMutacao;
  const metodos = [];
  iniciarAtualizacaoPeriodica({
    documento: {
      querySelector: (seletor) =>
        seletor === "[data-atualizacao-periodica]"
          ? { dataset: { revisaoAtualizacao: "estado-a" } }
          : null,
      querySelectorAll: () => [formulario],
      addEventListener(evento, callback) {
        if (evento === "submit") aoEnviar = callback;
      },
      removeEventListener() {},
    },
    janela: {
      location: { href: "http://restaurante/consulta/", assign() {} },
      addEventListener() {},
      removeEventListener() {},
    },
    agendar: (callback) => {
      executarCiclo = callback;
      return 1;
    },
    cancelarAgendamento() {},
    buscar: (_url, opcoes) => {
      metodos.push(opcoes.method);
      return new Promise((resolver) => {
        concluirMutacao = resolver;
      });
    },
    criarDadosFormulario: () => "dados",
  });

  const envio = aoEnviar({ target: formulario, preventDefault() {} });
  await executarCiclo();
  assert.deepEqual(metodos, ["POST"]);
  concluirMutacao({
    ok: true,
    redirected: true,
    status: 200,
    url: "http://restaurante/confirmado/",
  });
  await envio;
});


test("timeout controlado do polling sinaliza perda de comunicacao", async () => {
  const aviso = { hidden: true };
  let executarCiclo;
  let expirar;
  let tempoConfigurado;
  let rejeitarBusca;
  iniciarAtualizacaoPeriodica({
    documento: {
      querySelector(seletor) {
        if (seletor === "[data-atualizacao-periodica]") {
          return { dataset: { revisaoAtualizacao: "estado-a" } };
        }
        if (seletor === "[data-aviso-comunicacao]") return aviso;
        return null;
      },
      querySelectorAll: () => [],
      addEventListener() {},
      removeEventListener() {},
    },
    janela: {
      location: { href: "http://restaurante/consulta/" },
      addEventListener() {},
      removeEventListener() {},
    },
    agendar: (callback) => {
      executarCiclo = callback;
      return 1;
    },
    cancelarAgendamento() {},
    agendarLimite: (callback, tempo) => {
      expirar = callback;
      tempoConfigurado = tempo;
      return 2;
    },
    cancelarLimite() {},
    buscar: () =>
      new Promise((_resolver, rejeitar) => {
        rejeitarBusca = rejeitar;
      }),
    criarControlador: () => ({
      signal: "sinal",
      abort() {
        const erro = new Error("timeout");
        erro.name = "AbortError";
        rejeitarBusca(erro);
      },
    }),
  });

  const consulta = executarCiclo();
  expirar();
  await consulta;

  assert.equal(tempoConfigurado, TEMPO_LIMITE_REQUISICAO_MS);
  assert.equal(aviso.hidden, false);
});


test("timeout depois do envio deixa o resultado da mutacao incerto", async () => {
  const formulario = {
    action: "http://restaurante/operacao/",
    method: "post",
    matches: () => true,
    checkValidity: () => true,
    querySelectorAll: () => [],
  };
  const avisoIncerto = { hidden: true };
  let aoEnviar;
  let expirar;
  let rejeitarBusca;
  iniciarAtualizacaoPeriodica({
    documento: {
      querySelector(seletor) {
        if (seletor === "[data-atualizacao-periodica]") {
          return { dataset: { revisaoAtualizacao: "estado-a" } };
        }
        if (seletor === "[data-aviso-resultado-incerto]") {
          return avisoIncerto;
        }
        return null;
      },
      querySelectorAll: () => [formulario],
      addEventListener(evento, callback) {
        if (evento === "submit") aoEnviar = callback;
      },
      removeEventListener() {},
    },
    janela: {
      location: { href: "http://restaurante/consulta/" },
      addEventListener() {},
      removeEventListener() {},
    },
    agendar: () => 1,
    cancelarAgendamento() {},
    agendarLimite: (callback) => {
      expirar = callback;
      return 2;
    },
    cancelarLimite() {},
    buscar: () =>
      new Promise((_resolver, rejeitar) => {
        rejeitarBusca = rejeitar;
      }),
    criarDadosFormulario: () => "dados",
    criarControlador: () => ({
      signal: "sinal",
      abort() {
        const erro = new Error("timeout");
        erro.name = "AbortError";
        rejeitarBusca(erro);
      },
    }),
  });

  const envio = aoEnviar({ target: formulario, preventDefault() {} });
  expirar();
  await envio;

  assert.equal(avisoIncerto.hidden, false);
});


test("recuperacao apos envio incerto exibe o estado persistido real", async () => {
  const botao = { disabled: false };
  const formulario = {
    action: "http://restaurante/lancamentos/adicional/",
    method: "post",
    matches: () => true,
    checkValidity: () => true,
    querySelectorAll: () => [botao],
  };
  const aviso = { hidden: true };
  const avisoIncerto = { hidden: true };
  const novaRaiz = { dataset: { revisaoAtualizacao: "estado-persistido" } };
  let raizExibida = {
    dataset: { revisaoAtualizacao: "estado-anterior" },
    replaceWith(nova) {
      raizExibida = nova;
    },
  };
  let aoEnviar;
  let executarCiclo;
  iniciarAtualizacaoPeriodica({
    documento: {
      querySelector(seletor) {
        if (seletor === "[data-atualizacao-periodica]") return raizExibida;
        if (seletor === "[data-aviso-comunicacao]") return aviso;
        if (seletor === "[data-aviso-resultado-incerto]") return avisoIncerto;
        return null;
      },
      querySelectorAll: () => [formulario],
      addEventListener(evento, callback) {
        if (evento === "submit") aoEnviar = callback;
      },
      removeEventListener() {},
    },
    janela: {
      location: { href: "http://restaurante/comandas/consultar/" },
      addEventListener() {},
      removeEventListener() {},
    },
    agendar: (callback) => {
      executarCiclo = callback;
      return 1;
    },
    cancelarAgendamento() {},
    buscar: async (_url, opcoes) => {
      if (opcoes.method === "POST") throw new TypeError("Failed to fetch");
      return {
        ok: true,
        redirected: false,
        status: 200,
        text: async () => "<html>estado-persistido</html>",
      };
    },
    analisarHtml: () => ({ querySelector: () => novaRaiz }),
    criarDadosFormulario: () => "dados",
    criarControlador: () => ({ signal: "sinal", abort() {} }),
  });

  await aoEnviar({ target: formulario, preventDefault() {} });
  assert.equal(avisoIncerto.hidden, false);
  await executarCiclo();

  assert.equal(raizExibida, novaRaiz);
  assert.equal(aviso.hidden, true);
  assert.equal(avisoIncerto.hidden, true);
  assert.equal(botao.disabled, false);
});


test("captura todos os campos do POST antes de desabilitar o formulario", async () => {
  const FormDataOriginal = globalThis.FormData;
  class FormDataDoFormulario {
    constructor(formulario) {
      this.campos = new Map(
        formulario.elements
          .filter((campo) => campo.name && !campo.disabled)
          .map((campo) => [campo.name, campo.value]),
      );
    }

    get(nome) {
      return this.campos.get(nome);
    }
  }
  globalThis.FormData = FormDataDoFormulario;

  const campos = [
    { name: "csrfmiddlewaretoken", value: "csrf-real", disabled: false },
    { name: "chave_idempotencia", value: "chave-real", disabled: false },
    { name: "revisao", value: "revisao-real", disabled: false },
    { name: "quantidade", value: "2", disabled: false },
  ];
  const botao = { name: "", value: "", disabled: false };
  const formulario = {
    action: "http://restaurante/operacao/",
    method: "post",
    elements: campos,
    matches: () => true,
    checkValidity: () => true,
    querySelectorAll: () => [...campos, botao],
  };
  let aoEnviar;
  let concluirPost;
  let payload;

  try {
    iniciarAtualizacaoPeriodica({
      documento: {
        querySelector: (seletor) =>
          seletor === "[data-atualizacao-periodica]"
            ? { dataset: { revisaoAtualizacao: "estado-a" } }
            : null,
        querySelectorAll: () => [formulario],
        addEventListener(evento, callback) {
          if (evento === "submit") aoEnviar = callback;
        },
        removeEventListener() {},
      },
      janela: {
        location: { href: "http://restaurante/consulta/", assign() {} },
        addEventListener() {},
        removeEventListener() {},
      },
      agendar: () => 1,
      cancelarAgendamento() {},
      buscar: async (_url, opcoes) => {
        payload = opcoes.body;
        return new Promise((resolver) => {
          concluirPost = resolver;
        });
      },
    });

    const envio = aoEnviar({ target: formulario, preventDefault() {} });

    assert.equal(payload.get("csrfmiddlewaretoken"), "csrf-real");
    assert.equal(payload.get("chave_idempotencia"), "chave-real");
    assert.equal(payload.get("revisao"), "revisao-real");
    assert.equal(payload.get("quantidade"), "2");
    assert.equal(campos.every((campo) => campo.disabled), true);
    concluirPost({
      ok: true,
      redirected: true,
      status: 200,
      url: "http://restaurante/confirmado/",
    });
    await envio;
  } finally {
    globalThis.FormData = FormDataOriginal;
  }
});


test("POST aguarda GET pendente e ignora a resposta antiga do polling", async () => {
  const botao = { disabled: false };
  const formulario = {
    action: "http://restaurante/operacao/",
    method: "post",
    matches: () => true,
    checkValidity: () => true,
    querySelectorAll: () => [botao],
  };
  const raiz = {
    dataset: {
      revisaoAtualizacao: "estado-a",
      possivelmenteDesatualizados: "true",
    },
    replaceWith() {},
  };
  const aviso = { hidden: false };
  let aoEnviar;
  let executarCiclo;
  let concluirGet;
  let concluirPost;
  const metodos = [];
  iniciarAtualizacaoPeriodica({
    documento: {
      querySelector(seletor) {
        if (seletor === "[data-atualizacao-periodica]") return raiz;
        if (seletor === "[data-aviso-comunicacao]") return aviso;
        return null;
      },
      querySelectorAll: () => [formulario],
      addEventListener(evento, callback) {
        if (evento === "submit") aoEnviar = callback;
      },
      removeEventListener() {},
    },
    janela: {
      location: { href: "http://restaurante/consulta/", assign() {} },
      addEventListener() {},
      removeEventListener() {},
    },
    agendar: (callback) => {
      executarCiclo = callback;
      return 1;
    },
    cancelarAgendamento() {},
    buscar: (_url, opcoes) => {
      metodos.push(opcoes.method);
      if (opcoes.method === "GET") {
        return Promise.resolve({
          ok: true,
          redirected: false,
          status: 200,
          text: () =>
            new Promise((resolver) => {
              concluirGet = resolver;
            }),
        });
      }
      return new Promise((resolver) => {
        concluirPost = resolver;
      });
    },
    analisarHtml: () => ({
      querySelector: () => ({
        dataset: { revisaoAtualizacao: "estado-recuperado-antigo" },
      }),
    }),
    criarDadosFormulario: () => "dados",
    criarControlador: () => ({ signal: "sinal", abort() {} }),
  });

  const consulta = executarCiclo();
  await Promise.resolve();
  const envio = aoEnviar({ target: formulario, preventDefault() {} });

  assert.deepEqual(metodos, ["GET"]);
  assert.equal(botao.disabled, true);
  concluirGet("<html>estado-antigo</html>");
  await consulta;
  await Promise.resolve();

  assert.deepEqual(metodos, ["GET", "POST"]);
  assert.equal(botao.disabled, true);
  assert.equal(aviso.hidden, false);
  assert.equal(raiz.dataset.possivelmenteDesatualizados, "true");
  concluirPost({
    ok: true,
    redirected: true,
    status: 200,
    url: "http://restaurante/confirmado/",
  });
  await envio;
});


test("falha ao processar resposta do polling nao indica servidor offline", async () => {
  const aviso = { hidden: true };
  const raiz = { dataset: { revisaoAtualizacao: "estado-a" } };
  let executarCiclo;
  iniciarAtualizacaoPeriodica({
    documento: {
      querySelector(seletor) {
        if (seletor === "[data-atualizacao-periodica]") return raiz;
        if (seletor === "[data-aviso-comunicacao]") return aviso;
        return null;
      },
      querySelectorAll: () => [],
      addEventListener() {},
      removeEventListener() {},
    },
    janela: {
      location: { href: "http://restaurante/consulta/" },
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
      status: 200,
      text: async () => "<html>resposta-valida</html>",
    }),
    analisarHtml: () => {
      throw new Error("falha interna no parser");
    },
    criarControlador: () => ({ signal: "sinal", abort() {} }),
  });

  await executarCiclo();

  assert.equal(aviso.hidden, true);
  assert.equal(raiz.dataset.possivelmenteDesatualizados, undefined);
});


test("falha ao renderizar resposta do POST nao indica servidor offline", async () => {
  const formulario = {
    action: "http://restaurante/operacao/",
    method: "post",
    matches: () => true,
    checkValidity: () => true,
    querySelectorAll: () => [],
  };
  const aviso = { hidden: true };
  const avisoIncerto = { hidden: true };
  const raiz = { dataset: { revisaoAtualizacao: "estado-a" } };
  let aoEnviar;
  iniciarAtualizacaoPeriodica({
    documento: {
      querySelector(seletor) {
        if (seletor === "[data-atualizacao-periodica]") return raiz;
        if (seletor === "[data-aviso-comunicacao]") return aviso;
        if (seletor === "[data-aviso-resultado-incerto]") return avisoIncerto;
        return null;
      },
      querySelectorAll: () => [formulario],
      addEventListener(evento, callback) {
        if (evento === "submit") aoEnviar = callback;
      },
      removeEventListener() {},
    },
    janela: {
      location: { href: "http://restaurante/consulta/" },
      addEventListener() {},
      removeEventListener() {},
    },
    agendar: () => 1,
    cancelarAgendamento() {},
    buscar: async () => ({
      ok: false,
      redirected: false,
      status: 409,
      text: async () => "<html>erro-de-dominio</html>",
    }),
    criarDadosFormulario: () => "dados",
    substituirPagina: () => {
      throw new Error("falha interna no DOM");
    },
  });

  await aoEnviar({ target: formulario, preventDefault() {} });

  assert.equal(aviso.hidden, true);
  assert.equal(avisoIncerto.hidden, true);
  assert.equal(raiz.dataset.possivelmenteDesatualizados, undefined);
});
