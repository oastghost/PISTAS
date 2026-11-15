# Solver de restrições (CSP) da A PISTAS

> **Estado: em validação.** O solver ainda não é totalmente fiável. Os testes passam, mas não cobrem todos os casos. A decisão final é sempre da base de dados, por isso um erro do solver não cria reservas duplicadas.


Código: `app/backend/app/csp.py` (motor) e `app/solver.py` (modelo dos stands).
Escrito de raiz, só com a biblioteca standard do Python: sem OR-Tools nem outro solver.

## O que faz

O despachante pede um stand concreto. Se o pedido for recusado (stand ocupado, demasiado pequeno ou
retirado pela ANA a esse voo), o solver propõe até 5 stands alternativos. O solver só propõe: nunca
escreve na base de dados. Quem decide é a base de dados, por isso uma proposta pode ainda ser recusada
se outro pedido entrar primeiro, e o despachante simplesmente pede de novo.

## Motor (`csp.py`)

Resolve problemas com variáveis de domínio finito, restrições unárias e binárias e um custo aditivo por
(variável, valor). Técnicas da UC de IA:

| Técnica | Papel |
|---|---|
| Consistência de nó | as restrições unárias filtram cada domínio antes da procura |
| AC-3 | consistência de arco nas restrições binárias, antes da procura; deteta logo problemas impossíveis |
| Backtracking | procura em profundidade, uma variável de cada vez |
| MRV + grau | escolhe a variável com menos valores restantes e, em empate, mais vizinhas por atribuir |
| Forward checking | cada escolha retira dos vizinhos os valores que deixa de permitir |
| Branch and bound | valores por ordem de custo; corta o ramo quando nem o melhor caso bate a k-ésima melhor solução |

Devolve as `k` soluções mais baratas, da melhor para a pior; empates resolvidos pela ordem dos valores,
por isso é determinístico.

## Modelo dos stands (`solver.py`)

| Elemento | Definição |
|---|---|
| Variáveis | uma por voo; o valor é um stand |
| Restrições unárias | a aeronave cabe; a ANA não retirou o stand ao voo; nada o ocupa durante o voo (já com os 30 min de turnaround) |
| Restrição binária | dois voos que se sobrepõem no tempo não partilham stand |
| Objetivo | minimizar: sair do stand pedido, depois outro apron, depois envergadura não usada (poupa stands grandes para aeronaves grandes), depois o identificador |

- `propose(...)`: o caso de um só voo usado pela aplicação (alternativas, excluindo o stand pedido).
- `assign(...)`: vários voos em conjunto, custo total mínimo ou `None` se não couberem todos.

## Garantias e falhas

- Função pura: recebe uma fotografia do plano e devolve uma proposta. Sem código de base de dados.
- Determinística: sem aleatoriedade nem fios de execução.
- Se a procura não terminar no limite de tempo (2 s), levanta `SolverError`. O pedido de alternativas falha
  com 503 e nada é escrito.

## Como foi testado

- `tests/test_csp.py`: o motor em problemas clássicos com resposta conhecida (N-rainhas: 2, 10, 4 e 92
  soluções para n = 4, 5, 6, 8; coloração do mapa da Austrália; sem solução; k melhores contra força bruta;
  limite de tempo).
- `tests/test_solver.py`: contra um oráculo simples (primeiro lugar livre, `tests/first_fit_oracle.py`), em 150
  cenários aleatórios sobre os 84 stands reais as propostas são idênticas; todas cumprem as regras;
  `assign` tem o mesmo custo que a força bruta em 40 cenários; tempo bem abaixo de 2 s.
