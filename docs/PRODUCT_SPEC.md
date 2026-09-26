# JD Capital — Product Specification

## Propósito

JD Capital es un **agente personal de crecimiento patrimonial** con un centro de control financiero simple.

Su misión es:
- investigar de forma continua fuentes legítimas de ingresos e inversión;
- detectar oportunidades aunque produzcan importes pequeños;
- verificar requisitos, riesgos, costos, disponibilidad y forma de cobro;
- ejecutar automáticamente sólo aquello que sea técnicamente permitido y esté autorizado por las políticas del usuario;
- pedir intervención humana cuando sea necesaria;
- seguir trabajando en otras oportunidades mientras una tarea espera;
- medir resultados reales;
- repetir estrategias que sigan siendo rentables;
- abandonar, pausar o reemplazar las que dejen de serlo;
- acumular y reinvertir capital de forma progresiva;
- mantener trazabilidad completa del patrimonio.

El panel no es el producto principal. El producto principal es el **motor de crecimiento**. El panel es su centro de observación, control, autorización y configuración.

## Principio central

JD Capital debe poder responder siempre:
- cuánto patrimonio existe;
- dónde está;
- de dónde provino;
- qué parte está disponible, pendiente, invertida, reservada, bloqueada o en tránsito;
- qué estrategia produjo cada resultado;
- cuánto costó producirlo;
- qué oportunidades están activas;
- qué acciones requieren autorización;
- qué estrategias conviene seguir evaluando según evidencia real.

## Modelo operativo

`descubrir → verificar → analizar → priorizar → ejecutar/solicitar acción → medir → repetir o abandonar → reinvertir → continuar`

El ciclo no termina después de una sola oportunidad. El agente puede mantener varias actividades en paralelo. Una oportunidad esperando aprobación o pago no debe detener la investigación ni otras ejecuciones.

## Fase inicial

- capital inicial real: USD 0;
- costo operativo adicional: USD 0;
- sin API paga obligatoria;
- sin claves pagas obligatorias;
- infraestructura local;
- fuentes públicas, APIs gratuitas permitidas, RSS, feeds y conectores compatibles con términos de uso;
- investigación y gestión dentro de JD Capital siempre que sea técnicamente posible.

“Buscar en Internet” significa **cobertura web amplia y extensible mediante múltiples conectores**, no una promesa de indexar literalmente toda Internet sin infraestructura externa.

Cuando JD Capital genere ingresos reales, podrá destinar parte de ellos a APIs, infraestructura y servicios que aumenten cobertura, velocidad y automatización.

## Autonomía

Autonomía significa que JD Capital:
- investiga continuamente;
- mantiene una cola de trabajos;
- prioriza oportunidades;
- ejecuta varias tareas compatibles en paralelo;
- reintenta fallos transitorios;
- conserva estados y resultados;
- repite estrategias rentables;
- reasigna tiempo/capital;
- no se bloquea porque una tarea necesite acción humana.

Autonomía no significa:
- evadir CAPTCHA;
- crear identidades falsas;
- falsificar ubicación;
- automatizar donde los términos lo prohíben;
- saltar KYC;
- aceptar contratos sin autorización;
- mover o invertir dinero fuera de políticas explícitas.

Cuando una acción externa sea obligatoria, JD Capital crea una tarea precisa para el usuario y continúa con otras actividades.

## Política de capital

Debe admitir oportunidades sin inversión y con importes pequeños o mayores cuando exista capital.

El motor de autorización será configurable por:
- monto absoluto;
- porcentaje del patrimonio disponible;
- tipo de oportunidad;
- nivel de riesgo;
- plataforma;
- límite diario;
- límite mensual.

La configuración inicial debe ser conservadora: ninguna operación monetaria automática se habilita por accidente.

## Acumulación y reinversión

Los importes pequeños no se descartan sólo por su tamaño. Deben medirse por:
- valor producido;
- tiempo requerido;
- capital requerido;
- comisiones;
- probabilidad empírica de cobro;
- repetibilidad;
- escalabilidad;
- rendimiento real.

Una estrategia pequeña pero repetible puede seguir activa mientras cumpla las políticas de rentabilidad, riesgo y tiempo.

## Límites del producto

JD Capital:
- no es banco;
- no custodia fondos;
- no recibe depósitos de terceros;
- no emite tarjetas;
- no procesa pagos por QR;
- no reemplaza PayPal, Mercado Pago, bancos, brokers o exchanges.

Las cuentas externas se representan contablemente. Las integraciones reales futuras deberán usar APIs oficiales y permisos válidos.

## Estados del dinero

Distinguir como mínimo:
- potencial;
- generado;
- pendiente de aprobación;
- pendiente de liquidación;
- disponible;
- reservado;
- en tránsito;
- invertido;
- bloqueado;
- liquidado;
- retirado;
- cancelado;
- perdido;
- pendiente de conciliación.

“Generado” no equivale automáticamente a “disponible” ni a “bancarizado”.

## Unidades internas de plataformas

Debe soportar unidades que no sean fiat.

Ejemplo:
`1.000 créditos de plataforma → liquidación → USD 50 → PayPal`

Conservar:
- unidad original;
- cantidad original;
- tasa de conversión;
- fecha;
- monto final;
- comisiones;
- cuenta destino.

## Fiscalidad y documentación

Guardar información suficiente para distinguir:
- fecha de generación;
- liquidación;
- retiro;
- ingreso a billetera;
- bancarización;
- origen;
- país;
- moneda;
- comprobantes;
- estado de facturación;
- retenciones/comisiones.

No codificar reglas fiscales supuestas. Se configurarán sólo con información normativa/profesional verificada.

## Modos REAL y PRUEBA

Dos contextos estrictamente separados:
- **REAL**
- **PRUEBA**

Nunca mezclar saldos ficticios con patrimonio real.

## Módulos funcionales

- Centro de control
- Patrimonio
- Cuentas
- Movimientos / ledger
- Fuentes de ingreso
- Oportunidades
- Estrategias
- Inversiones
- Investigación
- Autorizaciones
- Reportes
- Ajustes

## Éxito del producto

JD Capital se evalúa por:
- oportunidades detectadas;
- acciones ejecutadas;
- ingresos generados;
- capital acumulado;
- capital reinvertido;
- rentabilidad real;
- costos;
- estrategias descartadas;
- tiempo ahorrado;
- crecimiento patrimonial neto.

La interfaz debe ser sencilla; la complejidad vive en el dominio financiero, el orquestador, las reglas, la investigación, la evidencia, la automatización y la auditoría.
