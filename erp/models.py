from django.db import models
from django.utils import timezone

# Choices for Units
UNIT_CHOICES = [
    ('KGS', 'Kilograms'),
    ('NOS', 'Numbers'),
    ('MTR', 'Meters'),
    ('PCS', 'Pieces'),
]

# Choices for Indian States (Simplified for now)
STATE_CHOICES = [
    ('GJ', 'Gujarat'),
    ('RJ', 'Rajasthan'),
    ('MH', 'Maharashtra'),
    ('DL', 'Delhi'),
    ('MP', 'Madhya Pradesh'),
]

class Party(models.Model):
    PARTY_TYPE_CHOICES = [
        ('VENDOR', 'Vendor'),
        ('CUSTOMER', 'Customer'),
        ('BOTH', 'Both'),
    ]

    name = models.CharField(max_length=200)
    gstin = models.CharField(max_length=15, unique=True)
    party_type = models.CharField(max_length=10, choices=PARTY_TYPE_CHOICES, default='CUSTOMER')
    state = models.CharField(max_length=2, choices=STATE_CHOICES, default='GJ') # <--- NEW: To check for IGST
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=15, blank=True)
    
    def __str__(self):
        return self.name

class Product(models.Model):
    name = models.CharField(max_length=200)
    hsn_code = models.CharField(max_length=20, blank=True)
    gst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=18.00)
    unit = models.CharField(max_length=10, choices=UNIT_CHOICES, default='KGS')
    current_stock = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    def __str__(self):
        return self.name

class Invoice(models.Model):
    customer = models.ForeignKey(Party, on_delete=models.CASCADE)
    invoice_number = models.CharField(max_length=20, unique=True)
    date = models.DateField(default=timezone.now)
    
    # New Fields found in your samples
    po_number = models.CharField(max_length=50, blank=True, help_text="Purchase Order No.")
    vehicle_number = models.CharField(max_length=20, blank=True)
    
    # Financials (Read-only, calculated automatically)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    cgst_total = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    sgst_total = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    igst_total = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    grand_total = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)

    def __str__(self):
        return f"{self.invoice_number} - {self.customer.name}"
    
    def save(self, *args, **kwargs):
        # Auto-capitalization for Vehicle Number
        if self.vehicle_number:
            self.vehicle_number = self.vehicle_number.upper()
        super().save(*args, **kwargs)

class InvoiceItem(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    rate = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Auto-calculated fields
    amount = models.DecimalField(max_digits=10, decimal_places=2, editable=False)
    cgst = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, editable=False)
    sgst = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, editable=False)
    igst = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, editable=False)

    def save(self, *args, **kwargs):
        # 1. Calculate Basic Amount
        self.amount = self.quantity * self.rate
        
        # 2. Check for IGST or CGST/SGST
        # We assume your company (Suraj Industries) is in Gujarat ('GJ')
        gst_percent = self.product.gst_rate
        total_tax_value = (self.amount * gst_percent) / 100

        if self.invoice.customer.state == 'GJ':
            # Intra-state: Split tax into CGST and SGST
            self.cgst = total_tax_value / 2
            self.sgst = total_tax_value / 2
            self.igst = 0
        else:
            # Inter-state: Full tax is IGST
            self.cgst = 0
            self.sgst = 0
            self.igst = total_tax_value
            
        super().save(*args, **kwargs)

# --- FACTORY / PRODUCTION MODELS ---

class Production(models.Model):
    date = models.DateField(default=timezone.now)
    finished_good = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='produced_in', verbose_name="Finished Good Produced")
    output_qty = models.DecimalField(max_digits=10, decimal_places=2, help_text="Qty Produced (KGS)")
    waste_qty = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Waste Generated (KGS)")
    
    def __str__(self):
        return f"PROD-{self.id} | {self.date} | {self.finished_good.name}"

    def save(self, *args, **kwargs):
        # 1. CREATE: Add Stock
        if not self.pk:
            self.finished_good.current_stock += self.output_qty
            self.finished_good.save()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # 2. DELETE: Reverse (Subtract) Stock
        self.finished_good.current_stock -= self.output_qty
        self.finished_good.save()
        super().delete(*args, **kwargs)

class ProductionInput(models.Model):
    production = models.ForeignKey(Production, on_delete=models.CASCADE, related_name='inputs')
    raw_material = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='consumed_in')
    quantity = models.DecimalField(max_digits=10, decimal_places=2, help_text="Qty Used (KGS)")

    def __str__(self):
        return f"{self.raw_material.name} - {self.quantity}"

    def save(self, *args, **kwargs):
        # 1. CREATE: Subtract Stock
        if not self.pk:
            self.raw_material.current_stock -= self.quantity
            self.raw_material.save()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # 2. DELETE: Reverse (Add Back) Stock
        self.raw_material.current_stock += self.quantity
        self.raw_material.save()
        super().delete(*args, **kwargs)