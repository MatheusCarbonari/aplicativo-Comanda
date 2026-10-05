---
status: accepted
---

# Usar Python, Django e templates renderizados no servidor no protótipo

O protótipo será implementado em Python com Django, SQLite e Django Templates, usando HTML, CSS e JavaScript apenas onde forem necessários. A escolha atende ao foco do sistema em regras de domínio, persistência transacional, migrações, comandos administrativos e testes, mantendo simples a execução do monólito modular na rede local. React, TypeScript e a separação entre frontend e backend não serão introduzidos sem uma necessidade concreta.

## Alternativas consideradas

- **Next.js full-stack com TypeScript:** oferece uma experiência integrada para aplicações React, mas adicionaria ao protótipo uma camada de frontend e uma complexidade que os requisitos atuais não justificam.
- **Django como monólito web com renderização no servidor:** escolhido por reunir persistência, transações, migrações, testes, comandos administrativos e interface web em uma única aplicação Python.

## Consequências

- A interface inicial será renderizada no servidor com Django Templates e será responsiva para navegadores em celulares e computadores.
- JavaScript será usado pontualmente para comportamentos interativos, leitura do identificador digitado pelo leitor, atualização periódica e indicação do estado de comunicação.
- A aplicação web operacional será implantada como um único processo no servidor central. As ferramentas administrativas usarão o mesmo projeto versionado e serão executadas sob demanda.
- As regras de domínio e os casos de uso ficarão, tanto quanto for prático, em módulos com dependência mínima do Django; ORM, requisições web, templates e comandos administrativos serão tratados nas bordas da aplicação.
- O Django ORM, o sistema de migrações e os comandos de gerenciamento poderão ser usados para implementar a persistência e as rotinas operacionais definidas para o protótipo.
- A adoção de Django é uma decisão da implementação inicial, não uma restrição permanente do produto. Frontend, banco de dados, implantação e partes da stack poderão ser reavaliados quando requisitos futuros justificarem a mudança.
- As operações concorrentes deverão respeitar as limitações do SQLite. A aplicação não poderá depender de bloqueios de linha ou de outros mecanismos que o banco não ofereça adequadamente.
- Invariantes críticas serão protegidas por transações curtas e restrições no banco sempre que possível, incluindo a garantia de no máximo um atendimento aberto por comanda física.

