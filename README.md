# Physics AI — MVP funcional

Tutor de Física con chat multimodal real, carga de fotografías, historial local, formulario y simulador de tiro parabólico. **No es la plataforma completa de las cinco fases**: es una primera versión ejecutable.

## Requisitos
- Python 3.10 o superior
- Clave API válida de OpenAI con facturación/cuota habilitada
- Internet para la API y para cargar las librerías de renderizado matemático del navegador

## Instalación

```bash
cd physics-ai
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Windows: copy .env.example .env
# Edita .env y coloca tu OPENAI_API_KEY real
uvicorn app.main:app --reload
```

Abre **http://127.0.0.1:8000** en tu navegador. La clave se mantiene en el servidor y no se envía al frontend.

## Qué funciona
- Chat de Física en cinco modos, usando un modelo real configurable por `OPENAI_MODEL`.
- Envío de fotografías PNG/JPEG/WebP (hasta 8 MB) al modelo multimodal.
- Historial de conversaciones en SQLite, recuperable tras reiniciar el servidor.
- Fórmulas con representación matemática.
- Simulación de trayectoria de proyectiles con parámetros configurables.
- API auxiliar `/api/verify` para expresiones matemáticas simples y `/docs` para explorar endpoints.

## Límites actuales (importante)
- Sin registro de usuarios: es **monousuario y solo para desarrollo local**. No lo publiques en Internet sin autenticación, controles de acceso, límites de solicitudes y seguridad adicionales.
- Las respuestas del chat **no se verifican automáticamente con SymPy**; `/api/verify` es una herramienta independiente y limitada. No se debe interpretar la etiqueta de IA como validación científica.
- Solo se admiten **imágenes**, no PDF, DOCX ni PPTX en esta versión.
- No hay todavía evaluación diagnóstica, adaptación por desempeño, seguimiento por tema, voz, exportación ni diagramas vectoriales automáticos.
- El historial reenvía texto, pero no vuelve a enviar imágenes anteriores. La API multimodal puede generar errores: verifica resultados importantes.
- Se guarda el texto de las conversaciones localmente; las imágenes no se almacenan, solo se marca que hubo adjunto.
- El navegador utiliza CDN para Marked, DOMPurify y MathJax.

## Costos
La aplicación es código local; **cada solicitud al modelo puede generar cargos** según el modelo y el volumen de tokens e imágenes. Revisa precios y cuotas de tu proveedor antes de usarla. La API de OpenAI es independiente de una suscripción ChatGPT.

## Siguientes fases
1. Autenticación y PostgreSQL, migraciones y perfiles.
2. Extracción de PDF/Word/PPT y referencias a páginas.
3. Orquestación real de verificadores matemáticos, dimensionales y de diagramas.
4. Diagnóstico, ejercicios, puntuaciones y progreso adaptativo.
5. Exportación, simuladores adicionales, pruebas científicas y despliegue seguro.
