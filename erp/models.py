from django.db import models
from django.utils import timezone
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

# --- CORE MODELS ---

class Party(models.Model):
    PARTY_TYPES = [
        ('customer', 'Customer'), 
        ('vendor', 'Vendor'), 
        ('both', 'Customer & Vendor')
    ]
    
    STATE_CHOICES = [
        ('Gujarat', 'Gujarat'), 
        ('Maharashtra', 'Maharashtra'), 
        ('Delhi', 'Delhi'),
        ('Rajasthan', 'Rajasthan'),
        ('Madhya Pradesh', 'Madhya Pradesh')
    ]

    name = models.CharField(max_length=100)
    party_type = models.CharField(max_length=10, choices=PARTY_TYPES)
    address = models.TextField()
    gstin = models.CharField(max_length=15, unique=True)
    phone = models.CharField(max_length=15, blank=True)
    state = models.CharField(max_length=50, choices=STATE_CHOICES, default='Gujarat')

    def __str__(self):
        return f"{self.name} ({self.party_type})"

class Product(models.Model):
    name = models.CharField(max_length=100)
    unit = models.CharField(max_length=10, choices=[('KGS', 'Kilograms'), ('NOS', 'Numbers'), ('MTR', 'Meters')])
    current_stock = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    gst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=18.00)
    hsn_code = models.CharField(max_length=10, blank=True)

    def __str__(self):
        return f"{self.name} | Stock: {self.current_stock} {self.unit}"

# --- INVOICE MODELS ---

# --- INVOICE MODELS ---

class Invoice(models.Model):
    invoice_number = models.CharField(max_length=20, unique=True)
    date = models.DateField(default=timezone.now)
    
    # UPDATE: Removed 'limit_choices_to'. Now shows ALL parties (Customer, Vendor, Both).
    customer = models.ForeignKey(Party, on_delete=models.CASCADE)
    
    po_number = models.CharField(max_length=50, blank=True, verbose_name="PO Number")
    vehicle_number = models.CharField(max_length=20, blank=True, verbose_name="Vehicle Number")
    # ... previous fields ...
    vehicle_number = models.CharField(max_length=20, blank=True, verbose_name="Vehicle Number")
    
    # --- NEW SHIPPING FIELDS ---
    shipping_name = models.CharField(max_length=100, blank=True, verbose_name="Ship To Name")
    shipping_address = models.TextField(blank=True, verbose_name="Ship To Address")
    shipping_state = models.CharField(max_length=50, choices=Party.STATE_CHOICES, blank=True, verbose_name="Ship To State")
    shipping_gstin = models.CharField(max_length=15, blank=True, verbose_name="Ship To GSTIN")
    
    # ... total_amount ...
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cgst_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    sgst_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    igst_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    grand_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    def __str__(self):
        return f"{self.invoice_number} - {self.customer.name}"

class InvoiceItem(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    rate = models.DecimalField(max_digits=10, decimal_places=2)
    amount = models.DecimalField(max_digits=12, decimal_places=2, editable=False)
    cgst = models.DecimalField(max_digits=10, decimal_places=2, default=0, editable=False)
    sgst = models.DecimalField(max_digits=10, decimal_places=2, default=0, editable=False)
    igst = models.DecimalField(max_digits=10, decimal_places=2, default=0, editable=False)

    def save(self, *args, **kwargs):
        self.amount = self.quantity * self.rate
        gst_percent = self.product.gst_rate
        tax_amount = (self.amount * gst_percent) / 100
        
        # Calculate Tax based on State
        if self.invoice.customer.state == 'Gujarat':
            self.cgst = tax_amount / 2
            self.sgst = tax_amount / 2
            self.igst = 0
        else:
            self.cgst = 0
            self.sgst = 0
            self.igst = tax_amount
            
        super().save(*args, **kwargs)

# --- FACTORY / PRODUCTION MODELS ---

class Production(models.Model):
    date = models.DateField(default=timezone.now)
    finished_good = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='produced_in', verbose_name="Finished Good Produced")
    output_qty = models.DecimalField(max_digits=10, decimal_places=2, help_text="Qty Produced (KGS)")
    waste_qty = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Waste Generated (KGS)")
    
    def __str__(self):
        return f"PROD-{self.id} | {self.date} | {self.finished_good.name}"

class ProductionInput(models.Model):
    production = models.ForeignKey(Production, on_delete=models.CASCADE, related_name='inputs')
    raw_material = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='consumed_in')
    quantity = models.DecimalField(max_digits=10, decimal_places=2, help_text="Qty Used (KGS)")

    def __str__(self):
        return f"{self.raw_material.name} - {self.quantity}"

# --- SIGNALS (THE RELIABLE STOCK LOGIC) ---

@receiver(post_save, sender=Production)
def add_fg_stock(sender, instance, created, **kwargs):
    if created:
        instance.finished_good.current_stock += instance.output_qty
        instance.finished_good.save()

@receiver(post_delete, sender=Production)
def remove_fg_stock(sender, instance, **kwargs):
    instance.finished_good.current_stock -= instance.output_qty
    instance.finished_good.save()

@receiver(post_save, sender=ProductionInput)
def remove_rm_stock(sender, instance, created, **kwargs):
    if created:
        instance.raw_material.current_stock -= instance.quantity
        instance.raw_material.save()

@receiver(post_delete, sender=ProductionInput)
def restore_rm_stock(sender, instance, **kwargs):
    instance.raw_material.current_stock += instance.quantity
    instance.raw_material.save()