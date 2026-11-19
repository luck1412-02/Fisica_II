# Publicar Physics AI en Render

Esta es una aplicación FastAPI (Python), no un sitio estático. Render necesita acceso a un repositorio Git que contenga el código: el ZIP por sí solo no despliega.

1. Sube el contenido de esta carpeta a un repositorio privado en GitHub (no subas el archivo `.env`).
2. En Render, crea un servicio Web con ese repositorio, o un Blueprint que use `render.yaml`.
3. Configuración: Python, build `pip install -r requirements.txt`; start `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
4. En Render > Environment, configura `OPENAI_API_KEY` como secreto y `OPENAI_MODEL=gpt-4.1-mini`. No coloques esta clave en JavaScript, chats ni archivos subidos a GitHub.
5. Comprueba `/api/status` y realiza una pregunta de física con una imagen de prueba.

AVISO: esta es una MVP sin cuentas ni separación de sesiones. Todas las conversaciones quedan expuestas a cualquier usuario del enlace. Para una demostración utiliza solo datos y ejercicios públicos, no documentos personales ni información confidencial. En hosting gratuito, SQLite puede perder los datos al reiniciar o redeplegar el servicio. El plan gratuito puede entrar en reposo y tardar en responder. La API de OpenAI se factura por separado.
