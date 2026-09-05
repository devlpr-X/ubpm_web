"""Pagination for the mobile API."""

from rest_framework.pagination import PageNumberPagination


class DefaultPagination(PageNumberPagination):
    """Хуудасны хэмжээг клиент тохируулж болно — вэбийн "10 / 25 / 50 / Бүгд".

    Апп нь жагсаалтаа гүйлгэхэд ``?page=`` -ээр дараагийн хуудсыг татна;
    тайлан/экспортод бүх мөр хэрэгтэй үед ``?page_size=200``.
    """

    page_size_query_param = "page_size"
    max_page_size = 200
