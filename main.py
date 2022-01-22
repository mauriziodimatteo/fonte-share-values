import calendar
import os
from datetime import datetime

import google.auth
import gspread
import pandas as pd
import requests
from bs4 import BeautifulSoup

# Constants
COMPARTO_COL = 'Comparto'
DATA_COL = 'Data'
VALORE_COL = 'Valore Quota (EUR)'
LAST_UPDATE_COL = 'Ultimo Aggiornamento'


def last_day_of_month(year, month):
    day = calendar.monthrange(year, month)[1]
    last_day = datetime(year, month, day).strftime('%d/%m/%Y')

    return last_day


def parse_page(url):
    # Constants
    MONTHS = ['Gennaio', 'Febbraio', 'Marzo', 'Aprile', 'Maggio', 'Giugno', 'Luglio', 'Agosto', 'Settembre',
              'Ottobre', 'Novembre', 'Dicembre']

    # Headers will fool FonTe's website
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36'}

    # Get and parse HTML
    html_content = requests.get(url, headers=headers).text
    soup = BeautifulSoup(html_content, 'html.parser')

    # Article is the main body
    article = soup.article
    compartment = article.find(class_="title-page").text

    # Get "year" tags
    year = article.find_all(class_='toggle-acf')

    res = []
    # For each year, extract quotes
    for y in year:
        quote_values = y.find_next(class_='toggle-content-acf').find_all(class_='toggle_element_row')
        for qv in quote_values:
            span = qv.find_all('span')

            if span[0].text.strip() in MONTHS:
                month = MONTHS.index(span[0].text.strip()) + 1
                date = last_day_of_month(int(y.text), month)
                value = float(span[1].text.strip().replace(',', '.'))
                res.append((compartment, date, value))

    return pd.DataFrame(res)


def fix_errors(quotes_df):
    """
    Public quotes contain some errors, this function fixes them.
    """

    # Error #1: "Comparto dinamico" has two quotes form Jul 2016 and June is missing.
    # Fix: the lowest quote is June's.
    #   Comparto Dinamico	2016-07-31	16.024
    #   Comparto Dinamico	2016-07-31	15.624

    quotes_df.loc[
        (quotes_df[COMPARTO_COL] == 'Comparto Dinamico') &
        (quotes_df[DATA_COL] == last_day_of_month(2016, 7)) &
        (quotes_df[VALORE_COL] == 15.624),
        DATA_COL] = last_day_of_month(2016, 6)

    # Error #2: value mismatch between public page and private page.
    #   Public page: Comparto Conservativo  2015-07-31  13.007
    #   FonTe portal: Comparto Conservativo 2015-07-31  13.011
    # Fix: replace public value with value from private page.

    quotes_df.loc[
        (quotes_df[COMPARTO_COL] == 'Comparto Conservativo') &
        (quotes_df[DATA_COL] == last_day_of_month(2015, 7)),
        VALORE_COL] = 13.011

    # Error #3: value mismatch between public page and private page.
    #   Public page: Comparto Conservativo  2017-10-31  13.319
    #   FonTe portal: Comparto Conservativo 2017-10-31  13.689
    # Fix: replace public value with value from private page.

    quotes_df.loc[
        (quotes_df[COMPARTO_COL] == 'Comparto Conservativo') &
        (quotes_df[DATA_COL] == last_day_of_month(2017, 10)),
        VALORE_COL] = 13.689

    # Error #4: value mismatch between public page and private page.
    #   Public page: Comparto Sviluppo	2007-04-30	12.889
    #   FonTe portal: Comparto Sviluppo	2007-04-30	12.890
    # Fix: replace public value with value from private page.

    quotes_df.loc[
        (quotes_df[COMPARTO_COL] == 'Comparto Sviluppo') &
        (quotes_df[DATA_COL] == last_day_of_month(2007, 4)),
        VALORE_COL] = 12.890

    return quotes_df


def write_sheet(quotes_df):
    sheet_key = os.environ.get('SHEET_KEY')
    SHEET_NAME = 'fonte_valori_quota'

    # Get credentials, authorize client and read Sheet
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets"
    ]
    creds, _ = google.auth.default(scopes)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(sheet_key)

    quotes_tuples = tuple(quotes_df.itertuples(index=False, name=None))
    sheet.values_update(
        f'{SHEET_NAME}!A2',
        params={
            'valueInputOption': 'USER_ENTERED'
        },
        body={
            'values': quotes_tuples
        }
    )


def run():
    urls = ['https://www.fondofonte.it/gestione-finanziaria/i-valori-quota-dei-comparti/comparto-garantito/',
            'https://www.fondofonte.it/gestione-finanziaria/i-valori-quota-dei-comparti/comparto-bilanciato/',
            'https://www.fondofonte.it/gestione-finanziaria/i-valori-quota-dei-comparti/comparto-crescita/',
            'https://www.fondofonte.it/gestione-finanziaria/i-valori-quota-dei-comparti/comparto-dinamico/']

    # Get quotes for all compartments
    quotes = []
    for url in urls:
        compartment_quotes = parse_page(url)
        quotes.append(compartment_quotes)

    # Concat quotes in a single dataframe
    quotes_df = pd.concat(quotes, sort=False)
    quotes_df[LAST_UPDATE_COL] = datetime.now().strftime('%d/%m/%Y %H:%M')
    quotes_df.columns = [COMPARTO_COL, DATA_COL, VALORE_COL, LAST_UPDATE_COL]

    # Fix errors and write result
    quotes_df = fix_errors(quotes_df)
    write_sheet(quotes_df)


def gcf_fonte_scraper(request):
    """Responds to any HTTP request.
          Args:
              request (flask.Request): HTTP request object.
   """

    run()

    return 'OK'


if __name__ == '__main__':
    run()