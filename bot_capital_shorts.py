import asyncio
from datetime import datetime
import json
import os
import random
import re
import sys
import time
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

CANAL_LINK = "https://www.youtube.com/@CapitalMinds"
ESTADO_FILE = "estado_capital_shorts_en.json"
TITULOS_FILE = "titulos_capital_shorts_en_publicados.json"
TEMAS_PUBLICADOS_FILE = "temas_shorts_en_publicados.json"
TRENDS_FILE = "trends_semanal.json"

ESTADO_FILE_ES = "estado_capital_shorts.json"
TITULOS_FILE_ES = "titulos_capital_shorts_publicados.json"
TEMAS_PUBLICADOS_FILE_ES = "temas_shorts_publicados.json"

META_DIARIA_SHORTS = 3
DIAS_SIN_REPETIR_TEMA = 30

# Variable global para rastrear imágenes usadas y evitar duplicados
_used_image_urls = set()

# ================================================================
# VOZ EN INGLÉS (Jenny - US Female)
# ================================================================
VOZ_FIJA = {"voz": "en-US-JennyNeural", "velocidad": "+10%", "tono": "-1Hz"}
CONFIG_VOZ_ACTUAL = VOZ_FIJA

# ================================================================
# 🎨 VARIEDAD VISUAL (paletas y composiciones)
# ================================================================
PALETAS_VIDEO = [
    "electric cyan and gold neon on dark navy",
    "emerald green and silver on black",
    "violet magenta and orange on deep blue",
    "crimson red and gold on charcoal",
    "teal and amber on dark slate",
    "ice blue and white on midnight black",
]

COMPOSICIONES_BLOQUE = [
    "extreme wide establishing shot",
    "medium shot with shallow depth of field, main object centered",
    "isometric 3D style scene",
    "top-down aerial view",
    "dramatic low-angle shot with rim lighting",
    "macro close-up of the main object with bokeh background",
]

SUJETOS_VISUALES = [
    (["bitcoin", "btc", "crypto", "cryptocurrency", "halving"], "a giant physical golden bitcoin coin"),
    (["gold", "silver", "metal"], "shiny gold bars stacked inside a bank vault"),
    (["fed", "reserve", "rate", "interest"], "a monumental central bank building with columns"),
    (["inflation", "cpi", "price"], "a shopping cart full of groceries over a rising chart"),
    (["etf", "fund", "institutional"], "a modern glass stock exchange building with digital tickers"),
    (["stock", "market", "trading", "trader"], "candlestick trading charts on multiple glowing screens"),
    (["scam", "fraud", "hack", "ftx", "collapse", "crash", "ponzi"], "a dark maze of falling dominoes made of coins"),
    (["regulation", "law", "sec", "mica", "legal"], "a wooden gavel over legal documents and a glowing blockchain"),
    (["ethereum", "solana", "layer", "blockchain", "technology", "rollup"], "a glowing network of interconnected blockchain nodes"),
    (["oil", "energy", "mining"], "oil barrels and mining rigs under dramatic light"),
    (["dollar", "forex", "currency"], "floating dollar bills and currency symbols in the air"),
    (["house", "real estate", "mortgage"], "a miniature house model over financial charts"),
    (["psychology", "fear", "greed", "panic"], "a human head silhouette filled with rising and falling charts"),
    (["war", "geopolitic", "country", "china", "russia"], "a world map with glowing trade routes and tension lines"),
]

def detectar_sujeto_visual(texto_ref):
    t = (texto_ref or "").lower()
    for keywords, sujeto in SUJETOS_VISUALES:
        if any(k in t for k in keywords):
            return sujeto
    return "a cinematic financial scene with glowing charts, coins and data visualizations"

# ================================================================
# 📊 ANÁLISIS SEMANAL DE TRENDS CON DEEPSEEK
# ================================================================
def analizar_trends_semanal():
    """
    Usa DeepSeek para analizar qué temas están trending semanalmente
    """
    
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
    
    prompt = f"""
You are a VIRAL TREND ANALYST for YouTube Shorts in finance/crypto.

CURRENT DATE: September 2024
YOUR TASK: Identify VIRAL TOPICS for this week.

📊 RECENTLY PUBLISHED TOPICS (avoid repeating):
{chr(10).join(temas_recientes[:10]) if temas_recientes else "None"}

🔥 TRENDING NOW (September 2024):

Based on current events, these topics are HOT:
1. Bitcoin price reaction to Fed rate cut
2. Federal Reserve interest rate decisions
3. Bitcoin vs Gold performance comparison
4. Crypto market volatility after economic news
5. Inflation data (CPI) impact on crypto
6. Central banks buying gold reserves
7. Bitcoin halving aftermath effects
8. Altcoin season predictions
9. Crypto regulation updates
10. DeFi and staking yields

📈 HIGH-SEARCH-VOLUME KEYWORDS:
- "Bitcoin price" (most searched)
- "Cryptocurrency"
- "Crypto news"
- "Bitcoin crash"
- "Fed rate cut"
- "Gold price"
- "Inflation"
- "Stock market"
- "Crypto scams"
- "Passive income crypto"

YOUR TASK: Generate 10 VIDEO TOPICS for this week.

For each topic provide:
- Topic name
- Why it's trending NOW
- Viral potential (1-10)
- Best format (news/educational/psychology/analysis)
- Suggested hook (first 3 seconds)

Return in JSON:
{{
    "trending_topics": [
        {{
            "topic": "Bitcoin Fed Rate Cut Reaction",
            "why_trending": "Fed just cut rates, Bitcoin reacted +7.7%",
            "viral_score": 9,
            "best_format": "news",
            "hook": "Bitcoin just did THIS after Fed announcement..."
        }},
        ...
    ],
    "topics_to_avoid": ["topic1", "topic2"],
    "best_topic_this_week": "Bitcoin Fed Rate Cut Reaction"
}}
"""
    
    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 1500,
        "response_format": {"type": "json_object"}
    }
    
    try:
        print("📊 Analyzing weekly trends with DeepSeek...")
        r = requests.post(url, headers=headers, json=payload, timeout=90)
        r.raise_for_status()
        data = r.json()
        content = data["choices"][0]["message"]["content"]
        
        inicio = content.find("{")
        fin = content.rfind("}")
        json_str = content[inicio:fin+1]
        
        trends = json.loads(json_str)
        
        with open(TRENDS_FILE, "w", encoding="utf-8") as f:
            json.dump(trends, f, indent=2, ensure_ascii=False)
        
        print(f"   ✅ Best topic this week: {trends.get('best_topic_this_week', 'N/A')}")
        return trends
        
    except Exception as e:
        print(f"⚠️ Error analyzing trends: {e}")
        return None

# ================================================================
# 🎬 GENERAR IDEA DE VIDEO CON FÓRMULAS VIRALES
# ================================================================
def generar_idea_video(tipo, fecha_actual, trends_data=None):
    """
    PROMPT MEJORADO: Enfocado en viralidad y CTR alto usando fórmulas probadas
    """
    
    # Si tenemos trends, usar el mejor tema
    tema_sugerido = ""
    if trends_data and "best_topic_this_week" in trends_data:
        tema_sugerido = f"SUGGESTED TOPIC: {trends_data['best_topic_this_week']}\n"
    
    prompt = f"""
You are a VIRAL CONTENT STRATEGIST for YouTube Shorts in finance/crypto.

📅 CURRENT DATE: {fecha_actual}
📊 YOUR GOAL: Generate ideas that get 10,000+ views

{tema_sugerido}
VIRAL TITLE FORMULAS THAT WORK (use these):

FORMULA 1 - FEAR + URGENCY:
"Why [TOPIC] Will CRASH in 24 Hours 🚨"
"WARNING: Don't Buy [CRYPTO] Until You See This"

FORMULA 2 - CURIOSITY GAP:
"The [NUMBER] Secret About [TOPIC] Nobody Talks About"
"What They're NOT Telling You About [NEWS]"

FORMULA 3 - CONTROVERSY:
"[COMMON BELIEF] Is a LIE - Here's Proof"
"Why 90% of People Are WRONG About [TOPIC]"

FORMULA 4 - SPECIFIC NUMBER + PROMISE:
"How I Made $[AMOUNT] with [STRATEGY] in [TIME]"
"[NUMBER] Reasons [TOPIC] Will EXPLODE This Week"

FORMULA 5 - COMPARISON SHOCK:
"[A] vs [B]: The SHOCKING Winner"
"I Tested [X] for 30 Days - Results Surprised Me"

FORMULA 6 - BREAKING NEWS:
"BREAKING: [EVENT] Just Happened"
"[EVENT] EXPOSED: The Truth"

 TRENDING TOPICS RIGHT NOW (September 2024):
- Bitcoin price volatility after Fed rate cut
- Fed interest rate decisions impact on crypto
- Bitcoin vs Gold performance comparison
- Crypto market reactions to economic news
- Inflation data and cryptocurrency
- Central banks buying gold
- Bitcoin halving effects
- Altcoin season predictions
- Crypto scams and how to avoid them
- Passive income with crypto staking

🎯 YOUR TASK: Generate 5 VIDEO IDEAS using the formulas above.

REQUIREMENTS:
✅ Title: 45-60 characters MAX (mobile optimized)
✅ Include 1 emoji (📈⚠️💰)
✅ Create CURIOSITY GAP (don't reveal everything in title)
✅ Use POWER WORDS: SHOCKING, WARNING, SECRET, EXPOSED, TRUTH, PROVEN, BREAKING
✅ AVOID: Generic titles like "Bitcoin Analysis" or "Market Update"

For each idea provide:
- Title (with formula used)
- Hook (first 3 seconds - MUST be SHOCKING)
- Main point (one sentence)
- Why it's viral (psychology trigger: fear/curiosity/greed/urgency)

Then SELECT THE BEST ONE and return in JSON:

{{
    "best_idea": {{
        "title": "Final viral title",
        "hook_3sec": "First 3 seconds text (MUST stop the scroll)",
        "description": "One sentence explanation",
        "formula_used": "Name of formula (e.g., 'Fear + Urgency')",
        "psychology_trigger": "fear/curiosity/controversy/greed/urgency",
        "type": "{tipo}"
    }},
    "all_ideas": [
        {{"title": "...", "hook_3sec": "...", "formula": "...", "viral_score": 9}},
        ...
    ]
}}
"""
    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.8,
        "max_tokens": 1200,
        "response_format": {"type": "json_object"}
    }
    
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=90)
        r.raise_for_status()
        data = r.json()
        content = data["choices"][0]["message"]["content"]
        inicio = content.find("{")
        fin = content.rfind("}")
        json_str = content[inicio:fin+1]
        return json.loads(json_str)
    except Exception as e:
        print(f"⚠️ Error generating ideas: {e}")
        return None

# ================================================================
# 📝 GENERAR GUION CON HOOK DE 3 SEGUNDOS OPTIMIZADO
# ================================================================
def generar_guion_financiero(tipo, idea=None, fecha_actual=None):
    if not fecha_actual:
        fecha_actual = datetime.now(ZoneInfo("America/Mexico_City")).strftime("%B %d, %Y")

    titulos_pub = cargar_titulos_publicados()["titulos"][-10:]
    titulos_referencia = "\n".join([f"- {t}" for t in titulos_pub]) if titulos_pub else "None yet."

    hook_sugerido = idea.get("hook_3sec", "") if idea else ""
    tema_elegido = idea["title"] if idea else "Bitcoin/Fed/Gold Analysis"
    
    prompt = f"""
You are a YouTube Shorts SCRIPTWRITER specializing in finance/crypto.

📌 TOPIC: "{tema_elegido}"
📌 HOOK: "{hook_sugerido}"
📅 DATE: {fecha_actual}

🎬 CRITICAL RULES:

1️⃣ FIRST 3 SECONDS (MOST IMPORTANT - MUST STOP THE SCROLL):
   - Use: SHOCKING statement + Visual urgency
   - Examples:
     * "STOP! Don't buy Bitcoin until you see this..."
     * "WARNING: Your crypto is about to..."
     * "This changes EVERYTHING..."
     * "90% of traders lose money. Here's why..."

2️⃣ STRUCTURE (Exactly 90-110 words):
   [0-3s] HOOK: Shocking statement (10 words)
   [3-10s] PROBLEM: Why this matters NOW (25 words)
   [10-25s] DATA: Facts/numbers/proof (35 words)
   [25-35s] SOLUTION: What to do (25 words)
   [35-40s] CTA: "Follow for more" (5 words)

3️⃣ IMAGE PROMPTS (One per segment - BE SPECIFIC):
   Each prompt MUST match the segment content:
   
   For HOOK: "dramatic financial crisis scene, red emergency lights, urgency, neon yellow and red, cinematic, 8k"
   For PROBLEM: "falling stock charts, red candles, panic, dark background with red glow"
   For DATA: "professional financial data visualization, glowing charts, blue and gold neon"
   For SOLUTION: "upward trending chart, green candles, success, gold accents"
   For CTA: "professional finance background, subtle, dark blue with gold"

4️⃣ THUMBNAIL PROMPT:
   Create a prompt for a HIGH-CTR thumbnail:
   - One dominant subject
   - High contrast (yellow/red on black)
   - Space for 3-5 words of text
   - Example: "Bitcoin coin cracking in half, red lightning, dramatic lighting, black background, space for text on right side"

5️⃣ HASHTAGS (4-6 specific to topic):
   - Include main keyword
   - Mix broad and specific
   - Example for Bitcoin: "#Bitcoin #BTC #CryptoNews #BitcoinPrice #Crypto2024"

6️⃣ TITLE OPTIMIZATION:
   - Keep 50-60 characters
   - Use 1 emoji max
   - Create curiosity gap
   - Use power words

🚫 TITLES ALREADY PUBLISHED (DO NOT REPEAT):
{titulos_referencia}

📤 RETURN JSON:
{{
    "title": "Optimized title (50-60 chars with emoji)",
    "alternative_title": "Second title for A/B testing",
    "keywords": ["keyword1", "keyword2", "keyword3"],
    "hook_description": "Hook for description (first 90 chars)",
    "context_description": "One sentence context",
    "source_story": "Data source (e.g., 'Federal Reserve data')",
    "cover_words": "2-3 WORDS FOR THUMBNAIL (e.g., 'BITCOIN CRASH')",
    "tags": "15-20 tags comma separated",
    "dynamic_hashtags": "#Bitcoin #Crypto #BTC #CryptoNews",
    "segments": [
        {{
            "block": "HOOK",
            "text": "shocking statement (~10 words)",
            "image_prompt": "dramatic crisis scene, red emergency lighting, neon yellow text space, cinematic 8k, vertical 9:16",
            "duration": 3.0
        }},
        {{
            "block": "PROBLEM", 
            "text": "why it matters (~25 words)",
            "image_prompt": "falling charts red candles panic, dark background with red glow, urgent, vertical 9:16",
            "duration": 7.0
        }},
        {{
            "block": "DATA",
            "text": "facts and numbers (~35 words)",
            "image_prompt": "professional financial data charts, glowing blue and gold neon lines, 8k hyperrealistic, vertical 9:16",
            "duration": 15.0
        }},
        {{
            "block": "SOLUTION",
            "text": "what to do (~25 words)",
            "image_prompt": "upward trending chart green candles success, gold accents on dark, optimistic, vertical 9:16",
            "duration": 10.0
        }},
        {{
            "block": "CLOSE",
            "text": "CTA (~5 words)",
            "image_prompt": "professional finance background dark blue subtle gold accents, vertical 9:16",
            "duration": 5.0
        }}
    ],
    "thumbnail_prompt": "Bitcoin crashing down with red lightning, dramatic crisis scene, black background with space for bold text on right, high contrast, YouTube thumbnail style, 16:9"
}}
"""
    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 1200,
        "response_format": {"type": "json_object"}
    }

    for intento in range(6):
        try:
            print(f"🔄 Attempt {intento+1}/6 generating script...")
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
                data = json.loads(json_str, strict=False)
            else:
                raise ValueError("No JSON found")

            if "segments" not in data or len(data["segments"]) != 5:
                raise ValueError("Missing segments")
            
            for seg in data["segments"]:
                if not seg.get("image_prompt") or len(seg["image_prompt"].split()) < 5:
                    seg["image_prompt"] = f"cinematic financial scene about {tema_elegido[:40]}, neon lighting, hyperrealistic, 8k, no people, no text, vertical 9:16"

            texto = ""
            for seg in data["segments"]:
                texto += f"[{seg['block']}] {seg['text']}\n"

            palabras = len(re.findall(r'\w+', texto))
            if palabras < 70 or palabras > 130:
                if palabras > 130:
                    data["segments"] = truncar_segmentos(data["segments"])
                    texto = ""
                    for seg in data["segments"]:
                        texto += f"[{seg['block']}] {seg['text']}\n"
                elif palabras < 70:
                    data["segments"][-1]["text"] += " This is a quick financial insight. Follow for more."
                    texto = ""
                    for seg in data["segments"]:
                        texto += f"[{seg['block']}] {seg['text']}\n"

            titulo = data.get("title", "").strip()
            titulo = re.sub(r'#\w+', '', titulo).strip()
            if titulo_ya_publicado(titulo):
                raise ValueError("Duplicate title")

            tags_raw = data.get("tags", "")
            tags_list = sanitizar_tags(tags_raw)
            keywords = data.get("keywords", [])
            for kw in keywords:
                if kw.lower() not in [t.lower() for t in tags_list]:
                    tags_list.append(kw.lower())
            extras = ["finance", "investing", "economy", "bitcoin", "crypto", "trading", "education"]
            for extra in extras:
                if len(tags_list) < 20 and extra not in tags_list:
                    tags_list.append(extra)
            data["tags"] = ", ".join(tags_list[:20])

            if "thumbnail_prompt" not in data or not data["thumbnail_prompt"]:
                data["thumbnail_prompt"] = "clean professional financial chart, dark background, blue and gold colors, no people, no text, high contrast"

            if "dynamic_hashtags" not in data:
                data["dynamic_hashtags"] = ""

            print(f"   🏷️ Title: {data['title']} ({len(data['title'])} chars)")
            print(f"   📊 Words: {palabras}")
            return data, tema_elegido, tipo
            
        except Exception as e:
            print(f"❌ Attempt {intento+1}/6 failed: {e}")
            if intento < 5:
                time.sleep(10)

    print("❌ ALL ATTEMPTS FAILED.")
    sys.exit(1)

def truncar_segmentos(segments):
    total_palabras = sum(len(seg["text"].split()) for seg in segments)
    if total_palabras <= 110:
        return segments
    objetivo = 110
    factor = objetivo / total_palabras
    nuevos = []
    for seg in segments:
        palabras = seg["text"].split()
        nuevo_largo = max(3, int(len(palabras) * factor))
        nuevas_palabras = palabras[:nuevo_largo]
        nuevos.append({"block": seg["block"], "text": " ".join(nuevas_palabras), "image_prompt": seg.get("image_prompt", ""), "duration": seg.get("duration", 5.0)})
    return nuevos

# ================================================================
# 🏷️ SANITIZAR HASHTAGS Y TAGS
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

def sanitizar_tags(tags_str, max_chars=500):
    if not tags_str:
        return []
    raw_tags = [t.strip() for t in tags_str.split(",") if t.strip()]
    cleaned = []
    for tag in raw_tags:
        clean = re.sub(r'[^a-zA-Z0-9áéíóúüñÁÉÍÓÚÜÑ\s\-]', '', tag).strip()
        if clean and len(clean) > 1:
            cleaned.append(clean)
    cleaned = list(dict.fromkeys(cleaned))
    result = ""
    for tag in cleaned:
        test = result + "," + tag if result else tag
        if len(test) <= max_chars:
            result = test
        else:
            break
    return result.split(",") if result else []

# ================================================================
# 🎵 MÚSICA CORPORATE
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
        print("ℹ️ No music found. Continuing without background music.")
        return None
    ultimo_fondo = estado.get("ultimo_fondo")
    if ultimo_fondo and ultimo_fondo in fondos_disponibles:
        fondos_disponibles.remove(ultimo_fondo)
    seleccionada = random.choice(fondos_disponibles) if fondos_disponibles else None
    if seleccionada:
        estado["ultimo_fondo"] = seleccionada
        print(f"🎵 Selected music: {os.path.basename(seleccionada)}")
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
            titulos_en = json.load(f).get("titulos", [])
    except:
        titulos_en = []
    try:
        with open(TITULOS_FILE_ES, "r", encoding="utf-8") as f:
            titulos_es = json.load(f).get("titulos", [])
    except:
        titulos_es = []
    return {"titulos": list(set(titulos_en + titulos_es))}

def guardar_titulo_publicado(titulo):
    try:
        with open(TITULOS_FILE, "r", encoding="utf-8") as f:
            data_en = json.load(f)
    except:
        data_en = {"titulos": []}
    if titulo not in data_en["titulos"]:
        data_en["titulos"].append(titulo)
        with open(TITULOS_FILE, "w", encoding="utf-8") as f:
            json.dump(data_en, f, indent=2, ensure_ascii=False)

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
            temas_en = json.load(f).get("temas", [])
    except:
        temas_en = []
    try:
        with open(TEMAS_PUBLICADOS_FILE_ES, "r", encoding="utf-8") as f:
            temas_es = json.load(f).get("temas", [])
    except:
        temas_es = []
    return temas_en + temas_es

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
# 🖼️ GENERAR IMAGEN VERTICAL (PEXELS API - OPTIMIZADO CON 5 INTENTOS)
# ================================================================
def generar_imagen_vertical(prompt, tema="", bloque="", intentos=5):
    """
    MEJORADO: 5 intentos, modificadores aleatorios y prevención de imágenes duplicadas.
    """
    global _used_image_urls
    
    # Mapa de palabras clave base según el bloque del guion
    keyword_map = {
        "HOOK": "urgent financial crisis red alert",
        "PROBLEM": "falling stock market crash panic",
        "DATA": "professional financial data charts glowing",
        "SOLUTION": "upward trending chart success growth",
        "CLOSE": "professional finance background subtle",
        "bitcoin": "bitcoin cryptocurrency trading",
        "crash": "stock market crash red chart",
        "gold": "gold bars wealth luxury",
        "fed": "federal reserve bank building",
        "crypto": "cryptocurrency blockchain technology",
        "trading": "trading charts candlestick graph",
        "money": "money cash dollars finance",
        "economy": "economy finance business stock market",
        "investment": "investment portfolio finance growth",
        "panic": "stress business crisis emergency",
        "success": "success growth profit upward chart",
        "warning": "warning alert danger red emergency",
    }
    
    # 1. Obtener palabra clave base
    base_query = "finance business stock market"
    prompt_lower = prompt.lower()
    
    # Priorizar el bloque si existe, luego el tema
    if bloque and bloque in keyword_map:
        base_query = keyword_map[bloque]
    else:
        for key, value in keyword_map.items():
            if key in prompt_lower:
                base_query = value
                break

    # 2. MODIFICADORES ALEATORIOS (Clave para evitar imágenes repetidas)
    modifiers = [
        "abstract dark background", "neon glowing lights", "cinematic dramatic lighting",
        "macro close up detail", "minimalist clean", "vibrant colors high contrast",
        "futuristic technology", "moody atmospheric"
    ]
    
    # 3. Lista de consultas a probar (Base + Modificador aleatorio)
    fallback_queries = [
        f"{base_query} {random.choice(modifiers)}",
        f"{base_query} {random.choice(modifiers)}",
        f"abstract {base_query.split()[0] if base_query else 'finance'} dark",
        "stock market trading charts neon",
        "cryptocurrency bitcoin technology"
    ]
    
    for intento in range(intentos):
        current_query = fallback_queries[intento % len(fallback_queries)]
        
        # Usamos page aleatorio para romper el caché de Pexels
        random_page = random.randint(1, 5)
        url = f"https://api.pexels.com/v1/search?query={current_query.replace(' ', '+')}&per_page=5&orientation=portrait&page={random_page}"
        headers = {"Authorization": PEXELS_API_KEY}
        
        try:
            print(f"   🖼️ Pexels search: '{current_query}' (Intento {intento+1}/{intentos})")
            r = requests.get(url, headers=headers, timeout=30)
            
            if r.status_code == 200:
                data = r.json()
                if data.get("photos") and len(data["photos"]) > 0:
                    photos = data["photos"][:5]
                    
                    for photo in photos:
                        img_url = photo["src"].get("portrait") or photo["src"].get("original")
                        
                        # VERIFICAR SI YA USAMOS ESTA IMAGEN
                        if img_url in _used_image_urls:
                            print(f"   ⚠️ Imagen ya usada, buscando otra...")
                            continue
                        
                        # Verificar que tenga buen color de fondo (oscuro para que resalte el texto)
                        avg_color = photo.get("avg_color", "#000000").lower()
                        # Aceptamos la imagen si no está en la lista de usadas
                        _used_image_urls.add(img_url)
                        print(f"   ✅ Found unique vertical image: {photo.get('photographer', 'Unknown')}")
                        return img_url
                        
        except Exception as e:
            print(f"   ⚠️ Error de conexión: {e}")
            
        # PAUSA MÁS LARGA para evitar caché y rate limits
        if intento < intentos - 1:
            print(f"   ⏳ Esperando 6 segundos antes del siguiente intento...")
            time.sleep(6)
    
    print(f"   ❌ No se encontraron imágenes únicas tras {intentos} intentos.")
    return None

# ================================================================
# 🖼️ GENERAR IMAGEN HORIZONTAL PARA MINIATURAS
# ================================================================
def generar_imagen_horizontal(prompt, tema="", intentos=3):
    search_query = tema if tema else prompt
    
    search_query = re.sub(r'[^a-zA-Z0-9\s]', '', search_query).strip()
    if len(search_query) > 50:
        search_query = search_query[:50]
    if not search_query:
        search_query = "finance business technology"

    fallback_queries = [
        search_query,
        "finance business technology",
        "abstract dark background",
        "stock market charts",
    ]
    
    for intento in range(intentos):
        current_query = fallback_queries[intento % len(fallback_queries)]
        url = f"https://api.pexels.com/v1/search?query={current_query.replace(' ', '+')}&per_page=1&orientation=landscape"
        headers = {"Authorization": PEXELS_API_KEY}
        
        try:
            print(f"   🖼️ Pexels horizontal: '{current_query}' (attempt {intento+1})")
            r = requests.get(url, headers=headers, timeout=30)
            if r.status_code == 200:
                data = r.json()
                if data.get("photos") and len(data["photos"]) > 0:
                    photo = data["photos"][0]
                    img_url = photo["src"].get("landscape") or photo["src"].get("original")
                    print(f"   ✅ Horizontal image found.")
                    return img_url
            else:
                print(f"   ⚠️ Pexels API error {r.status_code}")
        except Exception as e:
            print(f"   ⚠️ Connection error: {e}")
            
        if intento < intentos - 1:
            time.sleep(3)
            
    return None

# ================================================================
# 🎨 GENERAR FONDO SÓLIDO
# ================================================================
def generar_fondo_solido(color=(20, 20, 50), ancho=1080, alto=1920):
    img = Image.new('RGB', (ancho, alto), color)
    path = f"temp_fondo_{random.randint(1000,9999)}.jpg"
    img.save(path)
    return path

# ================================================================
# 🎙️ GENERAR AUDIO
# ================================================================
def generar_audio(texto, index, intentos_por_voz=2):
    global CONFIG_VOZ_ACTUAL
    texto_limpio = re.sub(r'[^a-zA-ZáéíóúüñÁÉÍÓÚÜÑ0-9\s.,;:!?¿¡\'\"]', '', texto)
    texto_limpio = re.sub(r'\s+', ' ', texto_limpio).strip()
    if len(texto_limpio) < 20:
        texto_limpio = "Financial news."
    filename = f"audio_short_en_{index}.mp3"
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
            print(f"   ❌ Voice failed {voz}: {e}")
        time.sleep(10)
        if os.path.exists(filename):
            try: os.remove(filename)
            except: pass
    return None

# ================================================================
# 🎬 GENERAR RECURSOS POR SEGMENTO
# ================================================================
def generar_recursos_por_segmento(segmentos_data, paleta_video, titulo, tema="", intentos_imagen=5):
    recursos = []
    total = len(segmentos_data)
    last_successful_url = None

    for idx, seg in enumerate(segmentos_data):
        seg_text = seg["text"]
        prompt_deepseek = seg.get("image_prompt", "")
        bloque = seg.get("block", "")
        
        print(f"  🎬 Segment {idx+1}/{total} - {bloque} ({len(seg_text.split())} words)")
        
        prompt_img = construir_prompt_segmento(titulo, prompt_deepseek, idx, paleta_video)
        
        print(f"    📝 Prompt: {prompt_img[:100]}...")
        
        img_url = None
        for intento in range(intentos_imagen):
            # Pasar el bloque para mejorar la búsqueda
            img_url = generar_imagen_vertical(prompt_img, tema=tema, bloque=bloque, intentos=1)
            if img_url:
                print(f"    ✅ Image generated (attempt {intento+1})")
                last_successful_url = img_url
                break
            time.sleep(6)  # Pausa de 6 segundos entre intentos
        
        if not img_url:
            if last_successful_url:
                print(f"    🔄 Reusing previous image")
                img_url = last_successful_url
            else:
                print(f"    ⚠️ No previous image. Retrying...")
                time.sleep(6)
                img_url = generar_imagen_vertical(prompt_img, tema=tema, bloque=bloque, intentos=1)
                if img_url:
                    last_successful_url = img_url
                else:
                    print(f"    ❌ Failed definitively, using solid background")
                    img_path = generar_fondo_solido(color=(20, 20, 50), ancho=1080, alto=1920)
                    img_url = img_path
                    last_successful_url = img_url
        
        if not img_url:
            img_path = generar_fondo_solido(color=(20, 20, 50), ancho=1080, alto=1920)
            img_url = img_path
            last_successful_url = img_url
        
        audio_path = generar_audio(seg_text, idx)
        if not audio_path:
            print(f"    ❌ Audio failed for segment {idx+1}. Aborting.")
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
            print(f"   ⏳ Waiting 6 seconds...")
            time.sleep(6)
    
    return recursos

def construir_prompt_segmento(titulo, prompt_deepseek, idx_bloque, paleta):
    if prompt_deepseek and len(prompt_deepseek.split()) > 5:
        base_prompt = prompt_deepseek
    else:
        sujeto = detectar_sujeto_visual(titulo)
        composicion = COMPOSICIONES_BLOQUE[idx_bloque % len(COMPOSICIONES_BLOQUE)]
        base_prompt = f"{sujeto}, {composicion}"
    
    return (
        f"{base_prompt}, color palette of {paleta}, "
        "cinematic financial documentary style, hyperrealistic, 8k resolution, "
        "dramatic lighting, high contrast, sharp focus, "
        "no people, no faces, no hands, no text, no letters, no numbers, no logos, "
        "no watermark, no black box, no rectangle overlay, vertical 9:16"
    )

def construir_prompt_miniatura(titulo, prompt_deepseek, paleta):
    if prompt_deepseek and len(prompt_deepseek.split()) > 5:
        base_prompt = prompt_deepseek
    else:
        sujeto = detectar_sujeto_visual(titulo)
        base_prompt = f"{sujeto}, dramatic composition with clean dark empty space on the RIGHT side"
    
    return (
        f"{base_prompt}, color palette of {paleta}, youtube finance thumbnail style, "
        "hyperrealistic, 8k, high contrast, cinematic lighting, sharp focus, "
        "no people, no faces, no text, no letters, no numbers, no watermark, no black box"
    )

# ================================================================
# 📝 SUBTÍTULOS CON PIL (VERTICAL) - MEJORADOS
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
                print("   ⚠️ Using default font")
        
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
        print(f"⚠️ Error in subtitles: {e}")
        return imagen_path

# ================================================================
# 🔤 FUENTE GRUESA REAL
# ================================================================
def obtener_ruta_fuente():
    if not os.path.exists("Anton.ttf"):
        try:
            print("📥 Downloading Anton font...")
            url = "https://github.com/google/fonts/raw/main/ofl/anton/Anton-Regular.ttf"
            r = requests.get(url, timeout=30)
            if r.status_code == 200 and len(r.content) > 10000:
                with open("Anton.ttf", "wb") as f:
                    f.write(r.content)
                print("✅ Anton font downloaded")
        except Exception as e:
            print(f"⚠️ Font download failed: {e}")
    rutas = [
        "Anton.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "fonts/Anton.ttf",
    ]
    for ruta in rutas:
        if os.path.exists(ruta):
            return ruta
    return None

# ================================================================
# 🖼️ MINIATURA PROFESIONAL HIGH-CTR (ESPECÍFICA PARA SHORTS)
# ================================================================
def crear_miniatura_profesional(prompt_miniatura, texto_portada, salida="miniatura_short_en.jpg"):
    """
    MINIATURA PARA SHORTS - Vertical 9:16 style adaptado a 16:9
    Más dinámica, colores más intensos, texto MÁS GRANDE
    """
    try:
        print("🖼️ Generating SHORT thumbnail (high-impact)...")
        
        # Prompt específico para SHORTS - más dramático
        prompt_corto = (
            f"{prompt_miniatura}, "
            "ultra high contrast, extreme close-up, "
            "bold neon colors (yellow #FFD700 and red #FF0000), "
            "dramatic lighting, eye-catching, viral style, "
            "space for BIG text on right side"
        )
        
        fondo_url = generar_imagen_horizontal(prompt_corto, tema=texto_portada, intentos=2)
        
        if fondo_url and fondo_url.startswith("http"):
            try:
                r = requests.get(fondo_url, timeout=30)
                r.raise_for_status()
                img_path = "temp_thumb_fondo_short_en.jpg"
                with open(img_path, "wb") as f:
                    f.write(r.content)
            except Exception as e:
                print(f"⚠️ Error downloading background: {e}. Using solid background.")
                img_path = generar_fondo_solido(color=(5, 5, 15), ancho=1280, alto=720)
        else:
            img_path = generar_fondo_solido(color=(5, 5, 15), ancho=1280, alto=720)
        
        img = Image.open(img_path)
        img = ImageOps.fit(img, (1280, 720), Image.Resampling.LANCZOS)
        draw = ImageDraw.Draw(img)
        
        # TEXTO PARA SHORTS - MÁXIMO 3-4 PALABRAS, MÁS GRANDE
        texto = texto_portada.upper().strip()
        palabras = texto.split()
        
        if len(palabras) > 4:
            texto = ' '.join(palabras[:4])
            palabras = texto.split()
        
        # Dividir en 2 líneas máximo
        if len(palabras) > 2:
            mitad = len(palabras) // 2
            lineas = [' '.join(palabras[:mitad+1]), ' '.join(palabras[mitad+1:])]
        else:
            lineas = [texto]
        
        ruta_fuente = obtener_ruta_fuente()
        
        # FUENTE MÁS GRANDE para SHORTS
        size = 180  # Más grande que en largos (150)
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
        
        alto_linea = size + 20
        alto_total = alto_linea * len(lineas)
        y_inicio = (720 - alto_total) // 2
        
        # Sombra negra EXTENDIDA para más contraste
        offset = 10  # Más que en largos (8)
        for i, linea in enumerate(lineas):
            bbox = draw.textbbox((0, 0), linea, font=font)
            text_w = bbox[2] - bbox[0]
            x = 1280 - text_w - 60  # Más pegado al borde
            y = y_inicio + i * alto_linea
            
            for dx in range(-offset, offset+1, 3):
                for dy in range(-offset, offset+1, 3):
                    draw.text((x + dx, y + dy), linea, fill='black', font=font)
            
            draw.text((x, y), linea, fill='black', font=font)
        
        # Texto AMARILLO MÁS BRILLANTE para SHORTS
        for i, linea in enumerate(lineas):
            bbox = draw.textbbox((0, 0), linea, font=font)
            text_w = bbox[2] - bbox[0]
            x = 1280 - text_w - 60
            y = y_inicio + i * alto_linea
            
            # Amarillo más intenso
            draw.text((x, y), linea, fill=(255, 255, 0), font=font)  # #FFFF00 vs #FFD700
            draw.text((x-2, y), linea, fill=(255, 240, 50), font=font)
            draw.text((x+2, y), linea, fill=(255, 240, 50), font=font)
        
        # Borde ROJO MÁS GRUESO para SHORTS
        draw.rectangle([(1180, 40), (1270, 680)], outline=(255, 50, 50), width=6)  # Más grueso
        
        # EFECTO DE BRILLO adicional para SHORTS
        draw.rectangle([(1190, 50), (1260, 670)], outline=(255, 200, 0), width=2)
        
        img.save(salida, quality=95)
        print(f"✅ SHORT thumbnail created: {salida}")
        print(f"   Text: '{texto}' (LARGER, BRIGHTER)")
        print(f"   Colors: Bright Yellow (#FFFF00) with THICK red border")
        return salida
    except Exception as e:
        print(f"⚠️ Error in SHORT thumbnail: {e}")
        import traceback
        traceback.print_exc()
        return None

# ================================================================
#  MONTAR VIDEO SHORTS CON EFECTOS DINÁMICOS
# ================================================================
def montar_video_shorts(recursos, fondo_path, salida="short_capital_en.mp4"):
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
                img_path = f"temp_short_en_{i}.jpg"
                with open(img_path, "wb") as f:
                    f.write(r.content)
            except:
                img_path = generar_fondo_solido(color=(20, 20, 50), ancho=1080, alto=1920)
        else:
            img_path = img_url
        
        img = Image.open(img_path)
        img = ImageOps.fit(img, (1080, 1920), Image.Resampling.LANCZOS)
        img.save(img_path)
        
        img_sub_path = f"temp_short_sub_en_{i}.jpg"
        img_path = agregar_subtitulos_con_pil(img_path, texto, img_sub_path)
        
        video_clip = ImageClip(img_path).set_duration(duracion)
        
        # EFECTOS ESPECIALES POR BLOQUE
        if bloque == "HOOK" or i == 0:
            # PRIMEROS 3 SEGUNDOS: EFECTO DRAMÁTICO
            # Zoom rápido IN (de 1.3x a 1.0x en 0.5s)
            video_clip = video_clip.resize(lambda t: 1.3 - 0.6 * min(t/0.5, 1.0))
            
            if duracion > 3:
                video_clip = video_clip.set_duration(3.0)
                duracion = 3.0
            
            print(f"   🎬 HOOK: Fast zoom effect applied (0-3s)")
            
        elif bloque == "PROBLEM" or i == 1:
            # Transición slide left
            video_clip = video_clip.resize(lambda t: 1.0 + 0.02 * t)
            
        elif bloque == "DATA":
            # Zoom lento y constante
            video_clip = video_clip.resize(lambda t: 1.0 + 0.01 * t)
            
        elif bloque == "SOLUTION":
            # Zoom out (optimismo)
            video_clip = video_clip.resize(lambda t: 1.0 - 0.02 * min(t/5, 0.1))
            
        else:
            # Zoom suave por defecto
            video_clip = video_clip.resize(lambda t: 1 + 0.02 * t)
        
        clips_video.append(video_clip)
        
        try:
            audio = AudioFileClip(audio_path)
            clips_audio.append(audio)
        except:
            silencio = AudioClip(lambda t: 0, duration=duracion)
            clips_audio.append(silencio)
    
    # CONCATENAR AUDIO CON PAUSAS
    PAUSA = 0.3
    audio_final_parts = []
    for i, aud in enumerate(clips_audio):
        audio_final_parts.append(aud)
        if i < len(clips_audio) - 1:
            audio_final_parts.append(AudioClip(lambda t: 0, duration=PAUSA))
    
    audio_narracion = concatenate_audioclips(audio_final_parts)
    duracion_total = audio_narracion.duration
    
    # CONCATENAR VIDEO
    video = concatenate_videoclips(clips_video, method="compose")
    video = video.set_duration(duracion_total)
    
    # AGREGAR MÚSICA DE FONDO
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
def subir_a_youtube(video_path, titulo, etiquetas_str, gancho, contexto, hashtags, fuente="", miniatura_path=None, dynamic_hashtags=""):
    try:
        creds = Credentials.from_authorized_user_info(YOUTUBE_USER_TOKEN)
        youtube = build("youtube", "v3", credentials=creds)
    except Exception as e:
        print(f"❌ Error authenticating: {e}")
        sys.exit(1)
    
    tags = sanitizar_tags(etiquetas_str)
    if not tags:
        print("⚠️ No valid tags found. Using default tags.")
        tags = ["finance", "investing", "crypto", "trading", "shorts"]
    
    tags_str_final = ",".join(tags)
    if len(tags_str_final) > 500:
        tags = tags[:10]
        tags_str_final = ",".join(tags)
        if len(tags_str_final) > 500:
            tags = tags[:5]
            tags_str_final = ",".join(tags)
    
    print(f" Final tags ({len(tags)}): {tags_str_final}")
    
    # Hashtags fijos + dinámicos
    hashtags_fijos = "#Shorts #Finance #Investing"
    if dynamic_hashtags:
        dynamic_hashtags = sanitizar_hashtags(dynamic_hashtags, max_tags=6)
        hashtags_final = f"{dynamic_hashtags} {hashtags_fijos}"
    else:
        hashtags_final = hashtags_fijos
    
    descripcion = f"""{gancho}

{contexto}

🔴 SUBSCRIBE to the channel: {CANAL_LINK}

 {fuente}

{hashtags_final}

⚠️ IMPORTANT NOTICE: This content is for educational purposes only and does not constitute financial, legal, or investment advice."""
    
    body = {
        "snippet": {
            "title": titulo[:100],
            "description": descripcion[:5000],
            "tags": tags[:30],
            "categoryId": "22",
            "defaultLanguage": "en",
            "defaultAudioLanguage": "en",
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
    print(f"✅ Short uploaded: https://youtu.be/{video_id}")
    
    if miniatura_path and os.path.exists(miniatura_path):
        try:
            media_thumb = MediaFileUpload(miniatura_path, chunksize=-1, resumable=True)
            youtube.thumbnails().set(videoId=video_id, media_body=media_thumb).execute()
            print("✅ Professional thumbnail uploaded")
        except Exception as e:
            print(f"⚠️ Error uploading thumbnail: {e}")
    
    return video_id

# ================================================================
# 🧹 LIMPIEZA
# ================================================================
def limpiar_archivos_temporales():
    import glob
    patrones = [
        "temp_*.jpg", "audio_short_en_*.mp3", "temp_thumb*.jpg",
        "miniatura_short_en.jpg", "short_capital_en.mp4", "placeholder*.jpg",
        "temp_fondo_*.jpg"
    ]
    for patron in patrones:
        for f in glob.glob(patron):
            try:
                os.remove(f)
                print(f"🧹 Removed: {f}")
            except:
                pass
    print("✅ Cleanup completed")

# ================================================================
# 📄 INICIALIZAR ARCHIVOS JSON
# ================================================================
def inicializar_archivos_json():
    """Crear archivos JSON si no existen"""
    archivos_needed = {
        "temas_shorts_publicados.json": {"temas": []},
        "temas_shorts_en_publicados.json": {"temas": []},
        "titulos_capital_shorts_publicados.json": {"titulos": []},
        "titulos_capital_shorts_en_publicados.json": {"titulos": []},
        "estado_capital_shorts.json": {"ultimo_fondo": None, "publicaciones_hoy": None},
        "estado_capital_shorts_en.json": {"ultimo_fondo": None, "publicaciones_hoy": None},
        "trends_semanal.json": {"trending_topics": [], "best_topic_this_week": ""}
    }
    
    for archivo, contenido_default in archivos_needed.items():
        if not os.path.exists(archivo):
            print(f"📄 Creating missing file: {archivo}")
            with open(archivo, "w", encoding="utf-8") as f:
                json.dump(contenido_default, f, indent=2, ensure_ascii=False)

# ================================================================
# 🎯 MAIN
# ================================================================
def main():
    global _used_image_urls
    _used_image_urls = set()  # RESETEAR AL INICIO DE CADA VIDEO
    
    # INICIALIZAR ARCHIVOS JSON
    inicializar_archivos_json()
    
    print("="*60)
    print("🎬 Capital Minds - SHORTS BOT (IMPROVED)")
    print("   ✓ Viral title formulas")
    print("   ✓ 3-second hook optimization")
    print("   ✓ High-CTR thumbnails (yellow on black)")
    print("   ✓ Dynamic zoom effects")
    print("   ✓ Trending topics analysis")
    print("   ✓ 5 image attempts with 6s delay")
    print("   ✓ Duplicate image prevention")
    print("="*60)

    tz_mexico = ZoneInfo("America/Mexico_City")
    fecha_actual = datetime.now(tz_mexico)
    fecha_formateada = fecha_actual.strftime("%B %d, %Y")
    print(f"📅 Current date: {fecha_formateada}")
    print("="*60)
    
    if not YOUTUBE_USER_TOKEN:
        print("❌ YOUTUBE_USER_TOKEN_CAPITAL missing")
        sys.exit(1)
    
    if not DEEPSEEK_API_KEY:
        print("❌ DEEPSEEK_API_KEY missing")
        sys.exit(1)
    
    if not PEXELS_API_KEY:
        print("❌ PEXELS_API_KEY missing")
        sys.exit(1)
    
    publicadas = obtener_publicaciones_hoy()
    if publicadas >= META_DIARIA_SHORTS:
        print(f"✅ Already published {META_DIARIA_SHORTS} shorts today. Exiting.")
        sys.exit(0)
    
    # Analizar trends semanales (si es medianoche o no existe el archivo)
    trends_data = None
    try:
        with open(TRENDS_FILE, "r", encoding="utf-8") as f:
            trends_data = json.load(f)
            print(f"   📈 Using trending topic: {trends_data.get('best_topic_this_week', 'N/A')}")
    except:
        # Si no existe o hay error, generar nuevo análisis
        if fecha_actual.hour < 2:  # Ejecutar a medianoche
            print("📊 Generating weekly trends analysis...")
            trends_data = analizar_trends_semanal()
        else:
            print("️ No trends file found, continuing without it")
    
    if publicadas == 0:
        tipo = "news"
    elif publicadas == 1:
        tipo = "educational"
    else:
        tipo = "analysis"
    
    print(f"📌 Type: {tipo.upper()} (Short #{publicadas+1} of the day)")
    
    estado = cargar_estado()
    fondo_path = seleccionar_fondo_disponible(estado)
    
    paleta_video = random.choice(PALETAS_VIDEO)
    print(f" Color palette for this video: {paleta_video}")
    
    print("💡 Generating viral video idea...")
    idea_data = generar_idea_video(tipo, fecha_formateada, trends_data)
    if idea_data and "best_idea" in idea_data:
        idea = idea_data["best_idea"]
        print(f"   ✅ Selected idea: {idea['title']}")
        print(f"   📌 Format: {idea.get('formula_used', 'general')}")
        print(f"   🎯 Psychology trigger: {idea.get('psychology_trigger', 'N/A')}")
    else:
        print("⚠️ No idea generated, using fallback topic.")
        idea = None
    
    guion, tema_elegido, restriccion = generar_guion_financiero(tipo, idea, fecha_formateada)
    titulo = guion["title"]
    dynamic_hashtags = guion.get("dynamic_hashtags", "")
    segments_data = guion["segments"]
    palabras_portada = guion.get("cover_words", "INSIGHT")
    prompt_miniatura = guion.get("thumbnail_prompt", "")
    
    # Extraer textos de segmentos
    segmentos = [seg["text"] for seg in segments_data]
    
    print(f"🏷️ Title: {titulo}")
    print(f"🏷️ Dynamic hashtags: {dynamic_hashtags}")
    
    # Generar recursos con prompts de DeepSeek
    recursos = generar_recursos_por_segmento(
        segments_data, paleta_video, titulo, tema=tema_elegido
    )
    if not recursos:
        print("❌ Error generating resources.")
        sys.exit(1)
    
    video_path = montar_video_shorts(recursos, fondo_path, "short_capital_en.mp4")
    print(f"🎬 Video assembled: {video_path}")
    
    # Miniatura adaptada
    miniatura_path = None
    if prompt_miniatura:
        print("🖼️ Generating professional thumbnail...")
        prompt_miniatura_final = construir_prompt_miniatura(titulo, prompt_miniatura, paleta_video)
        miniatura_path = crear_miniatura_profesional(
            prompt_miniatura_final,
            palabras_portada,
            "miniatura_short_en.jpg"
        )
    
    video_id = subir_a_youtube(
        video_path=video_path,
        titulo=guion["title"],
        etiquetas_str=guion["tags"],
        gancho=guion["hook_description"],
        contexto=guion["context_description"],
        hashtags="",  # Se construye internamente
        fuente=guion.get("source_story", "Based on financial analysis"),
        miniatura_path=miniatura_path,
        dynamic_hashtags=dynamic_hashtags
    )
    
    guardar_titulo_publicado(guion["title"])
    guardar_tema_publicado(tema_elegido, tipo)
    incrementar_publicaciones_hoy()
    guardar_estado(estado)
    
    limpiar_archivos_temporales()
    
    print(f"✅ Short published successfully!")
    print(f"🔗 https://youtu.be/{video_id}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
