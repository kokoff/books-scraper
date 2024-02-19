# Knizhoven Pazar Scraper


### Setup
```bash
pip install -r requirements.txt
```

### Credentials
Credentials can be provided as environment variables or as arguments to the `scrapy crawl` command.
```bash
export USERNAME=your username
export PASSWORD=ypur password
```

### Usage
```bash
python -m scrapy crawl books -o books.xlsx -a username=your email -a password=your password
```

### Delete Cache
```bash
rm -rf .scrapy/httpcache
```