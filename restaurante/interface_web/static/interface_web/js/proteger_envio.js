document.addEventListener("submit", (evento) => {
  const formulario = evento.target;
  if (!formulario.matches("[data-envio-unico]") || !formulario.checkValidity()) {
    return;
  }

  const botao = formulario.querySelector('button[type="submit"]');
  if (botao) {
    botao.disabled = true;
    botao.textContent = "Enviando…";
  }
});
