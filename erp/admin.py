import openpyxl
from django.http import HttpResponse
from datetime import datetime
from import_export.admin import ImportExportModelAdmin
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.shortcuts import redirect
from django.http import HttpResponseRedirect
from django.contrib import messages
from .models import Product, Party, Invoice, InvoiceItem, Production, ProductionInput, DeliveryChallan, ChallanItem, PaymentReceived

# --- Product & Party Admins ---
@admin.register(Product)
class ProductAdmin(ImportExportModelAdmin):
    list_display = ('name', 'current_stock', 'unit', 'gst_rate')
    search_fields = ('name',)

@admin.register(Party)
class PartyAdmin(ImportExportModelAdmin):
    list_display = ('name', 'party_type', 'gstin', 'phone', 'state')
    search_fields = ('name', 'gstin')
    list_filter = ('party_type', 'state')

# --- Invoice Configuration ---

class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 1
    readonly_fields = ('amount', 'cgst', 'sgst', 'igst')

def export_invoices_detailed(modeladmin, request, queryset):
    # 1. Setup Excel
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Detailed Invoices"

    # 2. Write Headers
    headers = ['Date', 'Invoice No', 'Customer', 'GSTIN', 'Product', 'HSN', 'Qty', 'Unit', 'Rate', 'Amount', 'CGST', 'SGST', 'IGST', 'Total Line Item']
    ws.append(headers)

    # 3. Loop through selected Invoices
    for invoice in queryset:
        # Loop through every item inside the invoice
        for item in invoice.items.all():
            # Write a row for this specific item
            ws.append([
                invoice.date,                   # Date
                invoice.invoice_number,         # Invoice No
                invoice.customer.name,          # Customer
                invoice.customer.gstin,         # GSTIN
                item.product.name,              # Product Name
                item.product.hsn_code,          # HSN
                item.quantity,                  # Qty
                item.product.unit,              # Unit
                item.rate,                      # Rate
                item.amount,                    # Taxable Value
                item.cgst,                      # CGST
                item.sgst,                      # SGST
                item.igst,                      # IGST
                item.amount + item.cgst + item.sgst + item.igst  # Total for this item
            ])

    # 4. Return file
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename=Sales_Register_{datetime.now().strftime("%Y-%m-%d")}.xlsx'
    wb.save(response)
    return response

export_invoices_detailed.short_description = "Export Detailed Report (Excel)"

@admin.register(Invoice)
class InvoiceAdmin(ImportExportModelAdmin):
    list_display = ('invoice_number', 'date', 'customer', 'grand_total', 'pdf_button')
    search_fields = ('invoice_number', 'customer__name', 'po_number')
    list_filter = ('date', 'customer')
    actions = [export_invoices_detailed]
    inlines = [InvoiceItemInline]

    # --- 1. HIDE ZEROS LOGIC ---
    # REPLACE your old get_fieldsets with this new one:
    def get_fieldsets(self, request, obj=None):
        fieldsets = [
            ('Basic Info', {
                'fields': ('customer', 'invoice_number', 'date', 'po_number', 'vehicle_number')
            }),
            # NEW: Shipping Section with the checkbox description
            ('Shipping Details', {
                'fields': ('shipping_name', 'shipping_address', 'shipping_state', 'shipping_gstin'),
                'description': '<input type="checkbox" id="same_as_bill_to" style="margin-right:5px;"> <strong>Ship to same address as Customer?</strong> (Uncheck to edit)'
            }),
        ]
        # Logic to only show Totals when editing (hides zeros on new invoices)
        if obj:
            fieldsets.append(('Totals', {'fields': ('total_amount', 'cgst_total', 'sgst_total', 'igst_total', 'grand_total'), 'classes': ('collapse',)}))
        return fieldsets

    # ADD this at the bottom of the InvoiceAdmin class (indentation must match the def above)
    class Media:
        js = ('admin/js/invoice_shipping.js',)

    def get_readonly_fields(self, request, obj=None):
        return ('total_amount', 'cgst_total', 'sgst_total', 'igst_total', 'grand_total')

    # --- 2. SAVE & PRINT LOGIC ---
    def response_add(self, request, obj, post_url_continue=None):
        if "_save_print" in request.POST:
            self.message_user(request, "Invoice Saved. Opening Print Window...", messages.SUCCESS)
            url = reverse('admin:erp_invoice_change', args=[obj.pk])
            return HttpResponseRedirect(f"{url}?print_pdf=1")
        return super().response_add(request, obj, post_url_continue)

    def response_change(self, request, obj):
        if "_save_print" in request.POST:
            self.message_user(request, "Invoice Saved. Opening Print Window...", messages.SUCCESS)
            url = reverse('admin:erp_invoice_change', args=[obj.pk])
            return HttpResponseRedirect(f"{url}?print_pdf=1")
        return super().response_change(request, obj)

    # --- 3. DASHBOARD BUTTONS ---
    def pdf_button(self, obj):
        return format_html('<a class="button" href="{}">PDF</a>&nbsp;<a class="button" href="{}" style="background-color:#28a745;">Excel</a>', reverse('invoice_pdf', args=[obj.pk]), reverse('invoice_excel', args=[obj.pk]))
    pdf_button.short_description = 'Actions'
    pdf_button.allow_tags = True

    # --- 4. CALCULATION ---
    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        invoice = form.instance

        for item in invoice.items.all():
            item.save()

        total = sum(item.amount for item in invoice.items.all())
        cgst = sum(item.cgst for item in invoice.items.all())
        sgst = sum(item.sgst for item in invoice.items.all())
        igst = sum(item.igst for item in invoice.items.all())
        invoice.total_amount = total
        invoice.cgst_total = cgst
        invoice.sgst_total = sgst
        invoice.igst_total = igst
        invoice.grand_total = total + cgst + sgst + igst
        invoice.save()

# --- FACTORY / PRODUCTION CONFIGURATION ---

class ProductionInputInline(admin.TabularInline):
    model = ProductionInput
    extra = 1
    autocomplete_fields = ['raw_material']

@admin.register(Production)
class ProductionAdmin(ImportExportModelAdmin):
    list_display = ('date', 'finished_good', 'output_qty', 'waste_qty', 'total_input_qty')
    list_filter = ('date', 'finished_good')
    inlines = [ProductionInputInline]
    
    def total_input_qty(self, obj):
        total = sum(item.quantity for item in obj.inputs.all())
        return f"{total} KGS"
    total_input_qty.short_description = "Total Input"

# --- PAYMENT ADMIN ---
@admin.register(PaymentReceived)
class PaymentAdmin(ImportExportModelAdmin):
    list_display = ('date', 'party', 'amount', 'mode', 'reference_number')
    list_filter = ('party', 'date', 'mode')
    search_fields = ('party__name', 'reference_number')

# --- CHALLAN ADMIN ---
class ChallanItemInline(admin.TabularInline):
    model = ChallanItem
    extra = 1

@admin.register(DeliveryChallan)
class DeliveryChallanAdmin(ImportExportModelAdmin):
    list_display = ('challan_number', 'date', 'customer', 'vehicle_number', 'pdf_list_button')
    search_fields = ('challan_number', 'customer__name', 'vehicle_number')
    inlines = [ChallanItemInline]
    
    # --- 1. Add "Print" Button to the Form ---
    readonly_fields = ('print_in_form',)

    def print_in_form(self, obj):
        if obj and obj.pk:
            url = reverse('challan_pdf', args=[obj.pk])
            return format_html(
                '<a href="{}" target="_blank" style="background-color:#417690; color:white; padding:8px 15px; border-radius:5px; text-decoration:none; font-weight:bold;">'
                '🖨️ PRINT CHALLAN PDF</a>', url
            )
        return "Save this challan first to print."
    print_in_form.short_description = "Actions"
    print_in_form.allow_tags = True

    # --- 2. Organize the Form Layout ---
    fieldsets = [
        ('Actions', {
            'fields': ('print_in_form',)  # Put the button at the very top
        }),
        ('Challan Details', {
            'fields': ('challan_number', 'date', 'customer', 'po_number', 'vehicle_number', 'job_work_nature')
        }),
    ]

    # --- 3. Button for the Dashboard List View ---
    def pdf_list_button(self, obj):
        return format_html('<a class="button" href="{}">Print</a>', reverse('challan_pdf', args=[obj.pk]))
    pdf_list_button.short_description = 'Print'
    pdf_list_button.allow_tags = True
    list_display = ('challan_number', 'date', 'customer', 'vehicle_number', 'pdf_button')
    search_fields = ('challan_number', 'customer__name', 'vehicle_number')
    inlines = [ChallanItemInline]
    
    # Add the PRINT button
    def pdf_button(self, obj):
        return format_html('<a class="button" href="{}">Print Challan</a>', reverse('challan_pdf', args=[obj.pk]))
    pdf_button.short_description = 'Actions'
    pdf_button.allow_tags = True

