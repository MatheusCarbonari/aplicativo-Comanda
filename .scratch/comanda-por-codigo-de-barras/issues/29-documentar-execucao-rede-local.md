# 29: Documentar execução única e acesso pela rede local

**What to build:** um procedimento operacional no qual o servidor é iniciado por um único comando e pode ser acessado com segurança pelos dispositivos da rede local sem depender da internet externa.

**Blocked by:** 02 — Configurar persistência SQLite durável; 05 — Expor e verificar a saúde do backend; 22 — Registrar logs estruturados com rotação.

**Status:** ready-for-agent

- [ ] Um único comando documentado inicia a aplicação após a instalação e informa a URL de acesso.
- [ ] Banco, backups e logs apontam para diretórios persistentes e conhecidos.
- [ ] A aplicação aceita conexões somente pelas interfaces necessárias à operação local.
- [ ] A documentação cobre firewall do Windows e recomenda endereço local estável sem alterar automaticamente o roteador.
- [ ] Não são configurados port forwarding, UPnP, hospedagem pública ou dependência de internet externa.
- [ ] O procedimento também descreve as diferenças mínimas para execução futura em Linux.
- [ ] Uma verificação automatizada ou roteiro reproduzível comprova inicialização, saúde e carregamento de recursos locais sem CDN.

