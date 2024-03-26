# Knizhen Pazar Scraper
Scraper that downloands your inventory from https://knizhen-pazar.net/ to excel file.

### Setup
```bash
pip install -r requirements.txt
```

### Credentials
Credentials can be provided as environment variables 
```bash
export USERNAME=your username
export PASSWORD=ypur password
```
or as arguments to the `scrapy crawl` command
```bash
python -m scrapy crawl ... -a username=your email -a password=your password
```

### Usage
Scrape books for sale
```bash
python -m scrapy crawl books -o books.xlsx
```
Scrape offsale books
```bash
python -m scrapy crawl offsale -o offsale.xlsx
```
Scrape balance
```bash
python -m scrapy crawl balance -o balance.xlsx
```

### Delete Cache
```bash
rm -rf .scrapy/httpcache
```
