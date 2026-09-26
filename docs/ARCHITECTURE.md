# JD Capital — Architecture

## Estado actual del repositorio

Componentes útiles que deben preservarse:
- FastAPI local en `127.0.0.1`;
- SQLite local con WAL;
- soporte futuro para PostgreSQL;
- Argon2 para contraseñas;
- keyring para credenciales;
- persistencia y recuperación de jobs;
- build Windows con PyInstaller;
- instalador Inno Setup;
- suite de pruebas;
- regresiones de frontend y logging ya cubiertas.

Limitaciones actuales:
- `app.py` concentra HTML, JavaScript, endpoints y presentación;
- `db.py` concentra esquema, migraciones y lógica financiera simple;
- `engine.py` representa una ejecución serializada, no un orquestador;
- `ai.py` está acoplado directamente a OpenAI;
- no existen cuentas, ledger de doble entrada, estrategias, autorizaciones ni ejecución paralela;
- el motor actual no opera sin OpenAI.

La reforma debe ser evolutiva, no una reescritura destructiva.

## Principios

1. Backend como fuente de verdad.
2. UI no calcula saldos críticos.
3. UI, IA e integraciones no escriben tablas financieras directamente.
4. Toda mutación financiera pasa por servicios deterministas del dominio.
5. Growth Engine desacoplado de proveedores de IA/búsqueda.
6. Proveedores reemplazables.
7. Operaciones idempotentes y atómicas.
8. REAL y PRUEBA aislados.
9. Todo bug conocido se convierte en prueba.
10. El dominio local debe poder migrar a cloud sin reescritura.

## Arquitectura objetivo

```text
jd_capital/
├── app/
│   ├── routes/
│   ├── schemas/
│   └── dependencies/
├── financial/
│   ├── accounts.py
│   ├── assets.py
│   ├── ledger.py
│   ├── transactions.py
│   ├── portfolio.py
│   ├── reconciliation.py
│   └── services.py
├── growth/
│   ├── opportunities.py
│   ├── income_sources.py
│   ├── strategies.py
│   ├── research.py
│   ├── decision.py
│   ├── risk.py
│   ├── authorization.py
│   ├── execution.py
│   ├── orchestrator.py
│   └── performance.py
├── providers/
│   ├── research/
│   ├── ai/
│   ├── financial/
│   └── notifications/
├── persistence/
│   ├── database.py
│   ├── migrations/
│   └── repositories/
├── security/
├── settings/
├── web/
│   ├── templates/
│   ├── static/
│   └── frontend/
└── workers/
    ├── scheduler.py
    └── jobs.py
```

No es obligatorio crear todos los archivos de una vez. Es la dirección de separación.

## Financial Core

Responsabilidades:
- activos/unidades;
- cuentas;
- ledger;
- transacciones;
- balances;
- patrimonio;
- conciliación;
- reversión;
- auditoría financiera.

No conoce OpenAI, HTML ni reglas de investigación.

## Growth Engine

### Research Engine
Descubre y verifica.

### Decision Engine
Prioriza según datos y políticas.

### Risk Engine
Evalúa factores de riesgo.

### Authorization Engine
Determina si una acción está permitida, necesita aprobación o está prohibida por política.

### Execution Engine
Ejecuta únicamente adaptadores permitidos.

### Performance Engine
Mide resultados reales.

### Orchestrator
Coordina el sistema completo.

## Orchestrator

Debe soportar:
- múltiples trabajos;
- estados;
- prioridades;
- reintentos/backoff;
- dependencias;
- tareas humanas;
- trabajos en espera;
- concurrencia controlada;
- presupuestos y límites;
- cancelación;
- recuperación tras reinicio.

Estados sugeridos:
- queued
- researching
- analyzing
- awaiting_authorization
- awaiting_human_action
- ready
- running
- waiting_external
- completed
- failed
- paused
- cancelled

Un trabajo bloqueado no detiene otros.

## Providers

Research providers reemplazables:
- RSS;
- feeds;
- APIs gratuitas permitidas;
- páginas públicas con acceso permitido;
- conectores específicos;
- búsqueda web paga futura;
- IA paga futura.

La IA será opcional y no debe ser requisito del Financial Core.

Execution adapters encapsulan cada automatización externa y declaran capacidades, necesidad de humano y autorización.

## Persistencia

SQLite es válida para etapa local con:
- WAL;
- foreign keys;
- transacciones;
- migraciones versionadas;
- constraints;
- índices;
- idempotency keys;
- UTC interno;
- backups verificables.

PostgreSQL será destino natural al migrar a cloud.

## UI

El HTML/JS inline actual es prototipo. Evolución:
- HTML a templates/componentes;
- CSS a estáticos;
- JS a módulos;
- endpoints a routers;
- validación a schemas;
- reglas a dominio.

## Local y cloud

Etapa local:
- FastAPI localhost;
- DB local;
- worker local;
- agente funciona mientras la PC y JD Capital están activos.

Etapa cloud futura:
- backend remoto;
- workers 24/7;
- base central;
- Windows/móvil/PWA clientes;
- autenticación reforzada.

## Aprendizajes de errores previos

- No depender de stdout/stderr en PyInstaller windowed.
- No incrustar JS crítico de forma frágil dentro de strings Python.
- No considerar suficiente que el backend funcione: probar UI crítica.
- Mantener una versión canónica para usuario.
- Toda operación financiera debe sobrevivir corte de energía con commit o rollback.
- Todo bug reproducido genera test de regresión.
