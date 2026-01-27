from django.shortcuts import redirect
from django.contrib import messages
from .models import Party, Product
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from django.template.loader import get_template
from xhtml2pdf import pisa
from .models import Invoice
import openpyxl
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from num2words import num2words

# --- Helper to Format Filenames ---
def get_filename(invoice, extension):
    # Format: "InvoiceNo, CustomerName, dd-mm-yyyy.ext"
    safe_name = "".join([c for c in invoice.customer.name if c.isalnum() or c in (' ', '.', '_')]).strip()
    # strftime('%d-%m-%Y') converts date to "21-01-2026"
    formatted_date = invoice.date.strftime('%d-%m-%Y')
    return f"{invoice.invoice_number}, {safe_name}, {formatted_date}.{extension}"

# --- PDF GENERATOR ---
def generate_invoice_pdf(request, invoice_id):
    invoice = get_object_or_404(Invoice, pk=invoice_id)
    
    # 1. Math Logic (Words, etc.)
    raw_words = num2words(invoice.grand_total, lang='en_IN', to='currency', currency='INR')
    clean_words = raw_words.replace(' and ', ' ')
    amount_in_words = clean_words.replace('rupees,', 'INR and').replace('rupees', 'INR').replace('cents', 'Paise')
    amount_in_words = amount_in_words.title()
    amount_in_words = amount_in_words.replace(' Inr And ', ' INR and ')

    # 2. Render HTML
    # --- NEW: Get Tax Rate for display ---
    first_item = invoice.items.first()
    tax_rate = first_item.product.gst_rate if first_item else 0
    cgst_rate = tax_rate / 2
    
    template_path = 'erp/invoice_pdf.html'
    context = {
        'invoice': invoice, 
        'amount_in_words': amount_in_words,
        'tax_rate': tax_rate,      # e.g., 18.00
        'cgst_rate': cgst_rate     # e.g., 9.00
    }
    template = get_template(template_path)
    html = template.render(context)
    
    # 3. Create Response
    response = HttpResponse(content_type='application/pdf')
    filename = get_filename(invoice, "pdf")
    
    # LOGIC CHANGE: Check if we want to "print" (view in browser) or "download"
    if request.GET.get('action') == 'print':
        # 'inline' opens it in the browser (Print Preview mode)
        response['Content-Disposition'] = f'inline; filename="{filename}"'
    else:
        # 'attachment' forces a download
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
        return HttpResponse('We had some errors <pre>' + html + '</pre>')
    return response

# --- EXCEL GENERATOR ---
def generate_invoice_excel(request, invoice_id):
    invoice = get_object_or_404(Invoice, pk=invoice_id)
    
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"INV-{invoice.invoice_number}"
    
    # --- STYLES ---
    bold_font = Font(bold=True)
    title_font = Font(size=18, bold=True)
    center_align = Alignment(horizontal='center', vertical='center')
    right_align = Alignment(horizontal='right', vertical='center')
    
    thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), 
                         top=Side(style='thin'), bottom=Side(style='thin'))
    gray_fill = PatternFill(start_color="EEEEEE", end_color="EEEEEE", fill_type="solid")

    # --- COLUMN WIDTHS ---
    ws.column_dimensions['A'].width = 5 
    ws.column_dimensions['B'].width = 35 
    ws.column_dimensions['C'].width = 12 
    ws.column_dimensions['D'].width = 10 
    ws.column_dimensions['E'].width = 12 
    ws.column_dimensions['F'].width = 15 

    # --- HEADER ---
    ws.merge_cells('A1:F1')
    ws['A1'] = "SURAJ INDUSTRIES"
    ws['A1'].font = title_font
    ws['A1'].alignment = center_align
    
    ws.merge_cells('A2:F2')
    ws['A2'] = "Survey No. 292/1, Baroda Halol Road, Anandpura, Baska"
    ws['A2'].alignment = center_align

    # --- INVOICE INFO ---
    ws['E4'] = "Invoice No:"
    ws['E4'].font = bold_font
    ws['F4'] = invoice.invoice_number
    
    ws['E5'] = "Date:"
    ws['E5'].font = bold_font
    # Force "21-Jan-2026" format inside the Excel cell
    ws['F5'] = invoice.date.strftime('%d-%b-%Y')

    if invoice.vehicle_number:
        ws['E6'] = "Vehicle:"
        ws['E6'].font = bold_font
        ws['F6'] = invoice.vehicle_number.upper()

    # --- ADDRESS BLOCKS ---
    ws['A4'] = "BILL TO:"
    ws['A4'].font = bold_font
    ws['B4'] = invoice.customer.name
    ws['B5'] = invoice.customer.address
    ws['B5'].alignment = Alignment(wrap_text=True)
    
    ws['A7'] = "GSTIN:"
    ws['A7'].font = bold_font
    ws['B7'] = invoice.customer.gstin

    # --- TABLE HEADER ---
    row_num = 9
    headers = ["#", "Item Description", "HSN", "Qty", "Rate", "Amount"]
    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=row_num, column=col_num, value=header)
        cell.font = bold_font
        cell.alignment = center_align
        cell.border = thin_border
        cell.fill = gray_fill

    # --- TABLE ITEMS ---
    row_num = 10
    for index, item in enumerate(invoice.items.all(), 1):
        ws.cell(row=row_num, column=1, value=index).border = thin_border
        ws.cell(row=row_num, column=2, value=item.product.name).border = thin_border
        ws.cell(row=row_num, column=3, value=item.product.hsn_code).border = thin_border
        ws.cell(row=row_num, column=4, value=item.quantity).border = thin_border
        ws.cell(row=row_num, column=5, value=item.rate).border = thin_border
        ws.cell(row=row_num, column=6, value=item.amount).border = thin_border
        row_num += 1

    # --- TOTALS ---
    row_num += 1
    def add_total_row(label, value, bold=False):
        nonlocal row_num
        ws.cell(row=row_num, column=5, value=label).font = bold_font
        ws.cell(row=row_num, column=5, value=label).alignment = right_align
        ws.cell(row=row_num, column=6, value=value).font = Font(bold=bold)
        ws.cell(row=row_num, column=6, value=value).border = thin_border
        row_num += 1

    add_total_row("Taxable Value:", invoice.total_amount)
    
    if invoice.igst_total > 0:
        add_total_row("IGST:", invoice.igst_total)
    else:
        add_total_row("CGST:", invoice.cgst_total)
        add_total_row("SGST:", invoice.sgst_total)
        
    add_total_row("GRAND TOTAL:", invoice.grand_total, bold=True)

    # --- FOOTER ---
    row_num += 2
    ws[f'A{row_num}'] = "Company's Bank Details:"
    ws[f'A{row_num}'].font = bold_font
    row_num += 1
    ws[f'A{row_num}'] = "Bank: Bank Of India"
    row_num += 1
    ws[f'A{row_num}'] = "A/c: 251830110000018"
    row_num += 1
    ws[f'A{row_num}'] = "IFSC: BKID0002518"

    row_num += 2
    ws[f'A{row_num}'] = "Terms & Conditions:"
    ws[f'A{row_num}'].font = bold_font
    row_num += 1
    ws[f'A{row_num}'] = "1. Interest @24% p.a. on overdue unpaid bills."
    row_num += 1
    ws[f'A{row_num}'] = "2. Subject to Halol Jurisdiction."

    # --- OUTPUT ---
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    filename = get_filename(invoice, "xlsx")
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    wb.save(response)
    return response

# --- BULK IMPORT VIEW ---
def import_page(request):
    if request.method == "POST":
        file = request.FILES.get('excel_file')
        import_type = request.POST.get('import_type')
        
        if not file:
            messages.error(request, "Please upload a file.")
            return redirect('import_page')

        try:
            wb = openpyxl.load_workbook(file)
            ws = wb.active
            count = 0
            
            # Skip the first row (Headers) and start from row 2
            for row in ws.iter_rows(min_row=2, values_only=True):
                # Stop if the first column is empty (end of data)
                if not row[0]:
                    break

                if import_type == 'parties':
                    # Columns: Name(0) | GSTIN(1) | Type(2) | State(3) | Phone(4)
                    Party.objects.create(
                        name=row[0],
                        gstin=str(row[1]).strip(),
                        party_type=str(row[2]).upper().strip(), # Force CAPS
                        state=str(row[3]).upper().strip(),      # Force CAPS (GJ, RJ)
                        phone=row[4] if row[4] else ""
                    )
                    count += 1
                
                elif import_type == 'products':
                    # Columns: Name(0) | HSN(1) | Rate(2) | Unit(3)
                    Product.objects.create(
                        name=row[0],
                        hsn_code=str(row[1]).strip(),
                        gst_rate=row[2],
                        unit=str(row[3]).upper().strip()
                    )
                    count += 1
            
            messages.success(request, f"Success! Imported {count} items.")
            
        except Exception as e:
            messages.error(request, f"Error: {e}. Check your Excel format.")
            
        return redirect('import_page')

    return render(request, 'erp/import_page.html')