# Solver de restrições (CSP) da A PISTAS

Código: `05_Artefactos/codigo/backend/app/solver.py`. Biblioteca: OR-Tools CP-SAT.

## O que faz

O despachante pede um stand concreto. Se o pedido for recusado (stand ocupado, demasiado pequeno ou
retirado pela ANA a esse voo), o solver propõe até 5 stands alternativos. O solver só propõe: nunca
escreve na base de dados. Quem decide é a base de dados, por isso uma proposta pode ainda ser recusada
se outro pedido entrar primeiro, e o despachante simplesmente pede de novo.

## Modelo

| Elemento | Definição |
|---|---|
| Variáveis | uma por par (voo, stand): "este voo usa este stand" |
| Domínio | stands onde a aeronave cabe (envergadura) e de onde a ANA não retirou o voo |
| Restrição 1 | cada voo tem exatamente um stand, ou nenhum (e então paga uma penalização grande) |
| Restrição 2 | no mesmo stand, dois voos nunca se sobrepõem, nem com reservas existentes (intervalo já inclui os 30 minutos de turnaround) |
| Objetivo | minimizar: stand noutro apron que o pretendido, depois envergadura não usada (poupa stands grandes para aeronaves grandes), depois o identificador |

As restrições 2 usam `NoOverlap` sobre intervalos opcionais, como as reservas existentes que a base de
dados guarda em `stand_block`. O modelo aceita vários voos em conjunto. Hoje a API usa um voo de cada
vez, mas a mesma função resolve um conjunto de pedidos em simultâneo sem sobreposição.

## Garantias e falhas

- Função pura: recebe uma fotografia do plano e devolve uma proposta. Sem código de base de dados.
- Determinística: um só fio de execução e semente fixa, mesma entrada dá a mesma saída.
- Se não provar a melhor resposta no limite de tempo (2 s), levanta `SolverError`. O pedido de
  alternativas falha com 503 e nada é escrito.

## Como foi testado (`backend/tests/test_solver.py`)

- Contra um oráculo simples (primeiro lugar livre, `tests/first_fit_oracle.py`): em 150 cenários
  aleatórios sobre os 84 stands reais, as propostas são idênticas.
- Todas as propostas cumprem as regras (cabe, livre, não retirado, não é o stand pedido).
- Com vários voos: nunca há sobreposição nem aeronave num stand pequeno, e o número de voos servidos é o
  máximo possível, confirmado por pesquisa exaustiva em 60 instâncias pequenas.
- Tempo: uma proposta com os 84 stands e 150 reservas demora bem menos de 2 s.
