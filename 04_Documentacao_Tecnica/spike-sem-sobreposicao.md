# Spike: garantia de não sobreposição na base de dados

Data: 2026-10-12. Código: `05_Artefactos/codigo/db/spike/`.

## Pergunta

A regra principal da A PISTAS é que um stand nunca tem duas reservas sobrepostas. O MariaDB não tem
`EXCLUDE` como o PostgreSQL. A opção preferida é um período de tempo da aplicação com
`UNIQUE (stand_id, periodo WITHOUT OVERLAPS)`. Funciona em InnoDB e, sobretudo, num cluster Galera?

## Ambiente

- MariaDB 11.4.13 (imagem oficial `mariadb:11.4`), Docker.
- Teste 1: um nó isolado.
- Teste 2: cluster Galera de 3 nós (`wsrep_cluster_size = 3`), `binlog_format=ROW`.

## Resultados

| Teste | Esperado | Obtido |
|---|---|---|
| Reserva sobreposta no mesmo stand, um nó | Recusada | Erro 1062 |
| Reserva adjacente (fim = início), mesmo stand | Aceite | Aceite |
| Mesmo período, outro stand | Aceite | Aceite |
| 20 inserções simultâneas, mesmo stand e período, um nó | Exatamente 1 aceite | 1 aceite |
| 2 nós, períodos diferentes mas sobrepostos, em simultâneo | 1 aceite, o outro recusado | 1 aceite, o outro erro 1213 |
| 8 stands x 3 nós, 3 períodos sobrepostos em simultâneo por stand | No máximo 1 por stand, nós consistentes | 6 stands com 1 reserva, 2 com 0, nenhum com 2. Os 3 nós iguais e `Synced` |

## Conclusões

1. `WITHOUT OVERLAPS` funciona em InnoDB e no cluster Galera de 3 nós. Nunca apareceu uma sobreposição
   nem uma divergência entre nós. Fica escolhida a opção (a). A tabela de slots (opção b) não é necessária.
2. Numa corrida entre nós, o perdedor recebe o erro 1213 (deadlock na certificação do Galera), não 1062.
3. Numa corrida entre três nós pode acontecer que todos percam com 1213 e ninguém fique com o stand
   (2 stands em 8). Isto é seguro mas devolve uma recusa falsa. O backend tem de repetir o pedido com o
   mesmo `request_id` quando recebe 1213. Na repetição, ou ganha, ou recebe 1062 e a recusa é verdadeira.
4. A regra do intervalo mínimo entre voos (turnaround) não está no período. Duas opções para a
   implementação: guardar o período já alargado pelo intervalo, ou verificar o intervalo na transação.
   Decidir ao desenhar o esquema.

## Limites do teste

- Só 3 nós numa máquina, sem partição de rede nem nós em falha (fazem parte dos testes T1, T5 a T7).
- Cargas pequenas. Serve para validar o mecanismo, não o desempenho.
