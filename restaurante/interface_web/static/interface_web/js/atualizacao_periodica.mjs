export const INTERVALO_ATUALIZACAO_MS = 2000;


export function iniciarAtualizacaoPeriodica({
  documento = document,
  janela = window,
  agendar = window.setInterval.bind(window),
  cancelarAgendamento = window.clearInterval.bind(window),
  buscar = window.fetch.bind(window),
  analisarHtml = (html) =>
    new DOMParser().parseFromString(html, "text/html"),
  criarControlador = () => new AbortController(),
} = {}) {
  let raiz = documento.querySelector("[data-atualizacao-periodica]");
  if (!raiz) {
    return null;
  }

  let consultaEmAndamento = false;
  let controlador = null;
  let ativo = true;

  const atualizar = async () => {
    if (!ativo || consultaEmAndamento) {
      return;
    }
    consultaEmAndamento = true;
    controlador = criarControlador();
    try {
      const resposta = await buscar(janela.location.href, {
        method: "GET",
        cache: "no-store",
        signal: controlador.signal,
      });
      if (resposta.redirected) {
        parar();
        janela.location.assign(resposta.url);
        return;
      }
      if (!resposta.ok) {
        return;
      }
      const paginaAtualizada = analisarHtml(await resposta.text());
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
    } catch (erro) {
      if (erro.name !== "AbortError") {
        console.warn("Não foi possível atualizar a tela.", erro);
      }
    } finally {
      consultaEmAndamento = false;
      controlador = null;
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
    janela.removeEventListener("pagehide", parar);
  };
  janela.addEventListener("pagehide", parar, { once: true });

  return { atualizar, parar };
}


if (typeof document !== "undefined" && typeof window !== "undefined") {
  iniciarAtualizacaoPeriodica();
}
