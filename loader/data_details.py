import os
import psycopg2
from psycopg2 import sql
import json
from datetime import datetime, timedelta
def find_news_files(base_path):
    """
    Recursively browse the base_path to find 'news.json' files in directories containing '/detail'.
    """
    news_files = []
    for root, dirs, files in os.walk(base_path):
        if 'detail' in root and 'news.json' in files:
            # Extract the path to the file
            file_path = os.path.join(root, 'news.json')
            
            # Infer stock_code and date from the path
            stock_code, date = infer_stock_code_and_date(root)
            if stock_code and date:
                news_files.append({
                    'file_path': file_path,
                    'stock_code': stock_code,
                    'date': date
                })
    
    return news_files

def infer_stock_code_and_date(file_path):
    """
    Infer stock_code and date from the directory structure.
    """
    # Split the path to get the relevant parts
    parts = file_path.split(os.sep)
    
    # Ensure we have at least the required parts
    if len(parts) < 4:
        return None, None
    
    # Extract date and stock_code
    date = parts[-3]  # The date is always 3 directories up from 'detail'
    stock_code = parts[-2]  # The stock_code is 4 directories up from 'detail'
    
    # Validate date format
    try:
        # You might want to validate the date format further
        year, month, day = map(int, date.split('-'))
        if len(date) != 10 or len(parts[-3]) != 10:
            raise ValueError("Invalid date format")
    except ValueError:
        return None, None
    
    return stock_code, date

def load_data(files):
    db_params = {
        'host': 'host.docker.internal',
        'port': 5432,
        'user': 'postgres',
        'password': 'password',
        'database': 'stocks'
    }

    # Connect to PostgreSQL
    conn = psycopg2.connect(**db_params)
    cursor = conn.cursor()
    for file in files:
        stock_code = file['stock_code']
        date = file['date']
        file_path = file['file_path']
        file_data = None
        with open(file_path, 'r') as file:
            file_data = json.load(file)
        for entry_new in file_data:

            cursor.execute("""
            SELECT 1 FROM public.stock_news
                    WHERE stock_code = %s AND url = %s
            """, (stock_code, entry_new["url"]))
            existing_record = cursor.fetchone()
            if not existing_record:
                print(f"Creating detail for {stock_code} -> {entry_new['url']}")
                insertParams = {
                    "stock_code": stock_code,
                    "date": date,
                    "url": entry_new["url"],
                    "title": entry_new["title"],
                    "detail": entry_new["detail"]
                }
                insert_query = sql.SQL("""
                    INSERT INTO public.stock_news (
                        stock_code, date, url, title, detail, sentiment_score
                    ) VALUES (
                        %(stock_code)s, %(date)s, %(url)s, %(title)s, %(detail)s, 0.0
                    )
                """)
                cursor.execute(insert_query, insertParams)

        rename_file_with_timestamp(file_path)
            
    conn.commit()
    conn.close()

def rename_file_with_timestamp(file_path):
    # Ensure the file path is valid
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"The file {file_path} does not exist.")
    
    # Get the directory and file name from the file path
    directory, original_filename = os.path.split(file_path)
    
    # Get the base name and extension
    basename, extension = os.path.splitext(original_filename)
    
    # Get the current timestamp in the desired format
    timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    
    # Create the new file name with the timestamp
    new_filename = f"processed+{timestamp}{extension}"
    
    # Join the directory with the new file name
    new_file_path = os.path.join(directory, new_filename)
    
    # Rename the file
    os.rename(file_path, new_file_path)
    print("rename_file_with_timestamp " + file_path)
    return new_file_path

# Example usage
base_path = '/app/local/stocks/scrapper/news'
news_files = find_news_files(base_path)

for item in news_files:
    print(f"File Path: {item['file_path']}")
    print(f"Stock Code: {item['stock_code']}")
    print(f"Date: {item['date']}")
    print()

load_data(news_files)