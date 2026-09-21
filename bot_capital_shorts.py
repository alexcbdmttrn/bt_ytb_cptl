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

META_DIARIA_SHORTS = 2
DIAS_SIN_REPETIR_TEMA = 30

# 🚫 PALABRAS PROHIBIDAS (ANTI-FED) — Solo se permiten si NO se usaron en 20 días
PALABRAS_ANTI_FED = [
    "fed", "fomc", "powell", "rate cut", "rate hike",
    "interest rate decision", "federal reserve", "monetary policy"
]

_used_image_urls = set()

# ================================================================
# VOZ FIJA
# ================================================================
VOZ_FIJA = {
    "voz": "en-US-JennyNeural",
    "velocidad": "+12%",
    "tono": "+2Hz",
    "volumen": "+10%"
}
CONFIG_VOZ_ACTUAL = VOZ_FIJA

# ================================================================
# 🎨 PALETAS Y SUJETOS VISUALES
# ================================================================
PALETAS_VIDEO = [
    "electric cyan #00FFFF and gold #FFD700 neon on dark navy #0A0E27",
    "emerald green #50C878 and silver #C0C0C0 on black #000000",
    "violet magenta #FF00FF and orange #FF8C00 on deep blue #00008B",
    "crimson red #DC143C and gold #FFD700 on charcoal #36454F",
    "teal #008080 and amber #FFBF00 on dark slate #2F4F4F",
    "ice blue #B0E0E6 and white #FFFFFF on midnight black #191970",
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
    (["bitcoin", "btc", "crypto", "cryptocurrency", "halving"], "a giant physical golden bitcoin coin with intricate details"),
    (["gold", "silver", "metal", "precious"], "shiny gold bars stacked inside a bank vault"),
    (["fed", "reserve", "rate", "interest"], "a monumental central bank building with columns"),
    (["inflation", "cpi", "price"], "a shopping cart full of groceries over a rising inflation chart"),
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
    (["history", "historical"], "vintage financial documents with aged paper texture"),
    (["education", "learn", "tutorial", "guide", "explained"], "educational infographic with clean charts"),
]

def detectar_sujeto_visual(texto_ref):
    t = (texto_ref or "").lower()
    for keywords, sujeto in SUJETOS_VISUALES:
        if any(k in t for k in keywords):
            return sujeto
    return "a cinematic financial scene with glowing charts, coins and data"

# ================================================================
# 🚫 VERIFICAR SI HAY CONTENIDO RECIENTE DE FED (últimos 20 días)
# ================================================================
def verificar_fed_reciente(dias=20):
    """
    Verifica si en los últimos N días se publicó contenido sobre Fed/FOMC/Powell.
    Si sí, prohíbe generar más sobre esos temas.
    """
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
    """Verifica si un título contiene palabras relacionadas con Fed."""
    t = (titulo or "").lower()
    return any(p in t for p in PALABRAS_ANTI_FED)

# ================================================================
# 📚 CATEGORÍAS DE CONTENIDO (para variedad)
# ================================================================
CATEGORIAS_SHORTS = {
    "educational": {
        "peso": 35,
        "temas": [
            "How Bitcoin Mining Actually Works",
            "Understanding Blockchain in 60 Seconds",
            "Gold vs Bitcoin: Quick Comparison",
            "How to Read Crypto Charts",
            "What is Dollar Cost Averaging",
            "Portfolio Diversification Explained",
            "What is a Crypto Wallet",
            "Staking vs Yield Farming",
            "How Smart Contracts Work",
            "DeFi Lending Explained Simply",
            "What Are Stablecoins",
            "Layer 1 vs Layer 2 Explained",
            "How Consensus Mechanisms Work",
            "Bitcoin vs Ethereum Differences",
            "What is Market Cap",
            "Understanding Crypto Volatility",
            "How to Spot a Crypto Scam",
            "What is a Hardware Wallet"
        ]
    },
    "historical": {
        "peso": 25,
        "temas": [
            "Bitcoin's 2017 Bull Run Story",
            "The 2008 Crisis and Bitcoin's Birth",
            "Mt Gox Hack Explained",
            "Bitcoin Pizza Day Story",
            "Tulip Mania: First Bubble",
            "The 2021 Crypto Crash",
            "FTX Collapse: What Happened",
            "Terra Luna Collapse",
            "The Silk Road Story",
            "How Satoshi Disappeared",
            "The First Bitcoin Transaction",
            "Venezuela's Crypto Story",
            "Cyprus Crisis and Bitcoin",
            "The 2022 Bear Market",
            "Gold's Historic Price Crashes"
        ]
    },
    "psychology": {
        "peso": 20,
        "temas": [
            "Why 90% of Traders Fail",
            "The Psychology of Panic Selling",
            "Why FOMO Costs You Money",
            "Loss Aversion Explained",
            "The Fear and Greed Cycle",
            "Why Investors Buy High Sell Low",
            "Overconfidence Bias in Trading",
            "Herding Behavior in Markets",
            "The Psychology of Bull Markets",
            "How Emotions Affect Investing",
            "Cognitive Biases in Crypto",
            "Why Patience Wins in Investing"
        ]
    },
    "analysis": {
        "peso": 15,
        "temas": [
            "Bitcoin Halving Cycles Explained",
            "Gold Price Patterns",
            "Bitcoin Dominance Analysis",
            "Institutional Adoption Trends",
            "Crypto Volatility Patterns",
            "Market Sentiment Indicators",
            "On-Chain Analysis Basics",
            "Whale Activity Explained",
            "The MVRV Ratio Explained",
            "Mining Hash Rate Analysis"
        ]
    },
    "news": {
        "peso": 5,  # 🔥 SOLO 5% noticias
        "temas": [
            "Major Crypto Regulation Update",
            "Bitcoin ETF Flow Analysis",
            "Institutional Crypto Adoption"
        ]
    }
}

def seleccionar_categoria_shorts():
    """Selecciona categoría evitando Fed si es reciente."""
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
    
    for _ in range(15):  # más intentos para encontrar variedad
        total_peso = sum(cat["peso"] for cat in CATEGORIAS_SHORTS.values())
        numero_aleatorio = random.uniform(0, total_peso)
        
        peso_acumulado = 0
        for categoria, datos in CATEGORIAS_SHORTS.items():
            peso_acumulado += datos["peso"]
            if numero_aleatorio <= peso_acumulado:
                # Si Fed está prohibida, saltar categoría news
                if fed_prohibida and categoria == "news":
                    continue
                
                temas_disponibles = [t for t in datos["temas"] if t.lower() not in temas_recientes]
                
                # Filtrar temas con Fed si está prohibida
                if fed_prohibida:
                    temas_disponibles = [t for t in temas_disponibles if not tema_contiene_fed(t)]
                
                if temas_disponibles:
                    return categoria, random.choice(temas_disponibles)
                else:
                    return categoria, random.choice(datos["temas"])
    
    return "educational", random.choice(CATEGORIAS_SHORTS["educational"]["temas"])

# ================================================================
# 📊 ANÁLISIS DE TRENDS (SIN SESGO DE FED)
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
    
    temas_text = "\n".join(temas_recientes[:10]) if temas_recientes else "None"
    
    prompt = f"""
You are a VIRAL TREND ANALYST for YouTube Shorts in finance/crypto.

CURRENT DATE: {hoy.strftime("%B %d, %Y")}

🚫 CRITICAL PROHIBITION: DO NOT focus on Federal Reserve, Fed rate decisions, FOMC, Jerome Powell, or interest rate news. We have covered those excessively. Focus on DIVERSE educational and historical content.

RECENTLY PUBLISHED TOPICS (avoid repeating):
{temas_text}

🎯 YOUR TASK: Generate 10 DIVERSE video topics for SHORTS (40-50 seconds).

CONTENT MIX (CRITICAL - MUST BE DIVERSE):
- 35% Educational (how-to, tutorials, explanations of concepts)
- 25% Historical (past events, case studies, lessons)
- 20% Psychology (investor behavior, emotions, biases)
- 15% Analysis (cycles, patterns, technical insights)
- 5% Major news (ONLY if truly major, NOT Fed-related)

DIVERSITY REQUIREMENT: Each of the 10 topics MUST be from a DIFFERENT subtopic. Do not repeat themes.

For each topic provide:
- topic: Topic name
- category: (educational/historical/psychology/analysis/news)
- why_trending: Data-driven reason
- viral_score: 1-10
- hook: First 3 seconds script

Return JSON:
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
        print("📊 Analyzing weekly trends (anti-Fed bias)...")
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
        
        print(f"   ✅ Best topic: {trends.get('best_topic_this_week', 'N/A')}")
        return trends
    except Exception as e:
        print(f"⚠️ Error analyzing trends: {e}")
        return None

# ================================================================
# 🎬 GENERAR IDEA DE VIDEO (CON FILTRO ANTI-FED)
# ================================================================
def generar_idea_video(categoria, tema_sugerido, fecha_actual, trends_data=None):
    fed_prohibida = verificar_fed_reciente(dias=20)
    
    fed_instruction = ""
    if fed_prohibida:
        fed_instruction = """
🚫 CRITICAL PROHIBITION (ACTIVE):
We have published content about Fed/FOMC/Powell in the last 20 days.
ABSOLUTELY DO NOT create titles about:
- Federal Reserve / Fed rate decisions / FOMC
- Jerome Powell
- Interest rate hikes or cuts
- Rate decision news
Focus ONLY on educational, historical, psychology, or technical analysis content.
"""
    
    seo_keywords = []
    if trends_data and "high_volume_keywords" in trends_data:
        seo_keywords = trends_data.get("high_volume_keywords", [])
    
    keywords_text = ", ".join(seo_keywords[:5]) if seo_keywords else "Bitcoin, crypto, gold, investing"
    
    prompt = f"""
You are a VIRAL CONTENT STRATEGIST for YouTube Shorts in finance/crypto.

CURRENT DATE: {fecha_actual}
CATEGORY: {categoria.upper()}
SUGGESTED TOPIC: {tema_sugerido}

{fed_instruction}

🎯 HIGH-VOLUME SEO KEYWORDS:
{keywords_text}

VIRAL TITLE FORMULAS:
1. CURIOSITY GAP: "The #1 Secret About Bitcoin"
2. CONTROVERSY: "Why 90% of Traders Are Wrong"
3. SPECIFIC NUMBER: "5 Reasons Bitcoin Will Surge"
4. COMPARISON: "Bitcoin vs Gold: The Winner"
5. EDUCATIONAL: "How Bitcoin Mining Works"

CONTENT GUIDELINES by category:

If EDUCATIONAL: Focus on teaching a concept clearly. Use analogies.
If HISTORICAL: Tell a story with dates and lessons learned.
If PSYCHOLOGY: Explain investor behavior, biases, emotions.
If ANALYSIS: Use data, patterns, technical insights.
If NEWS (only 5%): Focus on IMPACT, historical context.

🎯 YOUR TASK: Generate 5 SHORT VIDEO IDEAS (40-50 seconds).

REQUIREMENTS:
✅ Title: 50-60 chars max, front-load keyword
✅ Include 1 emoji max
✅ Create CURIOSITY GAP
✅ Use POWER WORDS: Secret, Truth, Exposed, Why, How, Shocking
✅ DO NOT use Fed / FOMC / Powell / rate cut in titles
✅ Must be suitable for 40-50 second short

Return JSON:
{{
    "best_idea": {{
        "title": "Final title (50-60 chars, NO Fed)",
        "hook_3sec": "First 3 seconds script",
        "description": "One sentence explanation",
        "formula_used": "Formula name",
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
            result = json.loads(json_str)
            
            # Verificar que el título no mencione Fed si está prohibida
            titulo_gen = result.get("best_idea", {}).get("title", "").lower()
            if fed_prohibida and tema_contiene_fed(titulo_gen):
                print(f"⚠️ Fed topic in title. Regenerating...")
                if intento < 2:
                    continue
            
            return result
        except Exception as e:
            print(f"⚠️ Error (attempt {intento+1}): {e}")
            time.sleep(5)
    
    return None

# ================================================================
# 🏷️ SANITIZAR TAGS (MANTIENE ESPACIOS INTERNOS)
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
    """
    MANTIENE espacios internos (crucial para SEO).
    Elimina solo espacios dobles, al inicio/final, y caracteres especiales.
    """
    if not tags_str:
        return []
    
    raw_tags = [t.strip() for t in tags_str.split(",") if t.strip()]
    
    cleaned = []
    for tag in raw_tags:
        # Solo letras, números y espacios simples
        clean = re.sub(r'[^a-zA-Z0-9áéíóúüñÁÉÍÓÚÜÑ\s]', '', tag)
        clean = re.sub(r'\s+', ' ', clean).strip()
        
        if not clean or len(clean) < 2:
            continue
        if len(clean) > 30:
            clean = clean[:30].strip()
        
        cleaned.append(clean)
    
    # Eliminar duplicados
    seen = set()
    unique = []
    for tag in cleaned:
        tag_lower = tag.lower()
        if tag_lower not in seen:
            seen.add(tag_lower)
            unique.append(tag)
    
    unique = unique[:max_tags]
    
    # Limitar longitud total
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
# MÚSICA
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
        print(f"🎵 Selected music: {os.path.basename(seleccionada)}")
    return seleccionada

# ================================================================
# FUNCIONES DE ESTADO
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

def _es_titulo_duplicado_real(titulo_nuevo, titulos_existentes):
    """Verificación estricta: solo considera duplicado si similitud > 85%."""
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
    """Modifica un título duplicado agregando variaciones únicas."""
    titulo_base = titulo_original.strip()
    
    sufijos_unicos = ["RIGHT NOW", "TODAY", "2026", "JUST IN", "UPDATE",
                     "EXCLUSIVE", "LIVE", "NEW DATA", "BREAKING", "ALERT"]
    
    prefijos_unicos = ["🚨 BREAKING:", "⚠️ WARNING:", "📈 UPDATE:", "💰 ALERT:",
                      "🔥 HOT:", "⚡ LIVE:", "📊 NEW:"]
    
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
# 🖼️ GENERAR IMAGEN VERTICAL (PEXELS)
# ================================================================
def generar_imagen_vertical(prompt, tema="", bloque="", intentos=10):
    global _used_image_urls
    
    keyword_map = {
        "HOOK": "urgent financial red alert",
        "PROBLEM": "falling charts panic",
        "DATA": "financial data charts glowing",
        "SOLUTION": "upward trend success",
        "CLOSE": "professional finance subtle",
        "bitcoin": "bitcoin cryptocurrency",
        "gold": "gold bars luxury",
        "crypto": "cryptocurrency blockchain",
        "trading": "trading charts",
        "mining": "mining rigs technology",
        "wallet": "crypto wallet technology",
        "history": "vintage financial documents",
        "psychology": "human brain psychology",
    }
    
    base_query = "finance business"
    prompt_lower = prompt.lower()
    
    if bloque and bloque in keyword_map:
        base_query = keyword_map[bloque]
    else:
        for key, value in keyword_map.items():
            if key in prompt_lower:
                base_query = value
                break

    modifiers = [
        "abstract dark background", "neon glowing lights", "cinematic dramatic",
        "macro close up", "minimalist clean", "vibrant colors",
        "futuristic technology", "moody atmospheric"
    ]
    
    for intento in range(intentos):
        current_query = f"{base_query} {random.choice(modifiers)}"
        random_page = random.randint(1, 10)
        
        url = f"https://api.pexels.com/v1/search?query={current_query.replace(' ', '+')}&per_page=10&orientation=portrait&page={random_page}"
        headers = {"Authorization": PEXELS_API_KEY}
        
        try:
            print(f"   🖼️ Pexels: '{current_query}' (attempt {intento+1}/{intentos})")
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
                        print(f"      ✅ Unique image found")
                        return img_url
        except Exception as e:
            print(f"      ⚠️ Error: {e}")
        
        if intento < intentos - 1:
            time.sleep(10)
    
    return None

def generar_imagen_horizontal(prompt, tema="", intentos=5):
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
# GENERAR AUDIO
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
            print(f"   ❌ Voice failed: {e}")
        time.sleep(10)
    return None

# ================================================================
# GENERAR GUION (CON FILTRO ANTI-FED)
# ================================================================
def generar_guion_financiero(categoria, tema_elegido, fecha_actual, idea=None):
    titulos_pub = cargar_titulos_publicados()["titulos"][-20:]
    titulos_referencia = "\n".join([f"- {t}" for t in titulos_pub]) if titulos_pub else "None yet."

    hook_sugerido = idea.get("hook_3sec", "") if idea else ""
    titulo_idea = idea["title"] if idea else tema_elegido
    
    fed_prohibida = verificar_fed_reciente(dias=20)
    fed_instruction = ""
    if fed_prohibida:
        fed_instruction = """
🚫 CRITICAL PROHIBITION (ACTIVE):
We have recently published Fed content. DO NOT mention Federal Reserve, Fed rate, FOMC, Powell, or interest rate decisions in the script or title.
Focus on educational, historical, psychology, or technical content instead.
"""
    
    prompt = f"""
You are a YouTube Shorts SCRIPTWRITER and SEO EXPERT in finance/crypto.

📌 TOPIC: "{titulo_idea}"
📌 CATEGORY: {categoria.upper()}
📌 HOOK: "{hook_sugerido}"
📅 DATE: {fecha_actual}

{fed_instruction}

 CRITICAL RULES:

1️⃣ FIRST 3 SECONDS (MUST STOP SCROLL):
   - Shocking statement + keyword
   - Examples: "Bitcoin just did THIS...", "Why 90% of traders..."

2️⃣ STRUCTURE (90-110 words for 40-50 seconds):
   [HOOK 0-3s] Shocking statement (10 words)
   [PROBLEM 3-10s] Why it matters (25 words)
   [DATA 10-25s] Facts/numbers with keyword (35 words)
   [SOLUTION 25-35s] What to do (25 words)
   [CLOSE 35-40s] CTA (5 words)

3️⃣ SEO:
   - Mention PRIMARY KEYWORD 2-3 times naturally
   - Include NUMBERS (increases engagement 40%)

4️⃣ IMAGE PROMPTS (one per segment, match content):
   - HOOK: "dramatic financial scene, urgent neon, cinematic 8k, vertical 9:16"
   - PROBLEM: "falling charts, red candles, dark background, vertical 9:16"
   - DATA: "financial data visualization, glowing charts, vertical 9:16"
   - SOLUTION: "upward trending chart, green candles, gold accents, vertical 9:16"
   - CLOSE: "professional finance background, subtle, vertical 9:16"

5️⃣ THUMBNAIL: High-CTR, dominant subject, high contrast, space for text.

6️⃣ HASHTAGS (6 total):
   - 2 HIGH volume (#Bitcoin #Crypto)
   - 2 MEDIUM (#BitcoinNews #CryptoNews)
   - 2 LOW niche (#BitcoinPrice #CryptoAlert)

7️⃣ TITLE:
   - 50-60 chars, keyword first
   - 1 emoji, curiosity gap, power words
   - NO Fed/FOMC/Powell references

🚫 TITLES ALREADY PUBLISHED (DO NOT REPEAT):
{titulos_referencia}

📤 RETURN JSON:
{{
    "title": "Title (50-60 chars, emoji, NO Fed)",
    "alternative_title": "Alternative title",
    "keywords": ["bitcoin", "crypto", "trading", "investment", "finance"],
    "hook_description": "Hook for description (90 chars)",
    "context_description": "One sentence context",
    "source_story": "Data source",
    "cover_words": "2-3 WORDS FOR THUMBNAIL",
    "tags": "25 tags comma separated (mix high/medium/low volume)",
    "dynamic_hashtags": "#Bitcoin #Crypto #BitcoinNews #CryptoNews #BitcoinPrice #CryptoAlert",
    "segments": [
        {{"block": "HOOK", "text": "~10 words", "image_prompt": "dramatic financial scene", "duration": 3.0}},
        {{"block": "PROBLEM", "text": "~25 words", "image_prompt": "falling charts", "duration": 7.0}},
        {{"block": "DATA", "text": "~35 words", "image_prompt": "financial data charts", "duration": 15.0}},
        {{"block": "SOLUTION", "text": "~25 words", "image_prompt": "upward trend", "duration": 10.0}},
        {{"block": "CLOSE", "text": "~5 words", "image_prompt": "finance background", "duration": 5.0}}
    ],
    "thumbnail_prompt": "Bitcoin dramatic, space for text, YouTube thumbnail 16:9",
    "seo_optimized_description": "Description with keywords for SEO"
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
                    seg["image_prompt"] = f"cinematic financial scene, neon lighting, 8k, vertical 9:16"

            # Verificar que el título no tenga Fed si está prohibida
            titulo = data.get("title", "").strip()
            titulo = re.sub(r'#\w+', '', titulo).strip()
            
            if fed_prohibida and tema_contiene_fed(titulo):
                print(f"   ⚠️ Title contains Fed reference. Regenerating...")
                if intento < 5:
                    continue
            
            # Verificar duplicados
            titulos_existentes = cargar_titulos_publicados()["titulos"]
            if _es_titulo_duplicado_real(titulo, titulos_existentes):
                print(f"   ⚠️ Title similar to existing: '{titulo}'")
                titulo = modificar_titulo_para_evitar_duplicado(titulo, titulos_existentes)
                data["title"] = titulo
                print(f"   ✅ Modified: {titulo}")

            tags_raw = data.get("tags", "")
            tags_list = sanitizar_tags(tags_raw)
            keywords = data.get("keywords", [])
            for kw in keywords:
                if kw.lower() not in [t.lower() for t in tags_list]:
                    tags_list.append(kw.lower())
            extras = ["finance", "investing", "economy", "bitcoin", "crypto", "trading", "education"]
            for extra in extras:
                if len(tags_list) < 25 and extra not in tags_list:
                    tags_list.append(extra)
            data["tags"] = ", ".join(tags_list[:25])

            if "thumbnail_prompt" not in data or not data["thumbnail_prompt"]:
                data["thumbnail_prompt"] = "clean professional financial chart, dark background, blue and gold, no people, no text"
            if "dynamic_hashtags" not in data:
                data["dynamic_hashtags"] = "#Bitcoin #Crypto #BitcoinNews #CryptoNews #BitcoinPrice #CryptoAlert"

            print(f"   🏷️ Title: {data['title']}")
            return data, tema_elegido, categoria
            
        except Exception as e:
            print(f"❌ Attempt {intento+1}/6 failed: {e}")
            if intento < 5:
                time.sleep(10)

    # Forced fallback
    print("⚠️ All attempts failed. Generating forced unique title...")
    fecha_corta = datetime.now().strftime("%b %d").upper()
    titulo_forzado = f"📊 {tema_elegido[:40]} - {fecha_corta}"
    
    return {
        "title": titulo_forzado,
        "alternative_title": f"⚠️ {tema_elegido[:40]} | {fecha_corta}",
        "keywords": ["bitcoin", "crypto", "finance"],
        "hook_description": f"Financial insight on {tema_elegido[:50]}",
        "context_description": f"Analysis for {fecha_corta}",
        "source_story": "Market analysis",
        "cover_words": "KEY INSIGHT",
        "tags": "bitcoin, crypto, finance, trading, investing, economy, market analysis, education",
        "dynamic_hashtags": "#Bitcoin #Crypto #BitcoinNews #CryptoNews #BitcoinPrice #CryptoAlert",
        "segments": [
            {"block": "HOOK", "text": f"Discover the truth about {tema_elegido[:30]}. This changes everything.", "image_prompt": "dramatic financial scene, neon lighting, 8k, vertical 9:16", "duration": 3.0},
            {"block": "PROBLEM", "text": "Most investors miss this critical detail that could make or break their portfolio.", "image_prompt": "falling charts, red candles, dark background, vertical 9:16", "duration": 7.0},
            {"block": "DATA", "text": "Historical data shows consistent patterns that smart investors use to their advantage.", "image_prompt": "financial data visualization, glowing charts, vertical 9:16", "duration": 15.0},
            {"block": "SOLUTION", "text": "Diversify, stay informed, and think long-term. Knowledge is your best investment.", "image_prompt": "upward trend, green candles, gold accents, vertical 9:16", "duration": 10.0},
            {"block": "CLOSE", "text": "Subscribe for daily insights.", "image_prompt": "professional finance background, vertical 9:16", "duration": 5.0}
        ],
        "thumbnail_prompt": "Bitcoin dramatic, space for text, YouTube thumbnail 16:9",
        "seo_optimized_description": f"Latest analysis on {tema_elegido[:50]}. Stay informed with daily updates."
    }, tema_elegido, categoria

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
        "no people, no faces, no text, no letters, no numbers, no logos, "
        "no watermark, vertical 9:16"
    )

def construir_prompt_miniatura(titulo, prompt_deepseek, paleta):
    if prompt_deepseek and len(prompt_deepseek.split()) > 5:
        base_prompt = prompt_deepseek
    else:
        sujeto = detectar_sujeto_visual(titulo)
        base_prompt = f"{sujeto}, dramatic composition with clean dark empty space on RIGHT side"
    
    return (
        f"{base_prompt}, color palette of {paleta}, youtube finance thumbnail style, "
        "hyperrealistic, 8k, high contrast, cinematic lighting, sharp focus, "
        "no people, no faces, no text, no letters, no numbers, no watermark"
    )

# ================================================================
# GENERAR RECURSOS POR SEGMENTO
# ================================================================
def generar_recursos_por_segmento(segmentos_data, paleta_video, titulo, tema="", intentos_imagen=10):
    recursos = []
    total = len(segmentos_data)
    last_successful_url = None

    for idx, seg in enumerate(segmentos_data):
        seg_text = seg["text"]
        prompt_deepseek = seg.get("image_prompt", "")
        bloque = seg.get("block", "")
        
        print(f"  🎬 Segment {idx+1}/{total} - {bloque} ({len(seg_text.split())} words)")
        
        prompt_img = construir_prompt_segmento(titulo, prompt_deepseek, idx, paleta_video)
        
        img_url = None
        for intento in range(intentos_imagen):
            img_url = generar_imagen_vertical(prompt_img, tema=tema, bloque=bloque, intentos=1)
            if img_url:
                print(f"    ✅ Image found (attempt {intento+1})")
                last_successful_url = img_url
                break
            print(f"    ⏳ Waiting 10 seconds...")
            time.sleep(10)
        
        if not img_url:
            if last_successful_url:
                print(f"    🔄 Reusing previous image")
                img_url = last_successful_url
            else:
                img_path = generar_fondo_solido(color=(20, 20, 50), ancho=1080, alto=1920)
                img_url = img_path
                last_successful_url = img_url
        
        audio_path = generar_audio(seg_text, idx)
        if not audio_path:
            print(f"    ❌ Audio failed. Aborting.")
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
# SUBTÍTULOS
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
        print(f"⚠️ Error in subtitles: {e}")
        return imagen_path

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
    rutas = ["Anton.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
    for ruta in rutas:
        if os.path.exists(ruta):
            return ruta
    return None

def crear_miniatura_profesional(prompt_miniatura, texto_portada, salida="miniatura_short_en.jpg"):
    try:
        print("🖼️ Generating SHORT thumbnail...")
        
        prompt_corto = (
            f"{prompt_miniatura}, ultra high contrast, extreme close-up, "
            "bold neon colors (yellow and red), dramatic lighting, "
            "eye-catching, viral style, space for BIG text on right side"
        )
        
        fondo_url = generar_imagen_horizontal(prompt_corto, tema=texto_portada, intentos=2)
        
        if fondo_url and fondo_url.startswith("http"):
            try:
                r = requests.get(fondo_url, timeout=30)
                r.raise_for_status()
                img_path = "temp_thumb_fondo_short_en.jpg"
                with open(img_path, "wb") as f:
                    f.write(r.content)
            except:
                img_path = generar_fondo_solido(color=(5, 5, 15), ancho=1280, alto=720)
        else:
            img_path = generar_fondo_solido(color=(5, 5, 15), ancho=1280, alto=720)
        
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
        print(f"✅ Thumbnail created: {salida}")
        return salida
    except Exception as e:
        print(f"⚠️ Error: {e}")
        return None

# ================================================================
# MONTAR VIDEO
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
                img_path = generar_fondo_solido(color=(20, 20, 50))
        else:
            img_path = img_url
        
        img = Image.open(img_path)
        img = ImageOps.fit(img, (1080, 1920), Image.Resampling.LANCZOS)
        img.save(img_path)
        
        img_sub_path = f"temp_short_sub_en_{i}.jpg"
        img_path = agregar_subtitulos_con_pil(img_path, texto, img_sub_path)
        
        video_clip = ImageClip(img_path).set_duration(duracion)
        
        if bloque == "HOOK" or i == 0:
            video_clip = video_clip.resize(lambda t: 1.3 - 0.6 * min(t/0.5, 1.0))
        elif bloque == "PROBLEM" or i == 1:
            video_clip = video_clip.resize(lambda t: 1.0 + 0.02 * t)
        elif bloque == "DATA":
            video_clip = video_clip.resize(lambda t: 1.0 + 0.01 * t)
        elif bloque == "SOLUTION":
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
# SUBIR A YOUTUBE
# ================================================================
def subir_a_youtube(video_path, titulo, etiquetas_str, gancho, contexto, hashtags, fuente="", miniatura_path=None, dynamic_hashtags="", seo_description=""):
    try:
        creds = Credentials.from_authorized_user_info(YOUTUBE_USER_TOKEN)
        youtube = build("youtube", "v3", credentials=creds)
    except Exception as e:
        print(f"❌ Auth error: {e}")
        sys.exit(1)
    
    tags = sanitizar_tags(etiquetas_str, max_tags=20, max_chars=480)
    
    if len(tags) < 5:
        print("⚠️ Not enough valid tags. Using fallback.")
        tags = ["bitcoin", "crypto", "investing", "blockchain", "trading",
                "finance", "gold", "cryptocurrency", "market analysis", "crypto news"]
    
    # Log de diagnóstico
    print(f"\n📝 TAG DIAGNOSTIC:")
    total_chars = 0
    for i, tag in enumerate(tags, 1):
        print(f"   {i}. '{tag}' ({len(tag)} chars)")
        total_chars += len(tag) + 1
    print(f"   Total: {total_chars} chars (limit: 500)")
    
    hashtags_fijos = "#Shorts #Finance #Investing"
    if dynamic_hashtags:
        dynamic_hashtags = sanitizar_hashtags(dynamic_hashtags, max_tags=6)
        hashtags_final = f"{dynamic_hashtags} {hashtags_fijos}"
    else:
        hashtags_final = hashtags_fijos
    
    descripcion = f"""{gancho}

{contexto}

{seo_description if seo_description else contexto}

🔴 SUBSCRIBE: {CANAL_LINK}

📖 {fuente}

{hashtags_final}

⚠️ IMPORTANT NOTICE: This content is for educational purposes only and does not constitute financial, legal, or investment advice."""
    
    body = {
        "snippet": {
            "title": titulo[:100],
            "description": descripcion[:5000],
            "tags": tags[:20],
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
            print("✅ Thumbnail uploaded")
        except Exception as e:
            print(f"⚠️ Thumbnail error: {e}")
    
    return video_id

# ================================================================
# LIMPIEZA
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
            except:
                pass
    print("✅ Cleanup completed")

def inicializar_archivos_json():
    archivos_needed = {
        "temas_shorts_publicados.json": {"temas": []},
        "temas_shorts_en_publicados.json": {"temas": []},
        "titulos_capital_shorts_publicados.json": {"titulos": []},
        "titulos_capital_shorts_en_publicados.json": {"titulos": []},
        "estado_capital_shorts.json": {"ultimo_fondo": None, "publicaciones_hoy": None},
        "estado_capital_shorts_en.json": {"ultimo_fondo": None, "publicaciones_hoy": None},
        "trends_semanal.json": {"trending_topics": [], "best_topic_this_week": ""}
    }
    for archivo, contenido in archivos_needed.items():
        if not os.path.exists(archivo):
            print(f"📝 Creating: {archivo}")
            with open(archivo, "w", encoding="utf-8") as f:
                json.dump(contenido, f, indent=2, ensure_ascii=False)

# ================================================================
# MAIN
# ================================================================
def main():
    global _used_image_urls
    _used_image_urls = set()
    
    inicializar_archivos_json()
    
    print("="*60)
    print("🎬 Capital Minds - SHORTS BOT (ANTI-FED + VARIEDAD)")
    print("   ✓ 35% Educational, 25% Historical, 20% Psychology")
    print("   ✓ 15% Analysis, 5% News (NO Fed bias)")
    print("   ✓ Anti-Fed filter (20 días sin Fed)")
    print("   ✓ Tags con espacios internos (SEO óptimo)")
    print("   ✓ Log de diagnóstico de tags")
    print("   ✓ Solo 2 shorts por día")
    print("="*60)

    tz_mexico = ZoneInfo("America/Mexico_City")
    fecha_actual = datetime.now(tz_mexico)
    fecha_formateada = fecha_actual.strftime("%B %d, %Y")
    print(f"📅 Date: {fecha_formateada}")
    
    fed_reciente = verificar_fed_reciente(dias=20)
    if fed_reciente:
        print("🚫 Anti-Fed filter: ACTIVE (recent Fed content detected)")
    else:
        print("✅ Anti-Fed filter: inactive")
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
        print(f"✅ Limit reached: {META_DIARIA_SHORTS} shorts today.")
        sys.exit(0)
    
    print(f"📊 Published today: {publicadas}/{META_DIARIA_SHORTS}")
    
    # 🔧 NUEVA LÓGICA: Seleccionar categoría por pesos (NO por hora del día)
    categoria, tema_sugerido = seleccionar_categoria_shorts()
    print(f"📌 Category: {categoria.upper()}")
    print(f"📝 Suggested topic: {tema_sugerido}")
    
    estado = cargar_estado()
    fondo_path = seleccionar_fondo_disponible(estado)
    
    paleta_video = random.choice(PALETAS_VIDEO)
    print(f"🎨 Palette: {paleta_video[:50]}...")
    
    # Trends opcional
    trends_data = None
    try:
        with open(TRENDS_FILE, "r", encoding="utf-8") as f:
            trends_data = json.load(f)
    except:
        if fecha_actual.hour < 2:
            trends_data = analizar_trends_semanal()
    
    # Generar idea
    print("💡 Generating idea...")
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
    
    print(f"🏷️ Title: {titulo}")
    print(f"🏷️ Hashtags: {dynamic_hashtags}")
    
    recursos = generar_recursos_por_segmento(segments_data, paleta_video, titulo, tema=tema_elegido)
    if not recursos:
        print("❌ Error generating resources.")
        sys.exit(1)
    
    video_path = montar_video_shorts(recursos, fondo_path, "short_capital_en.mp4")
    print(f"🎬 Video: {video_path}")
    
    miniatura_path = None
    if prompt_miniatura:
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
        hashtags="",
        fuente=guion.get("source_story", "Based on financial analysis"),
        miniatura_path=miniatura_path,
        dynamic_hashtags=dynamic_hashtags,
        seo_description=seo_description
    )
    
    guardar_titulo_publicado(guion["title"])
    guardar_tema_publicado(tema_elegido, categoria)
    incrementar_publicaciones_hoy()
    guardar_estado(estado)
    
    limpiar_archivos_temporales()
    
    print(f"\n✅ Short published!")
    print(f"🔗 https://youtu.be/{video_id}")
    print(f"📊 Category: {categoria.upper()}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
