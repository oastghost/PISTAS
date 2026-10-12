# Código da A PISTAS

```
frontend/   React + Vite + TypeScript (fala com o backend em /api; VITE_USE_MOCK=true usa a API simulada)
backend/    FastAPI, regras de reserva, testes
db/         migrações numeradas, dados iniciais (stands do eAIP), spike do Galera
docker-compose.yml   fase 1: um nó MariaDB. Fase 2: cluster Galera, 3 backends, nginx
```

## Arrancar o backend (fase 1)

Precisa de Docker e Python 3.12 ou superior. Em `05_Artefactos/codigo`:

```bash
cp .env.example .env          # preencher as palavras-passe e o JWT_SECRET
docker compose up -d db
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"   # Linux/macOS: .venv/bin/python
.venv/Scripts/python -m app.migrate               # aplica db/migrations
.venv/Scripts/python -m app.seed                  # stands, aeronaves e contas de pessoal
.venv/Scripts/python -m uvicorn app.main:app --port 8000
```

Contas criadas pelo seed (todas com a palavra-passe `SEED_PASSWORD` do `.env`):
`tap`, `easyjet` (despachantes), `ana`, `atc` (controlador), `menzies`, `portway` (ground handlers).
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
