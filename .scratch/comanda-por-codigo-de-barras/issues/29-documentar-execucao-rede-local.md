# 29: Documentar execução única e acesso pela rede local

**What to build:** um procedimento operacional no qual o servidor é iniciado por um único comando e pode ser acessado com segurança pelos dispositivos da rede local sem depender da internet externa.

**Blocked by:** 02 — Configurar persistência SQLite durável; 05 — Expor e verificar a saúde do backend; 22 — Registrar logs estruturados com rotação.

**Status:** resolved

- [x] Um único comando documentado inicia a aplicação após a instalação e informa a URL de acesso.
- [x] Banco, backups e logs apontam para diretórios persistentes e conhecidos.
- [x] A aplicação aceita conexões somente pelas interfaces necessárias à operação local.
- [x] A documentação cobre firewall do Windows e recomenda endereço local estável sem alterar automaticamente o roteador.
- [x] Não são configurados port forwarding, UPnP, hospedagem pública ou dependência de internet externa.
- [x] O procedimento também descreve as diferenças mínimas para execução futura em Linux.
- [x] Uma verificação automatizada ou roteiro reproduzível comprova inicialização, saúde e carregamento de recursos locais sem CDN.

## Answer

Adicionado o comando operacional `scripts/iniciar_servidor.ps1`, que localiza a
raiz, usa o Python da `.venv`, inicia `runserver 0.0.0.0:8000 --noreload`,
informa as URLs locais e propaga o código de saída. O IPv4 é descoberto em tempo
de execução, sem endereço fixo, e compõe os hosts permitidos do Django. A
documentação cobre acesso pela LAN, saúde, firewall privado limitado a
`LocalSubnet`, IP estável, diretórios persistentes, restrições contra exposição
pública e o equivalente mínimo no Linux. A verificação automatizada inicia o
wrapper com banco e log isolados, consulta `/saude/`, `/` e assets locais com
timeout, e encerra toda a árvore de processos. As mensagens acentuadas são
construídas de forma compatível com o parser do Windows PowerShell 5.1. Nos
testes, o wrapper e o Django pertencem a um Job Object local com encerramento da
árvore ao fechar o handle; tanto o caminho cooperativo quanto o fallback forçado
são cobertos sem deixar servidor órfão.

