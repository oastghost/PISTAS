# Alertas à ANA quando um controlador reporta um stand incorreto

> **Estado: em exploração.** Os alertas por e-mail (e o Mailpit) não estão fechados e não são uma funcionalidade prometida. O banner na página da ANA é a parte estável.


Quando um controlador reporta um voo (`POST /api/reports`), a ANA é avisada de duas formas:

1. **E-mail para todas as contas ANA** com número do voo, tipo de aeronave, stand (gate), horário,
   descrição e autor.
2. **Banner na página da ANA**, atualizado a cada 5 s. Fica visível até um operador clicar em
   "Reconhecer", por isso um reporte que chegou com a página fechada também é visto.

## Como funciona (outbox transacional)

- O reporte e uma linha em `email_outbox` por destinatário são gravados **na mesma transação**
  (migração `002_email_alerts.sql`). Não existe reporte sem os seus e-mails.
- O envio não fica no pedido HTTP. Cada backend tem uma thread que lê a `email_outbox` e envia por
  SMTP. Se o SMTP estiver em baixo o reporte é aceite na mesma e o e-mail fica `pending`.
- Falhas repetem com espera crescente (15 s, 30 s, ... até 5 min) e passam a `failed` ao fim de
  `MAIL_MAX_ATTEMPTS` (6).
- Os 3 backends partilham a fila sem duplicar: cada linha é reservada com um `UPDATE` condicional
  que adia `next_try_at` (uma licença de 60 s). No Galera, uma reserva simultânea noutro nó falha na
  certificação e conta como perdida. A entrega é *pelo menos uma vez*: uma queda entre o envio e a
  marcação pode repetir um e-mail, nunca perde nenhum.
- Os destinatários são todas as contas com `role = 'ana'` e e-mail preenchido (o seed cria `ana`,
  `ana2` e `ana3`). Acrescentar um operador é acrescentar uma conta.

## Configuração

Na pilha completa o `docker-compose.yml` inclui o **Mailpit**, que apanha todos os e-mails sem os
enviar para fora. Caixa de entrada em `http://localhost:8025`.

Para uma conta real, preencher no `.env` `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`,
`SMTP_STARTTLS=true` e `MAIL_FROM` (Gmail: porta 587 e uma palavra-passe de aplicação). Com
`SMTP_HOST` vazio os alertas por e-mail ficam desligados; o banner continua a funcionar.

## Prova de escala (T9 e T10)

`backend/tests/cluster/test_email_scale.py`, contra a pilha completa (nginx, 3 backends, 3 nós
Galera, Mailpit). 150 reportes enviados em simultâneo por 24 threads, 3 contas ANA:

| Teste | Resultado |
|---|---|
| T9 rajada de 150 reportes | 450 e-mails, todos entregues **uma só vez** (sem perdas nem duplicados, confirmado na caixa do Mailpit e na `email_outbox`). Latência do pedido p50 112 ms, p95 2,2 s, 36 reportes/s. O envio repartiu-se pelos 3 backends (168 / 155 / 127). |
| T10 Mailpit parado durante a rajada | Os 150 reportes foram aceites (máximo 2,3 s). Depois de o Mailpit voltar, os 450 e-mails chegaram uma só vez. |

Correr: `PISTAS_CLUSTER=1 .venv/Scripts/python -m pytest tests/cluster/test_email_scale.py -v -s`.
Os testes unitários (`tests/test_notify.py`) cobrem o conteúdo do e-mail, SMTP em baixo, desistência
após o máximo de tentativas, 8 workers em simultâneo sem duplicados e alertas desligados.

## Limites

- O p95 de 2,2 s inclui a espera das 24 threads pelos 3 backends no mesmo hardware, não é um
  valor de produção.
- Os endereços do seed são simulados (`@pistas.test`). Os endereços reais da ANA têm de vir da ANA.
- O banner usa polling de 5 s, não WebSocket. É suficiente para este volume.
