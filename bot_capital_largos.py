import asyncio
from datetime import datetime, timedelta
import json
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
    CompositeVideoClip,
)
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# ================================================================
# 🔧 CONFIGURACIÓN ÉLITE SEO
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
ESTADO_FILE = "estado_capital_largos_es.json"
TITULOS_FILE = "titulos_capital_largos_es_publicados.json"
TEMAS_PUBLICADOS_FILE = "temas_largos_es_publicados.json"
TRENDS_FILE = "trends_semanal_largos_es.json"

# 🔧 REGLA DE ORO: 1 video cada 2 días
META_DIARIA_LARGOS = 1
DIAS_ENTRE_PUBLICACIONES = 2
DIAS_SIN_REPETIR_TEMA = 45

_used_image_urls = set()

# ================================================================
# 🚫 PALABRAS PROHIBIDAS (ANTI-FED)
# ================================================================
PALABRAS_ANTI_FED = [
    "fed", "fomc", "powell", "tasa de interés", "decisión de tasas",
    "reserva federal", "política monetaria", "jerome powell"
]

# ================================================================
# 🎙️ VOZ FIJA (ESPAÑOL)
# ================================================================
VOZ_FIJA = {
    "voz": "es-ES-ElviraNeural",
    "velocidad": "+10%",
    "tono": "+1Hz",
    "volumen": "+5%"
}
CONFIG_VOZ_ACTUAL = VOZ_FIJA

# ================================================================
# 📚 CATEGORÍAS DE CONTENIDO (90% educ/hist, 10% news)
# ================================================================
CATEGORIAS_CONTENIDO = {
    "educational": {
        "peso": 40,
        "temas": [
            "Cómo Funciona la Minería de Bitcoin",
            "Entendiendo la Tecnología Blockchain",
            "Bitcoin vs Oro: Comparación Completa",
            "Cómo Leer Gráficos de Criptomonedas",
            "Estrategia Dollar Cost Averaging Explicada",
            "Diversificación de Portafolio con Crypto y Oro",
            "Entendiendo los Ciclos del Mercado",
            "Gestión de Riesgos en Inversión Crypto",
            "Análisis Técnico Básico",
            "Análisis Fundamental para Crypto",
            "Qué es una Billetera Crypto y Cómo Usarla",
            "Staking vs Yield Farming Explicado",
            "Cómo Funcionan los Smart Contracts",
            "Préstamos DeFi Explicados Simplemente",
            "Cómo Investigar un Proyecto Crypto",
            "Stablecoins: Tipos y Casos de Uso",
            "NFTs Explicados para Inversores",
            "Layer 1 vs Layer 2 Blockchains",
            "Mecanismos de Consenso Explicados",
            "Cómo Funcionan los Exchanges Crypto"
        ]
    },
    "historical": {
        "peso": 35,
        "temas": [
            "El Bull Run de Bitcoin 2017: Qué Realmente Pasó",
            "La Crisis Financiera 2008 y el Nacimiento de Bitcoin",
            "Patrón Oro: Por Qué Terminó y Qué Significa",
            "La Fiebre de los Tulipanes: Primera Burbuja",
            "Crash Crypto 2021: Lecciones Aprendidas",
            "La Gran Depresión y el Oro",
            "Hack de Mt Gox: Qué Pasó",
            "Primera Compra Real con Bitcoin (Pizza Day)",
            "Crisis de Chipre 2013 y Bitcoin",
            "Caídas Históricas del Precio del Oro",
            "El Shock Nixon 1971: Cambió el Dinero para Siempre",
            "Auge y Caída de FTX",
            "Colapso de Terra Luna: Historia Completa",
            "Historia de Silk Road: El Pasado Oscuro de Bitcoin",
            "Historia del Halving: 2012, 2016, 2020, 2024"
        ]
    },
    "analysis": {
        "peso": 15,
        "temas": [
            "Análisis de Ciclos de Halving de Bitcoin",
            "Patrones del Precio del Oro en 50 Años",
            "Análisis de Correlación del Mercado Crypto",
            "Tendencias de Adopción Institucional",
            "Impacto de las CBDCs",
            "Impacto de la Inflación en Oro y Bitcoin",
            "Modelo Stock to Flow Explicado",
            "Análisis On-Chain Básico",
            "Factores Macroeconómicos que Afectan Crypto",
            "Eventos Geopolíticos y Activos Refugio",
            "Dominancia de Bitcoin y Ciclos Altseason",
            "Ratio MVRV y Valoración de Mercado"
        ]
    },
    "news": {
        "peso": 10,
        "temas": [
            "Actualización Regulación Crypto",
            "Análisis Flujo Bitcoin ETF",
            "Reporte Compras Oro Bancos Centrales",
            "Noticias Grandes Exchanges",
            "Nueva Adopción Institucional Crypto"
        ]
    }
}

def seleccionar_categoria():
    total_peso = sum(cat["peso"] for cat in CATEGORIAS_CONTENIDO.values())
    numero_aleatorio = random.uniform(0, total_peso)
    peso_acumulado = 0
    for categoria, datos in CATEGORIAS_CONTENIDO.items():
        peso_acumulado += datos["peso"]
        if numero_aleatorio <= peso_acumulado:
            return categoria, random.choice(datos["temas"])
    return "educational", random.choice(CATEGORIAS_CONTENIDO["educational"]["temas"])

# ================================================================
# 🎨 PALETAS ÉLITE
# ================================================================
PALETAS_VIDEO = [
    "cian eléctrico y oro neón sobre azul marino oscuro",
    "verde esmeralda y plata sobre negro",
    "magenta violeta y naranja sobre azul profundo",
    "rojo carmesí y oro sobre carbón",
    "verde azulado y ámbar sobre pizarra oscura",
    "azul hielo y blanco sobre negro medianoche",
]

COMPOSICIONES_BLOQUE = [
    "extreme wide establishing shot with dramatic perspective",
    "medium shot with shallow depth of field, main object centered",
    "isometric 3D style scene with glowing elements",
    "top-down aerial view with geometric patterns",
    "dramatic low-angle shot with rim lighting",
    "macro close-up of the main object with bokeh background",
]

SUJETOS_VISUALES = [
    (["bitcoin", "btc", "crypto", "criptomoneda", "halving"], "una moneda dorada gigante de bitcoin con detalles intrincados"),
    (["oro", "gold", "plata", "metal", "precioso"], "lingotes de oro brillantes apilados dentro de una bóveda bancaria"),
    (["inflacion", "cpi", "precio"], "un carrito de compras lleno sobre un gráfico ascendente"),
    (["acciones", "mercado", "trading", "trader"], "gráficos de velas en múltiples pantallas brillantes"),
    (["historia", "historico", "pasado"], "documentos financieros vintage y gráficos con textura de papel envejecido"),
    (["educacion", "aprender", "tutorial", "guia", "explicado"], "infografía educativa con gráficos limpios"),
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
def verificar_fed_reciente(dias=15):
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

# ================================================================
# 🔧 REGLA DE ORO: 1 VIDEO CADA 2 DÍAS
# ================================================================
def puede_publicar():
    """Verifica si han pasado al menos 2 días desde la última publicación."""
    try:
        with open(ESTADO_FILE, "r", encoding="utf-8") as f:
            estado = json.load(f)
    except:
        return True
    
    ultima_fecha_str = estado.get("ultima_publicacion_fecha")
    if not ultima_fecha_str:
        return True
    
    try:
        ultima_fecha = datetime.strptime(ultima_fecha_str, "%Y-%m-%d").date()
        hoy = datetime.now(ZoneInfo("America/Mexico_City")).date()
        dias_desde_ultima = (hoy - ultima_fecha).days
        
        if dias_desde_ultima < DIAS_ENTRE_PUBLICACIONES:
            print(f"⏳ Último video publicado hace {dias_desde_ultima} día(s).")
            print(f"⚠️ Se requiere esperar al menos {DIAS_ENTRE_PUBLICACIONES} días entre publicaciones. Saliendo.")
            return False
        return True
    except Exception as e:
        print(f"⚠️ Error verificando fecha: {e}")
        return True

def registrar_publicacion():
    """Registra la fecha de hoy como la última publicación exitosa."""
    try:
        with open(ESTADO_FILE, "r", encoding="utf-8") as f:
            estado = json.load(f)
    except:
        estado = {}
    
    hoy = datetime.now(ZoneInfo("America/Mexico_City")).strftime("%Y-%m-%d")
    estado["ultima_publicacion_fecha"] = hoy
    
    with open(ESTADO_FILE, "w", encoding="utf-8") as f:
        json.dump(estado, f, indent=2, ensure_ascii=False)

# ================================================================
# 📊 ANÁLISIS SEMANAL DE TRENDS
# ================================================================
def analizar_trends_semanal_largos():
    temas_pub = cargar_temas_publicados()
    hoy = datetime.now(ZoneInfo("America/Mexico_City")).date()
    temas_recientes = []
    for t in temas_pub:
        try:
            fecha_tema = datetime.strptime(t["fecha"], "%Y-%m-%d").date()
            if (hoy - fecha_tema).days <= 45:
                temas_recientes.append(t["tema"])
        except:
            continue
    temas_text = "\n".join(temas_recientes[:10]) if temas_recientes else "Ninguno"
    
    prompt = f"""
Eres un ANALISTA DE TRENDS VIRALES y EXPERTO SEO para videos de YouTube en ESPAÑOL (7-9 minutos).
FECHA ACTUAL: {hoy.strftime("%B %d, %Y")}
🚫 PROHIBICIÓN CRÍTICA: NO te enfoques en Federal Reserve, Fed rate, FOMC, Jerome Powell. Enfócate en contenido educativo e histórico DIVERSO.
TEMAS PUBLICADOS RECIENTEMENTE (evitar repetir):
{temas_text}
🎯 TU TAREA: Genera 5 temas de video DIVERSOS para contenido LONG-FORM (7-9 min).
MIX DE CONTENIDO: 40% Educativo, 35% Histórico, 15% Análisis, 10% Noticias importantes.
Devuelve JSON:
{{
    "trending_topics": [
        {{
            "topic": "...",
            "category": "...",
            "why_trending": "...",
            "viral_score": 9,
            "hook": "...",
            "seo_keywords": ["...", "..."]
        }}
    ],
    "best_topic_this_week": "...",
    "high_volume_keywords": ["...", "..."]
}}
"""
    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
    payload = {"model": "deepseek-chat", "messages": [{"role": "user", "content": prompt}], "temperature": 0.8, "max_tokens": 1500, "response_format": {"type": "json_object"}}
    
    try:
        print("📊 Analizando trends semanales...")
        r = requests.post(url, headers=headers, json=payload, timeout=90)
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"].strip()
        if "```json" in content:
            content = content.replace("```json", "").replace("```", "").strip()
        inicio, fin = content.find("{"), content.rfind("}")
        if inicio != -1 and fin != -1:
            trends = json.loads(content[inicio:fin+1])
            with open(TRENDS_FILE, "w", encoding="utf-8") as f:
                json.dump(trends, f, indent=2, ensure_ascii=False)
            print(f"   ✅ Mejor tema: {trends.get('best_topic_this_week', 'N/A')}")
            return trends
        return None
    except Exception as e:
        print(f"⚠️ Error analizando trends: {e}")
        return None

# ================================================================
# 🎬 GENERAR IDEA DE VIDEO
# ================================================================
def generar_idea_video_largo(tipo, fecha_actual, trends_data=None):
    categoria_seleccionada, tema_sugerido = seleccionar_categoria()
    print(f"📚 Categoría: {categoria_seleccionada.upper()}")
    print(f"📝 Tema: {tema_sugerido}")
    
    fed_prohibida = verificar_fed_reciente(dias=15)
    fed_instruction = "🚫 CRÍTICO: NO menciones Federal Reserve, Fed rate, FOMC, Jerome Powell.\n" if fed_prohibida else ""
    
    seo_keywords = trends_data.get("high_volume_keywords", []) if trends_data and "high_volume_keywords" in trends_data else []
    keywords_text = ", ".join(seo_keywords[:5]) if seo_keywords else "Bitcoin, crypto, oro, inversión"
    
    prompt = f"""
Eres un ESTRATEGA DE CONTENIDO VIRAL y EXPERTO SEO para videos de YouTube en ESPAÑOL (7-9 minutos).
FECHA: {fecha_actual}
CATEGORÍA: {categoria_seleccionada.upper()}
TEMA: {tema_sugerido}
{fed_instruction}
🎯 KEYWORDS SEO: {keywords_text}
🚫 REGLA DE IDIOMA: DEBES RESPONDER COMPLETAMENTE EN ESPAÑOL. NO USES INGLÉS.
Genera 5 IDEAS DE VIDEO LONG-FORM optimizadas para SEO y viralidad.
REQUISITOS:
✅ Título: 60-70 caracteres (SEO optimizado, keyword al inicio)
✅ 1 emoji máximo
✅ Keyword PRIMARIA al inicio (primeras 3 palabras)
✅ Crear CURIOSIDAD
✅ Usar POWER WORDS: Completo, Definitivo, Verdad, Guía, Análisis, Secreto
✅ NO usar Federal Reserve / Fed / FOMC / Powell
✅ Adecuado para video de 7-9 minutos
✅ Coincidir con categoría: {categoria_seleccionada}
Devuelve JSON:
{{
    "best_idea": {{
        "title": "Título final (60-70 chars, EN ESPAÑOL)",
        "hook_30sec": "Primeros 30 segundos (EN ESPAÑOL)",
        "description": "Qué aprenderán los viewers (EN ESPAÑOL)",
        "formula_used": "Nombre de fórmula",
        "psychology_trigger": "curiosity/education",
        "type": "{categoria_seleccionada}",
        "seo_keywords": ["kw1", "kw2", "kw3"]
    }},
    "all_ideas": [
        {{"title": "...", "hook_30sec": "...", "seo_score": 9}}
    ]
}}
"""
    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
    payload = {"model": "deepseek-chat", "messages": [{"role": "user", "content": prompt}], "temperature": 0.9, "max_tokens": 1200, "response_format": {"type": "json_object"}}
    
    for intento in range(3):
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=90)
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"].strip()
            if "```json" in content:
                content = content.replace("```json", "").replace("```", "").strip()
            inicio, fin = content.find("{"), content.rfind("}")
            if inicio != -1 and fin != -1:
                result = json.loads(content[inicio:fin+1])
                titulo_gen = result.get("best_idea", {}).get("title", "").lower()
                if fed_prohibida and any(p in titulo_gen for p in PALABRAS_ANTI_FED):
                    if intento < 2:
                        continue
                return result
        except Exception as e:
            if intento < 2:
                time.sleep(5)
    return None

# ================================================================
# 📝 GENERAR GUION LARGO
# ================================================================
def generar_guion_largo(tipo, fecha_actual, idea=None):
    titulos_pub = cargar_titulos_publicados()["titulos"][-10:]
    titulos_referencia = "\n".join([f"- {t}" for t in titulos_pub]) if titulos_pub else "Ninguno aún."

    if not idea:
        print("💡 Generando idea...")
        idea_data = generar_idea_video_largo(tipo, fecha_actual)
        if idea_data and "best_idea" in idea_data:
            idea = idea_data["best_idea"]
            print(f"   ✅ Idea: {idea['title']}")
        else:
            idea = {"title": "Guía de Inversión en Bitcoin", "hook_30sec": "Bitcoin está cambiando todo...", "description": "Guía completa", "type": tipo}

    tema_elegido = idea["title"]
    hook_sugerido = idea.get("hook_30sec", "")
    
    fed_prohibida = verificar_fed_reciente(dias=15)
    fed_instruction = "🚫 NO menciones Federal Reserve, Fed rate, FOMC, Jerome Powell.\n" if fed_prohibida else ""
    
    prompt = f"""
Eres un GUIONISTA PROFESIONAL para videos de YouTube en ESPAÑOL (7-9 minutos).
REGLA DE IDIOMA: DEBES RESPONDER COMPLETAMENTE EN ESPAÑOL. NO USES INGLÉS.
IDEA DE VIDEO: "{tema_elegido}"
HOOK: "{hook_sugerido}"
TIPO: {tipo.upper()}
FECHA: {fecha_actual}
{fed_instruction}
REGLA DE FECHA:
🚫 NO uses fechas pasadas como 2020-2024.
✅ Usa año actual: {fecha_actual.split()[-1]}.
✅ Usa "hoy", "esta semana", "recientemente" para eventos recientes.
🎯 INCLUIR 3 LLAMADAS A LA ACCIÓN (CTA) EN EL GUION:
1. DESPUÉS DEL INTRO (0:45-1:00): "Si te gustan los análisis basados en datos y no en hype, suscríbete ahora y activa la campana 🔔"
2. A LA MITAD DEL VIDEO (4:00-4:30): Pregunta reflexiva + invitación a suscribirse
3. AL FINAL (8:30-9:00): Agradecimiento + like + suscripción + teaser del próximo video
ESTRUCTURA DEL GUION (7 bloques, 1300-1500 palabras total):
[HOOK - 0:00] Interrupción de patrón + promesa (100-150 palabras)
[INTRO - 0:30] Contexto y por qué importa (200-250 palabras)
[CAPÍTULO 1 - 1:30] Fundamentos/Background (250-300 palabras)
[CAPÍTULO 2 - 3:30] Análisis Profundo (300-350 palabras)
[CAPÍTULO 3 - 5:30] Insights Avanzados/Solución (300-350 palabras)
[CAPÍTULO 4 - 7:30] Pasos de Acción (250-300 palabras)
[CIERRE - 8:30] Resumen + CTA (150-200 palabras)
TÁCTICAS DE RETENCIÓN:
- "Pero aquí es donde se pone interesante..."
- "Ahora, aquí es donde la mayoría comete un error..."
- "Te mostraré exactamente cómo..."
- "Los datos muestran algo sorprendente..."
- "Esto es de lo que nadie está hablando..."
NÚMEROS: Escribe con LETRAS ("cuatrocientos" no "400")
PROMPTS DE IMAGEN (uno por segmento, debe coincidir con el contenido):
- HOOK: "escena financiera dramática, luces neón urgentes, alto contraste, cinematográfico 8k"
- INTRO: "fondo profesional finanzas, gráficos y datos, neón azul y oro"
- CAPÍTULO 1: "visual educativo, gráficos limpios, gráficos explicativos, cian y oro"
- CAPÍTULO 2: "visuales de análisis detallado, gráficos de datos, profesional, esmeralda y plata"
- CAPÍTULO 3: "visuales orientados a solución, tendencias ascendentes, éxito, acentos dorados"
- CAPÍTULO 4: "visual de pasos de acción, gráficos claros, profesional, verde azulado y ámbar"
- CIERRE: "visual de llamada a la acción, atractivo, dinámico, violeta y naranja"
HASHTAGS (5-8 específicos): Ejemplo "#Bitcoin #Crypto #AnalisisBitcoin #NoticiasCrypto #AnalisisMercado"
TAGS (20-25 keywords, simples, SIN caracteres especiales):
Ejemplos: "minería bitcoin", "trading crypto", "conceptos básicos inversión"
- Separados por coma SOLAMENTE
- SIN #, $, %, &, o cualquier caracter especial
- Cada tag máximo 30 caracteres
- Máximo 4 palabras por tag
- Máximo 25 tags total
TÍTULOS YA PUBLICADOS (NO REPETIR):
{titulos_referencia}
Devuelve JSON:
{{
    "title": "Título 60-70 chars con emoji (EN ESPAÑOL, SIN Fed)",
    "alternative_title": "Alternativa (EN ESPAÑOL)",
    "keywords": ["kw1", "kw2", "kw3"],
    "description": "Descripción completa con capítulos y hashtags (EN ESPAÑOL)",
    "tags": "20-25 tags simples separados por coma (SIN caracteres especiales)",
    "dynamic_hashtags": "#Bitcoin #Crypto #AnalisisBitcoin",
    "script": "Guion completo 1300-1500 palabras con 7 bloques marcados (EN ESPAÑOL)",
    "segments": [
        {{"block": "HOOK", "text": "texto (~100-150 palabras, EN ESPAÑOL)", "image_prompt": "escena financiera dramática", "timestamp": "0:00"}},
        {{"block": "INTRO", "text": "texto (~200-250 palabras, EN ESPAÑOL)", "image_prompt": "fondo profesional finanzas", "timestamp": "0:30"}},
        {{"block": "CAPÍTULO 1", "text": "texto (~250-300 palabras, EN ESPAÑOL)", "image_prompt": "visual educativo gráficos", "timestamp": "1:30"}},
        {{"block": "CAPÍTULO 2", "text": "texto (~300-350 palabras, EN ESPAÑOL)", "image_prompt": "visuales análisis detallado", "timestamp": "3:30"}},
        {{"block": "CAPÍTULO 3", "text": "texto (~300-350 palabras, EN ESPAÑOL)", "image_prompt": "visuales orientados solución", "timestamp": "5:30"}},
        {{"block": "CAPÍTULO 4", "text": "texto (~250-300 palabras, EN ESPAÑOL)", "image_prompt": "visual pasos de acción", "timestamp": "7:30"}},
        {{"block": "CIERRE", "text": "texto (~150-200 palabras, EN ESPAÑOL)", "image_prompt": "visual llamada a la acción", "timestamp": "8:30"}}
    ],
    "cover_words": "2-3 palabras para miniatura",
    "thumbnail_prompt": "Bitcoin iluminación dramática, amarillo y rojo sobre negro, espacio para texto"
}}
"""
    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
    payload = {"model": "deepseek-chat", "messages": [{"role": "user", "content": prompt}], "temperature": 0.8, "max_tokens": 8192, "response_format": {"type": "json_object"}}
    
    for intento in range(3):
        try:
            print(f"🔄 Generando guion (intento {intento+1}/3)...")
            r = requests.post(url, headers=headers, json=payload, timeout=180)
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"].strip()
            if "```json" in content:
                content = content.replace("```json", "").replace("```", "").strip()
            inicio, fin = content.find("{"), content.rfind("}")
            if inicio != -1 and fin != -1:
                json_str = content[inicio:fin+1]
                open_braces = json_str.count('{')
                close_braces = json_str.count('}')
                if open_braces > close_braces:
                    json_str += '}' * (open_braces - close_braces)
                open_brackets = json_str.count('[')
                close_brackets = json_str.count(']')
                if open_brackets > close_brackets:
                    json_str += ']' * (open_brackets - close_brackets)
                
                try:
                    result = json.loads(json_str)
                except json.JSONDecodeError:
                    import json5
                    result = json5.loads(json_str)
            else:
                raise ValueError("No se encontró JSON")
            
            guion_texto = result.get("script", "")
            palabras = len(re.findall(r'\w+', guion_texto))
            print(f"📊 Palabras del guion: {palabras}")
            
            if "thumbnail_prompt" not in result:
                result["thumbnail_prompt"] = "Bitcoin iluminación dramática, amarillo y rojo sobre negro"
            if "dynamic_hashtags" not in result:
                result["dynamic_hashtags"] = ""
            
            for seg in result.get("segments", []):
                if not seg.get("image_prompt") or len(seg["image_prompt"].split()) < 5:
                    seg["image_prompt"] = "escena financiera cinematográfica, iluminación neón, hiperrealista, 8k"
                if "timestamp" not in seg:
                    seg["timestamp"] = "0:00"
            
            return result, tema_elegido, idea.get("description", "Análisis financiero")
        except Exception as e:
            print(f"❌ Intento {intento+1}/3 falló: {e}")
            if intento < 2:
                time.sleep(10)
    
    print("❌ Error generando guion")
    sys.exit(1)

# ================================================================
# 🎨 GENERAR IMAGEN CON CLOUDFLARE AI (CON DETECCIÓN 429)
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
        
        # 🔧 DETECCIÓN EXPLÍCITA DE LÍMITE DE TASAS (429)
        if r.status_code == 429:
            print("⚠️ Cloudflare API rate limit (429 Too Many Requests). Usando Pexels como respaldo.")
            return None
            
        r.raise_for_status()
        data = r.json()
        if data.get("success") and "result" in data and "image" in data["result"]:
            with open(salida_path, "wb") as f:
                f.write(base64.b64decode(data["result"]["image"]))
            return salida_path
    except Exception as e:
        print(f"⚠️ Error Cloudflare AI: {e}")
    return None

# ================================================================
# 🖼️ GENERAR IMAGEN POR SEGMENTO (CLOUDFLARE → PEXELS)
# ================================================================
def generar_imagen_segmento(prompt, tema="", bloque=""):
    global _used_image_urls
    
    # 🔧 Solo 2 intentos de Cloudflare para evitar saturar la API
    for intento in range(2):
        cf_path = f"temp_cf_seg_{intento}.jpg"
        img_path = generar_imagen_cloudflare(prompt, cf_path)
        if img_path and os.path.exists(img_path):
            print(f"   ✅ Cloudflare AI generó imagen (intento {intento+1})")
            _used_image_urls.add(f"cf_{intento}")
            return img_path
        if intento == 0:
            print(f"   🔄 Cloudflare falló, reintentando una vez más...")
            time.sleep(5)
    
    print("   ⚠️ Cloudflare no disponible, usando Pexels...")
    img_url = generar_imagen_horizontal(prompt, tema=tema, bloque=bloque, intentos=5)
    if img_url:
        return img_url
    
    print("   ⚠️ Pexels también falló, usando fondo sólido")
    return generar_fondo_solido()

# ================================================================
# 🖼️ GENERAR IMAGEN HORIZONTAL (PEXELS - RESPALDO)
# ================================================================
def generar_imagen_horizontal(prompt, tema="", bloque="", intentos=5):
    global _used_image_urls
    keyword_map = {
        "HOOK": "crisis financiera urgente alerta roja",
        "INTRO": "fondo profesional finanzas gráficos",
        "CHAPTER 1": "gráficos financieros educativos datos",
        "CAPÍTULO 1": "gráficos financieros educativos datos",
        "CHAPTER 2": "análisis detallado gráficos datos",
        "CAPÍTULO 2": "análisis detallado gráficos datos",
        "CHAPTER 3": "solución éxito tendencia ascendente",
        "CAPÍTULO 3": "solución éxito tendencia ascendente",
        "CHAPTER 4": "pasos de acción estrategia planificación",
        "CAPÍTULO 4": "pasos de acción estrategia planificación",
        "CLOSE": "llamada a la acción profesional",
        "CIERRE": "llamada a la acción profesional",
        "bitcoin": "bitcoin criptomoneda trading",
        "crash": "crash mercado bursátil gráfico rojo",
        "oro": "lingotes oro riqueza lujo",
        "crypto": "tecnología blockchain criptomoneda",
        "trading": "gráficos trading velas",
        "analysis": "análisis financiero datos gráficos",
        "history": "documentos financieros vintage históricos",
        "education": "infografía educativa gráficos limpios",
    }
    base_query = "finanzas negocios bolsa gráficos"
    prompt_lower = prompt.lower()
    if bloque and bloque in keyword_map:
        base_query = keyword_map[bloque]
    else:
        for key, value in keyword_map.items():
            if key in prompt_lower:
                base_query = value
                break

    modifiers = ["fondo abstracto oscuro", "luces neón brillantes", "iluminación cinematográfica dramática", "detalle macro close up", "minimalista limpio", "colores vibrantes alto contraste"]
    fallback_queries = [
        f"{base_query} {random.choice(modifiers)}",
        f"{base_query} {random.choice(modifiers)}",
        f"abstracto {base_query.split()[0] if base_query else 'finanzas'} oscuro",
        "gráficos trading bolsa neón",
        "blockchain criptomoneda abstracto"
    ]
    
    for intento in range(intentos):
        current_query = fallback_queries[intento % len(fallback_queries)]
        random_page = random.randint(1, 5)
        url = f"https://api.pexels.com/v1/search?query={current_query.replace(' ', '+')}&per_page=5&orientation=landscape&page={random_page}"
        headers = {"Authorization": PEXELS_API_KEY}
        try:
            print(f"   🖼️ Pexels: '{current_query}' (Intento {intento+1}/{intentos})")
            r = requests.get(url, headers=headers, timeout=30)
            if r.status_code == 200:
                data = r.json()
                if data.get("photos") and len(data["photos"]) > 0:
                    for photo in data["photos"][:5]:
                        img_url = photo["src"].get("landscape") or photo["src"].get("original")
                        if img_url in _used_image_urls:
                            continue
                        _used_image_urls.add(img_url)
                        print(f"   ✅ Imagen única encontrada: {photo.get('photographer', 'Unknown')}")
                        return img_url
        except Exception as e:
            print(f"   ⚠️ Error: {e}")
        if intento < intentos - 1:
            time.sleep(6)
    return None

def generar_fondo_solido(color=(20, 20, 50), ancho=1280, alto=720):
    img = Image.new('RGB', (ancho, alto), color)
    path = f"temp_fondo_{random.randint(1000,9999)}.jpg"
    img.save(path)
    return path

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
            print(f"⚠️ Error descargando fuente: {e}")
    rutas = ["Anton.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
    for ruta in rutas:
        if os.path.exists(ruta):
            return ruta
    return None

# ================================================================
# 🖼️ MINIATURA PROFESIONAL ULTRA-LLAMATIVA
# ================================================================
def crear_miniatura_profesional(prompt_miniatura, texto_portada, salida="miniatura_largo_es.jpg"):
    try:
        print("🖼️ Generando miniatura ultra-llamativa...")
        prompt_super = f"{prompt_miniatura}, ultra high contrast, extreme close-up, vibrant neon colors (yellow #FFD700 and red #FF0000), professional YouTube thumbnail style, space for BIG BOLD TEXT on right side, eye-catching, viral thumbnail design, 8k resolution, highly detailed, no text in image, no watermark"
        
        # 🔧 Solo 2 intentos de Cloudflare para evitar 429
        cf_path = None
        for intento in range(2):
            cf_path = f"temp_cf_thumb_{intento}.jpg"
            img_path = generar_imagen_cloudflare(prompt_super, cf_path)
            if img_path and os.path.exists(img_path):
                print(f"   ✅ Cloudflare AI generó miniatura (intento {intento+1}/2)")
                break
            if intento == 0:
                print(f"   🔄 Cloudflare intento 1 falló, reintentando...")
                time.sleep(5)
        
        if not cf_path or not os.path.exists(cf_path):
            print("   ⚠️ Cloudflare no disponible, usando Pexels...")
            fondo_url = generar_imagen_horizontal(prompt_super, tema=texto_portada, intentos=5)
            if fondo_url and fondo_url.startswith("http"):
                try:
                    r = requests.get(fondo_url, timeout=30)
                    r.raise_for_status()
                    img_path = "temp_thumb_pexels.jpg"
                    with open(img_path, "wb") as f:
                        f.write(r.content)
                except:
                    img_path = generar_fondo_solido(color=(10, 10, 25))
            else:
                img_path = generar_fondo_solido(color=(10, 10, 25))
        else:
            img_path = cf_path
        
        img = Image.open(img_path)
        img = ImageOps.fit(img, (1280, 720), Image.Resampling.LANCZOS)
        draw = ImageDraw.Draw(img)
        
        texto = texto_portada.upper().strip()
        palabras = texto.split()
        if len(palabras) > 5:
            texto = ' '.join(palabras[:5])
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
            if ancho_max <= 1100 and alto_total <= 500:
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
            draw.text((x, y), linea, fill='black', font=font)
        
        for i, linea in enumerate(lineas):
            bbox = draw.textbbox((0, 0), linea, font=font)
            text_w = bbox[2] - bbox[0]
            x = 1280 - text_w - 60
            y = y_inicio + i * alto_linea
            draw.text((x, y), linea, fill=(255, 215, 0), font=font)
            draw.text((x-2, y), linea, fill=(255, 230, 100), font=font)
            draw.text((x+2, y), linea, fill=(255, 230, 100), font=font)
        
        draw.rectangle([(1210, 40), (1270, 680)], outline=(255, 50, 50), width=6)
        draw.rectangle([(1220, 50), (1260, 670)], outline=(255, 200, 0), width=2)
        
        img.save(salida, quality=95, optimize=True)
        print(f"✅ Miniatura ultra-llamativa creada: {salida}")
        print(f"   Texto: '{texto}' (TAMAÑO: {size}px)")
        print(f"   Colores: Amarillo Dorado (#FFD700) con borde rojo")
        return salida
    except Exception as e:
        print(f"⚠️ Error en miniatura: {e}")
        import traceback
        traceback.print_exc()
        return None

# ================================================================
# 📝 SUBTÍTULOS
# ================================================================
def agregar_subtitulos_con_pil_16_9(imagen_path, texto, salida_path):
    try:
        img = Image.open(imagen_path)
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
        except:
            try:
                font = ImageFont.truetype("arial.ttf", 28)
            except:
                font = ImageFont.load_default()
        palabras = texto.split()
        if len(palabras) > 20:
            texto_sub = ' '.join(palabras[:20])
        else:
            texto_sub = texto
        if len(texto_sub) > 60:
            mitad = len(texto_sub) // 2
            espacio = texto_sub.find(' ', mitad - 10)
            if espacio == -1:
                espacio = mitad
            linea1 = texto_sub[:espacio]
            linea2 = texto_sub[espacio+1:]
            lineas = [linea1, linea2]
        else:
            lineas = [texto_sub]
        y_base = 720 - 80 - (len(lineas) - 1) * 35
        for i, linea in enumerate(lineas):
            bbox = draw.textbbox((0, 0), linea, font=font)
            ancho = bbox[2] - bbox[0]
            x = (1280 - ancho) // 2
            y = y_base + i * 35
            draw.text((x+2, y+2), linea, fill='black', font=font)
            draw.text((x, y), linea, fill='white', font=font)
        img.save(salida_path)
        return salida_path
    except Exception as e:
        print(f"⚠️ Error en subtítulos: {e}")
        return imagen_path

# ================================================================
# 🎙️ GENERAR AUDIO
# ================================================================
def generar_audio(texto, index):
    global CONFIG_VOZ_ACTUAL
    texto_limpio = re.sub(r'[^a-zA-ZáéíóúüñÁÉÍÓÚÜÑ0-9\s.,;:!?¿¡\'\"]', '', texto)
    texto_limpio = re.sub(r'\s+', ' ', texto_limpio).strip()
    filename = f"audio_largo_es_{index}.mp3"
    voz = CONFIG_VOZ_ACTUAL["voz"]
    rate = CONFIG_VOZ_ACTUAL["velocidad"]
    pitch = CONFIG_VOZ_ACTUAL["tono"]
    async def _gen():
        communicate = edge_tts.Communicate(texto_limpio, voz, rate=rate, pitch=pitch)
        await communicate.save(filename)
    try:
        asyncio.run(_gen())
        return filename
    except Exception as e:
        print(f"❌ Error audio: {e}")
        return None

# ================================================================
# 📺 CAPÍTULOS VISUALES
# ================================================================
def crear_capitulo_visual_pil(titulo_capitulo, timestamp, duracion=3, ancho=1280, alto=720):
    try:
        img = Image.new('RGBA', (ancho, alto), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        texto = f"{timestamp} - {titulo_capitulo.upper()}"
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
        except:
            font = ImageFont.load_default()
        bbox = draw.textbbox((0, 0), texto, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        x = 20
        y = 15
        padding = 8
        overlay = Image.new('RGBA', (ancho, alto), (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        overlay_draw.rectangle([x - padding, y - padding, x - padding + text_w + padding * 2, y - padding + text_h + padding * 2], fill=(0, 0, 0, 160))
        img = Image.alpha_composite(img, overlay)
        draw = ImageDraw.Draw(img)
        draw.text((x+1, y+1), texto, fill='black', font=font)
        draw.text((x, y), texto, fill='white', font=font)
        temp_path = f"temp_capitulo_es_{timestamp.replace(':', '')}.png"
        img.save(temp_path)
        clip = ImageClip(temp_path, duration=duracion, transparent=True)
        clip = clip.crossfadein(0.3).crossfadeout(0.3)
        return clip
    except Exception as e:
        print(f"⚠️ Error capítulo: {e}")
        return None

# ================================================================
# 📣 CTA FINAL
# ================================================================
def crear_cta_final_pil(duracion=3, ancho=1280, alto=720):
    try:
        img = Image.new('RGB', (ancho, alto), (15, 15, 20))
        draw = ImageDraw.Draw(img)
        texto = "🔴 SUSCRÍBETE"
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 40)
        except:
            font = ImageFont.load_default()
        bbox = draw.textbbox((0, 0), texto, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        x = (ancho - text_w) // 2
        y = (alto - text_h) // 2
        for dx, dy in [(-2, -2), (-2, 2), (2, -2), (2, 2)]:
            draw.text((x + dx, y + dy), texto, fill='black', font=font)
        draw.text((x, y), texto, fill=(255, 50, 50), font=font)
        temp_path = "temp_cta_es.png"
        img.save(temp_path)
        clip = ImageClip(temp_path, duration=duracion)
        clip = clip.crossfadein(0.5)
        return clip
    except Exception as e:
        print(f"⚠️ Error CTA: {e}")
        return None

# ================================================================
# 🎵 MÚSICA
# ================================================================
FONDOS_DISPONIBLES = ["The Ascent.mp3", "Binary Pulse.mp3", "Peak Momentum.mp3", "Forward Momentum.mp3"]

def seleccionar_fondo_disponible(estado):
    fondos_disponibles = []
    for root, dirs, files in os.walk("."):
        if "/." in root or "\\." in root:
            continue
        for file in files:
            if file.lower() in [f.lower() for f in FONDOS_DISPONIBLES]:
                fondos_disponibles.append(os.path.join(root, file))
    if not fondos_disponibles:
        print("️ No se encontró música de fondo.")
        return None
    ultimo_fondo = estado.get("ultimo_fondo")
    if ultimo_fondo and ultimo_fondo in fondos_disponibles:
        fondos_disponibles.remove(ultimo_fondo)
    seleccionada = random.choice(fondos_disponibles) if fondos_disponibles else random.choice(FONDOS_DISPONIBLES)
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
        json.dump({"ultimo_fondo": estado.get("ultimo_fondo"), "publicaciones_hoy": estado.get("publicaciones_hoy")}, f, indent=2, ensure_ascii=False)

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

def titulo_ya_publicado(titulo):
    data = cargar_titulos_publicados()
    titulo_norm = titulo.lower().strip()
    for t in data["titulos"]:
        t_norm = t.lower().strip()
        if titulo_norm == t_norm:
            return True
        palabras1 = set(re.findall(r'\w+', titulo_norm))
        palabras2 = set(re.findall(r'\w+', t_norm))
        if len(palabras1) > 3 and len(palabras2) > 3:
            interseccion = palabras1.intersection(palabras2)
            similitud = len(interseccion) / min(len(palabras1), len(palabras2))
            if similitud > 0.7:
                return True
    return False

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
    data["temas"].append({"tema": tema, "tipo": tipo, "fecha": datetime.now(ZoneInfo("America/Mexico_City")).strftime("%Y-%m-%d")})
    if len(data["temas"]) > 200:
        data["temas"] = data["temas"][-200:]
    with open(TEMAS_PUBLICADOS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def tema_ya_publicado(tema, dias=45):
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
# 🏷️ SANITIZAR TAGS
# ================================================================
def sanitizar_hashtags(hashtags_str, max_tags=8):
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
    return " ".join(cleaned[:max_tags])

def sanitizar_tags(tags_str, max_tags=25, max_chars=500):
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
# 🎬 MONTAR VIDEO LARGO CON EFECTOS MEJORADOS
# ================================================================
def montar_video_largo(recursos, fondo_path, salida="largo_capital_es.mp4", capitulos=None):
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
        
        try:
            if img_url.startswith("http"):
                try:
                    r = requests.get(img_url, timeout=30)
                    r.raise_for_status()
                    img_path = f"temp_largo_es_{i}.jpg"
                    with open(img_path, "wb") as f:
                        f.write(r.content)
                except Exception as e:
                    print(f"⚠️ Falló descarga imagen {i}: {e}")
                    img_path = generar_fondo_solido()
            else:
                img_path = img_url
            
            img = Image.open(img_path)
            img = ImageOps.fit(img, (1280, 720), Image.Resampling.LANCZOS)
            img.save(img_path)
            
            img_sub_path = f"temp_largo_sub_es_{i}.jpg"
            img_path = agregar_subtitulos_con_pil_16_9(img_path, texto, img_sub_path)
            
            video_clip = ImageClip(img_path).set_duration(duracion)
            
            # ZOOMS MÁS AGRESIVOS
            if bloque == "HOOK":
                video_clip = video_clip.resize(lambda t: 1.4 - 0.8 * min(t/0.5, 1.0))
            elif bloque in ["CAPÍTULO 1", "CAPÍTULO 2", "CAPÍTULO 3"]:
                video_clip = video_clip.resize(lambda t: 1.0 + 0.015 * t)
            elif bloque == "CIERRE":
                video_clip = video_clip.resize(lambda t: 1.0 - 0.015 * min(t/3, 0.1))
            else:
                video_clip = video_clip.resize(lambda t: 1 + 0.02 * t)
            
        except Exception as e:
            print(f"⚠️ Falló imagen {i}: {e}")
            img_path = generar_fondo_solido()
            video_clip = ImageClip(img_path, duration=duracion).resize(lambda t: 1 + 0.015 * t)
        
        if capitulos and i < len(capitulos):
            cap_titulo = capitulos[i].get("bloque", "")
            cap_timestamp = capitulos[i].get("timestamp", f"{i:02d}:00")
            cap_clip = crear_capitulo_visual_pil(cap_titulo, cap_timestamp, duracion=3)
            if cap_clip:
                video_clip = CompositeVideoClip([video_clip, cap_clip])
        
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
    
    cta_clip = crear_cta_final_pil(duracion=3)
    if cta_clip:
        video = concatenate_videoclips([video, cta_clip], method="compose")
        duracion_total += 3
    
    if fondo_path and os.path.exists(fondo_path):
        try:
            fondo_clip = AudioFileClip(fondo_path)
            if fondo_clip.duration < duracion_total:
                veces = int(duracion_total / fondo_clip.duration) + 1
                fondo_clip = concatenate_audioclips([fondo_clip] * veces)
            fondo_clip = fondo_clip.subclip(0, duracion_total).volumex(0.05)
            audio_final = CompositeAudioClip([audio_narracion, fondo_clip])
        except:
            audio_final = audio_narracion
    else:
        audio_final = audio_narracion
    
    video = video.set_audio(audio_final)
    video.write_videofile(salida, fps=24, codec="libx264", audio_codec="aac", threads=4, preset="ultrafast")
    return salida

# ================================================================
# 💰 ENLACES DE AFILIACIÓN
# ================================================================
AFILIACION_CAPITAL_DIGITAL = """
🔗 RECURSOS RECOMENDADOS:
• Binance (compra crypto con 20% descuento en comisiones): https://accounts.binance.com/register?ref=XXXXX
• Ledger Wallet (protege tu crypto): https://shop.ledger.com/?r=XXXXX
• Audible - Audiolibro recomendado este mes: https://www.audible.com/ep/XXXXX

⚠️ Los enlaces de afiliación nos ayudan a mantener el canal. 
Tú no pagas nada extra, pero nos apoyas enormemente.
"""

# ================================================================
# 📤 SUBIR A YOUTUBE
# ================================================================
def subir_a_youtube(video_path, titulo, etiquetas_str, descripcion, miniatura_path=None, dynamic_hashtags="", seo_description=""):
    try:
        creds = Credentials.from_authorized_user_info(YOUTUBE_USER_TOKEN)
        youtube = build("youtube", "v3", credentials=creds)
    except Exception as e:
        print(f"❌ Error autenticación: {e}")
        sys.exit(1)
    
    tags = sanitizar_tags(etiquetas_str, max_tags=25, max_chars=500)
    if len(tags) < 5:
        print("⚠️ No hay suficientes tags válidos. Usando tags de respaldo.")
        tags = ["bitcoin", "crypto", "inversión", "blockchain", "trading", "finanzas", "oro", "criptomonedas", "análisis de mercado", "noticias crypto"][:25]
    
    print(f"\n📝 DIAGNÓSTICO TAGS:")
    print(f"   Total tags: {len(tags)}")
    total_chars = 0
    for i, tag in enumerate(tags, 1):
        print(f"   {i:2}. '{tag}' ({len(tag)} chars)")
        total_chars += len(tag) + 1
    print(f"   Longitud total: {total_chars} chars (límite YouTube: 500)")
    
    hashtags_fijos = "#Finanzas #Inversión #Crypto"
    if dynamic_hashtags:
        dynamic_hashtags = sanitizar_hashtags(dynamic_hashtags, max_tags=6)
        hashtags_final = f"{dynamic_hashtags} {hashtags_fijos}"
    else:
        hashtags_final = hashtags_fijos
    
    disclaimer = "\n\n⚠️ AVISO IMPORTANTE: Este contenido es solo para fines educativos y no constituye asesoramiento financiero, legal o de inversión."
    descripcion_final = f"{descripcion}\n\n{seo_description if seo_description else descripcion}\n\n{AFILIACION_CAPITAL_DIGITAL}\n\n{hashtags_final}\n{disclaimer}"
    
    body = {
        "snippet": {
            "title": titulo[:100],
            "description": descripcion_final[:5000],
            "tags": tags[:25],
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
    print(f"\n✅ Video subido: https://youtu.be/{video_id}")
    
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
        "temp_*.jpg", "temp_*.mp3", "audio_largo_es_*.mp3",
        "temp_thumb*.jpg", "miniatura_largo_es.jpg", "largo_capital_es.mp4",
        "placeholder*.jpg", "temp_*.png", "temp_capitulo_es_*.png",
        "temp_cta_es.png", "temp_fondo_*.jpg", "temp_cf_*.jpg"
    ]
    for patron in patrones:
        for f in glob.glob(patron):
            try:
                os.remove(f)
            except:
                pass
    print("✅ Limpieza completada")

# ================================================================
# 📄 INICIALIZAR JSON
# ================================================================
def inicializar_archivos_json():
    archivos_needed = {
        "temas_largos_es_publicados.json": {"temas": []},
        "titulos_capital_largos_es_publicados.json": {"titulos": []},
        "estado_capital_largos_es.json": {"ultimo_fondo": None, "publicaciones_hoy": None},
        "trends_semanal_largos_es.json": {"trending_topics": [], "best_topic_this_week": ""}
    }
    for archivo, contenido in archivos_needed.items():
        if not os.path.exists(archivo):
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
    print("🎬 Capital Minds - BOT VIDEO LARGO (ESPAÑOL)")
    print("   ✓ Cloudflare AI Thumbnails (Fallback Pexels)")
    print("   ✓ JSON Robusto (Reparación automática)")
    print("   ✓ CTAs Estratégicos (3 por video)")
    print("   ✓ Zooms Agresivos en HOOK")
    print("   ✓ Enlaces de Afiliación")
    print("   ✓ 90% Educativo/Histórico, 10% Noticias")
    print("   ✓ Filtro Anti-Fed: 15 días")
    print("   ✓ TODO EN ESPAÑOL")
    print("="*60)

    tz_mexico = ZoneInfo("America/Mexico_City")
    fecha_actual = datetime.now(tz_mexico)
    fecha_formateada = fecha_actual.strftime("%B %d, %Y")
    print(f"📅 Fecha: {fecha_formateada}")
    
    fed_reciente = verificar_fed_reciente(dias=15)
    if fed_reciente:
        print("🚫 Filtro Anti-Fed: ACTIVO")
    else:
        print("✅ Filtro Anti-Fed: inactivo")
    print("="*60)
    
    if not YOUTUBE_USER_TOKEN:
        print("❌ Falta YOUTUBE_USER_TOKEN_CAPITAL"); sys.exit(1)
    if not DEEPSEEK_API_KEY:
        print("❌ Falta DEEPSEEK_API_KEY"); sys.exit(1)
    if not PEXELS_API_KEY:
        print("❌ Falta PEXELS_API_KEY"); sys.exit(1)
    
    # 🔧 VERIFICACIÓN ESTRICTA DE 1 VIDEO CADA 2 DÍAS
    if not puede_publicar():
        sys.exit(0)
    
    trends_data = None
    try:
        with open(TRENDS_FILE, "r", encoding="utf-8") as f:
            trends_data = json.load(f)
    except:
        trends_data = analizar_trends_semanal_largos()
    
    tipo, tema_sugerido = seleccionar_categoria()
    print(f"📌 Tipo de Contenido: {tipo.upper()}")
    print(f"📝 Tema: {tema_sugerido}")
    
    estado = cargar_estado()
    fondo_path = seleccionar_fondo_disponible(estado)
    paleta_video = random.choice(PALETAS_VIDEO)
    print(f"🎨 Paleta: {paleta_video}")
    
    print("💡 Generando idea de video...")
    idea_data = generar_idea_video_largo(tipo, fecha_formateada, trends_data)
    if idea_data and "best_idea" in idea_data:
        idea = idea_data["best_idea"]
        print(f"   ✅ Idea: {idea['title']}")
    else:
        idea = None
    
    guion, tema, _ = generar_guion_largo(tipo, fecha_formateada, idea)
    titulo = guion["title"]
    descripcion = guion["description"]
    tags_str = guion.get("tags", "")
    segmentos = guion["segments"]
    palabras_portada = guion.get("cover_words", "MIRAR ESTO")
    prompt_miniatura = guion.get("thumbnail_prompt", "")
    dynamic_hashtags = guion.get("dynamic_hashtags", "")
    seo_description = guion.get("seo_optimized_description", "")
    
    print(f"🏷️ Título: {titulo}")
    print(f"🏷️ Hashtags: {dynamic_hashtags}")
    
    capitulos = [{"bloque": seg.get("block", "CAPÍTULO"), "timestamp": seg.get("timestamp", "0:00")} for seg in segmentos]
    
    print("\n🖼️ Generando imágenes por segmento...")
    imagenes_generadas = []
    for idx, seg in enumerate(segmentos):
        print(f"🎬 Segmento {idx+1}/{len(segmentos)} - {seg.get('block', '')}")
        prompt_img = seg.get("image_prompt", "")
        bloque = seg.get("block", "")
        img_url = generar_imagen_segmento(prompt_img, tema=tema, bloque=bloque)
        imagenes_generadas.append(img_url)
        if img_url:
            print(f"   ✅ Imagen encontrada")
        else:
            print(f"   ❌ Falló")
        time.sleep(2)

    print("\n🔄 SEGUNDO PASO...")
    def obtener_imagen_disponible(idx, imagenes):
        for i in range(idx - 1, -1, -1):
            if imagenes[i] is not None:
                return imagenes[i]
        for i in range(idx + 1, len(imagenes)):
            if imagenes[i] is not None:
                return imagenes[i]
        return None

    for idx, img_url in enumerate(imagenes_generadas):
        if img_url is None:
            img_disponible = obtener_imagen_disponible(idx, imagenes_generadas)
            if img_disponible:
                imagenes_generadas[idx] = img_disponible
                print(f"   ✅ Segmento {idx+1}: reutilizando imagen")
            else:
                imagenes_generadas[idx] = generar_fondo_solido()
                print(f"   🖼️ Segmento {idx+1}: fondo sólido")

    print("\n🎵 Generando audio...")
    recursos = []
    for idx, seg in enumerate(segmentos):
        print(f"🎬 Audio segmento {idx+1}/{len(segmentos)}")
        audio_path = generar_audio(seg["text"], idx)
        if not audio_path:
            continue
        try:
            dur = AudioFileClip(audio_path).duration
        except:
            dur = 10.0
        recursos.append({"imagen_url": imagenes_generadas[idx], "audio_path": audio_path, "duracion": dur, "texto": seg["text"], "block": seg.get("block", "")})
        time.sleep(2)

    if not recursos:
        print("❌ Sin recursos"); sys.exit(1)
    
    video_path = montar_video_largo(recursos, fondo_path, "largo_capital_es.mp4", capitulos)
    print(f"🎬 Video: {video_path}")
    
    print("🖼️ Generando miniatura...")
    miniatura_path = crear_miniatura_profesional(prompt_miniatura, palabras_portada, "miniatura_largo_es.jpg")
    
    video_id = subir_a_youtube(video_path, titulo, tags_str, descripcion, miniatura_path, dynamic_hashtags, seo_description)
    
    guardar_titulo_publicado(titulo)
    guardar_tema_publicado(tema, tipo)
    
    # 🔧 REGISTRAR PUBLICACIÓN EXITOSA
    registrar_publicacion()
    guardar_estado(estado)
    limpiar_archivos_temporales()
    
    print(f"\n✅ Publicado: https://youtu.be/{video_id}")
    print(f"📊 Tipo de Contenido: {tipo.upper()}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ Error fatal: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
