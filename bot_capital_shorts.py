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

ESTADO_FILE_ES = "estado_capital_shorts.json"
TITULOS_FILE_ES = "titulos_capital_shorts_publicados.json"
TEMAS_PUBLICADOS_FILE_ES = "temas_shorts_publicados.json"

META_DIARIA_SHORTS = 3
DIAS_SIN_REPETIR_TEMA = 30

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
# CONSTRUIR PROMPT DE IMAGEN POR SEGMENTO (USANDO PROMPT DE DEEPSEEK)
# ================================================================
def construir_prompt_segmento(titulo, prompt_deepseek, idx_bloque, paleta):
    """Enriquece el prompt de DeepSeek con paleta y composición para vertical."""
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
    """Fondo de miniatura adaptado al título y al prompt de DeepSeek."""
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
# 🏷️ SANITIZAR HASHTAGS
# ================================================================
def sanitizar_hashtags(hashtags_str, max_tags=6):
    """Limpia y formatea hashtags para YouTube/Rumble."""
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

# ================================================================
# MÚSICA CORPORATE
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
# FUNCIONES DE ESTADO (con soporte para revisar también los archivos en español)
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
            fecha_tema = datetime.strptime(t["fecha"], "%Y-%m-%d").date()
            if (hoy - fecha_tema).days < dias:
                return True
    return False

# ================================================================
# TREND-JACKING CON NOTICIAS DEL DÍA (EN INGLÉS)
# ================================================================
def obtener_noticia_trending():
    if not NEWSAPI_KEY:
        return None
    try:
        url = "https://newsapi.org/v2/top-headlines"
        params = {
            "category": "business",
            "language": "en",
            "apiKey": NEWSAPI_KEY,
            "pageSize": 5,
            "country": "us"
        }
        r = requests.get(url, params=params, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if data.get("articles"):
                for article in data["articles"]:
                    title = article.get("title", "")
                    keywords = ["bitcoin", "crypto", "gold", "etf", "inflation", "fed", "reserve", "stock", "market", "interest", "rates", "dollar", "economy"]
                    if any(word in title.lower() for word in keywords):
                        return title
                return data["articles"][0].get("title", "")
        return None
    except Exception as e:
        print(f"⚠️ Error getting news: {e}")
        return None

# ================================================================
# SANITIZAR TAGS MEJORADO
# ================================================================
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
# GENERAR FONDO SÓLIDO (fallback)
# ================================================================
def generar_fondo_solido(color=(20, 20, 50), ancho=1080, alto=1920):
    img = Image.new('RGB', (ancho, alto), color)
    path = f"temp_fondo_{random.randint(1000,9999)}.jpg"
    img.save(path)
    return path

def truncar_texto(texto):
    palabras = texto.split()
    if len(palabras) <= 110:
        return texto
    truncado = ' '.join(palabras[:110])
    if not truncado.endswith(('.', '!', '?')):
        truncado += '.'
    return truncado

# ================================================================
# GENERACIÓN DE IDEAS (CON 25 FORMATOS)
# ================================================================
def generar_idea_video(tipo, fecha_actual):
    prompt = f"""
You are a CONTENT STRATEGIST for YouTube Shorts in the finance/crypto niche.

📅 CURRENT DATE: {fecha_actual}
⚠️ IMPORTANT: DO NOT use past dates like 2020-2024. Use current date or "today".

🎯 YOUR TASK: Generate 5 diverse SHORT VIDEO IDEAS (30-60 seconds) covering different ANGLES within finance/crypto.

🎯 AVAILABLE FORMATS (choose a DIFFERENT one for each idea):
1. NEWS BREAKDOWN: Explain a recent financial news event (e.g., Fed rate decision, inflation report, Bitcoin ETF flow).
2. EDUCATIONAL CONCEPT: Teach a basic financial concept (e.g., "What is a bear market?", "How does staking work?").
3. PSYCHOLOGY & BEHAVIOR: Analyze investor psychology (e.g., "Why do we panic sell?", "How to avoid FOMO").
4. MARKET ANALYSIS: Give a quick market update (e.g., "Bitcoin dominance rises", "Altcoin season incoming").
5. HISTORICAL LESSON: Share a lesson from a past financial event (e.g., "What happened in 2008?", "Mt. Gox collapse").
6. COMPARISON: Compare two assets or strategies (e.g., "Bitcoin vs. Gold", "Active vs. Passive investing").
7. TIP & STRATEGY: Provide a practical tip (e.g., "How to secure your crypto", "How to read a candlestick chart").
8. MYTH BUSTING: Debunk a common financial myth (e.g., "Is gold always a safe haven?").
9. EXPERT OPINION: Summarize an expert's view on a topic (e.g., "What does Cathie Wood say about Bitcoin?").
10. DATA HIGHLIGHT: Show a surprising data point (e.g., "70% of retail traders lose money").
11. INTERVIEW SUMMARY: Summarize a key interview or statement from a CEO or influencer.
12. COUNTRY ANALYSIS: Analyze crypto adoption or regulation in a specific country.
13. BLOCKCHAIN TECHNOLOGY: Explain a technical concept (e.g., "What is Layer 2?", "Proof of Stake").
14. ADVANCED TRADING: Share a trading strategy (e.g., "How to use stop-loss orders").
15. REGULATION UPDATE: Discuss new laws or regulations affecting crypto/finance.
16. SUSTAINABILITY & MINING: Discuss the environmental impact of crypto mining and solutions.
17. SUCCESS STORY: Tell a story of a successful investor or trader.
18. FAILURE STORY: Tell a story of a loss or mistake and the lesson learned.
19. PREDICTION: Make a prediction about future trends or prices.
20. TECHNICAL ANALYSIS: Explain a chart pattern (e.g., "Cup and handle", "Head and shoulders").
21. EXCHANGE COMPARISON: Compare two popular exchanges (e.g., "Binance vs. Coinbase").
22. SECURITY BEST PRACTICES: Give security tips (e.g., "How to avoid phishing scams").
23. DEFI DEEP DIVE: Explain a DeFi protocol (e.g., "What is Uniswap?").
24. NFT & METAVERSE: Discuss the impact of NFTs or the metaverse on finance.
25. GEOPOLITICAL IMPACT: Explain how global events affect markets.

🎯 PREVENT REPETITION:
- DO NOT use the same format twice in the 5 ideas.
- DO NOT always use "$100" or "30 days" – vary amounts and timeframes.
- AVOID sensationalist titles like "turned $X into $Y" – prefer informative hooks.
- COVER different topics: macroeconomics, education, psychology, technology, regulation, etc.

CONTENT TYPE: {tipo} (news, educational, scam, psychology, analysis)

Your task is to generate 5 VIDEO IDEAS following the formats above.

For each idea, write:
- Title (50-60 characters, with emoji, generating CURIOSITY but realistic).
- 1-2 line description explaining the topic.
- Format used (from the list above).
- Curiosity level (1-10).

Then CHOOSE THE BEST IDEA (the one with the most curiosity and the most DIFFERENT from previous videos) and return it.

RESPONSE IN JSON:
{{
    "best_idea": {{
        "title": "Final title with curiosity (no past dates)",
        "description": "Idea description",
        "format": "Name of the format used (e.g., 'Educational Concept')",
        "type": "{tipo}"
    }},
    "ideas_generated": [
        {{"title": "...", "description": "...", "format": "...", "curiosity": 8}},
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
        "max_tokens": 1000,
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
# GENERAR GUION SHORT (CON PROMPTS DE IMAGEN POR SEGMENTO Y HASHTAGS DINÁMICOS)
# ================================================================
def generar_guion_financiero(tipo, idea=None, fecha_actual=None):
    if not fecha_actual:
        fecha_actual = datetime.now(ZoneInfo("America/Mexico_City")).strftime("%B %d, %Y")

    titulos_pub = cargar_titulos_publicados()["titulos"][-10:]
    titulos_referencia = "\n".join([f"- {t}" for t in titulos_pub]) if titulos_pub else "None yet."

    TEMAS_REALES = [
        "Federal Reserve interest rate decision and its impact on crypto",
        "Inflation report: CPI data exceeds expectations",
        "Bitcoin ETF inflows reach record high",
        "US dollar strength and its effect on Bitcoin",
        "Oil prices surge: implications for global markets",
        "China's economy slows down: impact on crypto",
        "European Central Bank rate cut expectations",
        "Global recession fears: are we heading for a downturn?",
        "US jobs report beats estimates: what it means for markets",
        "Japan's interest rate policy and crypto markets",
        "What is a bear market and how to survive it",
        "How to read a candlestick chart",
        "The difference between market cap and price",
        "What is a stablecoin and how does it work",
        "How to set up a crypto wallet safely",
        "What is staking and how does it generate yield?",
        "Understanding blockchain technology in 60 seconds",
        "What is a smart contract?",
        "What is an ETF and how does it work?",
        "What is dollar-cost averaging?",
        "Why do most traders lose money? Psychology explained",
        "How to overcome FOMO in crypto",
        "The importance of risk management",
        "Why panic selling is usually a mistake",
        "How to stay calm during market crashes",
        "What is the 'fear and greed index' and why it matters?",
        "The psychology of market cycles",
        "Bitcoin dominance: what it means for altcoins",
        "Ethereum's transition to proof-of-stake: explained",
        "Solana vs. Ethereum: which is better?",
        "Layer 2 scaling solutions explained",
        "What is DeFi and why is it important?",
        "RWA tokenization: the next big trend",
        "Altcoin season: what it is and when it happens",
        "Bitcoin halving: what it is and why it matters",
        "What we learned from the FTX collapse",
        "The 2008 financial crisis and Bitcoin's origin",
        "Mt. Gox hack: lessons for investors",
        "The 2020 COVID crash and recovery",
        "How the 2022 bear market shaped crypto",
        "The 2017 bull run and its aftermath",
        "How to use dollar-cost averaging",
        "Why you should never share your private keys",
        "How to spot a crypto scam",
        "How to choose a reliable exchange",
        "How to secure your crypto with a hardware wallet",
        "How to research a cryptocurrency before buying",
        "How to create a diversified crypto portfolio",
        "Is Bitcoin a bubble? Debunking the myth",
        "Is gold always a safe haven?",
        "Can you get rich overnight with crypto? The truth",
        "Are all altcoins scams? The reality",
        "Is crypto dead after a crash?",
        "70% of retail traders lose money: the data",
        "Bitcoin's energy consumption: facts vs. fiction",
        "How much crypto is held by institutions?",
        "The average crypto investor's portfolio composition",
        "What is a rollup? Layer 2 explained",
        "Zero-knowledge proofs: what they are and why they matter",
        "The future of blockchain interoperability",
        "Crypto regulation in the US: what's changing",
        "Europe's MiCA regulation explained",
        "How regulation affects crypto prices",
        "What is Uniswap? DeFi explained",
        "Yield farming: what it is and how it works",
        "What are DAOs? Decentralized organizations explained",
        "Web3: the future of the internet?"
    ]

    if not idea:
        print("💡 Generating idea with varied format...")
        idea_data = generar_idea_video(tipo, fecha_actual)
        if idea_data and "best_idea" in idea_data:
            idea = idea_data["best_idea"]
            print(f"   ✅ Selected idea: {idea['title']}")
            print(f"   📌 Format: {idea.get('format', 'general')}")
        else:
            print("⚠️ No idea generated, using fallback topic.")
            tema_aleatorio = random.choice(TEMAS_REALES)
            idea = {"title": tema_aleatorio, "restriction": "Educational content", "format": "Educational Concept"}

    tema_elegido = idea["title"]
    restriccion = idea.get("restriction", "Financial education")
    formato = idea.get("format", "Educational Concept")

    prompt = f"""
You are a FINANCE EXPERT and EDUCATIONAL CONTENT CREATOR for YouTube SHORTS.

📌 VIDEO IDEA: "{tema_elegido}"
📌 FORMAT TYPE: {formato}
📌 CONTENT TYPE: {tipo.upper()}
📅 CURRENT DATE: {fecha_actual}

⚠️ DATE RULE: DO NOT use past dates (2020-2024). Use current year only.

🎯 CONTENT RULES:
1. Write EXACTLY between 90 and 110 words.
2. Structure: HOOK → DATA → TAKEAWAY → CLOSE.
   - [HOOK] Present the topic with a curiosity gap (e.g., "Did you know that...", "Here's why...").
   - [DATA] Provide factual data, explanation, or context.
   - [TAKEAWAY] Give a clear takeaway or lesson.
   - [CLOSE] End with a CTA (e.g., "Follow for more insights").
3. Tone: Educational, informative, and engaging – NOT sensationalist.
4. Numbers written with LETTERS (not "400,500").

🎯 TITLE OPTIMIZATION (IMPORTANT):
- Make the title more clickable but NOT sensationalist.
- Add a curiosity gap (e.g., "Why..." instead of "This is why").
- Use power words like "The Truth About", "What You Need to Know".
- Keep the title between 50-60 characters.
- Use 1 emoji maximum.

🎯 SEO RULES:
1. KEYWORDS: 2-3 high-volume terms.
2. TAGS: 15-20 tags (no dates).
3. COVER WORDS: 2-3 impactful words (e.g., "BITCOIN", "CRASH", "EXPLAINED").

🎯 IMAGE PROMPTS (CRITICAL - MUST BE SEGMENT-SPECIFIC):
For EACH segment, you MUST generate a DETAILED image prompt that VISUALLY REPRESENTS the content of that specific segment's text.

RULES:
1. Each segment MUST have a UNIQUE image prompt based on its own text content.
2. If the segment talks about "panic selling", show panic selling visuals (red charts, fear).
3. If the segment talks about "Bitcoin halving", show Bitcoin halving visuals.
4. If the segment talks about "Fed rate hike", show a central bank or interest rate chart.
5. If the segment talks about "gold", show gold bars or coins.
6. DO NOT repeat the same prompt across segments.
7. Each prompt must be descriptive (at least 8 words).
8. Style: hyperrealistic, cinematic, neon, 8k.
9. PROHIBITED: people, faces, text, numbers, letters, watermarks, black boxes.

🎯 HASHTAGS RULES (CRITICAL - IN ENGLISH):
- Generate 4-6 hashtags that are SPECIFIC to the Shorts topic.
- Include the main keyword(s) of the video.
- Each hashtag must start with "#" and have no spaces.
- DO NOT use generic hashtags like #shorts or #video.
- DO NOT use #Finance or #Shorts as dynamic (they are added automatically).
- Separate hashtags with spaces.
- Example for Bitcoin halving: "#BitcoinHalving #BTC #CryptoHalving #BitcoinNews"

🎯 THUMBNAIL DESIGN:
Create a prompt in ENGLISH for the thumbnail background. It should represent the OVERALL topic.
- Style: "crypto YouTube thumbnail", neon, high contrast, cinematic, hyperrealistic.
- PROHIBITED: people, faces, text.
- Size: 1280x720 (horizontal).

🚫 TITLES ALREADY PUBLISHED (DO NOT REPEAT):
{titulos_referencia}

📤 RESPONSE: Return STRICTLY this JSON:
{{
    "title": "Optimized title (50-60 chars, with emoji and curiosity gap, no past dates)",
    "alternative_title": "Second title for A/B testing",
    "keywords": ["keyword1", "keyword2", "keyword3"],
    "hook_description": "Hook for description (max 90 chars)",
    "context_description": "Context in one sentence",
    "source_story": "Story source (e.g., 'Federal Reserve data' or 'Personal experience')",
    "cover_words": "2-3 words for thumbnail",
    "tags": "15-20 tags separated by commas (no dates)",
    "dynamic_hashtags": "4-6 hashtags specific to the topic (e.g., '#BitcoinHalving #BTC #CryptoHalving')",
    "segments": [
        {{"block": "HOOK", "text": "text (~10-15 words)", "image_prompt": "Detailed prompt for THIS specific segment's content"}},
        {{"block": "DATA", "text": "text (~20-30 words)", "image_prompt": "Detailed prompt for THIS specific segment's content"}},
        {{"block": "TAKEAWAY", "text": "text (~20-30 words)", "image_prompt": "Detailed prompt for THIS specific segment's content"}},
        {{"block": "CLOSE", "text": "text (~15-20 words)", "image_prompt": "Detailed prompt for THIS specific segment's content"}}
    ],
    "thumbnail_prompt": "Prompt in English for the thumbnail background (NO text, NO people, 1280x720)"
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

            # Verificar que hay segmentos con image_prompt
            if "segments" not in data or len(data["segments"]) != 4:
                raise ValueError("Missing segments")
            
            for seg in data["segments"]:
                if not seg.get("image_prompt") or len(seg["image_prompt"].split()) < 5:
                    seg["image_prompt"] = f"cinematic financial scene about {tema_elegido[:40]}, neon lighting, hyperrealistic, 8k, no people, no text"

            # Reconstruir full_text desde segments (para validación y logs)
            texto = ""
            for seg in data["segments"]:
                texto += f"[{seg['block']}] {seg['text']}\n"

            # Validar longitud del texto completo
            palabras = len(re.findall(r'\w+', texto))
            if palabras < 70 or palabras > 130:
                if palabras > 130:
                    data["segments"] = truncar_segmentos(data["segments"])
                    texto = ""
                    for seg in data["segments"]:
                        texto += f"[{seg['block']}] {seg['text']}\n"
                elif palabras < 70:
                    # Añadir algo al último segmento para cumplir
                    data["segments"][-1]["text"] += " This is a quick financial insight. Follow for more."
                    texto = ""
                    for seg in data["segments"]:
                        texto += f"[{seg['block']}] {seg['text']}\n"

            # Verificar duplicado
            titulo = data.get("title", "").strip()
            titulo = re.sub(r'#\w+', '', titulo).strip()
            if titulo_ya_publicado(titulo):
                raise ValueError("Duplicate title")

            # Tags
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
            return data, tema_elegido, restriccion
            
        except Exception as e:
            print(f"❌ Attempt {intento+1}/6 failed: {e}")
            if intento < 5:
                time.sleep(10)

    print("❌ ALL ATTEMPTS FAILED.")
    sys.exit(1)

def truncar_segmentos(segments):
    """Trunca el texto de los segmentos para mantener el total dentro del límite."""
    total_palabras = sum(len(seg["text"].split()) for seg in segments)
    if total_palabras <= 110:
        return segments
    # Reducir proporcionalmente cada segmento
    objetivo = 110
    factor = objetivo / total_palabras
    nuevos = []
    for seg in segments:
        palabras = seg["text"].split()
        nuevo_largo = max(3, int(len(palabras) * factor))
        nuevas_palabras = palabras[:nuevo_largo]
        nuevos.append({"block": seg["block"], "text": " ".join(nuevas_palabras), "image_prompt": seg.get("image_prompt", "")})
    return nuevos

# ================================================================
# GENERAR IMAGEN VERTICAL (PEXELS API - PORTRAIT)
# ================================================================
def generar_imagen_vertical(prompt, tema="", intentos=3):
    # Pexels API usa consultas de búsqueda, no prompts generativos detallados.
    search_query = tema if tema else prompt
    
    # Limpiar consulta: mantener solo letras y espacios, máx 50 caracteres
    search_query = re.sub(r'[^a-zA-Z0-9\s]', '', search_query).strip()
    if len(search_query) > 50:
        search_query = search_query[:50]
    if not search_query:
        search_query = "finance business technology"

    # Consultas de respaldo si la primera falla
    fallback_queries = [
        search_query,
        "finance business technology",
        "abstract dark background",
        "stock market charts"
    ]
    
    for intento in range(intentos):
        current_query = fallback_queries[intento % len(fallback_queries)]
        # Usamos orientation=portrait para obtener imágenes verticales (9:16)
        url = f"https://api.pexels.com/v1/search?query={current_query.replace(' ', '+')}&per_page=1&orientation=portrait"
        headers = {"Authorization": PEXELS_API_KEY}
        
        try:
            print(f"   🖼️ Buscando en Pexels (vertical): '{current_query}' (intento {intento+1}/{intentos})...")
            r = requests.get(url, headers=headers, timeout=30)
            if r.status_code == 200:
                data = r.json()
                if data.get("photos") and len(data["photos"]) > 0:
                    photo = data["photos"][0]
                    # Usar tamaño 'portrait' u 'original'
                    img_url = photo["src"].get("portrait") or photo["src"].get("original")
                    print(f"   ✅ Imagen vertical encontrada exitosamente en Pexels.")
                    return img_url
            else:
                print(f"   ⚠️ Error de API Pexels {r.status_code} - {r.text[:200]}")
        except Exception as e:
            print(f"   ⚠️ Error de conexión: {e}")
            
        if intento < intentos - 1:
            print("   ⏳ Esperando 5 segundos antes de reintentar...")
            time.sleep(5)
            
    return None

# ================================================================
# GENERAR IMAGEN HORIZONTAL PARA MINIATURA (PEXELS API - LANDSCAPE)
# ================================================================
def generar_imagen_horizontal(prompt, tema="", intentos=3):
    # Pexels API usa consultas de búsqueda.
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
        "stock market charts"
    ]
    
    for intento in range(intentos):
        current_query = fallback_queries[intento % len(fallback_queries)]
        # Usamos orientation=landscape para miniaturas
        url = f"https://api.pexels.com/v1/search?query={current_query.replace(' ', '+')}&per_page=1&orientation=landscape"
        headers = {"Authorization": PEXELS_API_KEY}
        
        try:
            print(f"   🖼️ Buscando en Pexels (horizontal): '{current_query}' (intento {intento+1}/{intentos})...")
            r = requests.get(url, headers=headers, timeout=30)
            if r.status_code == 200:
                data = r.json()
                if data.get("photos") and len(data["photos"]) > 0:
                    photo = data["photos"][0]
                    img_url = photo["src"].get("landscape") or photo["src"].get("original")
                    print(f"   ✅ Imagen horizontal encontrada exitosamente en Pexels.")
                    return img_url
            else:
                print(f"   ⚠️ Error de API Pexels {r.status_code} - {r.text[:200]}")
        except Exception as e:
            print(f"   ⚠️ Error de conexión: {e}")
            
        if intento < intentos - 1:
            print("   ⏳ Esperando 5 segundos antes de reintentar...")
            time.sleep(5)
            
    return None

# ================================================================
# GENERAR AUDIO (en inglés)
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
# GENERAR RECURSOS POR SEGMENTO (USANDO PROMPTS DE DEEPSEEK)
# ================================================================
def generar_recursos_por_segmento(segmentos, segments_data, paleta_video, titulo, tema="", intentos_imagen=3):
    recursos = []
    total = len(segmentos)
    last_successful_url = None

    for idx, seg_text in enumerate(segmentos):
        print(f"  🎬 Segment {idx+1}/{total} ({len(seg_text.split())} words)")
        
        # Obtener el prompt de imagen generado por DeepSeek para este segmento
        prompt_deepseek = segments_data[idx].get("image_prompt", "")
        
        # Enriquecerlo con título, paleta y composición
        prompt_img = construir_prompt_segmento(titulo, prompt_deepseek, idx, paleta_video)
        
        print(f"    📝 Prompt: {prompt_img[:100]}...")
        
        img_url = None
        for intento in range(intentos_imagen):
            img_url = generar_imagen_vertical(prompt_img, tema=tema, intentos=1)
            if img_url:
                print(f"    ✅ Image generated (attempt {intento+1})")
                last_successful_url = img_url
                break
            time.sleep(5)
        
        # REUTILIZACIÓN DE IMAGEN ANTERIOR SI FALLA
        if not img_url:
            if last_successful_url:
                print(f"    🔄 Reusing previous image")
                img_url = last_successful_url
            else:
                print(f"    ⚠️ No previous image. Retrying...")
                time.sleep(5)
                img_url = generar_imagen_vertical(prompt_img, tema=tema, intentos=1)
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
            dur = 8.0
        
        recursos.append({
            "imagen_url": img_url,
            "audio_path": audio_path,
            "duracion": dur,
            "texto": seg_text
        })
        
        if idx < total - 1:
            print(f"   ⏳ Waiting 5 seconds...")
            time.sleep(5)
    
    return recursos

# ================================================================
# SUBTÍTULOS CON PIL (VERTICAL) - MEJORADOS
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
            return imagen_path
        
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
# 🔤 FUENTE GRUESA REAL (descarga Anton, fallback a DejaVu del sistema)
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
# 🖼️ MINIATURA PROFESIONAL (SIN rectángulo con borde)
# ================================================================
def crear_miniatura_profesional(prompt_miniatura, texto_portada, salida="miniatura_short_en.jpg"):
    try:
        print("🖼️ Generating thumbnail background...")
        fondo_url = generar_imagen_horizontal(prompt_miniatura, tema=texto_portada, intentos=2)
        if not fondo_url:
            print("⚠️ Could not generate background, using solid background")
            fondo_path = generar_fondo_solido(color=(10, 10, 30), ancho=1280, alto=720)
            fondo_url = fondo_path
        
        if fondo_url.startswith("http"):
            try:
                r = requests.get(fondo_url, timeout=30)
                r.raise_for_status()
                img_path = "temp_thumb_fondo_short_en.jpg"
                with open(img_path, "wb") as f:
                    f.write(r.content)
            except Exception as e:
                print(f"⚠️ Error downloading background: {e}. Using solid background.")
                img_path = generar_fondo_solido(color=(10, 10, 30), ancho=1280, alto=720)
        else:
            img_path = fondo_url
        
        img = Image.open(img_path)
        img = ImageOps.fit(img, (1280, 720), Image.Resampling.LANCZOS)
        draw = ImageDraw.Draw(img)
        
        texto = texto_portada.upper().strip()
        lineas = texto.split()
        if len(lineas) > 3:
            texto = ' '.join(lineas[:3])
        else:
            texto = ' '.join(lineas)
        
        palabras = texto.split()
        if len(palabras) > 1:
            mitad = len(palabras) // 2
            lineas = [' '.join(palabras[:mitad+1]), ' '.join(palabras[mitad+1:])]
            lineas = [l for l in lineas if l]
        else:
            lineas = [texto]
        
        ruta_fuente = obtener_ruta_fuente()
        
        size = 130
        while size >= 60:
            if ruta_fuente:
                font = ImageFont.truetype(ruta_fuente, size)
            else:
                font = ImageFont.load_default()
            ancho_max = 0
            for linea in lineas:
                bbox = draw.textbbox((0, 0), linea, font=font)
                ancho_max = max(ancho_max, bbox[2] - bbox[0])
            if ancho_max <= 1150:
                break
            size -= 10
        
        alto_linea = size + 15
        alto_total = alto_linea * len(lineas)
        y_inicio = (720 - alto_total) // 2
        
        for i, linea in enumerate(lineas):
            bbox = draw.textbbox((0, 0), linea, font=font)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
            x = 1280 - text_w - 60
            y = y_inicio + i * alto_linea
            
            draw.text((x + 6, y + 8), linea, fill=(0, 0, 0), font=font)
            for dx in range(-6, 7, 2):
                for dy in range(-6, 7, 2):
                    draw.text((x + dx, y + dy), linea, fill='black', font=font)
            draw.text((x, y), linea, fill=(255, 230, 60), font=font)
        
        img.save(salida)
        print(f"✅ Professional thumbnail created: {salida}")
        return salida
    except Exception as e:
        print(f"⚠️ Error in professional thumbnail: {e}")
        return None

# ================================================================
# MONTAR VIDEO SHORTS
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
        
        try:
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
            
            video_clip = (ImageClip(img_path)
                         .resize(lambda t: 1 + 0.02 * t)
                         .set_duration(duracion))
        except Exception as e:
            print(f"⚠️ Failed image {i}: {e}")
            img_path = generar_fondo_solido(color=(20, 20, 50), ancho=1080, alto=1920)
            video_clip = ImageClip(img_path, duration=duracion).resize(lambda t: 1 + 0.02 * t)
        
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
# SUBIR A YOUTUBE (CON HASHTAGS DINÁMICOS)
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
    
    print(f"📝 Final tags ({len(tags)}): {tags_str_final}")
    
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

📖 {fuente}

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
                print(f"🧹 Removed: {f}")
            except:
                pass
    print("✅ Cleanup completed")

# ================================================================
# MAIN
# ================================================================
def main():
    print("="*60)
    print("🎬 Capital Minds - SHORTS BOT (ENGLISH VERSION) - IMPROVED")
    print("   ✓ PEXELS API FOR HIGH-QUALITY IMAGES (VERTICAL & LANDSCAPE)")
    print("   ✓ SEGMENT-SPECIFIC IMAGE PROMPTS from DeepSeek")
    print("   ✓ Each image matches the segment's narration content")
    print("   ✓ DYNAMIC HASHTAGS: 4-6 hashtags specific to each Short topic")
    print("   ✓ OPTIMIZED TITLES: more clickable without being sensationalist")
    print("   ✓ Title-adapted visual subjects (fallback)")
    print("   ✓ 6 different compositions (one per block)")
    print("   ✓ Random color palette per video")
    print("   ✓ NO black boxes: overlay removed + real font download")
    print("   ✓ 25+ formats, 60+ topics, duplicate control ES/EN")
    print("="*60)

    tz_mexico = ZoneInfo("America/Mexico_City")
    fecha_actual = datetime.now(tz_mexico)
    fecha_formateada = fecha_actual.strftime("%B %d, %Y")
    print(f"📅 Current date: {fecha_formateada}")
    print("="*60)
    
    if not YOUTUBE_USER_TOKEN:
        print("❌ YOUTUBE_USER_TOKEN_CAPITAL missing")
        sys.exit(1)
    
    publicadas = obtener_publicaciones_hoy()
    if publicadas >= META_DIARIA_SHORTS:
        print(f"✅ Already published {META_DIARIA_SHORTS} shorts today. Exiting.")
        sys.exit(0)
    
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
    print(f"🎨 Color palette for this video: {paleta_video}")
    
    print("💡 Generating video idea...")
    idea_data = generar_idea_video(tipo, fecha_formateada)
    if idea_data and "best_idea" in idea_data:
        idea = idea_data["best_idea"]
        print(f"   ✅ Selected idea: {idea['title']}")
        print(f"   📌 Format: {idea.get('format', 'general')}")
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
        segmentos, segments_data, paleta_video, titulo, tema=tema_elegido
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
