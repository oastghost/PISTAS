# Código da A PISTAS

```
frontend/   React + Vite + TypeScript (fala com o backend em /api; VITE_USE_MOCK=true usa a API simulada)
backend/    FastAPI, regras de reserva, testes
db/         migrações numeradas, dados iniciais (stands do eAIP), spike do Galera
docker-compose.yml       fase 2: nginx, 3 backends, cluster Galera de 3 nós
docker-compose.dev.yml   fase 1: um só nó MariaDB, para desenvolvimento e testes
nginx/                   proxy inverso (TLS, limite de logins) e frontend compilado
```

## Arrancar o sistema completo (fase 2)

```bash
cp .env.example .env          # preencher as palavras-passe e o JWT_SECRET
docker compose up -d --build
```

Abre em `https://localhost:8443` (certificado de desenvolvimento autoassinado). Arrancam 3 nós Galera,
o migrate (aplica o esquema e o seed uma vez), 3 backends e o nginx.

```bash
docker compose ps                              # estado
docker compose stop galera2 && docker compose start galera2   # parar e voltar a juntar um nó
```

Se o cluster inteiro tiver parado, o `galera1` arranca um cluster novo só se for o último nó a cair
(`safe_to_bootstrap`). Caso contrário o MariaDB recusa. Ver `04_Documentacao_Tecnica/testes-de-faltas.md`.

### Alertas por e-mail

Um reporte do controlador gera um e-mail para cada conta ANA e um banner na página da ANA. A pilha
completa inclui o Mailpit: caixa de entrada em `http://localhost:8025`. Detalhes, configuração de
uma conta real e a prova de escala em `04_Documentacao_Tecnica/alertas-por-email.md`.

### Testes de faltas T1 a T8

Param e matam contentores. Só correm com o sistema completo a funcionar e `PISTAS_CLUSTER=1`:

```bash
cd backend
PISTAS_CLUSTER=1 .venv/Scripts/python -m pytest tests/cluster -v -s
```

## Arrancar o backend em desenvolvimento (fase 1)

Precisa de Docker e Python 3.12 ou superior. Em `app`:

```bash
cp .env.example .env          # preencher as palavras-passe e o JWT_SECRET
docker compose -f docker-compose.dev.yml up -d db
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"   # Linux/macOS: .venv/bin/python
.venv/Scripts/python -m app.migrate               # aplica db/migrations
.venv/Scripts/python -m app.seed                  # stands, aeronaves e contas de pessoal
.venv/Scripts/python -m uvicorn app.main:app --port 8000
```

Contas criadas pelo seed (todas com a palavra-passe `SEED_PASSWORD` do `.env`):
`tap`, `tap2`, `easyjet`, `easyjet2` (despachantes), `ana`, `ana2`, `ana3` (operadores ANA), `supervisor` (supervisão ANA, gere companhias e contas, ver `04_Documentacao_Tecnica/contas-e-companhias.md`), `atc` (controlador), `menzies`, `portway` (ground handlers).
Não existe registo de utilizadores na aplicação.

## Arrancar o frontend

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173, reencaminha /api para o backend na porta 8000
```

Sem backend: `VITE_USE_MOCK=true npm run dev` usa os dados simulados (contas `tap`, `ana`, ... com a
palavra-passe `demo`).

## Testes

Precisam da base de dados a correr. Criam e apagam a base `pistas_test`.

```bash
cd backend
.venv/Scripts/python -m pytest
.venv/Scripts/python -m ruff check .
```

Os testes T3 (20 pedidos em simultâneo, 1 aprovado) e T4 (mesmo identificador duas vezes, 1 reserva)
estão em `backend/tests/test_reservations.py`.

## Regra principal

Um stand nunca tem duas reservas sobrepostas. É garantida pela tabela `stand_block`
(`UNIQUE (stand_id, occupied WITHOUT OVERLAPS)`), não só pelo Python. Ver
`04_Documentacao_Tecnica/spike-sem-sobreposicao.md`.
