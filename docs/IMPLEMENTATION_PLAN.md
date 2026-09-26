# JD Capital — Implementation Plan

## Fase 0 — Especificación
Definida en `/docs`. No cambiar código funcional todavía.

## Fase 1 — Separación arquitectónica sin cambiar comportamiento
- extraer rutas;
- separar frontend;
- introducir repositorios/servicios;
- mantener comportamiento actual;
- mantener tests.

Criterio: misma funcionalidad actual, estructura mejorada, tests verdes.

## Fase 2 — Financial Core
- environments REAL/PRUEBA;
- assets;
- accounts;
- double-entry ledger;
- transactions/entries;
- idempotencia;
- reversión;
- conciliación;
- migración legacy;
- portfolio metrics.

Criterio: invariantes financieras cubiertas por tests.

## Fase 3 — Growth Domain
- income sources;
- opportunities;
- evidence;
- strategies;
- work items;
- human tasks;
- authorization requests;
- performance.

Criterio: representar un ciclo completo sin depender de OpenAI.

## Fase 4 — Orchestrator
- cola persistente;
- concurrencia controlada;
- retries;
- pausa/reanudación;
- trabajos en espera;
- recuperación;
- budget/policy enforcement.

Criterio: varios trabajos progresan independientemente.

## Fase 5 — Research adapters sin costo obligatorio
- interfaz de providers;
- fuentes públicas permitidas;
- RSS/APIs gratuitas/conectores específicos;
- evidencia/revalidación;
- deduplicación.

Criterio: descubrir oportunidades sin OpenAI paga.

La cobertura inicial no equivale a un buscador web global; la arquitectura permitirá sumar search APIs/IA cuando el sistema pueda autofinanciarlas.

## Fase 6 — Decision, Risk y Authorization
- priorización por reglas;
- riesgo transparente;
- límites;
- autorización humana.

Criterio: ninguna acción monetaria fuera de política.

## Fase 7 — Nueva UI
- sidebar;
- dashboard simple;
- claro/oscuro;
- cuentas;
- movimientos;
- oportunidades;
- investigación;
- autorizaciones;
- ajustes.

Criterio: recorridos críticos desde UI con tests.

## Fase 8 — Seguridad y continuidad
- cambio de contraseña;
- email preparado;
- arquitectura de recovery;
- sesiones;
- auditoría;
- backup/restore;
- hardening.

Email real/recovery remoto requiere infraestructura de entrega; no fingir que existe mientras sea local-only.

## Fase 9 — Windows acceptance
- build;
- installer;
- upgrade;
- persistence;
- acceso directo canónico;
- smoke E2E.

## Fase 10 — Auto-financiación
Sólo después de ingresos reales:
- API de IA;
- search provider pago;
- backend cloud;
- workers 24/7;
- integraciones financieras oficiales;
- móvil/PWA.

Cada servicio pago debe tener costo atribuido a JD Capital para medir si se autofinancia.
