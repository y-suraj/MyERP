from django.urls import path
from . import views

urlpatterns = [
    path('invoice/<int:invoice_id>/pdf/', views.generate_invoice_pdf, name='invoice_pdf'),
    path('invoice/<int:invoice_id>/excel/', views.generate_invoice_excel, name='invoice_excel'),
    path('import/', views.import_page, name='import_page'),  # <--- NEW LINE
]