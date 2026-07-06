"""
https://www.analyticsvidhya.com/blog/2021/10/machine-learning-for-stock-market-prediction-with-step-by-step-implementation/#h-step-1-importing-the-libraries

High granularity of data. One cool feature of yfinance is that you can get highly refined data, all the way down to 5 minute, 3 minute and even 1 minute data! The full range of intervals available are:

1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo
However it is important to note that the 1m data is only retrievable for the last 7 days, and anything intraday (interval <1d) only for the last 60 days.


"""
import yfinance as yf
from datetime import datetime, timedelta
import psycopg2
from psycopg2 import sql
import json 


def print_company_info(ticker):
    stock = yf.Ticker(ticker)
    info = stock.info
    
    # Print company info
    print(f"\nCompany Info for {ticker}:")
    print()
    
    # Return company info as a dictionary for insertion
    company_info = {
        'stock_code': ticker,
        'date': datetime.now().date(),
        'name': info.get('longName', 'N/A'),
        'sector': info.get('sector', 'N/A'),
        'industry': info.get('industry', 'N/A'),
        'market_cap': float(info.get('marketCap', 0) or 0),
        'pe_ratio': float(info.get('trailingPE', 0) or 0),
        'dividend_yield': float(info.get('dividendYield', 0) or 0),
        'fifty_two_week_high': float(info.get('fiftyTwoWeekHigh', 0) or 0),
        'fifty_two_week_low': float(info.get('fiftyTwoWeekLow', 0) or 0),
        'previous_close': float(info.get('previousClose', 0) or 0),
        'current_price': float(info.get('currentPrice', 0) or 0),
        'beta': float(info.get('beta', 0) or 0),
        'total_revenue': float(info.get('totalRevenue', 0) or 0),
        'total_cash': float(info.get('totalCash', 0) or 0),
        'total_debt': float(info.get('totalDebt', 0) or 0),
        'gross_margins': float(info.get('grossMargins', 0) or 0),
        'operating_margins': float(info.get('operatingMargins', 0) or 0),
        'return_on_assets': float(info.get('returnOnAssets', 0) or 0),
        'return_on_equity': float(info.get('returnOnEquity', 0) or 0),
        'revenue_per_share': float(info.get('revenuePerShare', 0) or 0),
        'book_value': float(info.get('bookValue', 0) or 0),
        'debt_to_equity': float(info.get('debtToEquity', 0) or 0),
        'target_high_price': float(info.get('targetHighPrice', 0) or 0),
        'target_low_price': float(info.get('targetLowPrice', 0) or 0),
        'target_mean_price': float(info.get('targetMeanPrice', 0) or 0),
        'target_median_price': float(info.get('targetMedianPrice', 0) or 0),
        'recommendation_mean': float(info.get('recommendationMean', 0) or 0),
        'number_of_analyst_opinions': float(info.get('numberOfAnalystOpinions', 0) or 0),
        'website': info.get('website', 'N/A'),
        'address': f"{info.get('address1', 'N/A')}, {info.get('city', 'N/A')}, {info.get('state', 'N/A')} {info.get('zip', 'N/A')}, {info.get('country', 'N/A')}",
        'phone': info.get('phone', 'N/A'),
        'business_summary': info.get('longBusinessSummary', 'N/A')
    }
    info['symbol'] = ticker
    info['info_date'] = datetime.now().strftime('%Y-%m-%d')
    info['exDividendDate'] = str(datetime.fromtimestamp(info['exDividendDate'])) if 'exDividendDate' in info else None
    info['sharesShortPreviousMonthDate'] = str(datetime.fromtimestamp(info['sharesShortPreviousMonthDate'])) if 'sharesShortPreviousMonthDate' in info else None
    info['dateShortInterest'] = str(datetime.fromtimestamp(info['dateShortInterest'])) if 'dateShortInterest' in info else None
    info['lastFiscalYearEnd'] = str(datetime.fromtimestamp(info['lastFiscalYearEnd'])) if 'lastFiscalYearEnd' in info else None
    info['nextFiscalYearEnd'] = str(datetime.fromtimestamp(info['nextFiscalYearEnd'])) if 'nextFiscalYearEnd' in info else None
    info['mostRecentQuarter'] = str(datetime.fromtimestamp(info['mostRecentQuarter'])) if 'mostRecentQuarter' in info else None
    info['lastSplitDate'] = str(datetime.fromtimestamp(info['lastSplitDate'])) if 'lastSplitDate' in info else None
    info['irWebsite'] = info.get('irWebsite', '')
    info['lastSplitFactor'] = info.get('lastSplitFactor', '')
    info['state'] = info.get('state', '')

    return process_info(info)

def process_info(info):
    keys_to_check = [
        'address1', 'city', 'state', 'zip', 'country', 'phone', 'website', 'industry', 
        'sector', 'longBusinessSummary', 'fullTimeEmployees', 'auditRisk', 'boardRisk', 'compensationRisk', 
        'shareHolderRightsRisk', 'overallRisk', 'irWebsite', 'previousClose', 'open', 'dayLow', 'dayHigh', 
        'exDividendDate', 'beta', 'trailingPE', 'forwardPE', 'volume', 'averageVolume', 'bid', 'ask', 
        'bidSize', 'askSize', 'marketCap', 'fiftyTwoWeekLow', 'fiftyTwoWeekHigh', 'priceToSalesTrailing12Months', 
        'fiftyDayAverage', 'twoHundredDayAverage', 'currency', 'enterpriseValue', 'profitMargins', 'floatShares', 
        'sharesOutstanding', 'sharesShort', 'sharesShortPriorMonth', 'sharesShortPreviousMonthDate', 
        'dateShortInterest', 'sharesPercentSharesOut', 'heldPercentInsiders', 'heldPercentInstitutions', 'shortRatio', 
        'shortPercentOfFloat', 'impliedSharesOutstanding', 'bookValue', 'priceToBook', 'lastFiscalYearEnd', 
        'nextFiscalYearEnd', 'mostRecentQuarter', 'earningsQuarterlyGrowth', 'netIncomeToCommon', 'trailingEps', 
        'forwardEps', 'pegRatio', 'lastSplitFactor', 'lastSplitDate', 'enterpriseToRevenue', 'enterpriseToEbitda', 
        '52WeekChange', 'SandP52WeekChange', 'exchange', 'quoteType', 'symbol', 'underlyingSymbol', 'shortName', 
        'longName', 'firstTradeDateEpochUtc', 'timeZoneFullName', 'timeZoneShortName', 'uuid', 'messageBoardId', 
        'currentPrice', 'targetHighPrice', 'targetLowPrice', 'targetMeanPrice', 'targetMedianPrice', 
        'recommendationMean', 'recommendationKey', 'numberOfAnalystOpinions', 'totalCash', 'totalCashPerShare', 
        'ebitda', 'totalDebt', 'quickRatio', 'currentRatio', 'totalRevenue', 'debtToEquity', 'revenuePerShare', 
        'returnOnAssets', 'returnOnEquity', 'freeCashflow', 'operatingCashflow', 'earningsGrowth', 'revenueGrowth', 
        'grossMargins', 'ebitdaMargins', 'operatingMargins', 'financialCurrency', 'trailingPegRatio'
    ]

    for key in keys_to_check:
        if key not in info:
            info[key] = None

    return info


# Function to fetch data for a single ticker
def fetch_data(ticker):
    # Get today's date
    end_date = datetime.now().strftime('%Y-%m-%d')

    # Calculate the start date by subtracting 7 days from today
    start_date = (datetime.now() - timedelta(days=31)).strftime('%Y-%m-%d')
    print("start_date " + str(start_date))
    print("end_date " + str(end_date))
    print("ticker " + ticker)
    # Fetch historical data with 1-minute interval for the specified date range
    data = yf.download(ticker, period="5d", interval="1m")
    print("Data retrieved:")
    print(str(data))
    #data = yf.download(ticker, period="720d", interval="60m")
    return data

# List of ticker symbols
ticker_symbols = ["NET", "ABNB", "CRM", "RDDT", "PLTR", "SPOT", "WMT", "SMCI", 'AMD' , 'NVDA', 'MSFT', 'META', 'AMZN', 'MELI', 'INTC', 'TSLA', 'IBM', 'ORCL', '^GSPC', "BAC", "T", "C", "^NDX", "QQQ"] # Add more tickers as needed
#ticker_symbols = ['^GSPC', "BAC", "T", "C"]
# PostgreSQL connection parameters
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

# Process each ticker symbol one by one
for ticker in ticker_symbols:
    # Fetch data for the current ticker
    company_info = print_company_info(ticker)
    json_object = json.dumps(company_info, indent = 4) 
    print(str(json_object))
    # Insert company info into the table
    cursor.execute("""
            SELECT 1 FROM public.company_info
            WHERE stock_code = %s AND info_date = %s
    """, (ticker, company_info["info_date"]))
    existing_record = cursor.fetchone()
    if not existing_record:
        insert_query = sql.SQL("""
            INSERT INTO public.company_info (
                stock_code, info_date, address1, city, state, zip, country, phone, website, industry, sector, long_business_summary,
                full_time_employees, audit_risk, board_risk, compensation_risk, share_holder_rights_risk, overall_risk, ir_website,
                previous_close, open, day_low, day_high, ex_dividend_date, beta, trailing_pe, forward_pe, volume, average_volume, bid,
                ask, bid_size, ask_size, market_cap, fifty_two_week_low, fifty_two_week_high, price_to_sales_trailing_12_months, 
                fifty_day_average, two_hundred_day_average, currency, enterprise_value, profit_margins, float_shares, shares_outstanding, 
                shares_short, shares_short_prior_month, shares_short_previous_month_date, date_short_interest, shares_percent_shares_out, 
                held_percent_insiders, held_percent_institutions, short_ratio, short_percent_of_float, implied_shares_outstanding, book_value, 
                price_to_book, last_fiscal_year_end, next_fiscal_year_end, most_recent_quarter, earnings_quarterly_growth, net_income_to_common, 
                trailing_eps, forward_eps, peg_ratio, last_split_factor, last_split_date, enterprise_to_revenue, enterprise_to_ebitda, 
                week_change, sand_p_week_change, exchange, quote_type, symbol, underlying_symbol, short_name, long_name, first_trade_date_epoch_utc, 
                time_zone_full_name, time_zone_short_name, uuid, message_board_id, current_price, target_high_price, 
                target_low_price, target_mean_price, target_median_price, recommendation_mean, recommendation_key, number_of_analyst_opinions, 
                total_cash, total_cash_per_share, ebitda, total_debt, quick_ratio, current_ratio, total_revenue, debt_to_equity, revenue_per_share, 
                return_on_assets, return_on_equity, free_cashflow, operating_cashflow, earnings_growth, revenue_growth, gross_margins, 
                ebitda_margins, operating_margins, financial_currency, trailing_peg_ratio
            ) VALUES (
                %(symbol)s, %(info_date)s, %(address1)s, %(city)s, %(state)s, %(zip)s, %(country)s, %(phone)s, %(website)s, %(industry)s, 
                %(sector)s, %(longBusinessSummary)s, %(fullTimeEmployees)s, %(auditRisk)s, %(boardRisk)s, %(compensationRisk)s, 
                %(shareHolderRightsRisk)s, %(overallRisk)s, %(irWebsite)s, %(previousClose)s, %(open)s, %(dayLow)s, %(dayHigh)s, 
                %(exDividendDate)s, %(beta)s, %(trailingPE)s, %(forwardPE)s, %(volume)s, %(averageVolume)s, %(bid)s, %(ask)s, 
                %(bidSize)s, %(askSize)s, %(marketCap)s, %(fiftyTwoWeekLow)s, %(fiftyTwoWeekHigh)s, %(priceToSalesTrailing12Months)s, 
                %(fiftyDayAverage)s, %(twoHundredDayAverage)s, %(currency)s, %(enterpriseValue)s, %(profitMargins)s, %(floatShares)s, 
                %(sharesOutstanding)s, %(sharesShort)s, %(sharesShortPriorMonth)s, %(sharesShortPreviousMonthDate)s, 
                %(dateShortInterest)s, %(sharesPercentSharesOut)s, %(heldPercentInsiders)s, %(heldPercentInstitutions)s, %(shortRatio)s, 
                %(shortPercentOfFloat)s, %(impliedSharesOutstanding)s, %(bookValue)s, %(priceToBook)s, %(lastFiscalYearEnd)s, 
                %(nextFiscalYearEnd)s, %(mostRecentQuarter)s, %(earningsQuarterlyGrowth)s, %(netIncomeToCommon)s, %(trailingEps)s, 
                %(forwardEps)s, %(pegRatio)s, %(lastSplitFactor)s, %(lastSplitDate)s, %(enterpriseToRevenue)s, %(enterpriseToEbitda)s, 
                %(52WeekChange)s, %(SandP52WeekChange)s, %(exchange)s, %(quoteType)s, %(symbol)s, %(underlyingSymbol)s, %(shortName)s, 
                %(longName)s, %(firstTradeDateEpochUtc)s, %(timeZoneFullName)s, %(timeZoneShortName)s, %(uuid)s, %(messageBoardId)s, 
                %(currentPrice)s, %(targetHighPrice)s, %(targetLowPrice)s, %(targetMeanPrice)s, 
                %(targetMedianPrice)s, %(recommendationMean)s, %(recommendationKey)s, %(numberOfAnalystOpinions)s, %(totalCash)s, 
                %(totalCashPerShare)s, %(ebitda)s, %(totalDebt)s, %(quickRatio)s, %(currentRatio)s, %(totalRevenue)s, %(debtToEquity)s, 
                %(revenuePerShare)s, %(returnOnAssets)s, %(returnOnEquity)s, %(freeCashflow)s, %(operatingCashflow)s, %(earningsGrowth)s, 
                %(revenueGrowth)s, %(grossMargins)s, %(ebitdaMargins)s, %(operatingMargins)s, %(financialCurrency)s, %(trailingPegRatio)s
            )
        """)
        # Use the insert_query with positional parameters
        cursor.execute(insert_query, company_info)
    else:
        print("Record for Company already exists")

    
    data = fetch_data(ticker)
    for index, row in data.iterrows():
        # Check if record already exists
        cursor.execute("""
            SELECT 1 FROM public.stock
            WHERE year = %s AND month = %s AND day = %s AND hour = %s AND minute = %s AND stock_code = %s
        """, (index.year, index.month, index.day, index.hour, index.minute, ticker))
        existing_record = cursor.fetchone()

        if not existing_record:
            # Insert new record
            insert_query = sql.SQL("""
                INSERT INTO public.stock (datetime, "year", "month", "day", "hour", "minute", stock_code, timezone, "open", high, low, "close", volume, dividends, stock_splits)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """)
            cursor.execute(insert_query, (
                index  ,
                index.year,
                index.month,
                index.day,
                index.hour,
                index.minute,
                ticker,
                None,  # Replace with the actual timezone data if available
                float(row[('Open', ticker)]),
                float(row[('High', ticker)]),
                float(row[('Low', ticker)]),
                float(row[('Close', ticker)]),
                float(row[('Volume', ticker)]),
                float(row.get(('Dividends', ticker), 0)),
                row.get(('Stock Splits', ticker), 0)
            ))
            #print(f"Inserted record: {index}, Ticker: {ticker}")

# Commit the changes and close the connection
conn.commit()
conn.close()
