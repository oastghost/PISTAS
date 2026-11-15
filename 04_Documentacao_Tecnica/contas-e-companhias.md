# Companhias, despachantes e a supervisão da ANA

## Modelo

| Perfil | Pode |
|---|---|
| `despachante` | Pedir stands **em nome da sua companhia**, ver o plano todo (com os voos da sua companhia realçados), ver os avisos da sua companhia. |
| `ana` (operador) | Rever o plano, remover alocações, receber os alertas de reportes. Não gere contas. |
| `ana_supervisor` | Tudo o que o operador faz, mais: criar companhias, criar e desativar contas de despachante e de operador ANA, redefinir palavras-passe, ver o registo de alterações. |
| `controlador`, `handler` | Como antes. |

Uma companhia tem **vários despachantes**. A ligação é `app_user.company` (texto igual a
`airline.name` e a `reservation.company`). Não houve alteração às reservas existentes:

- Um pedido fica em nome da companhia, não da pessoa. `reservation.created_by` guarda quem o fez e
  o plano mostra-o na coluna "Pedido por".
- Quando a ANA remove uma alocação, o aviso é gravado para a **companhia**, por isso todos os
  despachantes dela o veem e os das outras companhias não.
- Reenviar o mesmo `requestId` de outra companhia é recusado.
- Um despachante vê o plano completo porque precisa de saber que stands estão livres.

## Gestão de contas (só `ana_supervisor`)

Página **Contas** (`/contas`), API em `/api/admin/*` (`backend/app/admin.py`):

- Criar companhia (nome único). Um despachante só pode ser criado para uma companhia que exista.
- Criar conta de despachante (com companhia) ou de operador ANA (sem companhia). Palavra-passe
  temporária com pelo menos 12 caracteres, guardada com Argon2id. O e-mail é obrigatório porque os
  operadores ANA e a supervisão recebem os alertas de reportes.
- Desativar e reativar. A conta desativada perde o acesso **de imediato**, mesmo com sessão aberta
  (o `active` é lido da base de dados em cada pedido) e o início de sessão falha como uma palavra-
  passe errada.
- Redefinir a palavra-passe.
- Registo de alterações: criação de companhia e de conta, desativação, reativação, redefinição de
  palavra-passe, em `audit_log`, com quem fez.

Limites de segurança: ninguém altera a própria conta por aqui, e a supervisão não gere supervisores,
controladores nem handlers (esses vêm do seed). Os perfis são verificados no backend, o ecrã só
esconde botões.

## Prefixos de voo por companhia

Cada companhia tem um ou mais prefixos (`airline_prefix`, migração 005): ICAO como `RYR`, `DLH`,
opcionalmente IATA como `FR`, `LH`. Um despachante só pode pedir voos desse prefixo seguido de 1 a
4 algarismos e, opcionalmente, uma letra (`RYR1234`, `TP123A`). A verificação é no backend, no
mesmo ponto que valida o resto do pedido; o ecrã só mostra o prefixo e avisa antes de enviar.

- Um prefixo pertence a **uma só companhia** (chave primária). Tentar usar um já atribuído é
  recusado e a mensagem diz a quem pertence.
- A supervisão define os prefixos **ao criar a companhia** (obrigatório, 1 a 6, 2 ou 3 caracteres,
  convertidos para maiúsculas) e pode acrescentar ou remover depois. Uma companhia não fica sem
  nenhum prefixo. Tudo fica no registo (`prefix_added`, `prefix_removed`, e o `airline_created`
  inclui os prefixos).
- Uma companhia sem prefixo (criada antes desta migração) não consegue pedir stands até a
  supervisão lhe dar um. A mensagem diz-lhe para o pedir.
- Reservas já existentes não são alteradas; a regra vale para pedidos novos.
- Seed: TAP (`TAP`, `TP`) e easyJet (`EZY`, `U2`).
- Só despachantes são limitados. A ANA remove alocações de qualquer voo.

## Mudança de palavra-passe no primeiro início de sessão

Uma conta criada pela supervisão, ou cuja palavra-passe a supervisão redefiniu, fica com
`must_change_password = 1` (migração 004). Enquanto estiver assim:

- O ecrã mostra só "Defina a sua palavra-passe" (palavra-passe temporária, nova e repetição).
- **O backend recusa tudo o resto** com `403 PASSWORD_CHANGE_REQUIRED`, exceto `GET /api/auth/me` e
  `POST /api/auth/change-password`. Não depende do ecrã.
- Uma redefinição pela supervisão bloqueia logo a sessão que já estiver aberta.
- A mudança exige a palavra-passe atual (um token roubado não chega), tem pelo menos 12
  caracteres, tem de ser diferente da atual e fica no registo (`password_changed`, sem a palavra-
  passe). O nginx aplica ao `change-password` o mesmo limite do início de sessão.
- As contas do seed não são obrigadas a mudar.

## Limites conhecidos

- Não há ainda "alterar a minha palavra-passe" fora do primeiro início de sessão, nem recuperação
  de palavra-passe esquecida (só a supervisão a redefine).

- A migração 003 cria a tabela `airline` a partir das companhias já existentes e não acrescenta
  chave estrangeira em `app_user.company`, porque os handlers também usam esse campo. A validação é
  feita pela API.
- Os endereços do seed são simulados (`@pistas.test`).
- A supervisão não valida se o prefixo é mesmo o da companhia no mundo real (não há lista oficial
  no projeto). Quem cria a companhia é responsável por o escrever bem.
- Contas seed novas: `tap2`, `easyjet2` (segundos despachantes) e `supervisor`.
