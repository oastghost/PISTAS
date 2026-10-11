# info.md

**Título do projeto:** A PISTAS: Plataforma Inteligente de Stands Tolerante a Avarias do Sudeis

**Ano letivo:** 2026/2027

**Semestre:** 5.º semestre

**Curso(s) envolvidos:** Licenciatura em Engenharia Informática (L-EI)

**Unidades curriculares:** Projeto de Desenvolvimento de Software, Engenharia de Software, Segurança Informática, Sistemas Distribuídos, Inteligência Artificial

**Docentes:** Rui Pascoal e Miguel Boavida (Projeto de Desenvolvimento de Software); Rui Ramos (Engenharia de Software); Sérgio Nunes e Pedro Brandão (Segurança Informática); Pedro Rosa (Sistemas Distribuídos); Samuel Gomes (Inteligência Artificial)

**Estudantes participantes:** Muhammad Sudeis Abdul Latif Sacoor, número de estudante 20241707

**Palavras-chave:** aviação, stands, reservas, sistemas distribuídos, tolerância a faltas, CSP, segurança, Docker, MariaDB Galera, LPPT

**Tecnologias utilizadas:** React com Vite (frontend), Python (backend, 3 contentores Docker), solver CSP (atribuição de stands), MariaDB em cluster Galera de 3 nós, nginx (balanceador de carga), Docker e Docker Compose, Git e GitHub

**Resumo curto:** A PISTAS é uma aplicação web para reservar os stands (lugares de estacionamento de aviões) do Aeroporto de Lisboa. O despachante de uma companhia pede um stand para um voo e um solver de restrições (CSP) escolhe um stand que cumpre todas as regras. Quando não há conflito, o pedido é aprovado automaticamente. A ANA pode remover alocações e o despachante é avisado. O despachante pode também pedir assistência em terra, e o ground handler (como a Menzies ou a Portway) só vê o pedido e atribui internamente uma das 8 equipas simuladas. A regra principal é nunca haver duas reservas sobrepostas, mesmo quando partes do sistema falham, por isso é garantida na base de dados e o sistema corre em vários contentores e nós. O acesso é protegido por autenticação. O projeto é individual e usa dados reais dos stands, com voos simulados.
