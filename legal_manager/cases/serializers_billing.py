"""
Serializers për Advanced Billing System
"""

from rest_framework import serializers
from decimal import Decimal
from .models_billing import (
    AdvancedInvoice, Currency, BillingRate, Expense, ExpenseCategory,
    Payment, InvoiceTimeEntry, InvoiceExpenseItem, RecurringInvoice,
    InvoiceTemplate
)
from .models import Case, Client, TimeEntry, User

class CurrencySerializer(serializers.ModelSerializer):
    class Meta:
        model = Currency
        fields = ['id', 'code', 'name', 'symbol', 'exchange_rate', 'is_base_currency', 'is_active']

class BillingRateSerializer(serializers.ModelSerializer):
    currency_name = serializers.CharField(source='currency.name', read_only=True)
    currency_symbol = serializers.CharField(source='currency.symbol', read_only=True)
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    
    class Meta:
        model = BillingRate
        fields = [
            'id', 'name', 'rate_type', 'amount', 'currency', 'currency_name', 
            'currency_symbol', 'user', 'user_name', 'case_category', 'is_active'
        ]

class ExpenseCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseCategory
        fields = [
            'id', 'name', 'description', 'is_billable', 
            'default_markup_percentage', 'is_active'
        ]

class ExpenseSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    currency_symbol = serializers.CharField(source='currency.symbol', read_only=True)
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    case_title = serializers.CharField(source='case.title', read_only=True)
    
    class Meta:
        model = Expense
        fields = [
            'id', 'case', 'case_title', 'category', 'category_name', 'user', 'user_name',
            'description', 'amount', 'currency', 'currency_symbol', 'markup_percentage',
            'billable_amount', 'receipt', 'is_billable', 'is_billed', 'expense_date', 'created_at'
        ]
        read_only_fields = ['billable_amount', 'is_billed', 'created_at']

class InvoiceTimeEntrySerializer(serializers.ModelSerializer):
    time_entry_description = serializers.CharField(source='time_entry.description', read_only=True)
    time_entry_date = serializers.DateTimeField(source='time_entry.created_at', read_only=True)
    user_name = serializers.CharField(source='time_entry.user.get_full_name', read_only=True)
    
    class Meta:
        model = InvoiceTimeEntry
        fields = [
            'id', 'time_entry', 'time_entry_description', 'time_entry_date',
            'user_name', 'billing_rate', 'hours', 'rate_amount', 'total'
        ]
        read_only_fields = ['hours', 'rate_amount', 'total']

class InvoiceExpenseItemSerializer(serializers.ModelSerializer):
    expense_description = serializers.CharField(source='expense.description', read_only=True)
    expense_date = serializers.DateField(source='expense.expense_date', read_only=True)
    category_name = serializers.CharField(source='expense.category.name', read_only=True)
    
    class Meta:
        model = InvoiceExpenseItem
        fields = [
            'id', 'expense', 'expense_description', 'expense_date',
            'category_name', 'billable_amount'
        ]
        read_only_fields = ['billable_amount']

class PaymentSerializer(serializers.ModelSerializer):
    currency_symbol = serializers.CharField(source='currency.symbol', read_only=True)
    processed_by_name = serializers.CharField(source='processed_by.get_full_name', read_only=True)
    invoice_number = serializers.CharField(source='invoice.invoice_number', read_only=True)
    
    class Meta:
        model = Payment
        fields = [
            'id', 'invoice', 'invoice_number', 'payment_id', 'amount', 'currency', 
            'currency_symbol', 'payment_method', 'external_transaction_id',
            'gateway_response', 'status', 'payment_date', 'notes', 
            'processed_by', 'processed_by_name', 'created_at'
        ]
        read_only_fields = ['payment_id', 'created_at']

class AdvancedInvoiceSerializer(serializers.ModelSerializer):
    case_title = serializers.CharField(source='case.title', read_only=True)
    client_name = serializers.CharField(source='client.name', read_only=True)
    client_email = serializers.EmailField(source='client.email', read_only=True)
    currency_symbol = serializers.CharField(source='currency.symbol', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    
    # Related items
    time_entries = InvoiceTimeEntrySerializer(many=True, read_only=True)
    expense_items = InvoiceExpenseItemSerializer(many=True, read_only=True)
    payments = PaymentSerializer(many=True, read_only=True)
    
    # Calculated fields
    total_payments = serializers.SerializerMethodField()
    outstanding_balance = serializers.SerializerMethodField()
    is_overdue = serializers.SerializerMethodField()
    
    class Meta:
        model = AdvancedInvoice
        fields = [
            'id', 'invoice_number', 'case', 'case_title', 'client', 'client_name', 
            'client_email', 'issue_date', 'due_date', 'currency', 'currency_symbol',
            'subtotal_time', 'subtotal_expenses', 'discount_amount', 'tax_rate',
            'tax_amount', 'total_amount', 'status', 'notes', 'is_auto_generated',
            'auto_send', 'created_by', 'created_by_name', 'created_at', 'updated_at',
            'time_entries', 'expense_items', 'payments', 'total_payments',
            'outstanding_balance', 'is_overdue'
        ]
        read_only_fields = [
            'invoice_number', 'subtotal_time', 'subtotal_expenses', 'tax_amount',
            'total_amount', 'created_at', 'updated_at'
        ]
    
    def get_total_payments(self, obj):
        return obj.payments.filter(status='completed').aggregate(
            total=serializers.models.Sum('amount')
        )['total'] or Decimal('0')
    
    def get_outstanding_balance(self, obj):
        total_payments = self.get_total_payments(obj)
        return obj.total_amount - total_payments
    
    def get_is_overdue(self, obj):
        from django.utils import timezone
        return obj.status == 'sent' and obj.due_date < timezone.now().date()

class RecurringInvoiceSerializer(serializers.ModelSerializer):
    case_title = serializers.CharField(source='case.title', read_only=True)
    template_invoice_number = serializers.CharField(source='template_invoice.invoice_number', read_only=True)
    
    class Meta:
        model = RecurringInvoice
        fields = [
            'id', 'case', 'case_title', 'template_invoice', 'template_invoice_number',
            'frequency', 'start_date', 'end_date', 'next_invoice_date', 'is_active', 'created_at'
        ]

class InvoiceTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceTemplate
        fields = ['id', 'name', 'html_template', 'is_default']

# Serializers të thjeshta për dropdown/autocomplete
class SimpleCaseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Case
        fields = ['id', 'title', 'case_number']

class SimpleClientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Client
        fields = ['id', 'name', 'email']

class SimpleUserSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    
    class Meta:
        model = User
        fields = ['id', 'username', 'full_name', 'role']

# Bulk operations serializers
class BulkInvoiceActionSerializer(serializers.Serializer):
    """
    Serializer për veprime masive në fatura
    """
    ACTION_CHOICES = [
        ('send_email', 'Dërgo Email'),
        ('mark_sent', 'Shëno si të Dërguar'),
        ('mark_paid', 'Shëno si të Paguar'),
        ('delete', 'Fshi'),
    ]
    
    invoice_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1
    )
    action = serializers.ChoiceField(choices=ACTION_CHOICES)
    
    def validate_invoice_ids(self, value):
        # Verifikonë që të gjitha ID-të ekzistojnë
        existing_ids = AdvancedInvoice.objects.filter(
            id__in=value
        ).values_list('id', flat=True)
        
        missing_ids = set(value) - set(existing_ids)
        if missing_ids:
            raise serializers.ValidationError(
                f"Faturat me ID {missing_ids} nuk ekzistojnë"
            )
        
        return value

class InvoiceGenerationSerializer(serializers.Serializer):
    """
    Serializer për gjenerimin automatik të faturave
    """
    case_id = serializers.IntegerField()
    period_start = serializers.DateField(required=False)
    period_end = serializers.DateField(required=False)
    auto_send = serializers.BooleanField(default=False)
    include_expenses = serializers.BooleanField(default=True)
    discount_percentage = serializers.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=0,
        min_value=0,
        max_value=100
    )
    
    def validate_case_id(self, value):
        try:
            Case.objects.get(id=value)
        except Case.DoesNotExist:
            raise serializers.ValidationError("Rasti nuk ekziston")
        return value
    
    def validate(self, data):
        period_start = data.get('period_start')
        period_end = data.get('period_end')
        
        if period_start and period_end:
            if period_start > period_end:
                raise serializers.ValidationError(
                    "Data e fillimit duhet të jetë para datës së mbarimit"
                )
        
        return data

# Dashboard stats serializer
class BillingDashboardStatsSerializer(serializers.Serializer):
    """
    Serializer për statistikat e dashboard-it të faturimit
    """
    total_invoices = serializers.IntegerField()
    this_month_invoices = serializers.IntegerField()
    pending_invoices = serializers.IntegerField()
    overdue_invoices = serializers.IntegerField()
    total_outstanding = serializers.DecimalField(max_digits=15, decimal_places=2)
    this_month_revenue = serializers.DecimalField(max_digits=15, decimal_places=2)
    collection_rate = serializers.DecimalField(max_digits=5, decimal_places=2)
    average_invoice_value = serializers.DecimalField(max_digits=12, decimal_places=2)
    
# Import për models në fund për të shmangur circular imports
from django.db import models