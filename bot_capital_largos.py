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

# 🚫 TEMAS PROHIBIDOS (para evitar repetición excesiva)
TEMAS_PROHIBIDOS_FRECUENTES = [
    "federal reserve", "fed rate", "fomc", "interest rate decision",
    "jerome powell", "fed meeting", "rate hike", "rate cut"
]

_used_image_urls = set()

# ================================================================
# VOZ ÉLITE
# ================================================================
VOZ_FIJA = {
    "voz": "en-US-JennyNeural",
    "velocidad": "+10%",
    "tono": "+1Hz",
    "volumen": "+5%"
}
CONFIG_VOZ_ACTUAL = VOZ_FIJA

# ================================================================
# 📚 CATEGORÍAS DE CONTENIDO (90% educativo/histórico, 10% noticias)
# ================================================================
CATEGORIAS_CONTENIDO = {
    "educational": {
        "peso": 40,
        "temas": [
            "How Bitcoin Mining Actually Works",
            "Understanding Blockchain Technology",
            "Gold vs Bitcoin: Complete Comparison",
            "How to Read Crypto Charts",
            "Dollar Cost Averaging Strategy Explained",
            "Portfolio Diversification with Crypto and Gold",
            "Understanding Market Cycles",
            "Risk Management in Crypto Investing",
            "Technical Analysis Basics",
            "Fundamental Analysis for Crypto",
            "What is a Crypto Wallet and How to Use It",
            "Staking vs Yield Farming Explained",
            "How Smart Contracts Work",
            "DeFi Lending and Borrowing Explained",
            "How to Research a Crypto Project",
            "Stablecoins: Types and Use Cases",
            "NFTs Explained for Investors",
            "Layer 1 vs Layer 2 Blockchains",
            "Consensus Mechanisms Explained",
            "How Crypto Exchanges Work",
            "Crypto Taxes: What You Need to Know",
            "Building a Crypto Investment Thesis",
            "Bitcoin vs Ethereum: Key Differences",
            "Altcoin Investing Strategy",
            "Understanding Market Cap and Volume"
        ]
    },
    "historical": {
        "peso": 35,
        "temas": [
            "Bitcoin's 2017 Bull Run: What Really Happened",
            "The 2008 Financial Crisis and Bitcoin's Birth",
            "Gold Standard: Why It Ended and What It Means",
            "Tulip Mania: First Bubble in History",
            "2021 Crypto Crash: Lessons Learned",
            "The Great Depression and Gold",
            "Mt Gox Hack: What Happened",
            "Bitcoin's First Real World Purchase",
            "2013 Cyprus Crisis and Bitcoin",
            "Historical Gold Price Crashes",
            "The Dot-Com Bubble and Crypto Parallels",
            "How the 1971 Nixon Shock Changed Money Forever",
            "The Rise and Fall of FTX",
            "Terra Luna Collapse: Full Story",
            "The Silk Road Story: Bitcoin's Dark Past",
            "Bitcoin Halving History: 2012, 2016, 2020, 2024",
            "The First Bitcoin Transaction Explained",
            "How Satoshi Nakamoto Disappeared",
            "The Venezuelan Hyperinflation and Crypto",
            "Greek Debt Crisis and Bitcoin"
        ]
    },
    "analysis": {
        "peso": 15,
        "temas": [
            "Bitcoin Halving Cycles Analysis",
            "Gold Price Patterns Over 50 Years",
            "Crypto Market Correlation Analysis",
            "Institutional Adoption Trends",
            "Central Bank Digital Currencies Impact",
            "Inflation Impact on Gold and Bitcoin",
            "Stock to Flow Model Explained",
            "On-Chain Analysis Basics",
            "Macro Economic Factors Affecting Crypto",
            "Geopolitical Events and Safe Haven Assets",
            "Bitcoin Dominance and Altseason Cycles",
            "MVRV Ratio and Market Valuation",
            "Mining Hash Rate and Price Correlation",
            "Whale Activity and Market Movements",
            "Crypto Volatility Patterns",
            "Market Sentiment Indicators",
            "The Psychology Behind Market Bubbles",
            "Interest Rates vs Crypto Performance"
        ]
    },
    "news": {
        "peso": 10,
        "temas": [
            "Major Crypto Regulation Update",
            "Bitcoin ETF Flow Analysis",
            "Central Bank Gold Purchases Report",
            "Major Exchange News",
            "New Institutional Crypto Adoption"
        ]
    }
}

def seleccionar_categoria():
    """Selecciona categoría basada en pesos y evita temas prohibidos recientes."""
    temas_pub = cargar_temas_publicados()
    hoy = datetime.now(ZoneInfo("America/Mexico_City")).date()
    
    temas_recientes_30d = set()
    for t in temas_pub:
        try:
            fecha_tema = datetime.strptime(t["fecha"], "%Y-%m-%d").date()
            if (hoy - fecha_tema).days <= 30:
                temas_recientes_30d.add(t["tema"].lower().strip())
        except:
            continue
    
    # Intentar hasta 10 veces encontrar un tema no repetido
    for _ in range(10):
        total_peso = sum(cat["peso"] for cat in CATEGORIAS_CONTENIDO.values())
        numero_aleatorio = random.uniform(0, total_peso)
        
        peso_acumulado = 0
        for categoria, datos in CATEGORIAS_CONTENIDO.items():
            peso_acumulado += datos["peso"]
            if numero_aleatorio <= peso_acumulado:
                temas_disponibles = [
                    t for t in datos["temas"]
                    if t.lower() not in temas_recientes_30d
                ]
                if temas_disponibles:
                    return categoria, random.choice(temas_disponibles)
                else:
                    # Si todos están usados, devolver aleatorio de todas formas
                    return categoria, random.choice(datos["temas"])
    
    return "educational", random.choice(CATEGORIAS_CONTENIDO["educational"]["temas"])

# ================================================================
# 🎨 PALETAS Y SUJETOS VISUALES
# ================================================================
PALETAS_VIDEO = [
    "electric cyan and gold neon on dark navy",
    "emerald green and silver on black",
    "violet magenta and orange on deep blue",
    "crimson red and gold on charcoal",
    "teal and amber on dark slate",
    "ice blue and white on midnight black",
]

SUJETOS_VISUALES = [
    (["bitcoin", "btc", "crypto", "cryptocurrency", "halving"], "a giant physical golden bitcoin coin"),
    (["gold", "silver", "metal", "precious"], "shiny gold bars stacked inside a bank vault"),
    (["fed", "reserve", "rate", "interest"], "a monumental central bank building with columns"),
    (["inflation", "cpi", "price"], "a shopping cart full of groceries over a rising chart"),
    (["etf", "fund", "institutional"], "a modern glass stock exchange building"),
    (["stock", "market", "trading", "trader"], "candlestick trading charts on glowing screens"),
    (["scam", "fraud", "hack", "ftx", "collapse", "crash", "ponzi"], "falling dominoes made of coins"),
    (["regulation", "law", "sec", "mica", "legal"], "a gavel over legal documents"),
    (["ethereum", "solana", "blockchain", "technology", "rollup"], "a glowing network of blockchain nodes"),
    (["dollar", "forex", "currency"], "floating dollar bills and currency symbols"),
    (["psychology", "fear", "greed", "panic"], "a head silhouette with charts"),
    (["war", "geopolitic", "china", "russia"], "a world map with trade routes"),
    (["history", "historical", "past"], "vintage financial documents and charts"),
    (["education", "learn", "tutorial", "guide", "explained"], "educational infographic with charts"),
]

def detectar_sujeto_visual(texto_ref):
    t = (texto_ref or "").lower()
    for keywords, sujeto in SUJETOS_VISUALES:
        if any(k in t for k in keywords):
            return sujeto
    return "a cinematic financial scene with glowing charts, coins and data"

# ================================================================
# 📊 ANÁLISIS SEMANAL DE TRENDS (SIN SESGO DE FED)
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
    
    temas_text = "\n".join(temas_recientes[:10]) if temas_recientes else "None"
    
    prompt = f"""
You are a VIRAL TREND ANALYST for YouTube LONG-FORM finance/crypto videos.

CURRENT DATE: {hoy.strftime("%B %d, %Y")}

🚫 CRITICAL PROHIBITION: DO NOT focus on Federal Reserve, Fed rate, FOMC, Jerome Powell, or interest rate decision news. We have already covered those topics extensively. Focus on DIVERSE educational and historical content instead.

RECENTLY PUBLISHED TOPICS (avoid repeating):
{temas_text}

🎯 YOUR TASK: Generate 5 DIVERSE video topics for LONG-FORM content (7-9 min).

CONTENT MIX PREFERRED:
- 40% Educational (how-to, tutorials, explanations of concepts)
- 35% Historical (past events, case studies, lessons learned)
- 15% Analysis (cycles, patterns, data-driven insights)
- 10% Major news (ONLY if truly major, NOT Fed-related)

DIVERSITY REQUIREMENT: Each of the 5 topics MUST be from a DIFFERENT category (Blockchain tech, History, DeFi, Psychology, Investing basics, Regulations, Altcoins, etc.)

For each topic provide:
- topic: Topic name
- category: (educational/historical/analysis/news)
- why_trending: Data-driven reason
- viral_score: 1-10
- hook: First 30 seconds script
- seo_keywords: 3-5 keywords

Return JSON:
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
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.8,
        "max_tokens": 1500,
        "response_format": {"type": "json_object"}
    }
    
    try:
        print("📊 Analyzing weekly trends (anti-Fed bias)...")
        r = requests.post(url, headers=headers, json=payload, timeout=90)
        r.raise_for_status()
        data = r.json()
        content = data["choices"][0]["message"]["content"]
        
        content = content.strip()
        if "```json" in content:
            content = content.replace("```json", "").replace("```", "").strip()
        
        inicio = content.find("{")
        fin = content.rfind("}")
        if inicio != -1 and fin != -1:
            json_str = content[inicio:fin+1]
            trends = json.loads(json_str)
            
            with open(TRENDS_FILE, "w", encoding="utf-8") as f:
                json.dump(trends, f, indent=2, ensure_ascii=False)
            
            print(f"   ✅ Best topic: {trends.get('best_topic_this_week', 'N/A')}")
            return trends
        return None
    except Exception as e:
        print(f"⚠️ Error analyzing trends: {e}")
        return None

# ================================================================
# 🎬 GENERAR IDEA DE VIDEO (SIN SESGO DE FED)
# ================================================================
def generar_idea_video_largo(tipo, fecha_actual, trends_data=None):
    categoria_seleccionada, tema_sugerido = seleccionar_categoria()
    
    print(f"📚 Category: {categoria_seleccionada.upper()}")
    print(f"📝 Topic: {tema_sugerido}")
    
    seo_keywords = []
    if trends_data and "high_volume_keywords" in trends_data:
        seo_keywords = trends_data.get("high_volume_keywords", [])
    
    keywords_text = ", ".join(seo_keywords[:5]) if seo_keywords else "Bitcoin, crypto, gold, investing"
    
    prompt = f"""
You are a VIRAL CONTENT STRATEGIST for YouTube LONG-FORM videos (7-9 minutes) in finance/crypto.

CURRENT DATE: {fecha_actual}
CONTENT CATEGORY: {categoria_seleccionada.upper()}
SUGGESTED TOPIC: {tema_sugerido}

🚫 CRITICAL PROHIBITION: DO NOT create titles or topics about:
- Federal Reserve / Fed rate decisions / FOMC
- Jerome Powell
- Interest rate hikes or cuts
- Rate decision news
We have already covered those topics extensively. Focus on DIVERSE educational and historical content.

🎯 HIGH-VOLUME SEO KEYWORDS TO INTEGRATE:
{keywords_text}

📚 CONTENT TYPE: {categoria_seleccionada}

If EDUCATIONAL:
- Focus on teaching and explaining clearly
- Use simple language and analogies
- Include practical examples
- Step-by-step breakdown

If HISTORICAL:
- Tell a compelling story
- Include specific events
- Show cause and effect
- Extract lessons learned
- Connect past to present

If ANALYSIS:
- Use data and charts
- Show patterns and trends
- Compare different scenarios
- Provide actionable insights

If NEWS (only 10%):
- Focus on IMPACT
- Explain what it means for investors
- Include historical context

🎯 YOUR TASK: Generate 5 LONG-FORM VIDEO IDEAS optimized for SEO and virality.

REQUIREMENTS:
✅ Title: 60-70 characters (SEO optimized, front-load keyword)
✅ Include 1 emoji maximum
✅ Front-load PRIMARY KEYWORD (first 3 words)
✅ Create CURIOSITY GAP
✅ Use POWER WORDS: Complete, Ultimate, Truth, Guide, Analysis
✅ DO NOT use Federal Reserve / Fed / FOMC / Powell in titles
✅ Must be suitable for 7-9 minute deep-dive
✅ Match the category: {categoria_seleccionada}

For each idea:
- title (with SEO keyword)
- hook_30sec (first 30 seconds)
- description
- psychology_trigger (curiosity/fear/greed/education)
- seo_score (1-10)

Then SELECT THE BEST ONE and return in JSON:
{{
    "best_idea": {{
        "title": "Final title (60-70 chars, no Fed references)",
        "hook_30sec": "First 30 seconds script",
        "description": "What viewers will learn",
        "formula_used": "Formula name",
        "psychology_trigger": "curiosity/education",
        "type": "{categoria_seleccionada}",
        "seo_keywords": ["keyword1", "keyword2", "keyword3"]
    }},
    "all_ideas": [
        {{"title": "...", "hook_30sec": "...", "seo_score": 9}}
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
            
            content = content.strip()
            if "```json" in content:
                content = content.replace("```json", "").replace("```", "").strip()
            
            inicio = content.find("{")
            fin = content.rfind("}")
            if inicio != -1 and fin != -1:
                json_str = content[inicio:fin+1]
                result = json.loads(json_str)
                
                # Verificar que el título no mencione Fed
                titulo_gen = result.get("best_idea", {}).get("title", "").lower()
                if any(p in titulo_gen for p in TEMAS_PROHIBIDOS_FRECUENTES):
                    print(f"⚠️ Title contains prohibited topic, regenerating...")
                    if intento < 2:
                        continue
                
                return result
        except Exception as e:
            print(f"⚠️ Error (attempt {intento+1}): {e}")
            time.sleep(5)
    
    return None

# ================================================================
# 🏷️ SANITIZAR HASHTAGS Y TAGS (CORREGIDO)
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

def sanitizar_tags(tags_str, max_tags=20):
    """
    Sanitización agresiva para evitar error 400 de YouTube.
    - Máximo 20 tags
    - Cada tag máximo 25 caracteres
    - Solo letras, números y espacios simples
    - Sin caracteres especiales
    - Sin comas dobles
    - Elimina tags de más de 3 palabras
    """
    if not tags_str:
        return []
    
    raw_tags = [t.strip() for t in tags_str.split(",") if t.strip()]
    
    cleaned = []
    for tag in raw_tags:
        # Solo permitir letras, números y espacios
        clean = re.sub(r'[^a-zA-Z0-9áéíóúüñÁÉÍÓÚÜÑ\s]', '', tag)
        clean = clean.strip()
        clean = re.sub(r'\s+', ' ', clean)
        
        # Validaciones estrictas
        if not clean:
            continue
        if len(clean) < 2:
            continue
        if len(clean) > 25:
            clean = clean[:25]
        
        # Máximo 3 palabras
        palabras = clean.split()
        if len(palabras) > 3:
            clean = ' '.join(palabras[:3])
        
        cleaned.append(clean)
    
    # Eliminar duplicados
    seen = set()
    unique = []
    for tag in cleaned:
        tag_lower = tag.lower()
        if tag_lower not in seen:
            seen.add(tag_lower)
            unique.append(tag)
    
    # Limitar a max_tags
    unique = unique[:max_tags]
    
    # Verificar longitud total
    result = ",".join(unique)
    while len(result) > 480 and len(unique) > 5:
        unique = unique[:-1]
        result = ",".join(unique)
    
    return unique

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
# 🖼️ GENERAR IMAGEN HORIZONTAL (PEXELS)
# ================================================================
def generar_imagen_horizontal(prompt, tema="", bloque="", intentos=5):
    global _used_image_urls
    
    keyword_map = {
        "HOOK": "urgent financial crisis red alert",
        "INTRO": "professional finance background charts",
        "CHAPTER 1": "educational financial data charts",
        "CHAPTER 2": "detailed analysis graphs data",
        "CHAPTER 3": "solution success upward trend",
        "CHAPTER 4": "action steps strategy planning",
        "CLOSE": "professional call to action",
        "bitcoin": "bitcoin cryptocurrency trading",
        "crash": "stock market crash red chart",
        "gold": "gold bars wealth luxury",
        "crypto": "cryptocurrency blockchain technology",
        "trading": "trading charts candlestick graph",
        "analysis": "financial analysis data charts",
        "history": "historical financial documents vintage",
        "education": "educational infographic clean charts",
    }
    
    base_query = "finance business stock market charts"
    prompt_lower = prompt.lower()
    
    if bloque and bloque in keyword_map:
        base_query = keyword_map[bloque]
    else:
        for key, value in keyword_map.items():
            if key in prompt_lower:
                base_query = value
                break

    modifiers = [
        "abstract dark background", "neon glowing lights", "cinematic dramatic lighting",
        "macro close up detail", "minimalist clean", "vibrant colors high contrast"
    ]
    
    fallback_queries = [
        f"{base_query} {random.choice(modifiers)}",
        f"{base_query} {random.choice(modifiers)}",
        f"abstract {base_query.split()[0] if base_query else 'finance'} dark",
        "stock market trading charts neon",
        "cryptocurrency blockchain abstract"
    ]
    
    for intento in range(intentos):
        current_query = fallback_queries[intento % len(fallback_queries)]
        random_page = random.randint(1, 5)
        
        url = f"https://api.pexels.com/v1/search?query={current_query.replace(' ', '+')}&per_page=5&orientation=landscape&page={random_page}"
        headers = {"Authorization": PEXELS_API_KEY}
        
        try:
            print(f"   🖼️ Pexels: '{current_query}' (attempt {intento+1}/{intentos})")
            r = requests.get(url, headers=headers, timeout=30)
            
            if r.status_code == 200:
                data = r.json()
                if data.get("photos") and len(data["photos"]) > 0:
                    photos = data["photos"][:5]
                    
                    for photo in photos:
                        img_url = photo["src"].get("landscape") or photo["src"].get("original")
                        
                        if img_url in _used_image_urls:
                            continue
                        
                        _used_image_urls.add(img_url)
                        print(f"   ✅ Unique image: {photo.get('photographer', 'Unknown')}")
                        return img_url
                        
        except Exception as e:
            print(f"   ⚠️ Error: {e}")
            
        if intento < intentos - 1:
            time.sleep(6)
    
    return None

# ================================================================
# 🎨 FONDO SÓLIDO
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
            print(f"⚠️ Font download failed: {e}")
    rutas = [
        "Anton.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    for ruta in rutas:
        if os.path.exists(ruta):
            return ruta
    return None

# ================================================================
# 🖼️ MINIATURA PROFESIONAL
# ================================================================
def crear_miniatura_profesional(prompt_miniatura, texto_portada, salida="miniatura_largo_en.jpg"):
    try:
        print("🖼️ Generating thumbnail...")
        
        prompt_largo = (
            f"{prompt_miniatura}, "
            "professional documentary style, balanced contrast, "
            "neon accents, space for text on right side"
        )
        
        fondo_url = generar_imagen_horizontal(prompt_largo, tema=texto_portada, intentos=2)
        
        if fondo_url and fondo_url.startswith("http"):
            try:
                r = requests.get(fondo_url, timeout=30)
                r.raise_for_status()
                img_path = "temp_thumb_fondo_largo_en.jpg"
                with open(img_path, "wb") as f:
                    f.write(r.content)
            except:
                img_path = generar_fondo_solido(color=(10, 10, 25))
        else:
            img_path = generar_fondo_solido(color=(10, 10, 25))
        
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
        
        size = 140
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
        
        offset = 8
        for i, linea in enumerate(lineas):
            bbox = draw.textbbox((0, 0), linea, font=font)
            text_w = bbox[2] - bbox[0]
            x = 1280 - text_w - 80
            y = y_inicio + i * alto_linea
            
            for dx in range(-offset, offset+1, 2):
                for dy in range(-offset, offset+1, 2):
                    draw.text((x + dx, y + dy), linea, fill='black', font=font)
        
        for i, linea in enumerate(lineas):
            bbox = draw.textbbox((0, 0), linea, font=font)
            text_w = bbox[2] - bbox[0]
            x = 1280 - text_w - 80
            y = y_inicio + i * alto_linea
            
            draw.text((x, y), linea, fill=(255, 215, 0), font=font)
        
        img.save(salida, quality=95)
        print(f"✅ Thumbnail created: {salida}")
        return salida
    except Exception as e:
        print(f"⚠️ Error in thumbnail: {e}")
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
        print(f"⚠️ Error chapter: {e}")
        return None

# ================================================================
# 🔴 CTA FINAL
# ================================================================
def crear_cta_final_pil(duracion=3, ancho=1280, alto=720):
    try:
        img = Image.new('RGB', (ancho, alto), (15, 15, 20))
        draw = ImageDraw.Draw(img)
        texto = "🔴 SUBSCRIBE"
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
        temp_path = "temp_cta_en.png"
        img.save(temp_path)
        clip = ImageClip(temp_path, duration=duracion)
        clip = clip.crossfadein(0.5)
        return clip
    except Exception as e:
        print(f"⚠️ Error CTA: {e}")
        return None

# ================================================================
# 📝 GENERAR GUION LARGO
# ================================================================
def generar_guion_largo(tipo, fecha_actual, idea=None):
    titulos_pub = cargar_titulos_publicados()["titulos"][-10:]
    titulos_referencia = "\n".join([f"- {t}" for t in titulos_pub]) if titulos_pub else "None yet."

    if not idea:
        print("💡 Generating idea...")
        idea_data = generar_idea_video_largo(tipo, fecha_actual)
        if idea_data and "best_idea" in idea_data:
            idea = idea_data["best_idea"]
            print(f"   ✅ Idea: {idea['title']}")
        else:
            idea = {"title": "Bitcoin Investing Guide", "hook_30sec": "Bitcoin is changing everything...", "description": "Full guide", "type": tipo}

    tema_elegido = idea["title"]
    hook_sugerido = idea.get("hook_30sec", "")
    
    prompt = f"""
You are a PROFESSIONAL SCRIPTWRITER for YouTube LONG-FORM videos (7-9 minutes).

VIDEO IDEA: "{tema_elegido}"
HOOK: "{hook_sugerido}"
TYPE: {tipo.upper()}
CURRENT DATE: {fecha_actual}

🚫 DO NOT use past dates like 2020-2024.
🚫 DO NOT focus on Federal Reserve, Fed rate, FOMC, or Powell unless absolutely necessary.
✅ Use current year: {fecha_actual.split()[-1]}.
✅ Use "today", "this week", "recently" for recent events.

SCRIPT STRUCTURE (7 blocks, 1300-1500 words total):
[HOOK - 0:00] Pattern interrupt + promise (100-150 words)
[INTRO - 0:30] Context and why it matters (200-250 words)
[CHAPTER 1 - 1:30] Foundation/Background (250-300 words)
[CHAPTER 2 - 3:30] Deep Dive/Analysis (300-350 words)
[CHAPTER 3 - 5:30] Advanced Insights/Solution (300-350 words)
[CHAPTER 4 - 7:30] Action Steps (250-300 words)
[CLOSE - 8:30] Summary + CTA (150-200 words)

RETENTION TACTICS:
- "But here's where it gets interesting..."
- "Now, this is where most people make a mistake..."
- "I'll show you exactly how to..."
- "The data shows something surprising..."
- "Here's what nobody is talking about..."

NUMBERS: Write with LETTERS ("four hundred" not "400")

IMAGE PROMPTS (one per segment, must match segment content):
- HOOK: "dramatic financial scene, urgent neon lights, high contrast, cinematic 8k"
- INTRO: "professional finance background, charts and data, blue and gold neon"
- CHAPTER 1: "educational visual, clean charts, explanatory graphics, cyan and gold"
- CHAPTER 2: "detailed analysis visuals, data charts, professional, emerald and silver"
- CHAPTER 3: "solution-oriented visuals, upward trends, success, gold accents"
- CHAPTER 4: "action steps visual, clear graphics, professional, teal and amber"
- CLOSE: "call-to-action visual, engaging, dynamic, violet and orange"

HASHTAGS (5-8 specific): Example "#Bitcoin #Crypto #BitcoinAnalysis #CryptoNews #MarketAnalysis"

TAGS (15-20 keywords, simple, NO special chars):
Examples: "bitcoin", "crypto", "trading", "investment", "blockchain"
- Comma-separated ONLY
- NO #, $, %, &, or any special chars
- Each tag max 25 characters
- Max 3 words per tag
- Max 20 tags total

TITLES ALREADY PUBLISHED (DO NOT REPEAT):
{titulos_referencia}

Return JSON:
{{
    "title": "Title 60-70 chars with emoji (NO Fed references)",
    "alternative_title": "Alternative",
    "keywords": ["kw1", "kw2", "kw3"],
    "description": "Full description with chapters and hashtags",
    "tags": "15-20 simple tags comma separated (NO special chars)",
    "dynamic_hashtags": "#Bitcoin #Crypto #BitcoinAnalysis",
    "script": "Full script 1300-1500 words with 7 marked blocks",
    "segments": [
        {{"block": "HOOK", "text": "text (~100-150 words)", "image_prompt": "dramatic financial scene", "timestamp": "0:00"}},
        {{"block": "INTRO", "text": "text (~200-250 words)", "image_prompt": "professional finance background", "timestamp": "0:30"}},
        {{"block": "CHAPTER 1", "text": "text (~250-300 words)", "image_prompt": "educational visual charts", "timestamp": "1:30"}},
        {{"block": "CHAPTER 2", "text": "text (~300-350 words)", "image_prompt": "detailed analysis visuals", "timestamp": "3:30"}},
        {{"block": "CHAPTER 3", "text": "text (~300-350 words)", "image_prompt": "solution oriented visuals", "timestamp": "5:30"}},
        {{"block": "CHAPTER 4", "text": "text (~250-300 words)", "image_prompt": "action steps visual", "timestamp": "7:30"}},
        {{"block": "CLOSE", "text": "text (~150-200 words)", "image_prompt": "call to action visual", "timestamp": "8:30"}}
    ],
    "cover_words": "2-3 words for thumbnail (e.g., 'FULL GUIDE')",
    "thumbnail_prompt": "Bitcoin dramatic lighting, yellow and red on black, space for text"
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
            print(f"🔄 Generating script (attempt {intento+1}/3)...")
            r = requests.post(url, headers=headers, json=payload, timeout=150)
            r.raise_for_status()
            data = r.json()
            content = data["choices"][0]["message"]["content"]
            
            content = content.strip()
            if "```json" in content:
                content = content.replace("```json", "").replace("```", "").strip()
            
            inicio = content.find("{")
            fin = content.rfind("}")
            if inicio != -1 and fin != -1:
                json_str = content[inicio:fin+1]
                try:
                    result = json.loads(json_str, strict=False)
                except json.JSONDecodeError:
                    # Intentar limpiar comas colgantes
                    json_str_clean = re.sub(r',\s*}', '}', json_str)
                    json_str_clean = re.sub(r',\s*]', ']', json_str_clean)
                    result = json.loads(json_str_clean, strict=False)
            else:
                raise ValueError("No JSON found")
            
            guion_texto = result.get("script", "")
            palabras = len(re.findall(r'\w+', guion_texto))
            print(f"📊 Script words: {palabras}")
            
            if "thumbnail_prompt" not in result:
                result["thumbnail_prompt"] = "Bitcoin dramatic lighting, yellow and red on black"
            
            if "dynamic_hashtags" not in result:
                result["dynamic_hashtags"] = ""
            
            for seg in result.get("segments", []):
                if not seg.get("image_prompt") or len(seg["image_prompt"].split()) < 5:
                    seg["image_prompt"] = f"cinematic financial scene, neon lighting, hyperrealistic, 8k"
                if "timestamp" not in seg:
                    seg["timestamp"] = "0:00"
            
            return result, tema_elegido, idea.get("description", "Financial analysis")
        except Exception as e:
            print(f"❌ Attempt {intento+1}/3 failed: {e}")
            if intento < 2:
                time.sleep(10)
    
    print("❌ Error generating script")
    sys.exit(1)

# ================================================================
# 🎬 MONTAR VIDEO
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
                    print(f"⚠️ Failed image download {i}: {e}")
                    img_path = generar_fondo_solido()
            else:
                img_path = img_url
            
            img = Image.open(img_path)
            img = ImageOps.fit(img, (1280, 720), Image.Resampling.LANCZOS)
            img.save(img_path)
            
            img_sub_path = f"temp_largo_sub_en_{i}.jpg"
            img_path = agregar_subtitulos_con_pil_16_9(img_path, texto, img_sub_path)
            
            video_clip = ImageClip(img_path).set_duration(duracion)
            
            if bloque == "HOOK":
                video_clip = video_clip.resize(lambda t: 1.1 - 0.05 * min(t/2, 1.0))
            elif bloque in ["CHAPTER 1", "CHAPTER 2", "CHAPTER 3"]:
                video_clip = video_clip.resize(lambda t: 1.0 + 0.01 * t)
            elif bloque == "CLOSE":
                video_clip = video_clip.resize(lambda t: 1.0 - 0.01 * min(t/3, 0.1))
            else:
                video_clip = video_clip.resize(lambda t: 1 + 0.015 * t)
            
        except Exception as e:
            print(f"⚠️ Failed image {i}: {e}")
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
# 📤 SUBIR A YOUTUBE (CON VERIFICACIÓN FINAL DE TAGS)
# ================================================================
def subir_a_youtube(video_path, titulo, etiquetas_str, descripcion, miniatura_path=None, dynamic_hashtags=""):
    try:
        creds = Credentials.from_authorized_user_info(YOUTUBE_USER_TOKEN)
        youtube = build("youtube", "v3", credentials=creds)
    except Exception as e:
        print(f"❌ Auth error: {e}")
        sys.exit(1)
    
    # Sanitizar tags
    tags = sanitizar_tags(etiquetas_str, max_tags=20)
    
    # Fallback a tags curados si la lista está vacía o es muy corta
    if len(tags) < 5:
        print("⚠️ Not enough valid tags. Using curated fallback tags.")
        tags = [
            "bitcoin", "crypto", "investing", "blockchain", "trading",
            "finance", "gold", "cryptocurrency", "market analysis", "investment",
            "crypto news", "bitcoin price", "altcoins", "defi", "web3",
            "financial education", "bitcoin analysis", "crypto market", "ethereum", "solana"
        ]
    
    # Verificación FINAL: cada tag válido individualmente
    final_tags = []
    for tag in tags:
        tag = tag.strip()
        if not tag:
            continue
        if len(tag) > 30:
            tag = tag[:30]
        if len(tag) < 2:
            continue
        # Verificar que solo tenga caracteres seguros
        if re.match(r'^[a-zA-Z0-9áéíóúüñÁÉÍÓÚÜÑ\s]+$', tag):
            final_tags.append(tag)
    
    # Verificar longitud total
    tags_str_final = ",".join(final_tags)
    while len(tags_str_final) > 480 and len(final_tags) > 5:
        final_tags = final_tags[:-1]
        tags_str_final = ",".join(final_tags)
    
    if len(final_tags) < 3:
        print("❌ Still not enough valid tags. Aborting.")
        sys.exit(1)
    
    print(f"📝 Final valid tags ({len(final_tags)}): {tags_str_final[:200]}...")
    
    # Hashtags
    hashtags_fijos = "#Finance #Investing"
    if dynamic_hashtags:
        dynamic_hashtags = sanitizar_hashtags(dynamic_hashtags, max_tags=6)
        hashtags_final = f"{dynamic_hashtags} {hashtags_fijos}"
    else:
        hashtags_final = hashtags_fijos
    
    disclaimer = "\n\n⚠️ IMPORTANT NOTICE: This content is for educational purposes only and does not constitute financial, legal, or investment advice."
    descripcion_final = f"{descripcion}\n\n{hashtags_final}\n{disclaimer}"
    
    body = {
        "snippet": {
            "title": titulo[:100],
            "description": descripcion_final[:5000],
            "tags": final_tags[:20],
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
    print(f"✅ Video uploaded: https://youtu.be/{video_id}")
    
    if miniatura_path and os.path.exists(miniatura_path):
        try:
            media_thumb = MediaFileUpload(miniatura_path, chunksize=-1, resumable=True)
            youtube.thumbnails().set(videoId=video_id, media_body=media_thumb).execute()
            print("✅ Thumbnail uploaded")
        except Exception as e:
            print(f"⚠️ Thumbnail error: {e}")
    
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
            except:
                pass
    print("✅ Cleanup done")

# ================================================================
# 📄 INICIALIZAR JSON
# ================================================================
def inicializar_archivos_json():
    archivos_needed = {
        "temas_largos_publicados.json": {"temas": []},
        "temas_largos_en_publicados.json": {"temas": []},
        "titulos_capital_largos_publicados.json": {"titulos": []},
        "titulos_capital_largos_en_publicados.json": {"titulos": []},
        "estado_capital_largos.json": {"ultimo_fondo": None, "publicaciones_hoy": None},
        "estado_capital_largos_en.json": {"ultimo_fondo": None, "publicaciones_hoy": None},
        "trends_semanal_largos.json": {"trending_topics": [], "best_topic_this_week": ""}
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
    print("🎬 Capital Minds - LONG VIDEO BOT (FIXED)")
    print("   ✓ 90% Educational/Historical, 10% News")
    print("   ✓ NO Fed/FOMC bias (anti-repetition)")
    print("   ✓ Aggressive tag sanitization (fixes YouTube 400)")
    print("   ✓ 15-20 simple tags, max 25 chars each")
    print("   ✓ Diverse topics across categories")
    print("="*60)

    tz_mexico = ZoneInfo("America/Mexico_City")
    fecha_actual = datetime.now(tz_mexico)
    fecha_formateada = fecha_actual.strftime("%B %d, %Y")
    print(f"📅 Date: {fecha_formateada}")
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
        print(f"✅ Already published today.")
        sys.exit(0)
    
    # Trends (opcional)
    trends_data = None
    try:
        with open(TRENDS_FILE, "r", encoding="utf-8") as f:
            trends_data = json.load(f)
    except:
        trends_data = analizar_trends_semanal_largos()
    
    # Seleccionar tipo/categoría
    tipo, tema_sugerido = seleccionar_categoria()
    print(f"📌 Content Type: {tipo.upper()}")
    print(f"📝 Topic: {tema_sugerido}")
    
    estado = cargar_estado()
    fondo_path = seleccionar_fondo_disponible(estado)
    
    # Generar idea
    print("💡 Generating video idea...")
    idea_data = generar_idea_video_largo(tipo, fecha_formateada, trends_data)
    if idea_data and "best_idea" in idea_data:
        idea = idea_data["best_idea"]
        print(f"   ✅ Idea: {idea['title']}")
    else:
        idea = None
    
    guion, tema, restriccion = generar_guion_largo(tipo, fecha_formateada, idea)
    titulo = guion["title"]
    descripcion = guion["description"]
    tags_str = guion.get("tags", "")
    segmentos = guion["segments"]
    palabras_portada = guion.get("cover_words", "WATCH THIS")
    prompt_miniatura = guion.get("thumbnail_prompt", "")
    dynamic_hashtags = guion.get("dynamic_hashtags", "")
    
    print(f"🏷️ Title: {titulo}")
    print(f"🏷️ Dynamic hashtags: {dynamic_hashtags}")
    
    capitulos = []
    for seg in segmentos:
        capitulos.append({
            "bloque": seg.get("block", "CHAPTER"),
            "timestamp": seg.get("timestamp", "0:00")
        })
    
    # Imágenes
    print("\n🖼️ Generating images...")
    imagenes_generadas = []
    for idx, seg in enumerate(segmentos):
        print(f"🎬 Segment {idx+1}/{len(segmentos)} - {seg.get('block', '')}")
        prompt_img = seg.get("image_prompt", "")
        bloque = seg.get("block", "")
        
        img_url = None
        for intento in range(5):
            img_url = generar_imagen_horizontal(prompt_img, tema=tema, bloque=bloque, intentos=1)
            if img_url:
                break
            if intento < 4:
                time.sleep(6)
        
        imagenes_generadas.append(img_url)
        if img_url:
            print(f"   ✅ Image found")
        else:
            print(f"   ❌ Failed")
        time.sleep(2)

    # Reusar imágenes para fallos
    print("\n🔄 SECOND PASS...")
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
                print(f"   ✅ Segment {idx+1}: reusing image")
            else:
                imagenes_generadas[idx] = generar_fondo_solido()
                print(f"   🖼️ Segment {idx+1}: solid background")

    # Audio
    print("\n🎵 Generating audio...")
    recursos = []
    for idx, seg in enumerate(segmentos):
        print(f"🎬 Audio segment {idx+1}/{len(segmentos)}")
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
        print("❌ No resources")
        sys.exit(1)
    
    video_path = montar_video_largo(recursos, fondo_path, "largo_capital_en.mp4", capitulos)
    print(f"🎬 Video: {video_path}")
    
    # Miniatura
    print("🖼️ Generating thumbnail...")
    miniatura_path = crear_miniatura_profesional(
        prompt_miniatura,
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
    print(f"📊 Content Type: {tipo.upper()}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
