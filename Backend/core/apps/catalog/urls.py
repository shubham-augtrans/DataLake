from django.urls import path

from .views import DataDictionaryView, NamespaceListView, TableDetailView, TableListView

urlpatterns = [
    path("namespaces/", NamespaceListView.as_view(), name="catalog-namespaces"),
    path("tables/", TableListView.as_view(), name="catalog-tables"),
    path("tables/detail/", TableDetailView.as_view(), name="catalog-table-detail"),
    path("dictionary/", DataDictionaryView.as_view(), name="catalog-dictionary"),
]
