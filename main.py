"""Physics AI: runnable physics tutor MVP. Start with uvicorn app.main:app --reload."""
import base64
import json
import math
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import sympy as sp
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

load_dotenv()
ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / 'app' / 'static'
DB = Path(os.getenv('PHYSICS_DB_PATH', str(ROOT / 'physics_ai.db')))
MODEL = os.getenv('OPENAI_MODEL', 'gpt-4.1-mini')
MAX_IMAGE_BYTES = 8 * 1024 * 1024

app = FastAPI(title='Physics AI', version='0.1.0', description='Tutor de física multimodal')

@contextmanager
def db():
    DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with db() as conn:
        conn.executescript('''
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY, title TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('user','assistant')),
            content TEXT NOT NULL, image_data TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(conversation_id) REFERENCES conversations(id)
        );
        CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id, created_at);
        ''')

init_db()

SYSTEM = '''Eres Physics AI, tutor universitario experto EXCLUSIVAMENTE en Física. Responde en español.
Ayuda en mecánica, termodinámica, ondas, óptica, electricidad, magnetismo y matemáticas aplicadas a Física.
Si la solicitud es ajena a Física, explica cortésmente tu especialización.
En modo resolver: 1) datos y unidades; 2) incógnitas; 3) hipótesis y diagrama descrito;
4) leyes físicas justificadas; 5) ejes y signos; 6) desarrollo algebraico; 7) sustitución numérica
sin redondear prematuramente; 8) resultado con unidades; 9) interpretación y comprobación dimensional.
Para dinámica, usa sumatoria de fuerzas por cada eje y g=9.8 m/s² salvo indicación contraria.
Si falta un dato, pregunta o señala una hipótesis explícita; no inventes información.
Si hay imagen, analiza su contenido sin fingir que se ve algo ilegible.
Usa LaTeX con $...$ y $$...$$ para las ecuaciones.
No afirmes haber verificado con SymPy algo que no has comprobado con una herramienta.
En modo aprender, enseña los fundamentos con ejemplos. En practicar, da pistas sin revelar la respuesta al inicio.
En examen, pregunta y evalúa sin mostrar soluciones hasta recibir respuesta. En aprender_a_resolver,
plantea una pregunta por turno y evalúa el razonamiento antes de avanzar.
Indica cuándo una respuesta está basada en supuestos o requiere revisión.
'''

class ChatRequest(BaseModel):
    conversation_id: Optional[str] = None
    message: str = Field(min_length=1, max_length=16000)
    mode: str = 'resolver'
    image_base64: Optional[str] = None
    image_mime: Optional[str] = None

class VerifyRequest(BaseModel):
    expression: str = Field(min_length=1, max_length=250)
    variable: Optional[str] = None


def stamp():
    return datetime.now(timezone.utc).isoformat()

@app.get('/')
def index():
    return FileResponse(STATIC / 'index.html')

@app.get('/api/status')
def status():
    return {'ready': bool(os.getenv('OPENAI_API_KEY')), 'model': MODEL, 'version': '0.1.0'}

@app.get('/api/conversations')
def conversations():
    with db() as conn:
        rows = conn.execute('SELECT id, title, created_at FROM conversations ORDER BY created_at DESC').fetchall()
    return [dict(r) for r in rows]

@app.get('/api/conversations/{cid}')
def conversation(cid: str):
    with db() as conn:
        exists = conn.execute('SELECT 1 FROM conversations WHERE id=?', (cid,)).fetchone()
        if not exists:
            raise HTTPException(404, 'Conversación no encontrada')
        rows = conn.execute('SELECT role, content, created_at, (image_data IS NOT NULL) AS has_image FROM messages WHERE conversation_id=? ORDER BY created_at, rowid', (cid,)).fetchall()
    return [dict(r) for r in rows]

@app.delete('/api/conversations/{cid}')
def delete_conversation(cid: str):
    with db() as conn:
        conn.execute('DELETE FROM messages WHERE conversation_id=?', (cid,))
        conn.execute('DELETE FROM conversations WHERE id=?', (cid,))
    return {'ok': True}

@app.post('/api/images')
async def upload_image(file: UploadFile = File(...)):
    if file.content_type not in ('image/png', 'image/jpeg', 'image/webp'):
        raise HTTPException(415, 'Solo PNG, JPEG y WebP')
    data = await file.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(413, 'Imagen demasiado grande (máximo 8 MB)')
    if not data:
        raise HTTPException(400, 'Imagen vacía')
    return {'base64': base64.b64encode(data).decode('ascii'), 'mime': file.content_type}

@app.post('/api/chat')
async def chat(req: ChatRequest):
    key = os.getenv('OPENAI_API_KEY')
    if not key or key == 'replace_with_your_api_key':
        raise HTTPException(503, 'Configura OPENAI_API_KEY en .env para activar el tutor.')
    if req.mode not in ('resolver','aprender','practicar','examen','aprender_a_resolver'):
        raise HTTPException(400, 'Modo no válido')
    if req.image_base64:
        if req.image_mime not in ('image/png','image/jpeg','image/webp'):
            raise HTTPException(415, 'Formato de imagen no admitido')
        try:
            raw = base64.b64decode(req.image_base64, validate=True)
        except Exception:
            raise HTTPException(400, 'Imagen base64 inválida')
        if len(raw) > MAX_IMAGE_BYTES:
            raise HTTPException(413, 'Imagen demasiado grande')
    cid = req.conversation_id or str(uuid.uuid4())
    with db() as conn:
        if req.conversation_id and not conn.execute('SELECT 1 FROM conversations WHERE id=?', (cid,)).fetchone():
            raise HTTPException(404, 'Conversación no encontrada')
        history = conn.execute('SELECT role, content, image_data FROM messages WHERE conversation_id=? ORDER BY created_at, rowid LIMIT 30', (cid,)).fetchall()
    messages = [{'role':'system', 'content': SYSTEM + '\nModo actual: ' + req.mode}]
    for row in history:
        # Historical images are deliberately not replayed to limit token costs; their text remains in context.
        messages.append({'role': row['role'], 'content': row['content']})
    user_content = [{'type':'text', 'text':req.message}]
    if req.image_base64:
        user_content.append({'type':'image_url', 'image_url': {'url':f'data:{req.image_mime};base64,{req.image_base64}', 'detail':'auto'}})
    messages.append({'role':'user','content':user_content})
    try:
        result = await AsyncOpenAI(api_key=key, timeout=75).chat.completions.create(
            model=MODEL, messages=messages, temperature=0.2, max_tokens=2500
        )
        answer = result.choices[0].message.content or 'No se obtuvo respuesta. Intenta de nuevo.'
    except Exception as exc:
        # Do not expose API secrets or provider exception internals to the browser.
        raise HTTPException(502, 'No se pudo contactar el modelo. Revisa la clave, el modelo, la cuota y la conexión.') from exc
    with db() as conn:
        if not req.conversation_id:
            conn.execute('INSERT INTO conversations VALUES (?,?,?)', (cid, req.message[:65], stamp()))
        conn.execute('INSERT INTO messages VALUES (?,?,?,?,?,?)', (str(uuid.uuid4()), cid, 'user', req.message, 'attached' if req.image_base64 else None, stamp()))
        conn.execute('INSERT INTO messages VALUES (?,?,?,?,?,?)', (str(uuid.uuid4()), cid, 'assistant', answer, None, stamp()))
    return {'conversation_id':cid, 'answer':answer, 'verification':'Generado por IA; no verificado automáticamente'}

# Whitelist SymPy symbols and operators; never eval arbitrary Python.
SYMBOLS = {s: sp.Symbol(s, real=True) for s in ['x','y','t','v','a','m','F','g','theta','r','I','V','R','Q','T']}
SYMBOLS.update({'pi':sp.pi, 'sin':sp.sin, 'cos':sp.cos, 'tan':sp.tan, 'sqrt':sp.sqrt})
@app.post('/api/verify')
def verify(req: VerifyRequest):
    import re
    from sympy.parsing.sympy_parser import parse_expr, standard_transformations, implicit_multiplication_application, convert_xor
    if not re.fullmatch(r'[0-9a-zA-Z_+*/^().,=\s-]+', req.expression):
        raise HTTPException(400, 'Expresión no admitida')
    identifiers = re.findall(r'[A-Za-z_][A-Za-z_0-9]*', req.expression)
    if any(identifier not in SYMBOLS for identifier in identifiers):
        raise HTTPException(400, 'Identificador no permitido')
    if re.search(r'(?<![0-9])\.|\.(?![0-9])', req.expression):
        raise HTTPException(400, 'Solo puntos decimales permitidos')
    if '__' in req.expression or len(req.expression) > 250:
        raise HTTPException(400, 'Expresión no admitida')
    try:
        transforms = standard_transformations + (implicit_multiplication_application, convert_xor)
        if '=' in req.expression:
            left, right = req.expression.split('=', 1)
            lhs = parse_expr(left, local_dict=SYMBOLS, global_dict={'__builtins__': {}}, transformations=transforms)
            rhs = parse_expr(right, local_dict=SYMBOLS, global_dict={'__builtins__': {}}, transformations=transforms)
            simplified = sp.simplify(lhs-rhs)
            if req.variable:
                if req.variable not in SYMBOLS or not isinstance(SYMBOLS[req.variable], sp.Symbol):
                    raise ValueError('Variable no admitida')
                solutions = sp.solve(sp.Eq(lhs, rhs), SYMBOLS[req.variable])
                return {'latex':sp.latex(sp.Eq(lhs,rhs)), 'solutions':[sp.latex(s) for s in solutions], 'difference':sp.latex(simplified)}
            return {'latex':sp.latex(sp.Eq(lhs,rhs)), 'difference':sp.latex(simplified), 'equivalent':simplified==0}
        parsed = parse_expr(req.expression, local_dict=SYMBOLS, global_dict={'__builtins__': {}}, transformations=transforms)
        simplified = sp.simplify(parsed)
        return {'latex':sp.latex(simplified), 'numeric':str(sp.N(simplified, 12))}
    except Exception:
        raise HTTPException(400, 'No se pudo interpretar la expresión. Usa símbolos y funciones permitidas.')

FORMULAS = [
    {'topic':'Cinemática','name':'Velocidad en MRUA','latex':'v_f=v_0+at','description':'Aceleración constante.'},
    {'topic':'Cinemática','name':'Posición en MRUA','latex':'x=x_0+v_0t+\\frac12at^2','description':'Movimiento rectilíneo con aceleración constante.'},
    {'topic':'Dinámica','name':'Segunda ley de Newton','latex':'\\sum \\vec F=m\\vec a','description':'Fuerza neta y aceleración.'},
    {'topic':'Energía','name':'Energía cinética','latex':'E_c=\\frac12mv^2','description':'Energía del movimiento.'},
    {'topic':'Termodinámica','name':'Calor sensible','latex':'Q=mc\\Delta T','description':'Sin cambio de fase.'},
    {'topic':'Electricidad','name':'Ley de Ohm','latex':'V=IR','description':'Conductor óhmico.'},
    {'topic':'Magnetismo','name':'Fuerza magnética','latex':'F=|q|vB\\sin\\theta','description':'Magnitud de la fuerza sobre una carga móvil.'},
]
@app.get('/api/formulas')
def formulas():
    return FORMULAS

class ProjectileRequest(BaseModel):
    speed: float = Field(ge=0, le=1000)
    angle: float = Field(ge=-89, le=89)
    height: float = Field(ge=0, le=10000, default=0)
    gravity: float = Field(gt=0, le=100, default=9.8)

@app.post('/api/projectile')
def projectile(p: ProjectileRequest):
    angle = math.radians(p.angle)
    vx = p.speed * math.cos(angle)
    vy = p.speed * math.sin(angle)
    duration = (vy + math.sqrt(vy*vy + 2*p.gravity*p.height))/p.gravity
    points = [{'x':vx*i*duration/100, 'y':max(0, p.height + vy*i*duration/100 - 0.5*p.gravity*(i*duration/100)**2)} for i in range(101)]
    peak_time = max(0, vy/p.gravity)
    return {'flight_time':duration, 'range':vx*duration, 'max_height':p.height+vy*peak_time-0.5*p.gravity*peak_time**2, 'vx':vx, 'vy':vy, 'points':points, 'assumptions':'Sin resistencia del aire; gravedad constante; suelo horizontal.'}
