import logging
import os
import urllib

import scrapy
from scrapy import Selector

import warnings

warnings.filterwarnings("ignore", category=UserWarning, module='scrapy.selector.unified')


class OffsaleSpider(scrapy.Spider):
    name = 'balance'
    start_urls = ['https://knizhen-pazar.net/users/sign_in']

    def __init__(self, username=None, password=None, *args, **kwargs):
        super(OffsaleSpider, self).__init__(*args, **kwargs)
        if username and password:
            self.username = username
            self.password = password
        elif os.environ.get('USERNAME', None) and os.environ.get('PASSWORD', None):
            self.username = os.environ['USERNAME']
            self.password = os.environ['PASSWORD']
        else:
            raise ValueError('No login credentials provided!')

    def parse(self, response):
        # Fetch the CSRF token from the login page
        token = response.xpath('//input[@name="authenticity_token"]/@value').extract_first()

        # Set up the form data, replacing the token and credentials with your own
        formdata = {
            'authenticity_token': token,
            'user[email]': self.username,
            'user[password]': self.password,
            'commit': 'Вход'
            # The commit parameter might be required based on how the server processes the form.
        }

        # Set up the headers as seen in the curl command
        headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-GB,en;q=0.9,bg-BG;q=0.8,bg;q=0.7,en-US;q=0.6',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Referer': 'https://knizhen-pazar.net/users/sign_in',
            # Include more headers as needed, but be mindful not to include headers like 'Content-Length' or 'Cookie' as Scrapy manages them
        }

        # Send a post request to the login URL with the form data and headers
        return scrapy.FormRequest(
            url='https://knizhen-pazar.net/users/sign_in',
            formdata=formdata,
            headers=headers,
            callback=self.after_login
        )

    def after_login(self, response):
        # Check if login was successful
        if response.url == 'https://knizhen-pazar.net/':
            self.log("Login successful")

            link_to_books_for_sale = response.xpath(
                '//a[contains(text(), "Книги за продажба")]/@href').get()

            # Parse the URL into components
            url_parts = list(urllib.parse.urlparse(link_to_books_for_sale))
            path_parts = url_parts[2].split("/")
            path_parts[-2] = "receipts"
            path_parts = path_parts[:-1]  # Slice off 'books'
            url_parts[2] = "/".join(path_parts)
            link_to_monthly_receipts = urllib.parse.urlunparse(url_parts)

            # Request the next page and handle it with another callback method
            yield scrapy.Request(url=link_to_monthly_receipts, callback=self.parse_monthly_receipts)
        else:
            self.log("Login failed", level=logging.ERROR)

    def parse_monthly_receipts(self, response):
        # Select each row in the table, excluding the header row
        rows = response.xpath(
            '//ol[@class="table-_tbl"]/li/ol[contains(@class, "tbl__row") and not(contains(@class, "tbl__row--header"))]')

        for row in rows:
            item = {
                'period': row.xpath('.//li[contains(@data-label, "Период:")]/a/text()').get(),
                'turnover': row.xpath('.//li[contains(@data-label, "Оборот:")]/text()').get(),
                'sold': row.xpath('.//li[contains(@data-label, "Продадени:")]/text()').get(),
                'average_price': row.xpath(
                    './/li[contains(@data-label, "Средна цена:")]/text()').get(),
                'percentage': row.xpath('.//li[contains(@data-label, "Процент:")]/text()').get(),
                'amount_per_receipt': row.xpath(
                    './/li[contains(@data-label, "Сума по разписка:")]/text()').get(),
                'settled': row.xpath('.//li[contains(@data-label, "Погасено:")]/text()').get(),
                'to_pay': row.xpath('.//li[contains(@data-label, "За плащане:")]/text()').get(),
                # Assuming 'Преглед' is the text of the button/link you want to follow
                'review_link': row.xpath('.//li[contains(@data-label, "Преглед:")]//a/@href').get()
                ,
            }

            if item['review_link']:
                book_by_book_link = response.urljoin(item['review_link'] + '/order_items')
                # Now call the sub_parsing function and pass the review_link as argument
                # For demonstration, assuming sub_parsing is another method of this spider
                # that handles the scraping of the detailed page pointed to by review_link
                request = scrapy.Request(book_by_book_link, callback=self.parse_book_by_book_link)
                request.meta['item'] = item  # Pass along the collected item to the sub-parser
                yield request
            break

        # Handling pagination
        next_page_url = response.xpath(
            '//nav[contains(@aria-label,"pager")]/div[@class="p__right"]/span/a/@href').get()
        if next_page_url:
            next_page_full_url = response.urljoin(next_page_url)
            yield scrapy.Request(next_page_full_url, callback=self.parse_monthly_receipts)

    # def parse_review_link(self, response):
    #     item = response.request.meta['item']
    #     # Extract the link for "Разгледай книга по книга"
    #     book_by_book_link = response.xpath(
    #         "//a[contains(text(), 'Разгледай книга по книга')]/@href").get()
    #
    #     if book_by_book_link:
    #         # Call the sub-function with the extracted link
    #         request = self.process_book_by_book_link(book_by_book_link)
    #         request.meta['item'] = item
    #         yield request

    def parse_book_by_book_link(self, response):
        item = response.meta['item']

        # Loop through each row in the table (excluding the header row)
        # rows = response.xpath(
        #     '//ol[@class="table-_tbl"]/li/ol[contains(@class, "tbl__row") and not(contains(@class, "tbl__row--header"))]')
        rows = response.xpath(
            '//ol[contains(@class, "table-_tbl")]/li/ol[contains(@class, "tbl__row") and not(contains(@class, "tbl__row--header"))]')
        for row in rows:
            sub_item = dict(
                order_number=row.xpath('.//li[@data-label="Поръчка: "]/text()').get(),
                title_link=row.xpath('.//li[@data-label="Заглавие: "]/a/@href').get(),
                title_text=row.xpath('.//li[@data-label="Заглавие: "]/a/text()').get(),
                author=row.xpath(
                    './/li[@data-label="Автор: "]/a/text()').get() or row.xpath(
                    './/li[@data-label="Автор: "]/text()').get(),
                status=row.xpath('.//li[@data-label="Статус: "]/text()').get(),
                quantity=row.xpath('.//li[@data-label="Брой: "]/text()').get(),
                price=row.xpath('.//li[@data-label="Цена: "]/text()').get(),
                fee=row.xpath('.//li[@data-label="Такса: "]/text()').get(),
                confirmation=row.xpath('.//li[@data-label="Потв./Отк.: "]/text()').get(),

            )
            for k, v in item.items():
                sub_item[f'month_{k}'] = v

            yield sub_item

        # Find the link to the next page and follow it
        next_page_url = response.xpath('//a[@rel="next"]/@href').extract_first()
        if next_page_url:
            request = scrapy.Request(response.urljoin(next_page_url), callback=self.parse_book_by_book_link)
            request.meta['item'] = response.meta['item']
            yield request
