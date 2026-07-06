import os

DB_URL            = os.getenv("DATABASE_URL",       "postgresql://postgres:password@localhost:5432/stocks")
QDRANT_URL        = os.getenv("QDRANT_URL",          "http://localhost:6333")
OLLAMA_URL        = os.getenv("OLLAMA_URL",           "http://localhost:11434")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION",   "stock_news_summaries")
EMBEDDING_MODEL   = os.getenv("EMBEDDING_MODEL",     "nomic-embed-text")

TIMEFRAMES = {
    "1 min":  60,
    "5 min":  300,
    "30 min": 1800,
    "60 min": 3600,
    "2h":     7200,
    "4h":     14400,
    "8h":     28800,
    "24h":    86400,
}

INDICATORS = ["SMA 20", "SMA 50", "EMA 20", "Bollinger Bands", "Volume", "RSI", "MACD"]
