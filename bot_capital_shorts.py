import asyncio
from datetime import datetime
import json
import json5
import os
import random
import re
import sys
import time
import base64
import requests
import edge_tts
from zoneinfo import ZoneInfo
from PIL import Image, ImageDraw, ImageFont, ImageOps
from moviepy.editor import (
    AudioFileClip,
    CompositeAudioClip,
    ImageClip,
    concatenate_audioclips,
    concatenate_videoclips,
    AudioClip,
)
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# ================================================================
# CONFIGURACIÓN
# ================================================================
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
YOUTUBE_USER_TOKEN = (
    json.loads(os.getenv("YOUTUBE_USER_TOKEN_CAPITAL"))
    if os.getenv("YOUTUBE_USER_TOKEN_CAPITAL")
    else {}
)
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")
CF_ACCOUNT_ID = os.getenv("CF_ACCOUNT_ID")
CF_API_TOKEN = os.getenv("CF_API_TOKEN")

CANAL_LINK = "https://www.youtube.com/@CapitalMinds"
ESTADO_FILE = "estado_capital_shorts_es.json"
TITULOS_FILE = "titulos_capital_shorts_es_publicados.json"
TEMAS_PUBLICADOS_FILE = "temas_shorts_es_publicados.json"
TRENDS_FILE = "trends_semanal_es.json"

META_DIARIA_SHORTS = 2
DIAS_SIN_REPETIR_TEMA = 30

# 🚫 PALABRAS PROHIBIDAS (ANTI-FED)
PALABRAS_ANTI_FED = [
    "fed", "fomc", "powell", "tasa de interés", "decisión de tasas",
    "reserva federal", "política monetaria", "jerome powell"
]

_used_image_urls = set()

# ================================================================
# 🎙️ VOZ FIJA (ESPAÑOL)
# ================================================================
VOZ_FIJA = {
    "voz": "es-ES-ElviraNeural",
    "velocidad": "+12%",
    "tono": "+2Hz",
    "volumen": "+10%"
}
CONFIG_VOZ_ACTUAL = VOZ_FIJA

# ================================================================
# 🎨 PALETAS Y SUJETOS VISUALES
# ================================================================
PALETAS_VIDEO = [
    "cian eléctrico y oro neón sobre azul marino oscuro",
    "verde esmeralda y plata sobre negro",
    "magenta violeta y naranja sobre azul profundo",
    "rojo carmesí y oro sobre carbón",
    "verde azulado y ámbar sobre pizarra oscura",
    "azul hielo y blanco sobre negro medianoche",
]

SUJETOS_VISUALES = [
    (["bitcoin", "btc", "crypto", "criptomoneda", "halving"], "una moneda dorada gigante de bitcoin con detalles intrincados"),
    (["oro", "gold", "plata", "metal", "precioso"], "lingotes de oro brillantes apilados dentro de una bóveda bancaria"),
    (["fed", "reserve", "rate", "interest", "reserva federal"], "un edificio monumental de banco central con columnas"),
    (["inflation", "cpi", "price", "inflacion"], "un carrito de compras lleno de groceries sobre un gráfico ascendente"),
    (["etf", "fund", "institutional"], "un edificio moderno de bolsa de valores con tickers digitales"),
    (["stock", "market", "trading", "trader"], "gráficos de velas en múltiples pantallas brillantes"),
    (["scam", "fraud", "hack", "ftx", "collapse", "crash", "ponzi"], "fichas de dominó cayendo hechas de monedas"),
    (["regulation", "law", "sec", "mica", "legal"], "un mazo de madera sobre documentos legales"),
    (["ethereum", "solana", "blockchain", "technology", "rollup"], "una red brillante de nodos blockchain interconectados"),
    (["dollar", "forex", "currency"], "billetes de dólar flotando y símbolos de moneda"),
    (["psychology", "fear", "greed", "panic"], "una silueta de cabeza humana con gráficos ascendentes y descendentes"),
    (["war", "geopolitic", "china", "russia"], "un mapa mundial con rutas comerciales brillantes"),
    (["history", "historical", "past"], "documentos financieros vintage y gráficos con textura de papel envejecido"),
    (["education", "learn", "tutorial", "guide", "explained"], "infografía educativa con gráficos limpios"),
]

def detectar_sujeto_visual(texto_ref):
    t = (texto_ref or "").lower()
    for keywords, sujeto in SUJETOS_VISUALES:
        if any(k in t for k in keywords):
            return sujeto
    return "una escena financiera cinematográfica con gráficos brillantes, monedas y visualización de datos"

# ================================================================
# 🚫 VERIFICAR SI HAY CONTENIDO RECIENTE DE FED
# ================================================================
def verificar_fed_reciente(dias=20):
    temas = cargar_temas_publicados()
    hoy = datetime.now(ZoneInfo("America/Mexico_City")).date()
    
    for t in temas:
        try:
            fecha_tema = datetime.strptime(t["fecha"], "%Y-%m-%d").date()
            if (hoy - fecha_tema).days <= dias:
                tema_lower = t["tema"].lower()
                if any(p in tema_lower for p in PALABRAS_ANTI_FED):
                    return True
        except:
            continue
    return False

def tema_contiene_fed(titulo):
    t = (titulo or "").lower()
    return any(p in t for p in PALABRAS_ANTI_FED)

# ================================================================
# 📚 CATEGORÍAS DE CONTENIDO
# ================================================================
CATEGORIAS_SHORTS = {
    "educational": {
        "peso": 35,
        "temas": [
            "Cómo Funciona la Minería de Bitcoin",
            "Entendiendo Blockchain en 60 Segundos",
            "Bitcoin vs Oro: Comparación Rápida",
            "Cómo Leer Gráficos de Crypto",
            "Qué es Dollar Cost Averaging",
            "Diversificación de Portafolio Explicada",
            "Qué es una Billetera Crypto",
            "Staking vs Yield Farming",
            "Cómo Funcionan los Smart Contracts",
            "Préstamos DeFi Explicados Simplemente",
            "Qué son las Stablecoins",
            "Layer 1 vs Layer 2 Explicado",
            "Cómo Funcionan los Mecanismos de Consenso",
            "Diferencias Bitcoin vs Ethereum",
            "Qué es el Market Cap",
            "Entendiendo la Volatilidad Crypto",
            "Cómo Detectar un Scam Crypto",
            "Qué es una Hardware Wallet"
        ]
    },
    "historical": {
        "peso": 25,
        "temas": [
            "El Bull Run de Bitcoin 2017",
            "La Crisis 2008 y el Nacimiento de Bitcoin",
            "Hack de Mt Gox Explicado",
            "Historia del Día de la Pizza Bitcoin",
            "La Fiebre de los Tulipanes: Primera Burbuja",
            "El Crash Crypto 2021",
            "Colapso de FTX: Qué Pasó",
            "Colapso de Terra Luna",
            "Historia de Silk Road",
            "Cómo Desapareció Satoshi",
            "La Primera Transacción de Bitcoin",
            "Historia Crypto de Venezuela",
            "Crisis de Chipre y Bitcoin",
            "El Bear Market 2022",
            "Caídas Históricas del Oro"
        ]
    },
    "psychology": {
        "peso": 20,
        "temas": [
            "Por Qué 90% de Traders Pierden",
            "Psicología del Panic Selling",
            "Por Qué el FOMO Te Cuesta Dinero",
            "Aversión a la Pérdida Explicada",
            "El Ciclo del Miedo y la Codicia",
            "Por Qué los Inversores Compran Alto y Venden Bajo",
            "Sesgo de Exceso de Confianza en Trading",
            "Comportamiento de Rebaño en Mercados",
            "Psicología de los Mercados Alcistas",
            "Cómo las Emociones Afectan la Inversión",
            "Sesgos Cognitivos en Crypto",
            "Por Qué la Paciencia Gana en Inversión"
        ]
    },
    "analysis": {
        "peso": 15,
        "temas": [
            "Ciclos de Halving de Bitcoin Explicados",
            "Patrones del Precio del Oro",
            "Análisis de Dominancia de Bitcoin",
            "Tendencias de Adopción Institucional",
            "Patrones de Volatilidad Crypto",
            "Indicadores de Sentimiento del Mercado",
            "Análisis On-Chain Básico",
            "Actividad de Ballenas Explicada",
            "El Ratio MVRV Explicado",
            "Análisis del Hash Rate de Minería"
        ]
    },
    "news": {
        "peso": 5,
        "temas": [
            "Actualización Regulación Crypto",
            "Análisis Flujo Bitcoin ETF",
            "Adopción Institucional Crypto"
        ]
    }
}

def seleccionar_categoria_shorts():
    fed_prohibida = verificar_fed_reciente(dias=20)
    
    temas_pub = cargar_temas_publicados()
    hoy = datetime.now(ZoneInfo("America/Mexico_City")).date()
    
    temas_recientes = set()
    for t in temas_pub:
        try:
            fecha_tema = datetime.strptime(t["fecha"], "%Y-%m-%d").date()
            if (hoy - fecha_tema).days <= 15:
                temas_recientes.add(t["tema"].lower().strip())
        except:
            continue
    
    for _ in range(15):
        total_peso = sum(cat["peso"] for cat in CATEGORIAS_SHORTS.values())
        numero_aleatorio = random.uniform(0, total_peso)
        
        peso_acumulado = 0
        for categoria, datos in CATEGORIAS_SHORTS.items():
            peso_acumulado += datos["peso"]
            if numero_aleatorio <= peso_acumulado:
                if fed_prohibida and categoria == "news":
                    continue
                
                temas_disponibles = [t for t in datos["temas"] if t.lower() not in temas_recientes]
                
                if fed_prohibida:
                    temas_disponibles = [t for t in temas_disponibles if not tema_contiene_fed(t)]
                
                if temas_disponibles:
                    return categoria, random.choice(temas_disponibles)
                else:
                    return categoria, random.choice(datos["temas"])
    
    return "educational", random.choice(CATEGORIAS_SHORTS["educational"]["temas"])

# ================================================================
# 🎨 GENERAR IMAGEN CON CLOUDFLARE AI
# ================================================================
def generar_imagen_cloudflare(prompt, salida_path="temp_cf_image.jpg"):
    if not CF_ACCOUNT_ID or not CF_API_TOKEN:
        return None
    
    url = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/ai/run/@cf/black-forest-labs/flux-1-schnell"
    headers = {"Authorization": f"Bearer {CF_API_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "prompt": prompt + ", ultra high quality, 8k resolution, cinematic lighting, highly detailed, professional, no text, no watermark",
        "steps": 4
    }
    
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=60)
        if r.status_code == 429:
            print("⚠️ Cloudflare API rate limit (429). Usando Pexels como respaldo.")
            return None
        r.raise_for_status()
        data = r.json()
        
        if data.get("success") and "result" in data and "image" in data["result"]:
            with open(salida_path, "wb") as f:
                f.write(base64.b64decode(data["result"]["image"]))
            return salida_path
        else:
            return None
    except Exception as e:
        print(f"⚠️ Error Cloudflare AI: {e}")
        return None

# ================================================================
# 🖼️ GENERAR IMAGEN VERTICAL (PEXELS - RESPALDO)
# ================================================================
def generar_imagen_vertical(prompt, tema="", bloque="", intentos=10):
    global _used_image_urls
    
    keyword_map = {
        "HOOK": "alerta roja crisis financiera urgente",
        "PROBLEM": "gráficos cayendo pánico",
        "DATA": "datos financieros gráficos brillantes",
        "SOLUTION": "tendencia ascendente éxito",
        "CLOSE": "finanzas profesionales sutil",
        "bitcoin": "bitcoin criptomoneda",
        "oro": "lingotes oro lujo",
        "crypto": "criptomoneda blockchain",
        "trading": "gráficos trading",
        "mining": "equipos minería tecnología",
        "wallet": "billetera crypto tecnología",
        "history": "documentos financieros vintage",
        "psychology": "cerebro humano psicología",
    }
    
    base_query = "finanzas negocios"
    prompt_lower = prompt.lower()
    
    if bloque and bloque in keyword_map:
        base_query = keyword_map[bloque]
    else:
        for key, value in keyword_map.items():
            if key in prompt_lower:
                base_query = value
                break

    modifiers = [
        "fondo abstracto oscuro", "luces neón brillantes", "cinematográfico dramático",
        "macro close up", "minimalista limpio", "colores vibrantes",
        "tecnología futurista", "atmosférico melancólico"
    ]
    
    for intento in range(intentos):
        current_query = f"{base_query} {random.choice(modifiers)}"
        random_page = random.randint(1, 10)
        
        url = f"https://api.pexels.com/v1/search?query={current_query.replace(' ', '+')}&per_page=10&orientation=portrait&page={random_page}"
        headers = {"Authorization": PEXELS_API_KEY}
        
        try:
            r = requests.get(url, headers=headers, timeout=30)
            
            if r.status_code == 200:
                data = r.json()
                if data.get("photos") and len(data["photos"]) > 0:
                    for photo in data["photos"]:
                        img_url = photo["src"].get("portrait") or photo["src"].get("original")
                        
                        if img_url in _used_image_urls:
                            continue
                        if not img_url or not img_url.startswith("http"):
                            continue
                        
                        _used_image_urls.add(img_url)
                        return img_url
        except Exception as e:
            print(f"      ️ Error: {e}")
        
        if intento < intentos - 1:
            time.sleep(10)
    
    return None

# ================================================================
# GENERAR IMAGEN POR SEGMENTO (CLOUDFLARE → PEXELS)
# ================================================================
def generar_imagen_segmento(prompt, tema="", bloque=""):
    global _used_image_urls
    
    # Intentar Cloudflare AI primero (5 intentos)
    for intento in range(5):
        cf_path = f"temp_cf_seg_{intento}.jpg"
        img_path = generar_imagen_cloudflare(prompt, cf_path)
        
        if img_path and os.path.exists(img_path):
            print(f"   ✅ Cloudflare AI generó imagen (intento {intento+1})")
            _used_image_urls.add(f"cf_{intento}")
            return img_path
        
        print(f"   🔄 Cloudflare intento {intento+1}/5, reintentando...")
        time.sleep(2)
    
    # Si Cloudflare falla, usar Pexels
    print("   ⚠️ Cloudflare falló 5 veces, usando Pexels...")
    img_url = generar_imagen_vertical(prompt, tema=tema, bloque=bloque, intentos=10)
    
    if img_url:
        return img_url
    
    # Si todo falla, fondo sólido
    print("   ⚠️ Pexels también falló, usando fondo sólido")
    return generar_fondo_solido(color=(20, 20, 50), ancho=1080, alto=1920)

def generar_imagen_horizontal(prompt, tema="", intentos=5):
    search_query = tema if tema else prompt
    search_query = re.sub(r'[^a-zA-Z0-9áéíóúüñÁÉÍÓÚÜÑ\s]', '', search_query).strip()
    if len(search_query) > 50:
        search_query = search_query[:50]
    if not search_query:
        search_query = "finanzas negocios tecnología"

    fallback_queries = [
        search_query,
        "finanzas negocios tecnología",
        "fondo abstracto oscuro",
        "gráficos bolsa valores",
    ]
    
    for intento in range(intentos):
        current_query = fallback_queries[intento % len(fallback_queries)]
        url = f"https://api.pexels.com/v1/search?query={current_query.replace(' ', '+')}&per_page=1&orientation=landscape"
        headers = {"Authorization": PEXELS_API_KEY}
        
        try:
            r = requests.get(url, headers=headers, timeout=30)
            if r.status_code == 200:
                data = r.json()
                if data.get("photos") and len(data["photos"]) > 0:
                    photo = data["photos"][0]
                    img_url = photo["src"].get("landscape") or photo["src"].get("original")
                    return img_url
        except Exception as e:
            print(f"   ⚠️ Error: {e}")
        
        if intento < intentos - 1:
            time.sleep(3)
    
    return None

def generar_fondo_solido(color=(20, 20, 50), ancho=1080, alto=1920):
    img = Image.new('RGB', (ancho, alto), color)
    path = f"temp_fondo_{random.randint(1000,9999)}.jpg"
    img.save(path)
    return path

# ================================================================
# 🎙️ GENERAR AUDIO (ESPAÑOL)
# ================================================================
def generar_audio(texto, index, intentos_por_voz=2):
    global CONFIG_VOZ_ACTUAL
    texto_limpio = re.sub(r'[^a-zA-ZáéíóúüñÁÉÍÓÚÜÑ0-9\s.,;:!?¿¡\'\"]', '', texto)
    texto_limpio = re.sub(r'\s+', ' ', texto_limpio).strip()
    if len(texto_limpio) < 20:
        texto_limpio = "Noticias financieras."
    filename = f"audio_short_es_{index}.mp3"
    voz = CONFIG_VOZ_ACTUAL["voz"]
    rate = CONFIG_VOZ_ACTUAL["velocidad"]
    pitch = CONFIG_VOZ_ACTUAL["tono"]
    for intento in range(intentos_por_voz):
        async def _gen():
            communicate = edge_tts.Communicate(texto_limpio, voz, rate=rate, pitch=pitch)
            await communicate.save(filename)
        try:
            asyncio.run(_gen())
            if os.path.exists(filename) and os.path.getsize(filename) > 0:
                return filename
        except Exception as e:
            print(f"   ❌ Voz falló: {e}")
        time.sleep(10)
    return None

# ================================================================
# 📊 ANÁLISIS DE TRENDS (ESPAÑOL)
# ================================================================
def analizar_trends_semanal():
    temas_pub = cargar_temas_publicados()
    hoy = datetime.now(ZoneInfo("America/Mexico_City")).date()
    
    temas_recientes = []
    for t in temas_pub:
        try:
            fecha_tema = datetime.strptime(t["fecha"], "%Y-%m-%d").date()
            if (hoy - fecha_tema).days <= 30:
                temas_recientes.append(t["tema"])
        except:
            continue
    
    temas_text = "\n".join(temas_recientes[:10]) if temas_recientes else "Ninguno"
    
    prompt = f"""
Eres un ANALISTA DE TRENDS VIRALES para YouTube Shorts en español sobre finanzas/crypto.

FECHA ACTUAL: {hoy.strftime("%B %d, %Y")}

🚫 PROHIBICIÓN CRÍTICA: NO te enfoques en Federal Reserve, decisiones de tasas Fed, FOMC, Jerome Powell. Enfócate en contenido educativo e histórico DIVERSO.

TEMAS PUBLICADOS RECIENTEMENTE (evitar repetir):
{temas_text}

🎯 TU TAREA: Genera 10 temas de video DIVERSOS para SHORTS (40-50 segundos).

MIX DE CONTENIDO (CRÍTICO - DEBE SER DIVERSO):
- 35% Educativo
- 25% Histórico
- 20% Psicología
- 15% Análisis
- 5% Noticias importantes (NO relacionadas con Fed)

REQUISITO DE DIVERSIDAD: Cada uno de los 10 temas DEBE ser de un subtema DIFERENTE. No repitas temas.

Devuelve JSON:
{{
    "trending_topics": [
        {{
            "topic": "...",
            "category": "...",
            "why_trending": "...",
            "viral_score": 9,
            "hook": "..."
        }}
    ],
    "best_topic_this_week": "...",
    "high_volume_keywords": ["...", "..."]
}}
"""
    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.85,
        "max_tokens": 1500,
        "response_format": {"type": "json_object"}
    }
    
    try:
        print("📊 Analizando trends semanales...")
        r = requests.post(url, headers=headers, json=payload, timeout=90)
        r.raise_for_status()
        data = r.json()
        content = data["choices"][0]["message"]["content"]
        
        inicio = content.find("{")
        fin = content.rfind("}")
        json_str = content[inicio:fin+1]
        try:
            trends = json.loads(json_str)
        except json.JSONDecodeError:
            trends = json5.loads(json_str)
        
        with open(TRENDS_FILE, "w", encoding="utf-8") as f:
            json.dump(trends, f, indent=2, ensure_ascii=False)
        
        print(f"   ✅ Mejor tema: {trends.get('best_topic_this_week', 'N/A')}")
        return trends
    except Exception as e:
        print(f"⚠️ Error analizando trends: {e}")
        return None

# ================================================================
# 🎬 GENERAR IDEA DE VIDEO (ESPAÑOL)
# ================================================================
def generar_idea_video(categoria, tema_sugerido, fecha_actual, trends_data=None):
    fed_prohibida = verificar_fed_reciente(dias=20)
    
    fed_instruction = ""
    if fed_prohibida:
        fed_instruction = """
🚫 PROHIBICIÓN CRÍTICA (ACTIVA):
Hemos publicado contenido sobre Fed/FOMC/Powell en los últimos 20 días.
ABSOLUTAMENTE NO crees títulos sobre:
- Federal Reserve / decisiones de tasas Fed / FOMC
- Jerome Powell
- Subidas o bajadas de tasas de interés
- Noticias de decisiones de tasas
Enfócate SOLO en contenido educativo, histórico, psicología o análisis técnico.
"""
    
    seo_keywords = []
    if trends_data and "high_volume_keywords" in trends_data:
        seo_keywords = trends_data.get("high_volume_keywords", [])
    
    keywords_text = ", ".join(seo_keywords[:5]) if seo_keywords else "Bitcoin, crypto, oro, inversión"
    
    prompt = f"""
Eres un ESTRATEGA DE CONTENIDO VIRAL para YouTube Shorts en español sobre finanzas/crypto.

FECHA ACTUAL: {fecha_actual}
CATEGORÍA: {categoria.upper()}
TEMA SUGERIDO: {tema_sugerido}

{fed_instruction}

🎯 KEYWORDS SEO DE ALTO VOLUMEN:
{keywords_text}

FÓRMULAS DE TÍTULOS VIRALES:
1. BRECHA DE CURIOSIDAD: "El Secreto #1 Sobre Bitcoin"
2. CONTROVERSIA: "Por Qué 90% de Traders Están Equivocados"
3. NÚMERO ESPECÍFICO: "5 Razones Por Qué Bitcoin Subirá"
4. COMPARACIÓN: "Bitcoin vs Oro: El Ganador"
5. EDUCATIVO: "Cómo Funciona la Minería de Bitcoin"

GUÍAS DE CONTENIDO por categoría:

Si EDUCATIVO: Enfócate en enseñar un concepto claramente. Usa analogías.
Si HISTÓRICO: Cuenta una historia con fechas y lecciones aprendidas.
Si PSICOLOGÍA: Explica comportamiento de inversores, sesgos, emociones.
Si ANÁLISIS: Usa datos, patrones, insights técnicos.
Si NOTICIAS (solo 5%): Enfócate en IMPACTO, contexto histórico.

🎯 TU TAREA: Genera 5 IDEAS DE VIDEO CORTO (40-50 segundos).

REQUISITOS:
✅ Título: 50-60 caracteres máx, keyword al inicio
✅ Incluir 1 emoji máx
✅ Crear BRECHA DE CURIOSIDAD
✅ Usar POWER WORDS: Secreto, Verdad, Revelado, Por Qué, Cómo, Impactante
✅ NO usar Fed / FOMC / Powell / tasa de interés en títulos
✅ Debe ser adecuado para short de 40-50 segundos
✅ TODO EN ESPAÑOL

Devuelve JSON:
{{
    "best_idea": {{
        "title": "Título final (50-60 chars, SIN Fed, EN ESPAÑOL)",
        "hook_3sec": "Primeros 3 segundos del guion (EN ESPAÑOL)",
        "description": "Explicación en una oración (EN ESPAÑOL)",
        "formula_used": "Nombre de fórmula",
        "psychology_trigger": "curiosity/education/fear",
        "type": "{categoria}"
    }},
    "all_ideas": [
        {{"title": "...", "hook_3sec": "...", "seo_score": 9}}
    ]
}}
"""
    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.9,
        "max_tokens": 1200,
        "response_format": {"type": "json_object"}
    }
    
    for intento in range(3):
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=90)
            r.raise_for_status()
            data = r.json()
            content = data["choices"][0]["message"]["content"]
            
            inicio = content.find("{")
            fin = content.rfind("}")
            json_str = content[inicio:fin+1]
            try:
                result = json.loads(json_str)
            except json.JSONDecodeError:
                result = json5.loads(json_str)
            
            titulo_gen = result.get("best_idea", {}).get("title", "").lower()
            if fed_prohibida and tema_contiene_fed(titulo_gen):
                print(f"⚠️ Tema Fed en título. Regenerando...")
                if intento < 2:
                    continue
            
            return result
        except Exception as e:
            print(f"⚠️ Error (intento {intento+1}): {e}")
            time.sleep(5)
    
    return None

# ================================================================
# 🏷️ SANITIZAR TAGS
# ================================================================
def sanitizar_hashtags(hashtags_str, max_tags=6):
    if not hashtags_str:
        return ""
    tags = hashtags_str.split()
    cleaned = []
    for tag in tags:
        tag = tag.strip()
        if not tag:
            continue
        if not tag.startswith("#"):
            tag = "#" + tag
        tag = re.sub(r'[^a-zA-Z0-9#]', '', tag)
        if tag and len(tag) > 1:
            cleaned.append(tag)
    cleaned = cleaned[:max_tags]
    return " ".join(cleaned)

def sanitizar_tags(tags_str, max_tags=20, max_chars=480):
    if not tags_str:
        return []
    
    raw_tags = [t.strip() for t in tags_str.split(",") if t.strip()]
    
    cleaned = []
    for tag in raw_tags:
        clean = re.sub(r'[^a-zA-Z0-9áéíóúüñÁÉÍÓÚÜÑ\s]', '', tag)
        clean = re.sub(r'\s+', ' ', clean).strip()
        
        if not clean or len(clean) < 2:
            continue
        if len(clean) > 30:
            clean = clean[:30].strip()
        
        cleaned.append(clean)
    
    seen = set()
    unique = []
    for tag in cleaned:
        tag_lower = tag.lower()
        if tag_lower not in seen:
            seen.add(tag_lower)
            unique.append(tag)
    
    unique = unique[:max_tags]
    
    result = []
    total_chars = 0
    for tag in unique:
        if total_chars + len(tag) + 1 <= max_chars:
            result.append(tag)
            total_chars += len(tag) + 1
        else:
            break
    
    return result

# ================================================================
# 🎵 MÚSICA
# ================================================================
FONDOS_DISPONIBLES = [
    "The Ascent.mp3",
    "Binary Pulse.mp3",
    "Peak Momentum.mp3",
    "Forward Momentum.mp3"
]

def seleccionar_fondo_disponible(estado):
    fondos_disponibles = []
    for root, dirs, files in os.walk("."):
        if "/." in root or "\\." in root:
            continue
        for file in files:
            if file.lower() in [f.lower() for f in FONDOS_DISPONIBLES]:
                fondos_disponibles.append(os.path.join(root, file))
    if not fondos_disponibles:
        return None
    ultimo_fondo = estado.get("ultimo_fondo")
    if ultimo_fondo and ultimo_fondo in fondos_disponibles:
        fondos_disponibles.remove(ultimo_fondo)
    seleccionada = random.choice(fondos_disponibles) if fondos_disponibles else None
    if seleccionada:
        estado["ultimo_fondo"] = seleccionada
        print(f"🎵 Música seleccionada: {os.path.basename(seleccionada)}")
    return seleccionada

# ================================================================
# 📂 FUNCIONES DE ESTADO
# ================================================================
def cargar_estado():
    try:
        with open(ESTADO_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "publicaciones_hoy" not in data:
                data["publicaciones_hoy"] = None
            return data
    except:
        return {"ultimo_fondo": None, "publicaciones_hoy": None}

def guardar_estado(estado):
    with open(ESTADO_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "ultimo_fondo": estado.get("ultimo_fondo"),
            "publicaciones_hoy": estado.get("publicaciones_hoy")
        }, f, indent=2, ensure_ascii=False)

def cargar_titulos_publicados():
    try:
        with open(TITULOS_FILE, "r", encoding="utf-8") as f:
            titulos = json.load(f).get("titulos", [])
    except:
        titulos = []
    return {"titulos": titulos}

def guardar_titulo_publicado(titulo):
    try:
        with open(TITULOS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except:
        data = {"titulos": []}
    if titulo not in data["titulos"]:
        data["titulos"].append(titulo)
        with open(TITULOS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

def _es_titulo_duplicado_real(titulo_nuevo, titulos_existentes):
    titulo_norm = titulo_nuevo.lower().strip()
    
    for t in titulos_existentes:
        t_norm = t.lower().strip()
        
        if titulo_norm == t_norm:
            return True
        
        palabras1 = set(re.findall(r'\w+', titulo_norm))
        palabras2 = set(re.findall(r'\w+', t_norm))
        
        if len(palabras1) > 5 and len(palabras2) > 5:
            interseccion = palabras1.intersection(palabras2)
            union = palabras1.union(palabras2)
            similitud = len(interseccion) / len(union) if union else 0
            
            if similitud > 0.85:
                return True
    
    return False

def modificar_titulo_para_evitar_duplicado(titulo_original, titulos_existentes):
    titulo_base = titulo_original.strip()
    
    sufijos_unicos = ["AHORA", "HOY", "2026", "JUSTO AHORA", "ACTUALIZACIÓN",
                     "EXCLUSIVO", "EN VIVO", "NUEVOS DATOS", "URGENTE", "ALERTA"]
    
    prefijos_unicos = [" URGENTE:", "⚠️ ALERTA:", "📈 ACTUALIZACIÓN:", "💰 ALERTA:",
                      "🔥 CALIENTE:", "🔴 EN VIVO:", " NUEVO:"]
    
    for _ in range(5):
        prefijo = random.choice(prefijos_unicos)
        titulo_mod = f"{prefijo} {titulo_base}"
        if len(titulo_mod) <= 100 and not _es_titulo_duplicado_real(titulo_mod, titulos_existentes):
            return titulo_mod
    
    for _ in range(5):
        sufijo = random.choice(sufijos_unicos)
        titulo_mod = f"{titulo_base} - {sufijo}"
        if len(titulo_mod) <= 100 and not _es_titulo_duplicado_real(titulo_mod, titulos_existentes):
            return titulo_mod
    
    timestamp = datetime.now().strftime("%H%M")
    return f"{titulo_base[:70]} [{timestamp}]"

def obtener_publicaciones_hoy():
    estado = cargar_estado()
    pub = estado.get("publicaciones_hoy")
    if not pub:
        return 0
    hoy = datetime.now(ZoneInfo("America/Mexico_City")).strftime("%Y-%m-%d")
    if pub.get("fecha") == hoy:
        return pub.get("cantidad", 0)
    return 0

def incrementar_publicaciones_hoy():
    estado = cargar_estado()
    hoy = datetime.now(ZoneInfo("America/Mexico_City")).strftime("%Y-%m-%d")
    pub = estado.get("publicaciones_hoy")
    if pub and pub.get("fecha") == hoy:
        pub["cantidad"] = pub.get("cantidad", 0) + 1
    else:
        estado["publicaciones_hoy"] = {"fecha": hoy, "cantidad": 1}
    guardar_estado(estado)

def cargar_temas_publicados():
    try:
        with open(TEMAS_PUBLICADOS_FILE, "r", encoding="utf-8") as f:
            temas = json.load(f).get("temas", [])
    except:
        temas = []
    return temas

def guardar_tema_publicado(tema, tipo):
    try:
        with open(TEMAS_PUBLICADOS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except:
        data = {"temas": []}
    data["temas"].append({
        "tema": tema,
        "tipo": tipo,
        "fecha": datetime.now(ZoneInfo("America/Mexico_City")).strftime("%Y-%m-%d")
    })
    if len(data["temas"]) > 200:
        data["temas"] = data["temas"][-200:]
    with open(TEMAS_PUBLICADOS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def tema_ya_publicado(tema, dias=30):
    temas = cargar_temas_publicados()
    hoy = datetime.now(ZoneInfo("America/Mexico_City")).date()
    for t in temas:
        if t["tema"].lower() == tema.lower():
            try:
                fecha_tema = datetime.strptime(t["fecha"], "%Y-%m-%d").date()
                if (hoy - fecha_tema).days < dias:
                    return True
            except:
                continue
    return False

# ================================================================
# 📝 GENERAR GUION (ESPAÑOL - CON FILTRO ANTI-FED)
# ================================================================
def generar_guion_financiero(categoria, tema_elegido, fecha_actual, idea=None):
    titulos_pub = cargar_titulos_publicados()["titulos"][-20:]
    titulos_referencia = "\n".join([f"- {t}" for t in titulos_pub]) if titulos_pub else "Ninguno aún."

    hook_sugerido = idea.get("hook_3sec", "") if idea else ""
    titulo_idea = idea["title"] if idea else tema_elegido
    
    fed_prohibida = verificar_fed_reciente(dias=20)
    fed_instruction = ""
    if fed_prohibida:
        fed_instruction = """
 PROHIBICIÓN CRÍTICA (ACTIVA):
Hemos publicado recientemente contenido sobre Fed. NO menciones Federal Reserve, tasa Fed, FOMC, Powell, o decisiones de tasas de interés en el guion o título.
Enfócate en contenido educativo, histórico, psicología o técnico en su lugar.
"""
    
    prompt = f"""
Eres un GUIONISTA de YouTube Shorts y EXPERTO SEO en español sobre finanzas/crypto.

📌 TEMA: "{titulo_idea}"
📌 CATEGORÍA: {categoria.upper()}
📌 HOOK: "{hook_sugerido}"
 FECHA: {fecha_actual}

{fed_instruction}

REGLAS CRÍTICAS:

1️⃣ PRIMEROS 3 SEGUNDOS (DEBEN DETENER EL SCROLL):
   - Declaración impactante + keyword
   - Ejemplos: "Bitcoin acaba de hacer ESTO...", "Por qué 90% de traders..."

2️ ESTRUCTURA (90-110 palabras para 40-50 segundos):
   [HOOK 0-3s] Declaración impactante (10 palabras)
   [PROBLEMA 3-10s] Por qué importa (25 palabras)
   [DATOS 10-25s] Hechos/números con keyword (35 palabras)
   [SOLUCIÓN 25-35s] Qué hacer (25 palabras)
   [CIERRE 35-40s] CTA (5 palabras)

3️ SEO:
   - Menciona la KEYWORD PRIMARIA 2-3 veces naturalmente
   - Incluye NÚMEROS (aumenta engagement 40%)

4️⃣ PROMPTS DE IMAGEN (uno por segmento, debe coincidir con el contenido):
   - HOOK: "escena financiera dramática, neón urgente, cinematográfico 8k, vertical 9:16"
   - PROBLEMA: "gráficos cayendo, velas rojas, fondo oscuro, vertical 9:16"
   - DATOS: "visualización de datos financieros, gráficos brillantes, vertical 9:16"
   - SOLUCIÓN: "gráfico de tendencia ascendente, velas verdes, acentos dorados, vertical 9:16"
   - CIERRE: "fondo de finanzas profesional, sutil, vertical 9:16"

5️⃣ MINIATURA: Alto CTR, sujeto dominante, alto contraste, espacio para texto.

6️⃣ HASHTAGS (6 totales):
   - 2 ALTO volumen (#Bitcoin #Crypto)
   - 2 MEDIO (#NoticiasBitcoin #NoticiasCrypto)
   - 2 BAJO nicho (#PrecioBitcoin #AlertaCrypto)

7️⃣ TÍTULO:
   - 50-60 caracteres, keyword primero
   - 1 emoji, brecha de curiosidad, power words
   - SIN referencias a Fed/FOMC/Powell
   - TODO EN ESPAÑOL

🚫 TÍTULOS YA PUBLICADOS (NO REPETIR):
{titulos_referencia}

DEVUELVE JSON:
{{
    "title": "Título (50-60 chars, emoji, SIN Fed, EN ESPAÑOL)",
    "alternative_title": "Título alternativo (EN ESPAÑOL)",
    "keywords": ["bitcoin", "crypto", "trading", "inversión", "finanzas"],
    "hook_description": "Hook para descripción (90 chars, EN ESPAÑOL)",
    "context_description": "Contexto en una oración (EN ESPAÑOL)",
    "source_story": "Fuente de datos",
    "cover_words": "2-3 PALABRAS PARA MINIATURA",
    "tags": "25 tags separados por coma (mix alto/medio/bajo volumen)",
    "dynamic_hashtags": "#Bitcoin #Crypto #NoticiasBitcoin #NoticiasCrypto #PrecioBitcoin #AlertaCrypto",
    "segments": [
        {{"block": "HOOK", "text": "~10 palabras", "image_prompt": "escena financiera dramática", "duration": 3.0}},
        {{"block": "PROBLEMA", "text": "~25 palabras", "image_prompt": "gráficos cayendo", "duration": 7.0}},
        {{"block": "DATOS", "text": "~35 palabras", "image_prompt": "gráficos de datos financieros", "duration": 15.0}},
        {{"block": "SOLUCIÓN", "text": "~25 palabras", "image_prompt": "tendencia ascendente", "duration": 10.0}},
        {{"block": "CIERRE", "text": "~5 palabras", "image_prompt": "fondo finanzas", "duration": 5.0}}
    ],
    "thumbnail_prompt": "Bitcoin dramático, espacio para texto, miniatura YouTube 16:9",
    "seo_optimized_description": "Descripción con keywords para SEO (EN ESPAÑOL)"
}}
"""
    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.85,
        "max_tokens": 1200,
        "response_format": {"type": "json_object"}
    }

    for intento in range(6):
        try:
            print(f"🔄 Intento {intento+1}/6 generando guion...")
            r = requests.post(url, headers=headers, json=payload, timeout=90)
            r.raise_for_status()
            respuesta = r.json()["choices"][0]["message"]["content"].strip()
            
            respuesta = re.sub(r"```json\s*", "", respuesta)
            respuesta = re.sub(r"```\s*", "", respuesta)
            inicio = respuesta.find("{")
            fin = respuesta.rfind("}")
            if inicio != -1 and fin != -1:
                json_str = respuesta[inicio:fin+1]
                json_str = re.sub(r",\s*}", "}", json_str)
                json_str = re.sub(r",\s*\]", "]", json_str)
                
                # Intento de parseo robusto
                try:
                    data = json.loads(json_str, strict=False)
                except json.JSONDecodeError:
                    data = json5.loads(json_str)
            else:
                raise ValueError("No se encontró JSON")

            if "segments" not in data or len(data["segments"]) != 5:
                raise ValueError("Faltan segmentos")
            
            for seg in data["segments"]:
                if not seg.get("image_prompt") or len(seg["image_prompt"].split()) < 5:
                    seg["image_prompt"] = f"escena financiera cinematográfica, iluminación neón, 8k, vertical 9:16"

            titulo = data.get("title", "").strip()
            titulo = re.sub(r'#\w+', '', titulo).strip()
            
            if fed_prohibida and tema_contiene_fed(titulo):
                print(f"   ⚠️ Título contiene referencia a Fed. Regenerando...")
                if intento < 5:
                    continue
            
            titulos_existentes = cargar_titulos_publicados()["titulos"]
            if _es_titulo_duplicado_real(titulo, titulos_existentes):
                print(f"   ⚠️ Título similar a existente: '{titulo}'")
                titulo = modificar_titulo_para_evitar_duplicado(titulo, titulos_existentes)
                data["title"] = titulo
                print(f"   ✅ Modificado: {titulo}")

            tags_raw = data.get("tags", "")
            tags_list = sanitizar_tags(tags_raw)
            keywords = data.get("keywords", [])
            for kw in keywords:
                if kw.lower() not in [t.lower() for t in tags_list]:
                    tags_list.append(kw.lower())
            extras = ["finanzas", "inversión", "economía", "bitcoin", "crypto", "trading", "educación"]
            for extra in extras:
                if len(tags_list) < 25 and extra not in tags_list:
                    tags_list.append(extra)
            data["tags"] = ", ".join(tags_list[:25])

            if "thumbnail_prompt" not in data or not data["thumbnail_prompt"]:
                data["thumbnail_prompt"] = "gráfico financiero profesional limpio, fondo oscuro, azul y oro, sin personas, sin texto"
            if "dynamic_hashtags" not in data:
                data["dynamic_hashtags"] = "#Bitcoin #Crypto #NoticiasBitcoin #NoticiasCrypto #PrecioBitcoin #AlertaCrypto"

            print(f"   ️ Título: {data['title']}")
            return data, tema_elegido, categoria
            
        except Exception as e:
            print(f"❌ Intento {intento+1}/6 falló: {e}")
            if intento < 5:
                time.sleep(10)

    print("️ Todos los intentos fallaron. Generando título forzado único...")
    fecha_corta = datetime.now().strftime("%b %d").upper()
    titulo_forzado = f"📊 {tema_elegido[:40]} - {fecha_corta}"
    
    return {
        "title": titulo_forzado,
        "alternative_title": f"⚠️ {tema_elegido[:40]} | {fecha_corta}",
        "keywords": ["bitcoin", "crypto", "finanzas"],
        "hook_description": f"Perspectiva financiera sobre {tema_elegido[:50]}",
        "context_description": f"Análisis para {fecha_corta}",
        "source_story": "Análisis de mercado",
        "cover_words": "CLAVE INSIGHT",
        "tags": "bitcoin, crypto, finanzas, trading, inversión, economía, análisis de mercado, educación",
        "dynamic_hashtags": "#Bitcoin #Crypto #NoticiasBitcoin #NoticiasCrypto #PrecioBitcoin #AlertaCrypto",
        "segments": [
            {"block": "HOOK", "text": f"Descubre la verdad sobre {tema_elegido[:30]}. Esto cambia todo.", "image_prompt": "escena financiera dramática, iluminación neón, 8k, vertical 9:16", "duration": 3.0},
            {"block": "PROBLEMA", "text": "La mayoría de inversores pierden este detalle crítico que podría hacer o deshacer su portafolio.", "image_prompt": "gráficos cayendo, velas rojas, fondo oscuro, vertical 9:16", "duration": 7.0},
            {"block": "DATOS", "text": "Los datos históricos muestran patrones consistentes que los inversores inteligentes usan a su favor.", "image_prompt": "visualización de datos financieros, gráficos brillantes, vertical 9:16", "duration": 15.0},
            {"block": "SOLUCIÓN", "text": "Diversifica, mantente informado y piensa a largo plazo. El conocimiento es tu mejor inversión.", "image_prompt": "tendencia ascendente, velas verdes, acentos dorados, vertical 9:16", "duration": 10.0},
            {"block": "CIERRE", "text": "Suscríbete para insights diarios.", "image_prompt": "fondo de finanzas profesional, vertical 9:16", "duration": 5.0}
        ],
        "thumbnail_prompt": "Bitcoin dramático, espacio para texto, miniatura YouTube 16:9",
        "seo_optimized_description": f"Último análisis sobre {tema_elegido[:50]}. Mantente informado con actualizaciones diarias."
    }, tema_elegido, categoria

# ================================================================
# 🎬 GENERAR RECURSOS POR SEGMENTO
# ================================================================
def generar_recursos_por_segmento(segmentos_data, paleta_video, titulo, tema="", intentos_imagen=10):
    recursos = []
    total = len(segmentos_data)
    last_successful_url = None

    for idx, seg in enumerate(segmentos_data):
        seg_text = seg["text"]
        prompt_deepseek = seg.get("image_prompt", "")
        bloque = seg.get("block", "")
        
        print(f"  🎬 Segmento {idx+1}/{total} - {bloque} ({len(seg_text.split())} palabras)")
        
        prompt_img = f"{prompt_deepseek}, paleta de colores {paleta_video}, estilo documental financiero cinematográfico, hiperrealista, resolución 8k, iluminación dramática, alto contraste, enfoque nítido, sin personas, sin caras, sin texto, sin letras, sin números, sin logos, sin watermark, vertical 9:16"
        
        img_url = generar_imagen_segmento(prompt_img, tema=tema, bloque=bloque)
        
        if not img_url:
            if last_successful_url:
                print(f"    🔄 Reutilizando imagen anterior")
                img_url = last_successful_url
            else:
                img_path = generar_fondo_solido(color=(20, 20, 50), ancho=1080, alto=1920)
                img_url = img_path
                last_successful_url = img_url
        
        audio_path = generar_audio(seg_text, idx)
        if not audio_path:
            print(f"    ❌ Audio falló. Abortando.")
            return None
        
        try:
            dur = AudioFileClip(audio_path).duration
        except:
            dur = seg.get("duration", 8.0)
        
        recursos.append({
            "imagen_url": img_url,
            "audio_path": audio_path,
            "duracion": dur,
            "texto": seg_text,
            "block": bloque
        })
        
        if idx < total - 1:
            time.sleep(10)
    
    return recursos

# ================================================================
# 📝 SUBTÍTULOS
# ================================================================
def agregar_subtitulos_con_pil(imagen_path, texto, salida_path):
    try:
        img = Image.open(imagen_path)
        draw = ImageDraw.Draw(img)
        
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 55)
        except:
            try:
                font = ImageFont.truetype("arial.ttf", 55)
            except:
                font = ImageFont.load_default()
        
        if not texto:
            img.save(salida_path)
            return salida_path
        
        palabras = texto.split()
        if len(palabras) > 14:
            texto_sub = ' '.join(palabras[:14])
        else:
            texto_sub = texto
        
        if len(texto_sub) > 50:
            mitad = len(texto_sub) // 2
            espacio = texto_sub.find(' ', mitad - 10)
            if espacio == -1:
                espacio = mitad
            linea1 = texto_sub[:espacio]
            linea2 = texto_sub[espacio+1:]
            lineas = [linea1, linea2]
        else:
            lineas = [texto_sub]
        
        y_base = 1700
        for i, linea in enumerate(lineas):
            bbox = draw.textbbox((0, 0), linea, font=font)
            ancho = bbox[2] - bbox[0]
            alto = bbox[3] - bbox[1]
            x = (1080 - ancho) // 2
            y = y_base + i * 60
            
            padding = 15
            bg_x = x - padding
            bg_y = y - padding
            bg_w = ancho + padding * 2
            bg_h = alto + padding * 2
            draw.rectangle([bg_x, bg_y, bg_x + bg_w, bg_y + bg_h], fill=(0, 0, 0, 180))
            draw.rectangle([bg_x, bg_y, bg_x + bg_w, bg_y + bg_h], outline=(0, 200, 255, 80), width=2)
            
            draw.text((x+3, y+3), linea, fill='black', font=font)
            draw.text((x, y), linea, fill='white', font=font)
        
        img.save(salida_path)
        return salida_path
    except Exception as e:
        print(f"⚠️ Error en subtítulos: {e}")
        return imagen_path

def obtener_ruta_fuente():
    if not os.path.exists("Anton.ttf"):
        try:
            print("📥 Descargando fuente Anton...")
            url = "https://github.com/google/fonts/raw/main/ofl/anton/Anton-Regular.ttf"
            r = requests.get(url, timeout=30)
            if r.status_code == 200 and len(r.content) > 10000:
                with open("Anton.ttf", "wb") as f:
                    f.write(r.content)
                print("✅ Fuente Anton descargada")
        except Exception as e:
            print(f"️ Error descargando fuente: {e}")
    rutas = ["Anton.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
    for ruta in rutas:
        if os.path.exists(ruta):
            return ruta
    return None

# ================================================================
# 🖼️ MINIATURA PROFESIONAL ULTRA-LLAMATIVA (CLOUDFLARE + PIL)
# ================================================================
def crear_miniatura_profesional(prompt_miniatura, texto_portada, salida="miniatura_short_es.jpg"):
    try:
        print("🖼️ Generando miniatura de SHORT ultra-llamativa...")
        
        prompt_super = f"""
{prompt_miniatura}, 
ultra high contrast, extreme close-up,
colores neón vibrantes (amarillo #FFD700 y rojo #FF0000),
estilo de miniatura profesional de YouTube,
espacio para TEXTO GRANDE Y GRUESO en el lado derecho,
llamativo, diseño de miniatura viral,
resolución 8k, altamente detallado,
sin texto en imagen, sin watermark
"""
        
        # Intentar Cloudflare AI (5 intentos)
        cf_path = None
        for intento in range(5):
            cf_path = f"temp_cf_thumb_{intento}.jpg"
            img_path = generar_imagen_cloudflare(prompt_super, cf_path)
            
            if img_path and os.path.exists(img_path):
                print(f"   ✅ Cloudflare AI generó miniatura (intento {intento+1}/5)")
                break
            
            print(f"   🔄 Cloudflare intento {intento+1}/5, reintentando...")
            time.sleep(2)
        
        # Si Cloudflare falla, usar Pexels
        if not cf_path or not os.path.exists(cf_path):
            print("   ⚠️ Cloudflare falló 5 veces, usando Pexels...")
            fondo_url = generar_imagen_horizontal(prompt_super, tema=texto_portada, intentos=5)
            
            if fondo_url and fondo_url.startswith("http"):
                try:
                    r = requests.get(fondo_url, timeout=30)
                    r.raise_for_status()
                    img_path = "temp_thumb_pexels.jpg"
                    with open(img_path, "wb") as f:
                        f.write(r.content)
                except:
                    img_path = generar_fondo_solido(color=(5, 5, 15), ancho=1280, alto=720)
            else:
                img_path = generar_fondo_solido(color=(5, 5, 15), ancho=1280, alto=720)
        else:
            img_path = cf_path
        
        img = Image.open(img_path)
        img = ImageOps.fit(img, (1280, 720), Image.Resampling.LANCZOS)
        draw = ImageDraw.Draw(img)
        
        texto = texto_portada.upper().strip()
        palabras = texto.split()
        
        if len(palabras) > 4:
            texto = ' '.join(palabras[:4])
            palabras = texto.split()
        
        if len(palabras) > 2:
            mitad = len(palabras) // 2
            lineas = [' '.join(palabras[:mitad+1]), ' '.join(palabras[mitad+1:])]
        else:
            lineas = [texto]
        
        ruta_fuente = obtener_ruta_fuente()
        
        size = 180
        while size >= 100:
            if ruta_fuente:
                font = ImageFont.truetype(ruta_fuente, size)
            else:
                font = ImageFont.load_default()
            
            ancho_max = 0
            alto_total = 0
            for linea in lineas:
                bbox = draw.textbbox((0, 0), linea, font=font)
                ancho_max = max(ancho_max, bbox[2] - bbox[0])
                alto_total += bbox[3] - bbox[1] + 20
            
            if ancho_max <= 1000 and alto_total <= 450:
                break
            size -= 10
        
        font = ImageFont.truetype(ruta_fuente, size) if ruta_fuente else ImageFont.load_default()
        
        alto_linea = size + 20
        alto_total = alto_linea * len(lineas)
        y_inicio = (720 - alto_total) // 2
        
        offset = 10
        for i, linea in enumerate(lineas):
            bbox = draw.textbbox((0, 0), linea, font=font)
            text_w = bbox[2] - bbox[0]
            x = 1280 - text_w - 60
            y = y_inicio + i * alto_linea
            
            for dx in range(-offset, offset+1, 3):
                for dy in range(-offset, offset+1, 3):
                    draw.text((x + dx, y + dy), linea, fill='black', font=font)
        
        for i, linea in enumerate(lineas):
            bbox = draw.textbbox((0, 0), linea, font=font)
            text_w = bbox[2] - bbox[0]
            x = 1280 - text_w - 60
            y = y_inicio + i * alto_linea
            draw.text((x, y), linea, fill=(255, 255, 0), font=font)
        
        draw.rectangle([(1180, 40), (1270, 680)], outline=(255, 50, 50), width=6)
        
        img.save(salida, quality=95)
        print(f"✅ Miniatura ultra-llamativa creada: {salida}")
        print(f"   Texto: '{texto}' (TAMAÑO: {size}px)")
        print(f"   Colores: Amarillo (#FFFF00) con borde rojo")
        return salida
        
    except Exception as e:
        print(f"⚠️ Error en miniatura: {e}")
        import traceback
        traceback.print_exc()
        return None

# ================================================================
# 🎬 MONTAR VIDEO
# ================================================================
def montar_video_shorts(recursos, fondo_path, salida="short_capital_es.mp4"):
    if not recursos:
        raise ValueError("No resources")
    
    clips_video = []
    clips_audio = []
    
    for i, rec in enumerate(recursos):
        img_url = rec["imagen_url"]
        audio_path = rec["audio_path"]
        duracion = rec["duracion"]
        texto = rec.get("texto", "")
        bloque = rec.get("block", "")
        
        if img_url.startswith("http"):
            try:
                r = requests.get(img_url, timeout=30)
                r.raise_for_status()
                img_path = f"temp_short_es_{i}.jpg"
                with open(img_path, "wb") as f:
                    f.write(r.content)
            except:
                img_path = generar_fondo_solido(color=(20, 20, 50))
        else:
            img_path = img_url
        
        img = Image.open(img_path)
        img = ImageOps.fit(img, (1080, 1920), Image.Resampling.LANCZOS)
        img.save(img_path)
        
        img_sub_path = f"temp_short_sub_es_{i}.jpg"
        img_path = agregar_subtitulos_con_pil(img_path, texto, img_sub_path)
        
        video_clip = ImageClip(img_path).set_duration(duracion)
        
        if bloque == "HOOK" or i == 0:
            video_clip = video_clip.resize(lambda t: 1.3 - 0.6 * min(t/0.5, 1.0))
        elif bloque == "PROBLEMA" or i == 1:
            video_clip = video_clip.resize(lambda t: 1.0 + 0.02 * t)
        elif bloque == "DATOS":
            video_clip = video_clip.resize(lambda t: 1.0 + 0.01 * t)
        elif bloque == "SOLUCIÓN":
            video_clip = video_clip.resize(lambda t: 1.0 - 0.02 * min(t/5, 0.1))
        else:
            video_clip = video_clip.resize(lambda t: 1 + 0.02 * t)
        
        clips_video.append(video_clip)
        
        try:
            audio = AudioFileClip(audio_path)
            clips_audio.append(audio)
        except:
            silencio = AudioClip(lambda t: 0, duration=duracion)
            clips_audio.append(silencio)
    
    PAUSA = 0.3
    audio_final_parts = []
    for i, aud in enumerate(clips_audio):
        audio_final_parts.append(aud)
        if i < len(clips_audio) - 1:
            audio_final_parts.append(AudioClip(lambda t: 0, duration=PAUSA))
    
    audio_narracion = concatenate_audioclips(audio_final_parts)
    duracion_total = audio_narracion.duration
    
    video = concatenate_videoclips(clips_video, method="compose")
    video = video.set_duration(duracion_total)
    
    if fondo_path and os.path.exists(fondo_path):
        try:
            fondo_clip = AudioFileClip(fondo_path)
            if fondo_clip.duration < duracion_total:
                veces = int(duracion_total / fondo_clip.duration) + 1
                fondo_clip = concatenate_audioclips([fondo_clip] * veces)
            fondo_clip = fondo_clip.subclip(0, duracion_total).volumex(0.06)
            audio_final = CompositeAudioClip([audio_narracion, fondo_clip])
        except:
            audio_final = audio_narracion
    else:
        audio_final = audio_narracion
    
    video = video.set_audio(audio_final)
    video.write_videofile(salida, fps=24, codec="libx264", audio_codec="aac", 
                          threads=4, preset="ultrafast")
    video.close()
    audio_final.close()
    
    for f in os.listdir("."):
        if f.startswith("temp_short_") and f.endswith(".jpg"):
            try: os.remove(f)
            except: pass
    
    return salida

# ================================================================
# 📤 SUBIR A YOUTUBE
# ================================================================
def subir_a_youtube(video_path, titulo, etiquetas_str, gancho, contexto, hashtags, fuente="", miniatura_path=None, dynamic_hashtags="", seo_description=""):
    try:
        creds = Credentials.from_authorized_user_info(YOUTUBE_USER_TOKEN)
        youtube = build("youtube", "v3", credentials=creds)
    except Exception as e:
        print(f"❌ Error autenticación: {e}")
        sys.exit(1)
    
    tags = sanitizar_tags(etiquetas_str, max_tags=20, max_chars=480)
    
    if len(tags) < 5:
        print("️ No hay suficientes tags válidos. Usando tags de respaldo.")
        tags = ["bitcoin", "crypto", "inversión", "blockchain", "trading",
                "finanzas", "oro", "criptomonedas", "análisis de mercado", "noticias crypto"]
    
    print(f"\n DIAGNÓSTICO TAGS:")
    total_chars = 0
    for i, tag in enumerate(tags, 1):
        print(f"   {i}. '{tag}' ({len(tag)} chars)")
        total_chars += len(tag) + 1
    print(f"   Total: {total_chars} chars (límite: 500)")
    
    hashtags_fijos = "#Shorts #Finanzas #Inversión"
    if dynamic_hashtags:
        dynamic_hashtags = sanitizar_hashtags(dynamic_hashtags, max_tags=6)
        hashtags_final = f"{dynamic_hashtags} {hashtags_fijos}"
    else:
        hashtags_final = hashtags_fijos
    
    descripcion = f"""{gancho}

{contexto}

{seo_description if seo_description else contexto}

 SUSCRÍBETE: {CANAL_LINK}

📖 {fuente}

{hashtags_final}

⚠️ AVISO IMPORTANTE: Este contenido es solo para fines educativos y no constituye asesoramiento financiero, legal o de inversión."""
    
    body = {
        "snippet": {
            "title": titulo[:100],
            "description": descripcion[:5000],
            "tags": tags[:20],
            "categoryId": "22",
            "defaultLanguage": "es",
            "defaultAudioLanguage": "es",
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
            "containsSyntheticMedia": True,
        },
    }
    
    media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = request.execute()
    video_id = response["id"]
    print(f"✅ Short subido: https://youtu.be/{video_id}")
    
    if miniatura_path and os.path.exists(miniatura_path):
        try:
            media_thumb = MediaFileUpload(miniatura_path, chunksize=-1, resumable=True)
            youtube.thumbnails().set(videoId=video_id, media_body=media_thumb).execute()
            print("✅ Miniatura subida")
        except Exception as e:
            print(f"⚠️ Error subiendo miniatura: {e}")
    
    return video_id

# ================================================================
# 🧹 LIMPIEZA
# ================================================================
def limpiar_archivos_temporales():
    import glob
    patrones = [
        "temp_*.jpg", "audio_short_es_*.mp3", "temp_thumb*.jpg",
        "miniatura_short_es.jpg", "short_capital_es.mp4", "placeholder*.jpg",
        "temp_fondo_*.jpg", "temp_cf_*.jpg"
    ]
    for patron in patrones:
        for f in glob.glob(patron):
            try:
                os.remove(f)
            except:
                pass
    print("✅ Limpieza completada")

def inicializar_archivos_json():
    archivos_needed = {
        "temas_shorts_es_publicados.json": {"temas": []},
        "titulos_capital_shorts_es_publicados.json": {"titulos": []},
        "estado_capital_shorts_es.json": {"ultimo_fondo": None, "publicaciones_hoy": None},
        "trends_semanal_es.json": {"trending_topics": [], "best_topic_this_week": ""}
    }
    for archivo, contenido in archivos_needed.items():
        if not os.path.exists(archivo):
            print(f" Creando: {archivo}")
            with open(archivo, "w", encoding="utf-8") as f:
                json.dump(contenido, f, indent=2, ensure_ascii=False)

# ================================================================
# 🎯 MAIN
# ================================================================
def main():
    global _used_image_urls
    _used_image_urls = set()
    
    inicializar_archivos_json()
    
    print("="*60)
    print("🎬 Capital Minds - BOT SHORTS (ESPAÑOL)")
    print("   ✓ 35% Educativo, 25% Histórico, 20% Psicología")
    print("   ✓ 15% Análisis, 5% Noticias (SIN sesgo Fed)")
    print("   ✓ Filtro Anti-Fed (20 días sin Fed)")
    print("   ✓ Miniaturas Cloudflare AI Ultra-Llamativas")
    print("   ✓ Imágenes por Segmento (Cloudflare → Pexels)")
    print("   ✓ Tags con espacios internos (SEO óptimo)")
    print("   ✓ Log de diagnóstico de tags")
    print("   ✓ Solo 2 shorts por día")
    print("   ✓ TODO EN ESPAÑOL")
    print("="*60)

    tz_mexico = ZoneInfo("America/Mexico_City")
    fecha_actual = datetime.now(tz_mexico)
    fecha_formateada = fecha_actual.strftime("%B %d, %Y")
    print(f"📅 Fecha: {fecha_formateada}")
    
    fed_reciente = verificar_fed_reciente(dias=20)
    if fed_reciente:
        print("🚫 Filtro Anti-Fed: ACTIVO (contenido Fed reciente detectado)")
    else:
        print("✅ Filtro Anti-Fed: inactivo")
    print("="*60)
    
    if not YOUTUBE_USER_TOKEN:
        print("❌ Falta YOUTUBE_USER_TOKEN_CAPITAL")
        sys.exit(1)
    
    if not DEEPSEEK_API_KEY:
        print("❌ Falta DEEPSEEK_API_KEY")
        sys.exit(1)
    
    if not PEXELS_API_KEY:
        print("❌ Falta PEXELS_API_KEY")
        sys.exit(1)
    
    publicadas = obtener_publicaciones_hoy()
    if publicadas >= META_DIARIA_SHORTS:
        print(f"✅ Límite alcanzado: {META_DIARIA_SHORTS} shorts hoy.")
        sys.exit(0)
    
    print(f"📊 Publicados hoy: {publicadas}/{META_DIARIA_SHORTS}")
    
    categoria, tema_sugerido = seleccionar_categoria_shorts()
    print(f"📌 Categoría: {categoria.upper()}")
    print(f"📝 Tema sugerido: {tema_sugerido}")
    
    estado = cargar_estado()
    fondo_path = seleccionar_fondo_disponible(estado)
    
    paleta_video = random.choice(PALETAS_VIDEO)
    print(f"🎨 Paleta: {paleta_video[:50]}...")
    
    trends_data = None
    try:
        with open(TRENDS_FILE, "r", encoding="utf-8") as f:
            trends_data = json.load(f)
    except:
        if fecha_actual.hour < 2:
            trends_data = analizar_trends_semanal()
    
    print("💡 Generando idea...")
    idea_data = generar_idea_video(categoria, tema_sugerido, fecha_formateada, trends_data)
    if idea_data and "best_idea" in idea_data:
        idea = idea_data["best_idea"]
        print(f"   ✅ Idea: {idea['title']}")
    else:
        idea = None
    
    guion, tema_elegido, tipo_final = generar_guion_financiero(categoria, tema_sugerido, fecha_formateada, idea)
    titulo = guion["title"]
    dynamic_hashtags = guion.get("dynamic_hashtags", "")
    segments_data = guion["segments"]
    palabras_portada = guion.get("cover_words", "INSIGHT")
    prompt_miniatura = guion.get("thumbnail_prompt", "")
    seo_description = guion.get("seo_optimized_description", "")
    
    print(f"🏷️ Título: {titulo}")
    print(f"🏷️ Hashtags: {dynamic_hashtags}")
    
    recursos = generar_recursos_por_segmento(segments_data, paleta_video, titulo, tema=tema_elegido)
    if not recursos:
        print("❌ Error generando recursos.")
        sys.exit(1)
    
    video_path = montar_video_shorts(recursos, fondo_path, "short_capital_es.mp4")
    print(f"🎬 Video: {video_path}")
    
    miniatura_path = None
    if prompt_miniatura:
        prompt_miniatura_final = f"{prompt_miniatura}, paleta de colores {paleta_video}, estilo documental financiero cinematográfico, hiperrealista, 8k, iluminación dramática, alto contraste, enfoque nítido, sin personas, sin caras, sin texto, sin letras, sin números, sin logos, sin watermark"
        miniatura_path = crear_miniatura_profesional(
            prompt_miniatura_final,
            palabras_portada,
            "miniatura_short_es.jpg"
        )
    
    video_id = subir_a_youtube(
        video_path=video_path,
        titulo=guion["title"],
        etiquetas_str=guion["tags"],
        gancho=guion["hook_description"],
        contexto=guion["context_description"],
        hashtags="",
        fuente=guion.get("source_story", "Basado en análisis financiero"),
        miniatura_path=miniatura_path,
        dynamic_hashtags=dynamic_hashtags,
        seo_description=seo_description
    )
    
    guardar_titulo_publicado(guion["title"])
    guardar_tema_publicado(tema_elegido, categoria)
    incrementar_publicaciones_hoy()
    guardar_estado(estado)
    
    limpiar_archivos_temporales()
    
    print(f"\n✅ Short publicado!")
    print(f" https://youtu.be/{video_id}")
    print(f"📊 Categoría: {categoria.upper()}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ Error fatal: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
