---
status: accepted
---

# Estruturar o protótipo como monólito modular em processo único

O protótipo será implantado como um único processo para reduzir a complexidade de instalação, atualização e monitoramento no restaurante. Internamente, preservará limites claros entre domínio, casos de uso, persistência, interface web, ferramentas administrativas e infraestrutura, permitindo separações futuras somente quando houver uma necessidade concreta.

## Consequências

- Frontend e backend não serão implantados como serviços independentes no primeiro protótipo.
- Após a instalação, a aplicação deve iniciar com um único comando documentado.
- Windows é o ambiente operacional principal, mas a aplicação deve permanecer executável em Linux sempre que possível.
- Docker pode ser oferecido como alternativa futura, mas não será obrigatório para a execução local.
- Banco, backups e arquivos operacionais usarão diretórios persistentes e conhecidos, nunca diretórios temporários ou dependentes da sessão atual.
- Migração, backup, restauração, integridade e reset serão comandos administrativos versionados, seguros por padrão e externos à interface operacional.
- Fontes, scripts, estilos, ícones e demais recursos de execução acompanharão a aplicação, sem dependência de CDN ou serviço externo para a interface funcionar.
- Logs estruturados serão gravados localmente com rotação, cobrindo o ciclo da aplicação e operações administrativas sem reproduzir desnecessariamente os dados de consumo.
- Uma entrega operacional futura poderá ser preparada para instalação sem internet, embora o protótipo não inclua um instalador offline.
