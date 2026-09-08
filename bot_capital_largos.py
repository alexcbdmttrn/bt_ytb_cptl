import asyncio
from datetime import datetime, timedelta
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
    CompositeVideoClip,
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
ESTADO_FILE = "estado_capital_largos_en.json"
TITULOS_FILE = "titulos_capital_largos_en_publicados.json"
TEMAS_PUBLICADOS_FILE = "temas_largos_en_publicados.json"
TRENDS_FILE = "trends_semanal_largos.json"

ESTADO_FILE_ES = "estado_capital_largos.json"
TITULOS_FILE_ES = "titulos_capital_largos_publicados.json"
TEMAS_PUBLICADOS_FILE_ES = "temas_largos_publicados.json"

META_DIARIA_LARGOS = 1
DIAS_SIN_REPETIR_TEMA = 45

# ================================================================
# VOZ EN INGLÉS
# ================================================================
VOZ_FIJA = {"voz": "en-US-JennyNeural", "velocidad": "+8%", "tono": "-1Hz"}
CONFIG_VOZ_ACTUAL = VOZ_FIJA

# ================================================================
# 🎨 PALETAS Y COMPOSICIONES
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
# 📊 ANÁLISIS SEMANAL DE TRENDS (OPTIMIZADO PARA LARGOS)
# ================================================================
def analizar_trends_semanal_largos():
    """
    Analiza temas trending específicos para videos largos (7-9 min)
    """
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
    
    prompt = f"""
You are a VIRAL TREND ANALYST for YouTube LONG-FORM finance/crypto videos (7-9 minutes).

CURRENT DATE: September 2024
YOUR TASK: Identify DEEP-DIVE TOPICS suitable for long-form content.

📊 RECENTLY PUBLISHED TOPICS (avoid repeating):
{chr(10).join(temas_recientes[:10]) if temas_recientes else "None"}

🔥 TRENDING TOPICS FOR LONG-FORM (September 2024):

Topics that work for 7-9 minute videos:
1. Bitcoin price reaction to Fed rate cut - Full analysis
2. Federal Reserve interest rate decisions - Complete breakdown
3. Bitcoin vs Gold performance - Comprehensive comparison
4. Crypto market volatility - Deep dive with data
5. Inflation data (CPI) impact - Detailed explanation
6. Central banks buying gold - Full story
7. Bitcoin halving aftermath - Complete analysis
8. Altcoin season predictions - In-depth research
9. Crypto regulation updates - Comprehensive guide
10. DeFi and staking yields - Detailed tutorial

 HIGH-SEARCH-VOLUME LONG-FORM KEYWORDS:
- "Bitcoin price prediction" (long-form intent)
- "Cryptocurrency explained" (educational)
- "Crypto news today" (breaking news)
- "Bitcoin crash analysis" (deep dive)
- "Fed rate cut impact" (comprehensive)
- "Gold vs Bitcoin" (comparison)
- "Inflation explained" (educational)
- "Stock market analysis" (detailed)
- "Crypto scams exposed" (investigative)
- "Passive income crypto guide" (tutorial)

YOUR TASK: Generate 5 VIDEO TOPICS for long-form this week.

For each topic provide:
- Topic name (suitable for 7-9 min)
- Why it's trending NOW
- Viral potential (1-10)
- Best format (deep-dive/educational/comparison/guide)
- Suggested hook (first 30 seconds)
- Chapters outline (3-5 chapters)

Return in JSON:
{{
    "trending_topics": [
        {{
            "topic": "Bitcoin Fed Rate Cut: Complete Analysis",
            "why_trending": "Fed just cut rates, Bitcoin reacted +7.7%, viewers want full breakdown",
            "viral_score": 9,
            "best_format": "deep-dive",
            "hook": "The Fed just did something unprecedented. Here's what it means for Bitcoin...",
            "chapters": ["The Announcement", "Market Reaction", "Historical Context", "What's Next"]
        }},
        ...
    ],
    "topics_to_avoid": ["topic1", "topic2"],
    "best_topic_this_week": "Bitcoin Fed Rate Cut: Complete Analysis"
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
        print("📊 Analyzing weekly trends for long-form...")
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
# 🎬 GENERAR IDEA DE VIDEO LARGO CON FÓRMULAS VIRALES
# ================================================================
def generar_idea_video_largo(tipo, fecha_actual, trends_data=None):
    """
    PROMPT MEJORADO: Enfocado en viralidad para videos largos (7-9 min)
    """
    tema_sugerido = ""
    if trends_data and "best_topic_this_week" in trends_data:
        tema_sugerido = f"SUGGESTED TOPIC: {trends_data['best_topic_this_week']}\n"
    
    prompt = f"""
You are a VIRAL CONTENT STRATEGIST for YouTube LONG-FORM videos (7-9 minutes) in finance/crypto.

📅 CURRENT DATE: {fecha_actual}
📊 YOUR GOAL: Generate ideas that get 10,000+ views and HIGH retention (60%+)

{tema_sugerido}
VIRAL TITLE FORMULAS FOR LONG-FORM (use these):

FORMULA 1 - COMPREHENSIVE GUIDE:
"The Complete Guide to [TOPIC] in 2024"
"Everything You Need to Know About [TOPIC]"

FORMULA 2 - DEEP DIVE:
"[TOPIC] Explained: The Full Story"
"The Truth About [TOPIC] (Deep Dive)"

FORMULA 3 - COMPARISON:
"[A] vs [B]: Which Is Better? (Full Comparison)"
"I Tested [X] vs [Y] for 30 Days"

FORMULA 4 - BREAKING NEWS:
"BREAKING: [EVENT] - What It Means (Full Analysis)"
"[EVENT] Just Happened - Here's What's Next"

FORMULA 5 - CONTROVERSY:
"Why [COMMON BELIEF] Is Wrong (Evidence)"
"The [TOPIC] Lie They Don't Want You to Know"

FORMULA 6 - PREDICTION:
"[TOPIC] Price Prediction: What's Next?"
"Where [TOPIC] Is Heading in 2024"

FORMULA 7 - STEP-BY-STEP:
"How to [ACHIEVE X] (Step-by-Step Guide)"
"[NUMBER] Steps to Master [TOPIC]"

 TRENDING TOPICS FOR LONG-FORM (September 2024):
- Bitcoin price reaction to Fed rate cut
- Federal Reserve interest rate decisions
- Bitcoin vs Gold performance comparison
- Crypto market volatility analysis
- Inflation data (CPI) impact
- Central banks buying gold
- Bitcoin halving effects
- Altcoin season predictions
- Crypto regulation updates
- DeFi and staking yields

🎯 YOUR TASK: Generate 5 LONG-FORM VIDEO IDEAS using the formulas above.

REQUIREMENTS:
✅ Title: 60-70 characters (SEO optimized)
✅ Include 1 emoji (📊📈💰🔍⚠️)
✅ Create CURIOSITY GAP (promise value)
✅ Use POWER WORDS: Complete, Ultimate, Truth, Exposed, Guide, Analysis, Prediction
✅ AVOID: Generic titles like "Bitcoin Update" or "Market News"
✅ Must be suitable for 7-9 minute deep-dive

For each idea provide:
- Title (with formula used)
- Hook (first 30 seconds - MUST hook viewers)
- Main value proposition (what viewers will learn)
- Why it's viral (psychology trigger)
- Estimated chapters (3-5)

Then SELECT THE BEST ONE and return in JSON:

{{
    "best_idea": {{
        "title": "Final viral title (60-70 chars)",
        "hook_30sec": "First 30 seconds script (MUST retain viewers)",
        "description": "What viewers will learn",
        "formula_used": "Name of formula",
        "psychology_trigger": "curiosity/fear/greed/education/urgency",
        "type": "{tipo}",
        "estimated_duration": "7-9 minutes"
    }},
    "all_ideas": [
        {{"title": "...", "hook_30sec": "...", "formula": "...", "viral_score": 9}},
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
# ️ SANITIZAR HASHTAGS Y TAGS
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
    cleaned = cleaned[:max_tags]
    return " ".join(cleaned)

def sanitizar_tags(tags_str, max_tags=30):
    if not tags_str:
        return []
    
    raw_tags = [t.strip() for t in tags_str.split(",") if t.strip()]
    
    cleaned = []
    for tag in raw_tags:
        clean = re.sub(r'[^a-zA-Z0-9áéíóúüñÁÉÍÓÚÜÑ\s\-]', '', tag)
        clean = clean.strip()
        clean = re.sub(r'\s+', ' ', clean)
        if clean and len(clean) > 1:
            if len(clean) > 30:
                clean = clean[:30]
            cleaned.append(clean)
    
    seen = set()
    cleaned_unique = []
    for tag in cleaned:
        tag_lower = tag.lower()
        if tag_lower not in seen:
            seen.add(tag_lower)
            cleaned_unique.append(tag)
    
    cleaned_unique = cleaned_unique[:max_tags]
    
    return cleaned_unique

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
        print("ℹ️ No music found. Continuing without background music.")
        return None
    ultimo_fondo = estado.get("ultimo_fondo")
    if ultimo_fondo and ultimo_fondo in fondos_disponibles:
        fondos_disponibles.remove(ultimo_fondo)
    seleccionada = random.choice(fondos_disponibles) if fondos_disponibles else random.choice(FONDOS_DISPONIBLES)
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

def tema_ya_publicado(tema, dias=45):
    temas = cargar_temas_publicados()
    hoy = datetime.now(ZoneInfo("America/Mexico_City")).date()
    for t in temas:
        if t["tema"].lower() == tema.lower():
            fecha_tema = datetime.strptime(t["fecha"], "%Y-%m-%d").date()
            if (hoy - fecha_tema).days < dias:
                return True
    return False

# ================================================================
# 📝 GENERAR GUION LARGO OPTIMIZADO (RETENCIÓN ALTA)
# ================================================================
def generar_guion_largo(tipo, fecha_actual, idea=None):
    titulos_pub = cargar_titulos_publicados()["titulos"][-10:]
    titulos_referencia = "\n".join([f"- {t}" for t in titulos_pub]) if titulos_pub else "None yet."

    if not idea:
        print("💡 Generating idea with viral formulas...")
        idea_data = generar_idea_video_largo(tipo, fecha_actual)
        if idea_data and "best_idea" in idea_data:
            idea = idea_data["best_idea"]
            print(f"   ✅ Selected idea: {idea['title']}")
            print(f"   📌 Format: {idea.get('formula_used', 'general')}")
        else:
            print("⚠️ No idea generated, using fallback topic.")
            idea = {"title": "Bitcoin Market Analysis", "hook_30sec": "Bitcoin just did something unprecedented...", "description": "Full market breakdown", "type": "analysis"}

    tema_elegido = idea["title"]
    hook_sugerido = idea.get("hook_30sec", "")
    
    prompt = f"""
You are a PROFESSIONAL SCRIPTWRITER and FINANCE EXPERT for YouTube LONG-FORM videos (7-9 minutes).

 VIDEO IDEA: "{tema_elegido}"
📌 HOOK (first 30s): "{hook_sugerido}"
 CONTENT TYPE: {tipo.upper()}
📅 CURRENT DATE: {fecha_actual}

⚠️ DATE RULE (CRITICAL):
   - DO NOT use past dates like 2020, 2021, 2022, 2023 or 2024.
   - Use current year: {fecha_actual.split()[-1]}.
   - Say "today", "this week", or "recently" for recent events.

🎯 GOLDEN RULE (CRITICAL FOR RETENTION):
- Script MUST be 1300-1500 words (7-9 minutes at normal pace).
- First 30 seconds MUST hook viewers (use pattern interrupt).
- Include MINI-HOOKS every 2 minutes to maintain retention.
- Each section must deliver value and create curiosity for next section.

🎯 MANDATORY STRUCTURE (Challenge → Process → Result):

[HOOK - 0:00] Pattern interrupt + promise (100-150 words)
   - Start with shocking statement, question, or pattern interrupt
   - Promise specific value viewers will get
   - Create curiosity gap

[INTRO - 0:30] Context and why it matters (200-250 words)
   - Explain the topic and why viewers should care
   - Establish credibility
   - Preview what's coming (chapters)

[CHAPTER 1 - 1:30] Foundation/Background (250-300 words)
   - Set the stage with context
   - Key concepts explained
   - First mini-hook at end

[CHAPTER 2 - 3:30] Deep Dive/Analysis (300-350 words)
   - Main content with data/examples
   - Step-by-step breakdown
   - Second mini-hook at end

[CHAPTER 3 - 5:30] Advanced Insights/Solution (300-350 words)
   - Advanced strategies or solution
   - Real examples and proof
   - Third mini-hook at end

[CHAPTER 4 - 7:30] What's Next/Action Steps (250-300 words)
   - Practical application
   - What viewers should do
   - Final insights

[CLOSE - 8:30] Summary and CTA (150-200 words)
   - Recap key points
   - Strong CTA (subscribe, comment, like)
   - Tease next video

🎯 RETENTION TACTICS (USE THROUGHOUT):
- "But here's where it gets interesting..."
- "Now, this is where most people make a mistake..."
- "I'll show you exactly how to..."
- "The data shows something surprising..."
- "Here's what nobody is talking about..."

🎯 NUMBERS RULE:
- Write numbers with LETTERS: "four hundred", not "400"
- For ranges: "between X and Y"

🎯 TONE:
- Conversational, like talking to a friend
- Use rhetorical questions
- Include analogies and comparisons
- Vary sentence length for rhythm

🎯 IMAGE PROMPTS (One per segment - BE SPECIFIC):
   Each prompt MUST match the segment content:
   
   For HOOK: "dramatic financial scene, urgent neon lights, high contrast, cinematic 8k"
   For INTRO: "professional finance background, charts and data, blue and gold neon"
   For CHAPTER 1: "educational visual, clean charts, explanatory graphics, cyan and gold"
   For CHAPTER 2: "detailed analysis visuals, data charts, professional, emerald and silver"
   For CHAPTER 3: "solution-oriented visuals, upward trends, success, gold accents"
   For CHAPTER 4: "action steps visual, clear graphics, professional, teal and amber"
   For CLOSE: "call-to-action visual, engaging, dynamic, violet and orange"

🎯 HASHTAGS (5-8 specific to topic):
   Example: "#Bitcoin #Crypto #BitcoinAnalysis #CryptoNews #MarketAnalysis"

🎯 THUMBNAIL PROMPT:
   - One dominant subject
   - High contrast (yellow/red on black)
   - Space for 3-5 words of text
   - Example: "Bitcoin with dramatic lighting, yellow and red accents, black background, space for text"

🎯 TAGS (25-30 keywords):
   - Comma-separated ONLY
   - NO special characters (#, $, %, &)
   - Simple keywords: "bitcoin", "crypto", "trading"
   - Maximum 500 characters total

🚫 TITLES ALREADY PUBLISHED (DO NOT REPEAT):
{titulos_referencia}

 RESPONSE IN JSON:
{{
    "title": "Optimized title (60-70 chars with emoji)",
    "alternative_title": "Alternative for A/B testing",
    "keywords": ["kw1", "kw2", "kw3", "kw4", "kw5"],
    "description": "Full description with chapters and hashtags",
    "tags": "25-30 tags comma separated (NO #, NO special chars)",
    "dynamic_hashtags": "#Bitcoin #Crypto #BitcoinAnalysis #MarketAnalysis",
    "script": "Full script 1300-1500 words with 7 marked blocks: [HOOK], [INTRO], [CHAPTER 1], [CHAPTER 2], [CHAPTER 3], [CHAPTER 4], [CLOSE]",
    "segments": [
        {{"block": "HOOK", "text": "text (~100-150 words)", "image_prompt": "dramatic financial scene, urgent neon lights, high contrast, cinematic 8k", "timestamp": "0:00"}},
        {{"block": "INTRO", "text": "text (~200-250 words)", "image_prompt": "professional finance background, charts and data, blue and gold neon", "timestamp": "0:30"}},
        {{"block": "CHAPTER 1", "text": "text (~250-300 words)", "image_prompt": "educational visual, clean charts, explanatory graphics, cyan and gold", "timestamp": "1:30"}},
        {{"block": "CHAPTER 2", "text": "text (~300-350 words)", "image_prompt": "detailed analysis visuals, data charts, professional, emerald and silver", "timestamp": "3:30"}},
        {{"block": "CHAPTER 3", "text": "text (~300-350 words)", "image_prompt": "solution-oriented visuals, upward trends, success, gold accents", "timestamp": "5:30"}},
        {{"block": "CHAPTER 4", "text": "text (~250-300 words)", "image_prompt": "action steps visual, clear graphics, professional, teal and amber", "timestamp": "7:30"}},
        {{"block": "CLOSE", "text": "text (~150-200 words)", "image_prompt": "call-to-action visual, engaging, dynamic, violet and orange", "timestamp": "8:30"}}
    ],
    "cover_words": "2-3 words for thumbnail (e.g., 'FULL ANALYSIS')",
    "thumbnail_prompt": "Bitcoin dramatic lighting, yellow and red on black, space for text, YouTube thumbnail style, 16:9"
}}
"""
    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.8,
        "max_tokens": 4000,
        "response_format": {"type": "json_object"}
    }
    
    for intento in range(3):
        try:
            print(f" Generating script (attempt {intento+1}/3)...")
            r = requests.post(url, headers=headers, json=payload, timeout=150)
            r.raise_for_status()
            data = r.json()
            content = data["choices"][0]["message"]["content"]
            inicio = content.find("{")
            fin = content.rfind("}")
            json_str = content[inicio:fin+1]
            result = json.loads(json_str)
            
            guion_texto = result.get("script", "")
            palabras = len(re.findall(r'\w+', guion_texto))
            print(f" Script words: {palabras}")
            
            if palabras < 1100:
                print(f"⚠️ Script too short ({palabras} words). Adjusting...")
                global VOZ_FIJA, CONFIG_VOZ_ACTUAL
                VOZ_FIJA = {"voz": "en-US-JennyNeural", "velocidad": "+5%", "tono": "-1Hz"}
                CONFIG_VOZ_ACTUAL = VOZ_FIJA
            
            if "thumbnail_prompt" not in result:
                result["thumbnail_prompt"] = "Bitcoin dramatic lighting, yellow and red on black, space for text"
            
            if "dynamic_hashtags" not in result:
                result["dynamic_hashtags"] = ""
            
            for seg in result.get("segments", []):
                if not seg.get("image_prompt") or len(seg["image_prompt"].split()) < 5:
                    seg["image_prompt"] = f"cinematic financial scene about {tema_elegido[:50]}, neon lighting, hyperrealistic, 8k, no people, no text"
                if "timestamp" not in seg:
                    seg["timestamp"] = "0:00"
            
            return result, tema_elegido, idea.get("description", "Financial analysis")
        except Exception as e:
            print(f"❌ Attempt {intento+1}/3 failed: {e}")
            time.sleep(10)
    
    print("❌ Error generating script after 3 attempts")
    sys.exit(1)

# ================================================================
# 🖼️ GENERAR IMAGEN HORIZONTAL (PEXELS - OPTIMIZADO)
# ================================================================
def generar_imagen_horizontal(prompt, tema="", intentos=3):
    keyword_map = {
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
        "chart": "financial charts graph trading",
        "market": "stock market trading floor",
        "analysis": "financial analysis data charts",
        "guide": "educational finance tutorial",
    }
    
    search_query = ""
    prompt_lower = prompt.lower()
    
    for key, value in keyword_map.items():
        if key in prompt_lower:
            search_query = value
            break
    
    if not search_query:
        search_query = "finance business stock market charts"
    
    fallback_queries = [
        search_query,
        "abstract dark finance background",
        "stock market trading charts",
        "cryptocurrency bitcoin technology",
        "business finance economy",
    ]
    
    for intento in range(intentos):
        current_query = fallback_queries[intento % len(fallback_queries)]
        
        url = f"https://api.pexels.com/v1/search?query={current_query.replace(' ', '+')}&per_page=5&orientation=landscape"
        headers = {"Authorization": PEXELS_API_KEY}
        
        try:
            print(f"   🖼️ Pexels search: '{current_query}' (attempt {intento+1})")
            r = requests.get(url, headers=headers, timeout=30)
            
            if r.status_code == 200:
                data = r.json()
                if data.get("photos") and len(data["photos"]) > 0:
                    photos = data["photos"][:5]
                    
                    best_photo = None
                    best_score = 0
                    
                    for photo in photos:
                        score = 0
                        if photo.get("src", {}).get("landscape"):
                            score += 10
                        if photo.get("avg_color") and photo["avg_color"].lower() in ["#1a1a1a", "#2d2d2d", "#000000", "#1c1c1c"]:
                            score += 5
                        if score > best_score:
                            best_score = score
                            best_photo = photo
                    
                    if best_photo:
                        img_url = best_photo["src"].get("landscape") or best_photo["src"].get("original")
                        print(f"   ✅ Found landscape image: {best_photo.get('photographer', 'Unknown')}")
                        return img_url
                        
        except Exception as e:
            print(f"   ️ Error: {e}")
            
        if intento < intentos - 1:
            time.sleep(3)
    
    return None

# ================================================================
# 🎨 GENERAR FONDO SÓLIDO
# ================================================================
def generar_fondo_solido(color=(20, 20, 50), ancho=1280, alto=720):
    img = Image.new('RGB', (ancho, alto), color)
    path = f"temp_fondo_{random.randint(1000,9999)}.jpg"
    img.save(path)
    return path

# ================================================================
# 🔤 FUENTE
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
            print(f"️ Font download failed: {e}")
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
# 🖼️ MINIATURA PROFESIONAL HIGH-CTR
# ================================================================
def crear_miniatura_profesional(prompt_miniatura, texto_portada, salida="miniatura_largo_en.jpg"):
    try:
        print("🖼️ Generating HIGH-CTR thumbnail...")
        
        fondo_url = generar_imagen_horizontal(prompt_miniatura, tema=texto_portada, intentos=2)
        
        if fondo_url and fondo_url.startswith("http"):
            try:
                r = requests.get(fondo_url, timeout=30)
                r.raise_for_status()
                img_path = "temp_thumb_fondo_largo_en.jpg"
                with open(img_path, "wb") as f:
                    f.write(r.content)
            except Exception as e:
                print(f"⚠️ Error downloading background: {e}. Using solid background.")
                img_path = generar_fondo_solido(color=(10, 10, 30), ancho=1280, alto=720)
        else:
            img_path = generar_fondo_solido(color=(10, 10, 30), ancho=1280, alto=720)
        
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
        
        size = 150
        while size >= 80:
            if ruta_fuente:
                font = ImageFont.truetype(ruta_fuente, size)
            else:
                font = ImageFont.load_default()
            
            ancho_max = 0
            alto_total = 0
            for linea in lineas:
                bbox = draw.textbbox((0, 0), linea, font=font)
                ancho_max = max(ancho_max, bbox[2] - bbox[0])
                alto_total += bbox[3] - bbox[1] + 15
            
            if ancho_max <= 1100 and alto_total <= 500:
                break
            size -= 10
        
        alto_linea = size + 15
        alto_total = alto_linea * len(lineas)
        y_inicio = (720 - alto_total) // 2
        
        # Sombra negra
        offset = 8
        for i, linea in enumerate(lineas):
            bbox = draw.textbbox((0, 0), linea, font=font)
            text_w = bbox[2] - bbox[0]
            x = 1280 - text_w - 80
            y = y_inicio + i * alto_linea
            
            for dx in range(-offset, offset+1, 2):
                for dy in range(-offset, offset+1, 2):
                    draw.text((x + dx, y + dy), linea, fill='black', font=font)
            
            draw.text((x, y), linea, fill='black', font=font)
        
        # Texto amarillo neón
        for i, linea in enumerate(lineas):
            bbox = draw.textbbox((0, 0), linea, font=font)
            text_w = bbox[2] - bbox[0]
            x = 1280 - text_w - 80
            y = y_inicio + i * alto_linea
            
            draw.text((x, y), linea, fill=(255, 215, 0), font=font)
            draw.text((x-1, y), linea, fill=(255, 230, 100), font=font)
            draw.text((x+1, y), linea, fill=(255, 230, 100), font=font)
        
        # Borde rojo
        draw.rectangle([(1200, 50), (1260, 670)], outline=(255, 0, 0), width=4)
        
        img.save(salida, quality=95)
        print(f"✅ High-CTR thumbnail created: {salida}")
        print(f"   Text: '{texto}'")
        print(f"   Colors: Yellow (#FFD700) on dark with red accent")
        return salida
    except Exception as e:
        print(f"⚠️ Error in thumbnail: {e}")
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
        print(f"⚠️ Error in subtitles: {e}")
        return imagen_path

# ================================================================
# 🎙️ GENERAR AUDIO
# ================================================================
def generar_audio(texto, index):
    global CONFIG_VOZ_ACTUAL
    texto_limpio = re.sub(r'[^a-zA-ZáéíóúüñÁÉÍÓÚÜÑ0-9\s.,;:!?¿¡\'\"]', '', texto)
    texto_limpio = re.sub(r'\s+', ' ', texto_limpio).strip()
    
    filename = f"audio_largo_en_{index}.mp3"
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
        print(f"❌ Audio error: {e}")
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
            try:
                font = ImageFont.truetype("arial.ttf", 14)
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
        temp_path = f"temp_capitulo_en_{timestamp.replace(':', '')}.png"
        img.save(temp_path)
        clip = ImageClip(temp_path, duration=duracion, transparent=True)
        clip = clip.crossfadein(0.3).crossfadeout(0.3)
        return clip
    except Exception as e:
        print(f"⚠️ Error creating chapter: {e}")
        return None

# ================================================================
# 📣 CTA FINAL
# ================================================================
def crear_cta_final_pil(duracion=3, ancho=1280, alto=720):
    try:
        img = Image.new('RGB', (ancho, alto), (15, 15, 20))
        draw = ImageDraw.Draw(img)
        texto = "🔴 SUBSCRIBE"
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 40)
        except:
            try:
                font = ImageFont.truetype("arial.ttf", 40)
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
        temp_path = "temp_cta_en.png"
        img.save(temp_path)
        clip = ImageClip(temp_path, duration=duracion)
        clip = clip.crossfadein(0.5)
        return clip
    except Exception as e:
        print(f"⚠️ Error creating CTA: {e}")
        return None

# ================================================================
#  MONTAR VIDEO LARGO CON EFECTOS
# ================================================================
def montar_video_largo(recursos, fondo_path, salida="largo_capital_en.mp4", capitulos=None):
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
                    img_path = f"temp_largo_en_{i}.jpg"
                    with open(img_path, "wb") as f:
                        f.write(r.content)
                except Exception as e:
                    print(f"⚠️ Failed to download image {i}: {e}")
                    img_path = generar_fondo_solido()
            else:
                img_path = img_url
            
            img = Image.open(img_path)
            img = ImageOps.fit(img, (1280, 720), Image.Resampling.LANCZOS)
            img.save(img_path)
            
            img_sub_path = f"temp_largo_sub_en_{i}.jpg"
            img_path = agregar_subtitulos_con_pil_16_9(img_path, texto, img_sub_path)
            
            # Efectos dinámicos según el bloque
            video_clip = ImageClip(img_path).set_duration(duracion)
            
            if bloque == "HOOK":
                # Zoom rápido en hook
                video_clip = video_clip.resize(lambda t: 1.1 - 0.05 * min(t/2, 1.0))
            elif bloque in ["CHAPTER 1", "CHAPTER 2", "CHAPTER 3"]:
                # Zoom lento y constante
                video_clip = video_clip.resize(lambda t: 1.0 + 0.01 * t)
            elif bloque == "CLOSE":
                # Zoom out
                video_clip = video_clip.resize(lambda t: 1.0 - 0.01 * min(t/3, 0.1))
            else:
                # Zoom suave por defecto
                video_clip = video_clip.resize(lambda t: 1 + 0.015 * t)
            
        except Exception as e:
            print(f"⚠️ Failed image {i}: {e}")
            img_path = generar_fondo_solido()
            video_clip = ImageClip(img_path, duration=duracion).resize(lambda t: 1 + 0.015 * t)
        
        # Agregar capítulo visual si existe
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
    
    # Concatenar audio con pausas
    PAUSA = 0.3
    audio_final_parts = []
    for i, aud in enumerate(clips_audio):
        audio_final_parts.append(aud)
        if i < len(clips_audio) - 1:
            audio_final_parts.append(AudioClip(lambda t: 0, duration=PAUSA))
    
    audio_narracion = concatenate_audioclips(audio_final_parts)
    duracion_total = audio_narracion.duration
    
    # Concatenar video
    video = concatenate_videoclips(clips_video, method="compose")
    video = video.set_duration(duracion_total)
    
    # Agregar CTA final
    cta_clip = crear_cta_final_pil(duracion=3)
    if cta_clip:
        video = concatenate_videoclips([video, cta_clip], method="compose")
        duracion_total += 3
    
    # Agregar música de fondo
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
# 📤 SUBIR A YOUTUBE
# ================================================================
def subir_a_youtube(video_path, titulo, etiquetas_str, descripcion, miniatura_path=None, dynamic_hashtags=""):
    try:
        creds = Credentials.from_authorized_user_info(YOUTUBE_USER_TOKEN)
        youtube = build("youtube", "v3", credentials=creds)
    except Exception as e:
        print(f" Error authenticating: {e}")
        sys.exit(1)
    
    tags = sanitizar_tags(etiquetas_str)
    if not tags:
        print("⚠️ No valid tags found. Using default tags.")
        tags = ["finance", "investing", "crypto", "trading", "analysis"]
    
    tags_str_final = ",".join(tags)
    while len(tags) > 5 and len(tags_str_final) > 500:
        tags = tags[:-1]
        tags_str_final = ",".join(tags)
    
    print(f"📝 Final tags ({len(tags)}): {tags_str_final}")
    
    hashtags_fijos = "#Finance #Investing"
    if dynamic_hashtags:
        dynamic_hashtags = sanitizar_hashtags(dynamic_hashtags, max_tags=8)
        hashtags_final = f"{dynamic_hashtags} {hashtags_fijos}"
    else:
        hashtags_final = hashtags_fijos
    
    disclaimer = "\n\n⚠️ IMPORTANT NOTICE: This content is for educational purposes only and does not constitute financial, legal, or investment advice."
    descripcion_final = f"{descripcion}\n\n{hashtags_final}\n{disclaimer}"
    
    body = {
        "snippet": {
            "title": titulo[:100],
            "description": descripcion_final[:5000],
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
    print(f"✅ Long video uploaded: https://youtu.be/{video_id}")
    
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
        "temp_*.jpg", "temp_*.mp3", "audio_largo_en_*.mp3",
        "temp_thumb*.jpg", "miniatura_largo_en.jpg", "largo_capital_en.mp4",
        "placeholder*.jpg", "temp_*.png", "temp_capitulo_en_*.png",
        "temp_cta_en.png", "temp_fondo_*.jpg"
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
# 🎯 MAIN
# ================================================================
def main():
    print("="*60)
    print("🎬 Capital Minds - LONG VIDEO BOT (IMPROVED)")
    print("   ✓ Viral title formulas")
    print("   ✓ High-retention script structure")
    print("   ✓ High-CTR thumbnails (yellow on black)")
    print("   ✓ Dynamic zoom effects")
    print("   ✓ Visual chapters for retention")
    print("   ✓ Trending topics analysis")
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
    if publicadas >= META_DIARIA_LARGOS:
        print(f"✅ Already published {META_DIARIA_LARGOS} long video today. Exiting.")
        sys.exit(0)
    
    # Analizar trends semanales
    trends_data = None
    try:
        with open(TRENDS_FILE, "r", encoding="utf-8") as f:
            trends_data = json.load(f)
            print(f"   📈 Using trending topic: {trends_data.get('best_topic_this_week', 'N/A')}")
    except:
        # Si no existe o hay error, generar nuevo análisis
        print("📊 Generating weekly trends analysis...")
        trends_data = analizar_trends_semanal_largos()
    
    tipos = ["news", "educational", "psychology", "analysis"]
    tipo = random.choice(tipos)
    print(f"📌 Type: {tipo.upper()}")
    
    estado = cargar_estado()
    fondo_path = seleccionar_fondo_disponible(estado)
    
    paleta_video = random.choice(PALETAS_VIDEO)
    print(f"🎨 Color palette for this video: {paleta_video}")
    
    print(" Generating viral video idea...")
    idea_data = generar_idea_video_largo(tipo, fecha_formateada, trends_data)
    if idea_data and "best_idea" in idea_data:
        idea = idea_data["best_idea"]
        print(f"   ✅ Selected idea: {idea['title']}")
        print(f"   📌 Format: {idea.get('formula_used', 'general')}")
        print(f"   🎯 Psychology trigger: {idea.get('psychology_trigger', 'N/A')}")
    else:
        print("️ No idea generated, using fallback topic.")
        idea = None
    
    guion, tema, restriccion = generar_guion_largo(tipo, fecha_formateada, idea)
    titulo = guion["title"]
    descripcion = guion["description"]
    tags_str = guion.get("tags", "")
    segmentos = guion["segments"]
    palabras_portada = guion.get("cover_words", "WATCH THIS")
    prompt_miniatura = guion.get("thumbnail_prompt", "")
    dynamic_hashtags = guion.get("dynamic_hashtags", "")
    
    print(f"️ Title: {titulo}")
    print(f"🏷️ Dynamic hashtags: {dynamic_hashtags}")
    
    capitulos = []
    for seg in segmentos:
        capitulos.append({
            "bloque": seg.get("block", "CHAPTER"),
            "timestamp": seg.get("timestamp", "0:00")
        })
    
    # Generar imágenes
    print("\n🖼️ Generating segment-specific images via Pexels...")
    imagenes_generadas = []
    for idx, seg in enumerate(segmentos):
        print(f"🎬 Segment {idx+1}/{len(segmentos)} - {seg.get('block', '')}")
        prompt_img = seg.get("image_prompt", "")
        print(f"   📝 Prompt: {prompt_img[:120]}...")
        img_url = generar_imagen_horizontal(prompt_img, tema=tema, intentos=3)
        imagenes_generadas.append(img_url)
        if img_url:
            print(f"   ✅ Image found successfully.")
        else:
            print(f"   ❌ Failed to find image.")
        time.sleep(2)

    # Reutilizar imágenes para fallos
    print("\n🔄 SECOND PASS: Reusing images for failed segments...")
    def obtener_imagen_disponible(idx, imagenes):
        for i in range(idx - 1, -1, -1):
            if imagenes[i] is not None:
                return imagenes[i], f"previous segment {i+1}"
        for i in range(idx + 1, len(imagenes)):
            if imagenes[i] is not None:
                return imagenes[i], f"next segment {i+1}"
        return None, None

    for idx, img_url in enumerate(imagenes_generadas):
        if img_url is None:
            img_disponible, origen = obtener_imagen_disponible(idx, imagenes_generadas)
            if img_disponible:
                imagenes_generadas[idx] = img_disponible
                print(f"   ✅ Segment {idx+1}: using image from {origen}")
            else:
                imagenes_generadas[idx] = generar_fondo_solido()
                print(f"   🖼️ Segment {idx+1}: using solid background")

    # Generar audio y recursos
    print("\n Generating audio and building resources...")
    recursos = []
    for idx, seg in enumerate(segmentos):
        print(f"🎬 Generating audio for segment {idx+1}/{len(segmentos)}")
        audio_path = generar_audio(seg["text"], idx)
        if not audio_path:
            continue
        try:
            dur = AudioFileClip(audio_path).duration
        except:
            dur = 10.0
        recursos.append({
            "imagen_url": imagenes_generadas[idx],
            "audio_path": audio_path,
            "duracion": dur,
            "texto": seg["text"],
            "block": seg.get("block", "")
        })
        time.sleep(2)

    if not recursos:
        print("❌ No resources generated.")
        sys.exit(1)
    
    video_path = montar_video_largo(recursos, fondo_path, "largo_capital_en.mp4", capitulos)
    print(f"🎬 Video assembled: {video_path}")
    
    # Miniatura
    miniatura_path = None
    print("🖼️ Generating professional thumbnail...")
    prompt_miniatura_final = prompt_miniatura  # Ya viene optimizado del prompt
    miniatura_path = crear_miniatura_profesional(
        prompt_miniatura_final,
        palabras_portada,
        "miniatura_largo_en.jpg"
    )
    
    video_id = subir_a_youtube(
        video_path, titulo, tags_str, descripcion, miniatura_path, dynamic_hashtags
    )
    
    guardar_titulo_publicado(titulo)
    guardar_tema_publicado(tema, tipo)
    incrementar_publicaciones_hoy()
    guardar_estado(estado)
    
    limpiar_archivos_temporales()
    
    print(f"✅ Published: https://youtu.be/{video_id}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f" Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
