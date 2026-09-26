# JD Capital — Rules for Coding Agents

Leer antes de modificar código:
- `docs/PRODUCT_SPEC.md`
- `docs/ARCHITECTURE.md`
- `docs/FINANCIAL_GROWTH_MODEL.md`
- `docs/UI_UX_SPEC.md`
- `docs/TEST_PLAN.md`
- `docs/IMPLEMENTATION_PLAN.md`

## Reglas obligatorias

1. No reescribir el proyecto desde cero sin razón documentada.
2. Preservar datos y migraciones.
3. No tocar archivos históricos externos al repositorio.
4. No usar `float` para dinero.
5. UI, IA y providers no escriben directamente en el ledger.
6. No editar destructivamente transacciones posteadas.
7. Toda mutación financiera debe ser atómica e idempotente.
8. REAL y PRUEBA deben estar aislados.
9. No agregar APIs pagas salvo instrucción explícita.
10. No mover/invertir dinero real sin política y autorización.
11. No automatizar evasión de CAPTCHA, KYC, restricciones o términos.
12. No guardar secretos en código, DB normal o logs.
13. No depender de stdout/stderr en ejecutable windowed.
14. Evitar JS crítico embebido frágilmente en strings Python.
15. Tests backend no sustituyen pruebas de UI crítica.
16. Todo bug reproducido debe generar test de regresión.
17. No crear tag/release/installer salvo pedido de fase.
18. Cambios grandes siempre en rama.
19. Mantener `main` estable hasta aceptación.
20. Reportar archivos, migraciones, tests, resultados y limitaciones.

## Prioridad

1. integridad financiera;
2. seguridad;
3. trazabilidad;
4. continuidad de datos;
5. funcionalidad;
6. rendimiento;
7. estética.
