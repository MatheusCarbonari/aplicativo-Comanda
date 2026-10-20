export const INTERVALO_ATUALIZACAO_MS = 2000;
export const TEMPO_LIMITE_REQUISICAO_MS = 8000;


export function iniciarAtualizacaoPeriodica({
  documento = document,
  janela = window,
  agendar = window.setInterval.bind(window),
  cancelarAgendamento = window.clearInterval.bind(window),
  buscar = window.fetch.bind(window),
  analisarHtml = (html) =>
    new DOMParser().parseFromString(html, "text/html"),
  criarControlador = () => new AbortController(),
  agendarLimite = null,
  cancelarLimite = null,
  criarDadosFormulario = (formulario) => new FormData(formulario),
  substituirPagina = (html) => {
    document.open();
    document.write(html);
    document.close();
  },
} = {}) {
  let raiz = documento.querySelector("[data-atualizacao-periodica]");
  const gerenciadorComunicacao = documento.querySelector(
    "[data-gerenciador-comunicacao]",
  );
  if (!raiz && !gerenciadorComunicacao) {
    return null;
  }

  let consultaEmAndamento = false;
  let operacaoEmAndamento = false;
  let controlador = null;
  let identificadorLimite = null;
  let consultaExpirou = false;
  let concluirConsultaAtual = null;
  let fimConsultaAtual = Promise.resolve();
  let controladorOperacao = null;
  let ativo = true;
  let semComunicacao = false;
  let formularioResultadoIncerto = null;
  const avisoComunicacao = documento.querySelector(
    "[data-aviso-comunicacao]",
  );
  const avisoResultadoIncerto = documento.querySelector(
    "[data-aviso-resultado-incerto]",
  );
  const controlesDesabilitados = new Set();
  const agendarTimeout =
    agendarLimite ?? globalThis.setTimeout.bind(globalThis);
  const cancelarTimeout =
    cancelarLimite ?? globalThis.clearTimeout.bind(globalThis);

  const formulariosMutaveis = () =>
    documento.querySelectorAll?.("form[data-acao-mutavel]") ?? [];

  const desabilitarFormulario = (formulario) => {
    for (const controle of formulario.querySelectorAll(
      "button, input, select, textarea",
    )) {
      if (!controle.disabled) {
        controlesDesabilitados.add(controle);
        controle.disabled = true;
      }
    }
  };

  const marcarSemComunicacao = () => {
    semComunicacao = true;
    if (avisoComunicacao) avisoComunicacao.hidden = false;
    (raiz ?? gerenciadorComunicacao).dataset.possivelmenteDesatualizados =
      "true";
    for (const formulario of formulariosMutaveis()) {
      desabilitarFormulario(formulario);
    }
  };

  const marcarComunicacaoRecuperada = () => {
    semComunicacao = false;
    if (avisoComunicacao) avisoComunicacao.hidden = true;
    if (avisoResultadoIncerto) avisoResultadoIncerto.hidden = true;
    delete (raiz ?? gerenciadorComunicacao).dataset
      .possivelmenteDesatualizados;
    for (const controle of controlesDesabilitados) {
      controle.disabled = false;
    }
    controlesDesabilitados.clear();
    formularioResultadoIncerto = null;
  };

  const aoEnviar = async (evento) => {
    const formulario = evento.target;
    if (!formulario.matches?.("form[data-acao-mutavel]")) {
      return;
    }
    evento.preventDefault();
    if (
      semComunicacao ||
      operacaoEmAndamento ||
      !formulario.checkValidity()
    ) {
      return;
    }

    const dadosFormulario = criarDadosFormulario(formulario);
    operacaoEmAndamento = true;
    desabilitarFormulario(formulario);
    if (consultaEmAndamento) {
      controlador.abort();
      await fimConsultaAtual;
    }
    if (!ativo) {
      operacaoEmAndamento = false;
      return;
    }
    controladorOperacao = criarControlador();
    let operacaoExpirou = false;
    const identificadorLimiteOperacao = agendarTimeout(() => {
      operacaoExpirou = true;
      controladorOperacao.abort();
    }, TEMPO_LIMITE_REQUISICAO_MS);
    try {
      let resposta;
      try {
        resposta = await buscar(formulario.action, {
          method: formulario.method.toUpperCase(),
          body: dadosFormulario,
          cache: "no-store",
          credentials: "same-origin",
          signal: controladorOperacao.signal,
        });
      } catch (erro) {
        if (erro.name === "AbortError" && !operacaoExpirou && !ativo) {
          return;
        }
        formularioResultadoIncerto = formulario;
        if (avisoResultadoIncerto) avisoResultadoIncerto.hidden = false;
        marcarSemComunicacao();
        console.warn(
          "Não foi possível confirmar o resultado da operação.",
          erro,
        );
        return;
      }
      if (resposta.status === 503) {
        marcarSemComunicacao();
        return;
      }
      if (resposta.redirected) {
        parar();
        janela.location.assign(resposta.url);
        return;
      }
      let html;
      try {
        html = await resposta.text();
      } catch (erro) {
        if (erro.name === "AbortError" && !operacaoExpirou && !ativo) {
          return;
        }
        formularioResultadoIncerto = formulario;
        if (avisoResultadoIncerto) avisoResultadoIncerto.hidden = false;
        marcarSemComunicacao();
        console.warn(
          "Não foi possível confirmar o resultado da operação.",
          erro,
        );
        return;
      }
      try {
        substituirPagina(html);
        parar();
      } catch (erro) {
        console.warn("Não foi possível processar a resposta da operação.", erro);
      }
    } finally {
      cancelarTimeout(identificadorLimiteOperacao);
      controladorOperacao = null;
      operacaoEmAndamento = false;
    }
  };
  documento.addEventListener?.("submit", aoEnviar);

  const atualizar = async () => {
    if (!ativo || consultaEmAndamento || operacaoEmAndamento) {
      return;
    }
    consultaEmAndamento = true;
    fimConsultaAtual = new Promise((resolver) => {
      concluirConsultaAtual = resolver;
    });
    controlador = criarControlador();
    consultaExpirou = false;
    identificadorLimite = agendarTimeout(() => {
      consultaExpirou = true;
      controlador.abort();
    }, TEMPO_LIMITE_REQUISICAO_MS);
    try {
      const urlConsulta = raiz
        ? janela.location.href
        : gerenciadorComunicacao.dataset.urlSaude;
      let resposta;
      try {
        resposta = await buscar(urlConsulta, {
          method: "GET",
          cache: "no-store",
          signal: controlador.signal,
        });
      } catch (erro) {
        if (erro.name !== "AbortError" || consultaExpirou) {
          marcarSemComunicacao();
          console.warn("Não foi possível atualizar a tela.", erro);
        }
        return;
      }
      if (operacaoEmAndamento) {
        return;
      }
      if (resposta.redirected) {
        parar();
        janela.location.assign(resposta.url);
        return;
      }
      if (resposta.status === 503) {
        marcarSemComunicacao();
        return;
      }
      if (!resposta.ok) {
        return;
      }
      if (!raiz) {
        if (formularioResultadoIncerto?.dataset.urlVerificacao) {
          const identificador = formularioResultadoIncerto.elements
            .namedItem("identificador_comanda")?.value;
          const destino = new URL(
            formularioResultadoIncerto.dataset.urlVerificacao,
            janela.location.href,
          );
          destino.searchParams.set("identificador", identificador);
          parar();
          janela.location.assign(destino.href);
          return;
        }
        marcarComunicacaoRecuperada();
        return;
      }
      let html;
      try {
        html = await resposta.text();
      } catch (erro) {
        if (erro.name !== "AbortError" || consultaExpirou) {
          marcarSemComunicacao();
          console.warn("Não foi possível atualizar a tela.", erro);
        }
        return;
      }
      try {
        if (operacaoEmAndamento) {
          return;
        }
        const paginaAtualizada = analisarHtml(html);
        const novaRaiz = paginaAtualizada.querySelector(
          "[data-atualizacao-periodica]",
        );
        if (
          novaRaiz &&
          novaRaiz.dataset.revisaoAtualizacao !==
            raiz.dataset.revisaoAtualizacao
        ) {
          raiz.replaceWith(novaRaiz);
          raiz = novaRaiz;
        }
        if (novaRaiz) {
          marcarComunicacaoRecuperada();
        }
      } catch (erro) {
        console.warn("Não foi possível processar a atualização da tela.", erro);
      }
    } finally {
      if (identificadorLimite !== null) {
        cancelarTimeout(identificadorLimite);
      }
      consultaEmAndamento = false;
      controlador = null;
      identificadorLimite = null;
      consultaExpirou = false;
      concluirConsultaAtual();
      concluirConsultaAtual = null;
    }
  };

  const identificadorIntervalo = agendar(
    atualizar,
    INTERVALO_ATUALIZACAO_MS,
  );
  const parar = () => {
    ativo = false;
    cancelarAgendamento(identificadorIntervalo);
    if (controlador) {
      controlador.abort();
    }
    if (controladorOperacao) {
      controladorOperacao.abort();
    }
    documento.removeEventListener?.("submit", aoEnviar);
    janela.removeEventListener("pagehide", parar);
  };
  janela.addEventListener("pagehide", parar, { once: true });

  return { atualizar, parar };
}


if (typeof document !== "undefined" && typeof window !== "undefined") {
  iniciarAtualizacaoPeriodica();
}
