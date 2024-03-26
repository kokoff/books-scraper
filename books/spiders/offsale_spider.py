import logging
import os
import urllib

import scrapy
from scrapy import Selector

import warnings

warnings.filterwarnings("ignore", category=UserWarning, module='scrapy.selector.unified')


class OffsaleSpider(scrapy.Spider):
    name = 'offsale'
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
            path_parts[-2] = "offsale_products"
            path_parts = path_parts[:-1]  # Slice off 'books'
            url_parts[2] = "/".join(path_parts)
            link_to_offsale_books = urllib.parse.urlunparse(url_parts)

            # Request the next page and handle it with another callback method
            yield scrapy.Request(url=link_to_offsale_books, callback=self.parse_next_page)
        else:
            self.log("Login failed", level=logging.ERROR)

    def parse_next_page(self, response):
        # self.logger.info(f'Processing {response}, cached={"cached" in response.flags}')

        # Define the base XPath to select each book row in the "Публикувани" section
        books = response.xpath(
            f'//ol[@class="table-_tbl"]/li[@class="t_product"]/ol[@class="tbl__row"]')

        books += response.xpath(
            f'//ol[@class="table-_tbl"]/li[@class="t_product"]/ol[@class="tbl__row tbl__row--on_even_position"]')

        # Extract the next page URL
        next_page_url = response.xpath(f'//a[contains(text(), "Следваща")]/@href').get()

        if next_page_url:
            # If a next page URL is found, make a full URL by combining the base URL with the extracted path
            next_page_url = response.urljoin(next_page_url)

            # Follow the next page URL
            yield scrapy.Request(next_page_url, callback=self.parse_next_page)

        # Iterate over each book to extract details
        for book in books:
            item = dict(
                # Assuming 'edit_link' targets a link for editing, but you mentioned "Промени: " which wasn't in the snippet. Adjust if it's actually "Действие: "
                edit_link=book.xpath(
                    './/li[contains(@data-label, "Действие: ")]/a/@href').extract_first(),
                # Extracts the book ID, considering it might be bold or regular text
                book_id=book.xpath('.//li[@data-label="№: "]/text()').extract_first(),
                # Targets the image src within the cell that does not have a clear data-label for images
                image_link=book.xpath('.//li[@data-label="-: "]//img/@src').extract_first(),
                # Extracts the book title from the link within the correct labeled cell
                title=book.xpath('.//li[@data-label="Заглавие: "]/a/text()').extract_first(),
                # Extracts the author name from the link
                author=book.xpath('.//li[@data-label="Автор: "]/a/text()').extract_first(),
                # Direct text extraction for condition
                condition=book.xpath('.//li[@data-label="Състояние: "]/text()').extract_first(),
                # Extracts the price text from the link
                price=book.xpath('.//li[@data-label="Цена: "]/a/text()').extract_first(),
                # Direct text extraction for the year
                year=book.xpath('.//li[@data-label="Год.: "]/text()').extract_first(),
                # Extracts the entry date, considering the hover or toggle elements for revealing dates
                entry_date=book.xpath(
                    './/li[@data-label="Въвеждане: "]//div[contains(@class, "js_hover_next_tag")]/text()').extract_first(),
                # Extracts the link for an action, which seems to be for returning the book for sale or editing after return
                action_link=book.xpath('.//li[@data-label="Действие: "]/a/@href').extract_first(),
                # Note value extraction remains the same, assuming it's part of a larger form or context not shown in the snippet
                note_value=book.xpath('.//input[@id="published_product_note"]/@value').get(),
            )

            book_detail_url = item['edit_link'].rsplit('/', 1)[0]
            yield item
