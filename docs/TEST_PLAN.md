# JD Capital — Test Plan

## Regla

Cada bug reproducido debe convertirse en prueba automática. No se considera estable una función crítica porque “el endpoint respondió”.

## Regresiones existentes a conservar

- Uvicorn sin stdout/stderr en PyInstaller windowed;
- persistencia tras reinicio;
- migraciones idempotentes;
- login;
- credenciales;
- error controlado de proveedor;
- recuperación de jobs;
- URL segura;
- retiro superior al saldo;
- JavaScript real de formularios.

## Financial Core

Probar:
- owner contribution;
- income;
- expense;
- transfer;
- personal withdrawal;
- fee;
- investment;
- return;
- loss;
- refund;
- tax;
- conversion;
- reconciliation;
- reversal;
- opening balance;
- legacy migration.

## Invariantes

- transferencia propia no cambia patrimonio;
- comisión sí lo reduce;
- aporte no cuenta como ingreso generado;
- inversión no cuenta como gasto;
- no existe doble posteo por reintento;
- fallo parcial hace rollback;
- posted no se elimina;
- REAL no cruza con PRUEBA;
- balances derivados coinciden con ledger.

## Fallos

Simular:
- corte antes y después de commit;
- DB bloqueada;
- excepción a mitad de transferencia;
- duplicado;
- timeout;
- pérdida de conexión;
- proveedor no disponible;
- respuesta inválida;
- reinicio durante job.

## Orchestrator

Probar:
- varios jobs simultáneos;
- espera humana no bloquea otros;
- autorización pendiente no bloquea investigación;
- retry/backoff;
- límites de intentos;
- pausa/reanudación;
- cancelación;
- recuperación;
- prioridades;
- budget enforcement.

## Growth Engine

Probar:
- deduplicación;
- evidencia;
- revalidación;
- descarte;
- estrategia;
- repetición;
- stop condition;
- medición real;
- cambio de prioridad por historial.

## UI

Probar:
- login;
- tema;
- REAL/PRUEBA;
- cuenta;
- movimiento;
- transferencia;
- conciliación;
- oportunidad;
- autorización;
- ejecutar;
- pausar/reanudar;
- errores visibles;
- doble clic.

## Windows

Smoke:
- instalación;
- primer inicio;
- usuario;
- cierre/reinicio;
- persistencia;
- upgrade;
- uninstall sin pérdida no solicitada;
- acceso directo;
- logs;
- una única versión canónica.

## Backups

Probar creación, integridad, restauración, compatibilidad y fallo. Un backup no es válido hasta probar restauración.
