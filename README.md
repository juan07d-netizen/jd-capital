# JD Capital Cloud

Versión cloud-first de JD Capital: el panel y el motor de agentes viven en la nube,
por lo que tu PC puede estar apagada. El teléfono entra al panel mediante una URL HTTPS.

Arquitectura:
Web/PWA -> FastAPI -> Agents SDK + WebSearchTool -> PostgreSQL

Incluye:
- Director, Scout, Researcher, CFO, Validator y Portfolio Manager.
- Búsqueda web.
- PostgreSQL en producción y SQLite local.
- Autenticación por usuario/contraseña vía variables de entorno.
- PWA para instalar desde el celular.
- Scheduler opcional.
- Gasto automático = 0 por defecto.
- No incluye transferencias, deuda ni trading.

Despliegue recomendado: Render. Render soporta FastAPI, Docker, PostgreSQL y
servicios web; puede inyectar secretos como variables de entorno. Para una ejecución
continua del scheduler, usar un plan que mantenga la instancia activa. El sistema
puede empezar en modo manual y luego activar el scheduler.

Variables:
OPENAI_API_KEY
OPENAI_MODEL=gpt-5.6-luna
JD_ADMIN_USER
JD_ADMIN_PASSWORD
JD_SESSION_SECRET
DATABASE_URL
JD_SCHEDULER_ENABLED=false
JD_MISSION_INTERVAL_MINUTES=360
JD_AUTO_SPEND_USD=0

Primera misión:
Encontrar y verificar oportunidades actuales para conseguir el primer USD con capital
inicial cero, priorizando Argentina. Incluir microtareas, pruebas de productos,
afiliación, leads, productos digitales, automatización con IA, micro-SaaS, e-commerce,
agent economy y nuevas categorías. Verificar reglas, cobros y demanda.

Nunca pongas API keys, contraseñas bancarias o semillas de wallet en el repositorio.
