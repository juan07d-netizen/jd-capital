# JD Capital — Financial & Growth Domain Model

## Reglas financieras innegociables

1. No usar `float` para dinero.
2. Los saldos no se editan manualmente.
3. Todo saldo se deriva del ledger.
4. Toda transacción posteada conserva historial.
5. Las correcciones usan reversión/ajuste.
6. Una transferencia propia no cambia patrimonio.
7. Un aporte del propietario no es ingreso generado.
8. Un retiro personal no es transferencia entre cuentas propias.
9. Una inversión no es gasto.
10. Una pérdida reduce patrimonio.
11. Una comisión se registra explícitamente.
12. Movimientos históricos conservan su tipo de cambio.
13. REAL y PRUEBA nunca se mezclan.

## Asset

Campos:
- id
- code
- name
- type: fiat / internal_unit / crypto / other
- precision
- active

No asumir dos decimales para todas las unidades.

## Account

Campos:
- id
- environment_id
- name
- type
- asset principal
- provider/platform
- country opcional
- allow_negative
- active
- integration_mode
- external_reference opcional
- created_at
- updated_at

Tipos:
- cash
- bank
- wallet
- income_platform
- investment
- exchange
- clearing
- owner_equity
- expense
- revenue
- other

## Ledger de doble entrada

`Transaction`:
- id
- environment_id
- type
- status
- idempotency_key
- effective_at
- settled_at
- created_at
- created_by
- description
- external_reference
- source_entity_type/id
- reversal_of
- metadata

`Entry`:
- id
- transaction_id
- account_id
- asset_id
- amount_decimal
- availability_state
- memo

Toda operación debe mantener balance contable según las reglas del activo.

## Tipos de transacción

- owner_contribution
- income
- expense
- transfer
- investment_open
- investment_return
- investment_close
- loss
- fee
- refund
- personal_withdrawal
- tax
- conversion
- reconciliation_adjustment
- reversal
- opening_balance
- legacy_migration

## Estado de transacción

Separado del estado del dinero:
- draft
- pending
- posted
- settled
- reversed
- cancelled
- failed

Una transacción `posted` no se edita destructivamente.

## Disponibilidad

- pending
- earned
- available
- reserved
- in_transit
- invested
- blocked
- settled
- withdrawn
- cancelled

## Transferencias

Ejemplo:
PayPal USD -100
Banco USD +98
Fee USD -2

La transferencia principal no cambia patrimonio; la comisión sí.

## Conversión

Guardar:
- activo/cantidad origen;
- activo/cantidad destino;
- tasa;
- dirección;
- timestamp;
- fuente;
- comisión.

No recalcular historia con cotización actual.

## Conciliación

`ReconciliationSnapshot`:
- account_id
- asset_id
- observed_balance
- ledger_balance
- difference
- observed_at
- source
- note

Diferencias producen ajuste explícito, no edición de saldo.

## Patrimonio

Métricas derivadas:
- assets_total
- liabilities_total
- net_worth
- available
- pending
- reserved
- in_transit
- invested
- blocked
- generated_income
- realized_profit
- operating_cost
- jd_capital_cost

Aporte del propietario y rendimiento del sistema siempre separados.

## IncomeSource

- id
- name
- category
- platform
- status
- country
- payout_method
- payout_threshold
- created_at
- last_verified_at
- notes

## Opportunity

- id
- source_id
- title
- description
- source_url
- discovered_at
- last_verified_at
- country_eligibility
- required_capital
- estimated_reward
- estimated_time
- payout_method
- payout_threshold
- requirements
- automation_class
- evidence_status
- status
- risk_factors
- notes

Estados:
- detected
- researching
- needs_verification
- viable
- rejected
- awaiting_human
- awaiting_authorization
- active
- waiting_payment
- paid
- paused
- exhausted
- closed

## Evidence

- source_url
- source_type
- retrieved_at
- title
- structured facts/excerpt
- freshness
- primary_source
- checksum opcional

Una oportunidad vieja debe revalidarse.

## Strategy

- id
- name
- source/opportunity relation
- status
- repeatable
- automation_mode
- capital_limit
- time_budget
- success_count
- failure_count
- total_generated
- total_cost
- total_time
- last_run_at
- next_run_at
- stop_conditions

## WorkItem / Job

- id
- type
- priority
- status
- strategy_id
- opportunity_id
- parent_job_id
- attempts
- max_attempts
- next_attempt_at
- timeout
- requires_human
- requires_authorization
- budget
- result
- error

Debe soportar varios trabajos simultáneos.

## HumanTask

- id
- work_item_id
- title
- exact_action_required
- reason
- external_url
- deadline
- status
- completed_at

El agente sigue trabajando aunque existan tareas humanas pendientes.

## AuthorizationRequest

- id
- action_type
- amount
- asset
- percent_of_available
- risk_level
- reason
- expires_at
- status
- approved_by
- approved_at

Políticas:
- monto máximo automático;
- % máximo de patrimonio;
- riesgo máximo;
- plataformas permitidas;
- gasto diario;
- gasto mensual;
- tipos de acción.

## Risk Engine

Factores transparentes:
- capital requerido;
- pérdida máxima;
- liquidez;
- duración;
- reputación;
- verificabilidad;
- jurisdicción;
- bloqueo de fondos;
- dependencia de terceros;
- restricciones de automatización;
- concentración;
- incertidumbre.

## Performance

Medir:
- intentos;
- éxitos;
- tasa histórica;
- ingresos brutos;
- comisiones;
- costos;
- beneficio neto;
- capital medio usado;
- tiempo humano;
- tiempo de sistema;
- retorno realizado;
- demora de cobro;
- repetibilidad.

## Asignación de capital

Separar:
- reserva;
- capital operativo;
- capital de inversión;
- costos de infraestructura;
- retiro personal.

La reinversión se rige por políticas, no por decisión libre de un LLM.

## Idempotencia, concurrencia y auditoría

- idempotency key obligatoria en operaciones sensibles;
- constraints de DB contra duplicados;
- transacciones y locking apropiado;
- auditoría de actor, acción, timestamp, before/after, motivo y correlation id;
- secretos nunca en logs.

## Regla de acceso al ledger

Sólo servicios financieros autorizados pueden postear transacciones.

Prohibido:
- SQL directo desde UI;
- SQL directo desde IA;
- SQL directo desde research providers;
- modificar saldo mediante endpoint genérico.
