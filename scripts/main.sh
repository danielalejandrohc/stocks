#!/bin/bash

# Define the list of items
list=(
  #"NVDA"	
  "NET" "ABNB" "CRM" "RDDT" "PLTR" "SPOT" "WMT" "SMCI"
  "AMD" "NVDA" "MSFT" "META" "AMZN" "MELI" "INTC" "TSLA"
  "IBM" "ORCL" "^GSPC" "BAC" "T" "C" "^NDX" "QQQ"
)

# Iterate over the list
for item in "${list[@]}"; do
  echo "Processing $item"  
  # Gather title and url of the news
  python /app/local/stocks/scrapper/gather_yfinance_news.py $item 
  # Add your processing command here
  # For example, you might want to fetch some data or execute a command with $item
done

# Load the the prices into the database
#python /app/local/stocks/loader/data_loader.py 
# Load the details of the data
#python /app/local/stocks/loader/data_details.py 
# Load the news into the database
#python /app/local/stocks/scrapper/process_news_in_db.py