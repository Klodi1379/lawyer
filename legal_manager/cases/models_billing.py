"""
Advanced Billing System Models për Legal Case Manager
Përfshin: Auto-generation, Multi-currency, Expense tracking, Payment integration
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal
import uuid
from .models import Case, Client, TimeEntry

User = get_user_model()

class Currency(models.Model):
    """
    Valuta të mbështetura nga sistemi
    """
    code = models.CharField(max_length=3, unique=True, verbose_name="Kodi i Valutës")  # USD, EUR, ALL
    name = models.CharField(max_length=50, verbose_name="Emri")
    symbol = models.CharField(max_length=5, verbose_name="Simboli")  # $, €, L
    exchange_rate = models.DecimalField(
        max_digits=10, 
        decimal_places=6, 
        default=1.0,
        verbose_name="Kursi i Këmbimit"
    )
    is_base_currency = models.BooleanField(default=False, verbose_name="Valuta Bazë")
    is_active = models.BooleanField(default=True, verbose_name="Aktive")
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Valuta"
        verbose_name_plural = "Valutat"
        ordering = ['name']
    
    def __str__(self):
        return f"{self.code} - {self.name}"

class BillingRate(models.Model):
    """
    Tarifat e faturimit për lloje të ndryshme pune dhe përdorues
    """
    RATE_TYPE_CHOICES = [
        ('hourly', 'Tarife Orare'),
        ('fixed', 'Tarife Fikse'),
        ('contingency', 'Përqindje nga Rezultati'),
    ]
    
    name = models.CharField(max_length=100, verbose_name="Emri i Tarifës")
    rate_type = models.CharField(max_length=20, choices=RATE_TYPE_CHOICES, verbose_name="Lloji i Tarifës")
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Sasia")
    currency = models.ForeignKey(Currency, on_delete=models.CASCADE, verbose_name="Valuta")
    
    # Opsionale: Tarifë specifike për përdorues ose kategorinë e rastit
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    case_category = models.CharField(max_length=100, null=True, blank=True, verbose_name="Kategoria e Rastit")
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Tarifa e Faturimit"
        verbose_name_plural = "Tarifat e Faturimit"
    
    def __str__(self):
        return f"{self.name} - {self.amount} {self.currency.code}"

class ExpenseCategory(models.Model):
    """
    Kategoritë e shpenzimeve (transport, fotokopiim, taksa gjyqi, etj.)
    """
    name = models.CharField(max_length=100, unique=True, verbose_name="Emri")
    description = models.TextField(blank=True, verbose_name="Përshkrimi")
    is_billable = models.BooleanField(default=True, verbose_name="E Faturueshme")
    default_markup_percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="Përqindja e Markup-it Default"
    )
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "Kategoria e Shpenzimeve"
        verbose_name_plural = "Kategoritë e Shpenzimeve"
        ordering = ['name']
    
    def __str__(self):
        return self.name

class Expense(models.Model):
    """
    Shpenzimet e lidhura me rastet
    """
    case = models.ForeignKey(Case, related_name="expenses", on_delete=models.CASCADE)
    category = models.ForeignKey(ExpenseCategory, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Regjistruar nga")
    
    description = models.CharField(max_length=255, verbose_name="Përshkrimi")
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Sasia")
    currency = models.ForeignKey(Currency, on_delete=models.CASCADE)
    
    # Markup për klientët
    markup_percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    billable_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Receipt/Document
    receipt = models.FileField(upload_to='expenses/receipts/', null=True, blank=True)
    
    # Status
    is_billable = models.BooleanField(default=True)
    is_billed = models.BooleanField(default=False)
    expense_date = models.DateField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Shpenzimi"
        verbose_name_plural = "Shpenzimet"
        ordering = ['-expense_date']
    
    def save(self, *args, **kwargs):
        if self.is_billable and not self.billable_amount:
            markup_amount = self.amount * (self.markup_percentage / 100)
            self.billable_amount = self.amount + markup_amount
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.case.title} - {self.description} ({self.amount} {self.currency.code})"

class AdvancedInvoice(models.Model):
    """
    Sistema e avancuar e faturimit
    """
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('sent', 'Dërguar'),
        ('paid', 'Paguar'),
        ('overdue', 'Vonuar'),
        ('cancelled', 'Anuluar'),
    ]
    
    # Basic info
    invoice_number = models.CharField(max_length=50, unique=True, verbose_name="Numri i Faturës")
    case = models.ForeignKey(Case, related_name="advanced_invoices", on_delete=models.CASCADE)
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    
    # Dates
    issue_date = models.DateField(default=timezone.now, verbose_name="Data e Lëshimit")
    due_date = models.DateField(verbose_name="Data e Scadencës")
    
    # Amounts
    currency = models.ForeignKey(Currency, on_delete=models.CASCADE)
    subtotal_time = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    subtotal_expenses = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)  # TVA në përqindje
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Status dhe metadata
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    notes = models.TextField(blank=True, verbose_name="Shënime")
    
    # Auto-generation settings
    is_auto_generated = models.BooleanField(default=False)
    auto_send = models.BooleanField(default=False)
    
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Fatura e Avancuar"
        verbose_name_plural = "Faturat e Avancuara"
        ordering = ['-issue_date']
    
    def calculate_totals(self):
        """Llogarit totalet e faturës"""
        self.subtotal_time = sum([item.total for item in self.time_entries.all()])
        self.subtotal_expenses = sum([item.billable_amount or 0 for item in self.expense_items.all()])
        
        subtotal = self.subtotal_time + self.subtotal_expenses - self.discount_amount
        self.tax_amount = subtotal * (self.tax_rate / 100)
        self.total_amount = subtotal + self.tax_amount
    
    def generate_invoice_number(self):
        """Gjeneron numrin unik të faturës"""
        if not self.invoice_number:
            year = timezone.now().year
            count = AdvancedInvoice.objects.filter(
                issue_date__year=year
            ).count() + 1
            self.invoice_number = f"INV-{year}-{count:04d}"
    
    def save(self, *args, **kwargs):
        if not self.invoice_number:
            self.generate_invoice_number()
        self.calculate_totals()
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.invoice_number} - {self.client.name}"

class InvoiceTimeEntry(models.Model):
    """
    Hyrjet e kohës të përfshira në faturë
    """
    invoice = models.ForeignKey(AdvancedInvoice, related_name="time_entries", on_delete=models.CASCADE)
    time_entry = models.ForeignKey(TimeEntry, on_delete=models.CASCADE)
    billing_rate = models.ForeignKey(BillingRate, on_delete=models.CASCADE)
    
    hours = models.DecimalField(max_digits=8, decimal_places=2)
    rate_amount = models.DecimalField(max_digits=10, decimal_places=2)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    
    class Meta:
        unique_together = ['invoice', 'time_entry']
    
    def save(self, *args, **kwargs):
        self.hours = Decimal(self.time_entry.minutes) / 60
        self.rate_amount = self.billing_rate.amount
        self.total = self.hours * self.rate_amount
        super().save(*args, **kwargs)

class InvoiceExpenseItem(models.Model):
    """
    Shpenzimet e përfshira në faturë
    """
    invoice = models.ForeignKey(AdvancedInvoice, related_name="expense_items", on_delete=models.CASCADE)
    expense = models.ForeignKey(Expense, on_delete=models.CASCADE)
    billable_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    class Meta:
        unique_together = ['invoice', 'expense']
    
    def save(self, *args, **kwargs):
        self.billable_amount = self.expense.billable_amount or self.expense.amount
        super().save(*args, **kwargs)

class Payment(models.Model):
    """
    Pagesat e kryera për faturat
    """
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('bank_transfer', 'Transfer Bankar'),
        ('credit_card', 'Kartë Krediti'),
        ('paypal', 'PayPal'),
        ('stripe', 'Stripe'),
        ('check', 'Çek'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Në Pritje'),
        ('completed', 'Përfunduar'),
        ('failed', 'Dështuar'),
        ('refunded', 'Rimbursuar'),
    ]
    
    invoice = models.ForeignKey(AdvancedInvoice, related_name="payments", on_delete=models.CASCADE)
    payment_id = models.UUIDField(default=uuid.uuid4, unique=True)
    
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.ForeignKey(Currency, on_delete=models.CASCADE)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    
    # Integrimi me sistemet e pagesave
    external_transaction_id = models.CharField(max_length=255, null=True, blank=True)
    gateway_response = models.JSONField(null=True, blank=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_date = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True)
    
    processed_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Pagesa"
        verbose_name_plural = "Pagesat"
        ordering = ['-payment_date']
    
    def __str__(self):
        return f"Payment {self.payment_id} - {self.amount} {self.currency.code}"

class RecurringInvoice(models.Model):
    """
    Faturat periodike (mujore, tremujore, etj.)
    """
    FREQUENCY_CHOICES = [
        ('weekly', 'Javore'),
        ('monthly', 'Mujore'),
        ('quarterly', 'Tremujore'),
        ('yearly', 'Vjetore'),
    ]
    
    case = models.ForeignKey(Case, related_name="recurring_invoices", on_delete=models.CASCADE)
    template_invoice = models.ForeignKey(AdvancedInvoice, on_delete=models.CASCADE)
    
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    
    next_invoice_date = models.DateField()
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Fatura Periodike"
        verbose_name_plural = "Faturat Periodike"
    
    def generate_next_invoice(self):
        """Gjeneron faturën e ardhshme bazuar në template"""
        # Implementimi i gjenerimit automatik
        pass

class InvoiceTemplate(models.Model):
    """
    Template për faturat
    """
    name = models.CharField(max_length=100, verbose_name="Emri")
    html_template = models.TextField(verbose_name="Template HTML")
    is_default = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = "Template Fature"
        verbose_name_plural = "Template Faturash"
    
    def __str__(self):
        return self.name