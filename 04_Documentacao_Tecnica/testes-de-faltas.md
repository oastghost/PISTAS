# Testes de faltas T1 a T8

Data: 2026-10-12. Código: `05_Artefactos/codigo/backend/tests/cluster/`.
Execução: `PISTAS_CLUSTER=1 python -m pytest tests/cluster -v -s` com o sistema completo a correr.

## Ambiente

| Parte | Configuração |
|---|---|
| Entrada | nginx 1.27, TLS, limite de 10 logins por minuto por endereço, verificação de saúde passiva |
| Backends | 3 contentores FastAPI. Cada um prefere um nó diferente e passa para os outros se falhar |
| Base de dados | MariaDB 11.4, cluster Galera de 3 nós (`galera1`, `galera2`, `galera3`) |
| Regra principal | `UNIQUE (stand_id, occupied WITHOUT OVERLAPS)` em `stand_block`, ver `spike-sem-sobreposicao.md` |

Uma "avaria" de um nó é `docker kill` (SIGKILL, sem aviso ao cluster). O reinício automático do
Docker é desligado durante o teste, para a avaria não ser escondida.

## Resultados

Execução completa de 2026-10-12: 10 testes, todos passaram, 11 minutos.

| Id | O que foi feito | Esperado | Resultado |
|---|---|---|---|
| T1 | Nó `galera2` morto durante 60 pedidos feitos por 4 fios | Sem erros visíveis, sem duplicados | 60 de 60 aprovados (201), 60 reservas na base, nenhuma sobreposição, cluster com 2 nós |
| T2 | Contentor `backend1` parado durante 60 pedidos, com reenvio do mesmo identificador | O pedido reenviado funciona | 60 de 60 aprovados, 60 reservas, 60 identificadores distintos |
| T3 | 20 pedidos simultâneos para o mesmo stand e hora, pelo nginx e pelos 3 backends | Exatamente 1 aprovado | 1 aprovado (201) e 19 recusados (409). 1 reserva e 1 bloco em cada um dos 3 nós |
| T4 | Mesmo identificador duas vezes, e 12 vezes em simultâneo | 1 reserva | 1 reserva, mesma resposta em todos os pedidos |
| T5 | `galera3` desligado da rede da base de dados | O nó isolado recusa escritas, os outros continuam | `galera3` passou a `non-Primary`, escrita direta falhou com erro 1047. 10 pedidos aprovados pelos outros dois. Cluster com 2 nós |
| T6 | `galera2` e `galera3` mortos | Escritas recusadas | `galera1` perdeu o quórum (`non-Primary`). 5 pedidos recusados com 503, `/health` devolveu 503, nada foi escrito. Ao voltarem os nós, o cluster refez-se sozinho com os dados intactos |
| T7 | `galera2` morto, 15 reservas feitas, `galera2` reiniciado | Sincroniza e volta a juntar-se | Voltou a `Synced` e a 3 nós. As 15 reservas existem nos 3 nós, sem sobreposições |
| T8 | ANA remove uma alocação com `galera2` morto | Remoção e aviso gravados juntos | Nos nós `galera1` e `galera3`: estado `removed`, 1 aviso, 0 blocos. Depois de `galera2` voltar, o mesmo. O despachante vê o aviso com o contacto da ANA |

Testes adicionais:

| O que | Resultado |
|---|---|
| Limite de logins no nginx | O 1.º pedido devolve 401, a partir do limite devolve 429 |
| Paragem limpa (`docker stop`) de 2 nós | O serviço continua no último nó, 1 pedido aprovado |

## O que isto mostra

1. **Escritas duplicadas não aconteceram em nenhum cenário.** A garantia vem da base de dados, não
   do código Python.
2. **Há duas famílias de avaria muito diferentes.** Uma paragem limpa de um nó é um adeus: os outros
   recalculam o quórum e o serviço continua mesmo com um só nó. Uma queda (matar o processo ou
   cortar a rede) pode custar o quórum. Com 2 de 3 nós em queda, o nó que fica recusa tudo. É a
   escolha correta para uma regra que não pode falhar, e o preço é a indisponibilidade.
3. **Recusa falsa em corrida entre nós.** Quando dois nós aceitam pedidos sobrepostos ao mesmo
   tempo, o perdedor recebe o erro 1213. O backend repete o pedido (até 6 vezes), por isso o
   despachante só vê uma recusa verdadeira.
4. **Não existe modo só de leitura em partição.** Um nó sem quórum recusa também as leituras. É a
   decisão provisória do modelo de faltas e fica assim. Uma alternativa (`wsrep_dirty_reads`)
   daria leituras possivelmente desatualizadas, e não foi implementada.

## Limites

- A verificação de saúde do nginx é passiva (open source): um backend que falha duas vezes fica
  de fora 5 segundos. Não há verificação ativa. O `proxy_next_upstream` reenvia pedidos falhados
  para outro backend, o que é seguro porque os pedidos têm identificador.
- O reenvio de uma remoção da ANA cuja resposta se perdeu devolve 404 (já estava removida). Não
  duplica nada, mas a ANA vê um erro apesar de a remoção ter sido feita.
- Todos os nós e os contentores correm na mesma máquina. Não foram testadas latência nem perdas
  de pacotes.

## Queda simultânea dos 3 nós

Cada nó recusa criar um cluster novo se não foi o último a sair (`safe_to_bootstrap: 0`), para não
perder reservas confirmadas. Foi confirmado depois de `docker kill` aos 3 nós: o `galera1`
recusou arrancar. É o comportamento correto e exige um procedimento de recuperação:

```powershell
cd 05_Artefactos/codigo
.\db\galera\recover.ps1
```

O script lê a posição de cada nó (`--wsrep-recover`), escolhe o mais avançado, marca só esse como
seguro e arranca-o primeiro. Testado: os 3 nós tinham a posição 686, o cluster voltou a 3 nós com
os dados intactos e o sistema voltou a responder.
