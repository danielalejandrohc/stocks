from langchain_core.prompts import ChatPromptTemplate

SUMMARY_PROMPT = ChatPromptTemplate.from_template("""
Your task is to generate a brief summary for sentiment analysis. Follow these rules:
- The summary MUST include the stock code "{stock_code}".
- Focus on what moved or could move {stock_code}'s price: earnings, revenue, guidance,
  analyst ratings, partnerships, product launches, regulatory actions, or market share shifts.
- State whether the impact on {stock_code} is positive or negative, and include specific
  numbers (price, %, revenue, EPS) when available.
- Never mention other stock tickers, company names, or people's names.
  Replace them with generic terms (e.g., "analyst", "competitor", "sector").
- If no relevant information is found, return exactly:
  'No direct information about {stock_code} found.'
-------
Current Text: {text}

Final Answer (one sentence, <20 words):
""")

SENTIMENT_PROMPT = ChatPromptTemplate.from_template("""
You are a financial sentiment analyst.
Rate the sentiment of the following financial statement for the stock it mentions.

Scale:
  0.0 = very negative (strongly bad for the stock)
  0.5 = neutral
  1.0 = very positive (strongly good for the stock)

Statement: {summary}

Reply with only a single decimal number between 0.0 and 1.0. No explanation.
Score:
""")
