import logging
import os

import scrapy
from scrapy import Selector


class BooksSpider(scrapy.Spider):
    name = 'books'
    start_urls = ['https://knizhen-pazar.net/users/sign_in']

    def __init__(self, username=None, password=None, *args, **kwargs):
        super(BooksSpider, self).__init__(*args, **kwargs)
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

            # Request the next page and handle it with another callback method
            yield scrapy.Request(url=link_to_books_for_sale, callback=self.parse_next_page, meta={'section': 'Чакащи Вашата редакция или преглед'}, dont_filter=True)
            yield scrapy.Request(url=link_to_books_for_sale, callback=self.parse_next_page, meta={'section': 'Непрегледани от валидатор*'})
            yield scrapy.Request(url=link_to_books_for_sale, callback=self.parse_next_page, meta={'section': 'Прегледани от валидатор (изчакват публикация)**'})
            yield scrapy.Request(url=link_to_books_for_sale, callback=self.parse_next_page, meta={'section': 'Публикувани'}, dont_filter=True)
        else:
            self.log("Login failed", level=logging.ERROR)

    def parse_next_page(self, response):
        section = response.meta['section']

        # Assuming `response` is your variable containing the full HTML content
        sel = Selector(text=response.text).xpath(
            f'//section[h2[contains(text(), "{section}")]]')

        # Define the base XPath to select each book row in the "Публикувани" section
        books = sel.xpath(
            f'//section[h2[contains(text(), "{section}")]]//ol[@class="table-_tbl"]/li[@class="t_product"]/ol[@class="tbl__row"]')

        books += sel.xpath(
            f'//section[h2[contains(text(), "{section}")]]//ol[@class="table-_tbl"]/li[@class="t_product"]/ol[@class="tbl__row tbl__row--on_even_position"]')

        # Iterate over each book to extract details
        for book in books:
            item = dict(
                edit_link=book.xpath('.//li[@data-label="Промени: "]/a/@href').extract_first(),
                book_id=book.xpath('.//li[@data-label="№: "]/b/text() | .//li[@data-label="№: "]/text()').extract_first(),
                image_link=book.xpath('.//li[@data-label="-: "]//img/@src').extract_first(),
                title=book.xpath('.//li[@data-label="Заглавие: "]/a/text()').extract_first(),
                author=book.xpath('.//li[@data-label="Автор: "]/a/text()').extract_first(),
                condition=book.xpath('.//li[@data-label="Състояние: "]/text()').extract_first(),
                price=book.xpath('.//li[@data-label="Цена: "]/a/text()').extract_first(),
                year=book.xpath('.//li[@data-label="Год.: "]/text()').extract_first(),
                entry_date=book.xpath(
                    './/li[@data-label="Въвеждане: "]//div[@class="js_hover_next_tag"]/text()').extract_first(),
                action_link=book.xpath('.//li[@data-label="Действие: "]/a/@href').extract_first(),
                note_value=book.xpath('//input[@id="published_product_note"]/@value').get(),
                section = section
            )
            yield item

        # Extract the next page URL
        next_page_url = sel.css('a[rel="next"]::attr(href)').get()

        if next_page_url:
            # If a next page URL is found, make a full URL by combining the base URL with the extracted path
            next_page_url = response.urljoin(next_page_url)

            # Log the next page URL (optional)
            self.logger.info('Next page URL: %s', next_page_url)

            # Follow the next page URL
            yield scrapy.Request(next_page_url, callback=self.parse_next_page, meta={'section': section})
