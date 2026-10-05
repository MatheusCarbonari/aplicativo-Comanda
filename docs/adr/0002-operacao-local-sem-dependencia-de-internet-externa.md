---
status: accepted
---

# Operar o protótipo pela rede local sem depender da internet externa

O protótipo exigirá comunicação online com um backend central acessível pela rede local, mas não dependerá conceitualmente de internet externa ou hospedagem em nuvem. Não haverá gravação offline nem sincronização nesta versão; a separação entre regras de domínio, aplicação web e infraestrutura deve preservar a possibilidade futura de servidor local, PWA, sincronização ou arquitetura híbrida.

## Consequências

- Perder comunicação com o backend impede novas operações e deve produzir uma mensagem clara de falha.
- Perder apenas a internet externa não deve interromper o protótipo quando dispositivos e backend continuam conectados pela rede local.
- Dados de negócio não terão o navegador como fonte de verdade nesta versão.
- Sem autenticação real, a aplicação fica restrita a uma rede local confiável e não pode ser exposta publicamente.
- O backend carrega o usuário operacional selecionado e valida seu papel em cada operação; esconder ações na interface não substitui autorização.
- A instalação não abre portas no roteador, não configura port forwarding e não usa UPnP para exposição automática.
- O servidor deve aceitar conexões somente pelas interfaces necessárias à operação local, com instruções explícitas para o firewall do computador central.
- Reserva de IP ou nome local estável torna a URL previsível; configurar o roteador automaticamente permanece fora do escopo.
- Qualquer dispositivo na rede confiável ainda pode tentar assumir a identidade de um usuário, pois autorização por papel sem autenticação forte não comprova identidade.
- Uma publicação externa futura exige autenticação, autorização e proteção das operações.
- Autenticação real, autorização de dispositivos ou segmentação de rede serão avaliadas futuramente se a confiança implícita da rede deixar de ser suficiente.
- Funcionalidades offline, sincronização e resolução de conflitos permanecem explicitamente fora do escopo inicial.
