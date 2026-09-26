# JD Capital — UI / UX Specification

## Objetivo

La interfaz debe sentirse como un centro financiero moderno, no como un formulario técnico. Debe ser simple, legible, consistente, responsive y con tema claro/oscuro.

## Navegación principal

Barra lateral:
- Inicio
- Patrimonio
- Cuentas
- Movimientos
- Ingresos
- Inversiones
- Oportunidades
- Investigación
- Reportes
- Ajustes

## Barra superior

- ambiente REAL/PRUEBA;
- patrimonio resumido;
- estado del agente;
- notificaciones;
- perfil;
- selector de tema.

REAL/PRUEBA debe ser visualmente inequívoco.

## Inicio

No contiene formularios largos.

Primer nivel:
- Patrimonio total
- Disponible
- Pendiente
- Invertido
- En tránsito

Segundo nivel:
- Estado del agente
- Oportunidades activas
- Estrategias activas
- Acciones pendientes
- Autorizaciones pendientes
- Actividad reciente
- Evolución patrimonial

## Estado del agente

Controles:
- Iniciar
- Pausar
- Reanudar
- Detener de forma segura

Estados:
- detenido
- ejecutando
- pausado
- degradado
- requiere atención

Resumen:
- fuentes revisadas;
- oportunidades detectadas;
- trabajos activos;
- trabajos esperando;
- tareas humanas;
- autorizaciones;
- últimos resultados.

## Investigación

Mostrar:
- consultas activas;
- fuentes;
- resultados;
- evidencia;
- fecha de verificación;
- elegibilidad;
- restricciones;
- motivo de descarte;
- oportunidad creada.

## Oportunidades

Lista con:
- nombre;
- fuente;
- capital requerido;
- ingreso estimado;
- tiempo estimado;
- estado;
- riesgo;
- automatización;
- fecha de verificación.

Detalle:
- evidencia;
- requisitos;
- método de cobro;
- pasos;
- historial;
- resultados;
- autorizaciones;
- tareas humanas.

## Movimientos

Tabla con:
- fecha;
- tipo;
- cuenta origen;
- cuenta destino;
- importe;
- moneda;
- comisión;
- estado;
- fuente;
- referencia;
- notas.

Filtros por fecha, cuenta, tipo, estado, activo, fuente y ambiente.

## Cuentas

Mostrar:
- saldo;
- disponible;
- pendiente;
- reservado;
- en tránsito;
- última conciliación;
- movimientos recientes.

## Inversiones

Separadas de gastos. Mostrar:
- capital comprometido;
- capital recuperado;
- beneficio/pérdida realizada;
- estado;
- fecha;
- riesgo;
- estrategia;
- autorización;
- salida.

## Autorizaciones

Cada autorización debe mostrar:
- acción propuesta;
- capital;
- cuenta origen;
- efecto sobre disponible;
- % del patrimonio;
- riesgos;
- motivo;
- vencimiento.

Acciones:
- Aprobar
- Rechazar
- Revisar

## Ajustes

- Perfil
- Seguridad
- Tema
- Moneda base
- Límites de autorización
- Cuentas
- Integraciones
- Notificaciones
- Backups
- Sistema
- Acerca de

## Tema

Desde primera UI seria:
- Claro
- Oscuro
- Sistema opcional

Luego:
- color de acento;
- logo/avatar;
- densidad;
- widgets.

## Errores

Nunca dejar botones sin respuesta. Toda acción produce:
- éxito visible;
- error visible;
- loading;
- prevención de doble envío.

Los errores técnicos van a logs; el usuario recibe mensajes entendibles.
